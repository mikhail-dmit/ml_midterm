#!/usr/bin/env python3
"""Build leakage-safe user/airing and user/programme tables and local Top-5 labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow

from inspect_time_alignment import continuity
from interaction_core import (
    LOCAL_WINDOWS, TIMEZONE, boundary_epoch, clip_views, join_channel,
    local_epoch, local_text, merge_views, utc_text, watched_mask,
)

ROOT = Path(__file__).resolve().parents[1]
LOG = "dataset11-30.csv"
SCHEDULES = ["export_arh_11-20-final.csv", "export_arh_21-30-final.csv"]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                               default=lambda x: int(x) if isinstance(x, np.integer) else float(x)) + "\n", encoding="utf-8")


def quantiles(values):
    if not len(values):
        return {}
    return {str(q): float(values.quantile(q)) for q in [0, .25, .5, .75, .9, .99, 1]}


def read_views(data_dir, chunk_size):
    frames = []
    mismatches = {"naive": 0, "timezone_elapsed": 0}
    clock_change_users = []
    for raw in pd.read_csv(data_dir / LOG, dtype={"user_id": "uint64", "vsetv_id": "int32", "duraton": "int32"}, chunksize=chunk_size):
        start = local_epoch(raw.start_time, "%Y-%m-%d %H:%M:%S")
        end = local_epoch(raw.stop_time, "%Y-%m-%d %H:%M:%S")
        naive_start = pd.to_datetime(raw.start_time, format="%Y-%m-%d %H:%M:%S")
        naive_end = pd.to_datetime(raw.stop_time, format="%Y-%m-%d %H:%M:%S")
        wall_mismatch = (naive_end - naive_start).dt.total_seconds() != raw.duraton
        mismatches["naive"] += int(wall_mismatch.sum())
        if wall_mismatch.any() and len(clock_change_users) < 5:
            clock_change_users.extend(str(x) for x in raw.loc[wall_mismatch, "user_id"].head(5).tolist())
        mismatches["timezone_elapsed"] += int(((end - start) != raw.duraton.to_numpy()).sum())
        frames.append(pd.DataFrame({"user_id": raw.user_id.to_numpy(), "channel_id": raw.vsetv_id.to_numpy(),
                                    "start": start, "end": end, "recorded_duration": raw.duraton.to_numpy()}))
    views = pd.concat(frames, ignore_index=True)
    if mismatches["timezone_elapsed"]:
        raise AssertionError(f"Declared timezone does not explain all viewing durations: {mismatches}")
    if not (views.end > views.start).all():
        raise AssertionError("Invalid viewing intervals")
    n_raw = len(views)
    views = views.drop_duplicates().copy()
    views["source_rows"] = 1
    return views, {"raw_rows": n_raw, "duplicate_rows_removed": n_raw - len(views),
                   "unique_rows": len(views), "duration_mismatches": mismatches,
                   "clock_change_sample_user_ids": clock_change_users[:5]}


def read_airings(data_dir):
    frames, probe = [], {}
    naive_frames, utc_frames = [], []
    zero_rows, nonpositive = 0, 0
    for filename in SCHEDULES:
        raw = pd.read_csv(data_dir / filename, dtype={"channel_id": "int32", "tv_show_id": "int64", "duration": "int32"}, keep_default_na=False)
        start = local_epoch(raw.start_time, "%d.%m.%Y %H:%M:%S")
        naive = pd.to_datetime(raw.start_time, format="%d.%m.%Y %H:%M:%S").astype("int64").to_numpy() // 10**9
        naive_frame = pd.DataFrame({"channel_id": raw.channel_id, "start": naive, "end": naive + raw.duration.to_numpy()})
        utc_frame = pd.DataFrame({"channel_id": raw.channel_id, "start": start, "end": start + raw.duration.to_numpy()})
        probe[filename] = {"naive": continuity(naive_frame), "timezone_elapsed": continuity(utc_frame)}
        naive_frames.append(naive_frame)
        utc_frames.append(utc_frame)
        zero_rows += int((raw.tv_show_id == 0).sum())
        nonpositive += int((raw.duration <= 0).sum())
        selected = (raw.tv_show_id != 0) & (raw.duration > 0)
        frame = raw.loc[selected, ["channel_id", "tv_show_id", "tv_show_title", "tv_show_category", "duration"]].copy()
        frame["source_file"] = filename
        frame["source_csv_record"] = frame.index.to_numpy() + 2
        frame["start"] = start[selected]
        frame["end"] = frame.start + frame.duration
        frame["start_local_raw"] = raw.loc[selected, "start_time"]
        frames.append(frame)
    airings = pd.concat(frames, ignore_index=True)
    identity = ["channel_id", "tv_show_id", "start", "end"]
    n_before = len(airings)
    airings = airings.drop_duplicates(identity).sort_values(
        ["channel_id", "start", "end", "tv_show_id"], kind="stable").reset_index(drop=True)
    airings["airing_id"] = np.arange(len(airings), dtype="int32")
    # A conflicting labelled schedule is flagged; the join still considers all overlaps.
    labelled_continuity = continuity(airings)
    probe["combined_historical_schedule"] = {
        "naive": continuity(pd.concat(naive_frames, ignore_index=True)),
        "timezone_elapsed": continuity(pd.concat(utc_frames, ignore_index=True)),
    }
    return airings, {"unlabelled_rows_excluded": zero_rows, "nonpositive_rows_excluded": nonpositive,
                      "labelled_airings": len(airings), "duplicate_airing_identities_removed": n_before - len(airings),
                      "labelled_schedule_continuity": labelled_continuity}, probe


def make_events(merged, airings, split):
    lower, upper = [boundary_epoch(x) for x in LOCAL_WINDOWS[split]]
    views = clip_views(merged, lower, upper)
    eligible = airings.loc[(airings.start < upper) & (airings.end > lower)]
    by_channel = {int(c): f for c, f in eligible.groupby("channel_id", sort=False)}
    parts = []
    for channel, group in views.groupby("channel_id", sort=False):
        if int(channel) not in by_channel:
            continue
        overlaps = join_channel(group, by_channel[int(channel)])
        if len(overlaps):
            parts.append(overlaps)
    if not parts:
        raise ValueError(f"No interactions in {split}")
    segments = pd.concat(parts, ignore_index=True)
    events = segments.groupby(["user_id", "airing_id"], sort=False).agg(
        watched_seconds=("overlap_seconds", "sum"), union_fragments=("overlap_seconds", "size"),
        first_overlap=("overlap_start", "min"), last_overlap=("overlap_end", "max"),
    ).reset_index()
    events = events.merge(airings[["airing_id", "channel_id", "tv_show_id", "start", "end", "duration"]],
                          on="airing_id", validate="many_to_one")
    events["coverage"] = events.watched_seconds / events.duration
    events["watched_80pct"] = watched_mask(events.watched_seconds, events.duration)
    events["split"] = split
    events = events.sort_values(["user_id", "start", "channel_id", "tv_show_id"], kind="stable").reset_index(drop=True)
    if not ((events.watched_seconds > 0) & (events.watched_seconds <= events.duration)).all():
        raise AssertionError("Watched union time outside (0, full programme duration]")
    if not ((events.first_overlap >= lower) & (events.last_overlap <= upper)).all():
        raise AssertionError("Viewing leaked outside split")
    return events, {
        "window_start_local": LOCAL_WINDOWS[split][0], "window_end_local_exclusive": LOCAL_WINDOWS[split][1],
        "window_start_utc": utc_text(lower), "window_end_utc": utc_text(upper),
        "clipped_merged_view_segments": len(views), "overlap_segments": len(segments),
        "eligible_programme_ids": int(eligible.tv_show_id.nunique()),
        "eligible_airings": len(eligible), "user_airing_pairs": len(events),
        "qualifying_watched_airings": int(events.watched_80pct.sum()),
        "users_with_any_programme_overlap": int(events.user_id.nunique()),
        "users_with_qualified_watches": int(events.loc[events.watched_80pct, "user_id"].nunique()),
        "programmes_with_qualified_watches": int(events.loc[events.watched_80pct, "tv_show_id"].nunique()),
        "watched_seconds_quantiles": quantiles(events.watched_seconds), "coverage_quantiles": quantiles(events.coverage),
        "exactly_80pct_events": int((events.watched_seconds * 5 == events.duration * 4).sum()),
        "more_than_one_union_fragment_events": int((events.union_fragments > 1).sum()),
        "boundary_crossing_airing_events": int(((events.start < lower) | (events.end > upper)).sum()),
        "qualified_boundary_crossing_airing_events": int((((events.start < lower) | (events.end > upper)) & events.watched_80pct).sum()),
    }


def aggregate_programmes(events):
    keyed = ["split", "user_id", "tv_show_id"]
    result = events.groupby(keyed, sort=False).agg(
        overlap_airings=("airing_id", "size"), watched_airings=("watched_80pct", "sum"),
        total_watched_seconds=("watched_seconds", "sum"),
        first_overlap=("first_overlap", "min"), last_overlap=("last_overlap", "max"),
    ).reset_index()
    qualified = events.loc[events.watched_80pct].groupby(keyed, sort=False).agg(
        qualified_watched_seconds=("watched_seconds", "sum"),
        last_qualified_overlap=("last_overlap", "max"),
    ).reset_index()
    result = result.merge(qualified, on=keyed, how="left", validate="one_to_one")
    result["qualified_watched_seconds"] = result.qualified_watched_seconds.fillna(0).astype("int64")
    result["last_qualified_overlap"] = result.last_qualified_overlap.astype("Int64")
    result["watched_airings"] = result.watched_airings.astype("int64")
    return result.sort_values(keyed, kind="stable").reset_index(drop=True)


def make_labels(programmes, views, template, airings, events):
    positive = programmes.loc[programmes.watched_airings > 0]
    validation = positive.loc[positive.split == "validation"].copy()
    validation = validation.sort_values(["user_id", "watched_airings", "tv_show_id"],
                                         ascending=[True, False, True], kind="stable")
    validation["rank"] = validation.groupby("user_id", sort=False).cumcount() + 1
    top = validation.loc[validation["rank"] <= 5].copy()
    # Titles vary by episode. Display an airing this user actually watched, not an
    # arbitrary episode from the catalogue. This lookup is explanatory only.
    lookup = events.loc[(events.split == "validation") & events.watched_80pct].sort_values(
        ["user_id", "tv_show_id", "last_overlap", "airing_id"], ascending=[True, True, False, True], kind="stable"
    ).drop_duplicates(["user_id", "tv_show_id"])[["user_id", "tv_show_id", "airing_id"]]
    lookup = lookup.merge(airings[["airing_id", "tv_show_title", "tv_show_category", "source_file", "source_csv_record"]],
                          on="airing_id", validate="many_to_one").rename(columns={
                              "airing_id": "title_airing_id", "source_file": "title_source_file",
                              "source_csv_record": "title_source_csv_record"})
    top = top.merge(lookup, on=["user_id", "tv_show_id"], validate="one_to_one")
    top = top.sort_values(["user_id", "rank"], kind="stable")
    all_users = pd.DataFrame({"user_id": np.sort(views.user_id.unique())})
    all_users["is_test_user"] = all_users.user_id.isin(template.user_id)
    for split in LOCAL_WINDOWS:
        p = positive.loc[positive.split == split]
        counts = p.groupby("user_id").agg(qualified_programmes=("tv_show_id", "size"), watched_airings=("watched_airings", "sum"))
        for col in counts:
            all_users[f"{split}_{col}"] = all_users.user_id.map(counts[col]).fillna(0).astype("int64")
    all_users["primary_validation_eligible"] = all_users.validation_qualified_programmes >= 5
    all_users["broad_validation_eligible"] = all_users.validation_qualified_programmes >= 1
    all_users["training_cold_start"] = all_users.train_qualified_programmes == 0
    eligible_users = all_users.loc[all_users.primary_validation_eligible, "user_id"]
    primary = top.loc[top.user_id.isin(eligible_users)]
    ground_truth = primary.groupby("user_id", sort=True).tv_show_id.agg(lambda x: " ".join(map(str, x))).reset_index()
    fifth = validation.loc[validation["rank"] == 5, ["user_id", "watched_airings"]]
    sixth = validation.loc[validation["rank"] == 6, ["user_id", "watched_airings"]]
    ties = fifth.merge(sixth, on="user_id", suffixes=("_5", "_6"))
    train_ids = set(positive.loc[positive.split == "train", "tv_show_id"])
    top["unseen_in_training_interactions"] = ~top.tv_show_id.isin(train_ids)
    info = {
        "raw_users": len(all_users), "users_no_validation_qualified_programmes": int((all_users.validation_qualified_programmes == 0).sum()),
        "users_one_to_four_validation_qualified_programmes": int(all_users.validation_qualified_programmes.between(1, 4).sum()),
        "primary_users_at_least_five": len(eligible_users), "primary_ground_truth_rows": len(ground_truth),
        "primary_cold_start_users": int((all_users.primary_validation_eligible & all_users.training_cold_start).sum()),
        "primary_test_template_users": int((all_users.primary_validation_eligible & all_users.is_test_user).sum()),
        "test_template_users_without_training_qualified_history": int((all_users.is_test_user & all_users.training_cold_start).sum()),
        "primary_users_with_fifth_sixth_count_tie": int((ties.watched_airings_5 == ties.watched_airings_6).sum()),
        "validation_top5_unseen_in_training_items": int(top.unseen_in_training_interactions.sum()),
        "primary_validation_top5_unseen_in_training_items": int(top.loc[top.user_id.isin(eligible_users), "unseen_in_training_interactions"].sum()),
        "validation_qualified_programme_count_quantiles": quantiles(all_users.validation_qualified_programmes),
        "tie_break": "Descending qualifying-airing count, then ascending numeric tv_show_id; organiser tie-break unspecified",
        "display_title": "Title/category of this user's most recent qualifying validation airing for that ID; explanatory lookup only",
        "primary_cohort": "All raw-log users with >=5 distinct qualified validation programmes; no warm-user filter",
        "broad_cohort": "All users with >=1 qualified validation programme, with up to five true IDs",
    }
    ambiguous_users = ties.loc[ties.watched_airings_5 == ties.watched_airings_6, "user_id"]
    tie_rows = []
    for user, group in validation.loc[validation.user_id.isin(ambiguous_users)].groupby("user_id", sort=True):
        group = group.sort_values("rank")
        threshold = int(group.watched_airings.iloc[4])
        above = int((group.watched_airings > threshold).sum())
        tied_ids = group.loc[group.watched_airings == threshold, "tv_show_id"].tolist()
        tie_rows.append({"user_id": str(user), "fifth_place_count": threshold,
                         "programmes_strictly_above": above, "tied_programmes": len(tied_ids),
                         "remaining_top5_slots": 5 - above, "all_boundary_tied_ids": " ".join(map(str, tied_ids))})
    return top, ground_truth, all_users, info, pd.DataFrame(tie_rows)


def export_frame(frame, path):
    frame = frame.copy()
    if "user_id" in frame:
        frame["user_id"] = frame.user_id.astype(str)
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False, compression="zstd")
    else:
        frame.to_csv(path, index=False)


def export_example(data_dir, report_dir, events, programmes, top, users, airings, chunk_size):
    folder = report_dir / "manual_example"
    folder.mkdir(parents=True, exist_ok=True)
    candidates = users.loc[(users.validation_qualified_programmes.between(6, 10))
                            & (users.train_qualified_programmes > 0)].sort_values(
                                ["validation_watched_airings", "user_id"], kind="stable")
    if candidates.empty:
        candidates = users.loc[users.primary_validation_eligible].sort_values(["validation_watched_airings", "user_id"])
    user = int(candidates.user_id.iloc[0])
    raw_parts = []
    for raw in pd.read_csv(data_dir / LOG, dtype={"user_id": "uint64", "vsetv_id": "int32", "duraton": "int32"}, chunksize=chunk_size):
        selected = raw.loc[raw.user_id == user].copy()
        selected["source_csv_record"] = selected.index.to_numpy() + 2
        if len(selected):
            raw_parts.append(selected)
    raw = pd.concat(raw_parts, ignore_index=True)
    user_events = events.loc[events.user_id == user].merge(
        airings[["airing_id", "tv_show_title", "tv_show_category", "source_file", "source_csv_record"]],
        on="airing_id", validate="many_to_one")
    for col in ["start", "end", "first_overlap", "last_overlap"]:
        user_events[col + "_local"] = user_events[col].map(local_text)
    val_events = user_events.loc[user_events.split == "validation"]
    positive = val_events.loc[val_events.watched_80pct].sort_values(
        ["union_fragments", "coverage", "duration", "start"], ascending=[False, True, True, True])
    negative = val_events.loc[~val_events.watched_80pct].sort_values("coverage", ascending=False)
    worked = pd.concat([positive.head(1), negative.head(1)], ignore_index=True)
    raw["start_epoch"] = local_epoch(raw.start_time, "%Y-%m-%d %H:%M:%S")
    raw["end_epoch"] = local_epoch(raw.stop_time, "%Y-%m-%d %H:%M:%S")
    raw["duplicate_raw_row"] = raw.duplicated(["user_id", "vsetv_id", "start_time", "stop_time", "duraton"])
    fragments, calculations = [], []
    low, high = [boundary_epoch(x) for x in LOCAL_WINDOWS["validation"]]
    for event in worked.itertuples(index=False):
        a, b = max(event.start, low), min(event.end, high)
        matching = raw.loc[(raw.vsetv_id == event.channel_id) & (raw.start_epoch < b) & (raw.end_epoch > a)]
        pieces = []
        for row in matching.itertuples(index=False):
            x, y = max(int(row.start_epoch), a), min(int(row.end_epoch), b)
            fragments.append({"airing_id": event.airing_id, "source_csv_record": int(row.source_csv_record),
                              "raw_start_local": row.start_time, "raw_stop_local": row.stop_time,
                              "overlap_start_local": local_text(x), "overlap_end_local": local_text(y),
                              "overlap_seconds_before_union": y - x, "duplicate_raw_row": row.duplicate_raw_row})
            pieces.append((x, y))
        # Deliberately simple independent union for a checkable worked example.
        union = []
        for x, y in sorted(set(pieces)):
            if union and x <= union[-1][1]:
                union[-1] = (union[-1][0], max(union[-1][1], y))
            else:
                union.append((x, y))
        total = sum(y - x for x, y in union)
        if total != event.watched_seconds:
            raise AssertionError("Manual-example union disagrees with main join")
        calculations.append({"airing_id": int(event.airing_id), "tv_show_id": int(event.tv_show_id),
                             "title": event.tv_show_title, "duration": int(event.duration),
                             "watched_seconds": total, "coverage": total / event.duration,
                             "watched": bool(event.watched_80pct),
                             "schedule_file": event.source_file, "schedule_csv_record": int(event.source_csv_record),
                             "airing_start_local": local_text(event.start), "airing_end_local": local_text(event.end),
                             "union_intervals": [{"start_local": local_text(x), "end_local": local_text(y), "seconds": y - x} for x, y in union]})
    counts = programmes.loc[(programmes.user_id == user) & (programmes.split == "validation")].sort_values(
        ["watched_airings", "tv_show_id"], ascending=[False, True])
    chosen_top = top.loc[top.user_id == user].sort_values("rank")
    export_frame(raw, folder / "raw_views.csv")
    export_frame(user_events, folder / "all_airing_interactions.csv")
    export_frame(counts, folder / "validation_programme_counts.csv")
    export_frame(chosen_top, folder / "validation_top5.csv")
    export_frame(worked, folder / "worked_airings.csv")
    pd.DataFrame(fragments).to_csv(folder / "worked_raw_fragments.csv", index=False)
    selected_airings = airings.loc[airings.airing_id.isin(user_events.airing_id)]
    selected_airings.to_csv(folder / "matched_schedule_rows.csv", index=False)
    result = {"user_id": str(user), "raw_view_rows": len(raw), "validation_qualified_programmes": int((counts.watched_airings > 0).sum()),
              "selection": "Readable verification example: 6–10 validation positives, nonempty train history, fewest qualified validation airings; no recommendation/model score used",
              "worked_airings": calculations,
              "validation_top5_ids": [int(x) for x in chosen_top.tv_show_id]}
    dump_json(folder / "example.json", result)
    lines = [f"# Manual verification example — user {user}", "",
             "This example was computed by the assistant. It is prepared for the student to independently check later; personal verification is not claimed.",
             "", "## 1. Reconstruct one watched/not-watched decision", "",
             "Use `worked_raw_fragments.csv` and `worked_airings.csv`. Source CSV record numbers include the header as record 1. Times with offsets are Europe/Kyiv local time."]
    for item in calculations:
        lines += ["", f"### Programme {item['tv_show_id']}: {item['title']}", "",
                  f"Schedule: `{item['schedule_file']}`, CSV record **{item['schedule_csv_record']}**.",
                  f"Airing: {item['airing_start_local']} → {item['airing_end_local']}; full duration **{item['duration']} seconds**.",
                  "", "| Non-overlapping watched union interval | Seconds |", "|---|---:|"]
        for piece in item["union_intervals"]:
            lines.append(f"| {piece['start_local']} → {piece['end_local']} | {piece['seconds']} |")
        lines += ["", f"Watched union time = **{item['watched_seconds']}s**. Coverage = {item['watched_seconds']} / {item['duration']} = **{item['coverage']:.6f}**.",
                  f"Exact comparison: 5 × {item['watched_seconds']} {'≥' if item['watched'] else '<'} 4 × {item['duration']}; watched = **{item['watched']}**."]
    lines += ["", "## 2. Reproduce the validation Top-5", "",
              "Filter `all_airing_interactions.csv` to validation and watched_80pct=True. Count rows per tv_show_id. Sort count descending, numeric ID ascending. Compare with `validation_programme_counts.csv` and the table below.",
              "", "| Rank | Programme ID | Title | Category | Qualified airings |", "|---:|---:|---|---|---:|"]
    for row in chosen_top.itertuples(index=False):
        lines.append(f"| {row.rank} | {row.tv_show_id} | {row.tv_show_title} | {row.tv_show_category} | {row.watched_airings} |")
    positives = counts.loc[counts.watched_airings > 0]
    fifth_count = int(chosen_top.watched_airings.iloc[4])
    tied_ids = positives.loc[positives.watched_airings == fifth_count, "tv_show_id"].tolist()
    lines += ["", f"There are **{len(positives)} qualified programmes** for this user. IDs tied at the fifth-place frequency ({fifth_count}): **{' '.join(map(str, tied_ids))}**.",
              "The local labels resolve this with ascending numeric ID. Kaggle does not document its tie-break; the exact hidden choice among boundary-tied programmes is therefore unknown.",
              "Displayed titles come from this user's most recent qualifying airing for each ID; episode titles can vary under one programme ID."]
    lines += ["", "## 3. Trace back to the originals", "",
              "`raw_views.csv` contains every original log record for this user, including duplicate markers. `matched_schedule_rows.csv` includes the original schedule filename/record, title, duration and raw start. All matches, including below-threshold cases, remain in `all_airing_interactions.csv`.",
              "For full independence you can scan the original schedule for that user's channels/time intervals too; the exported matched schedule is an aid, not a substitute for checking missed matches.", ""]
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def report_markdown(report):
    lines = ["# SWEET.TV user–programme interactions and local validation labels", "",
             "## Definition", "",
             "1. Interpret supplied timestamp strings as Europe/Kyiv local time, convert to UTC seconds. Schedule end is localized start plus supplied elapsed duration. This is an empirically supported assumption, not a declared organiser timezone.",
             "2. Exclude programme ID 0 and nonpositive-duration airings. Read both historical schedule files; do not partition by filename. Preserve IDs exactly.",
             "3. Remove identical log rows, union all overlapping/touching view intervals per user and channel, and clip observed viewing to each temporal window.",
             "4. Join on the same channel and a strictly positive interval overlap. For each user and airing, add the non-overlapping watched fragments.",
             "5. A watched airing has union watched seconds / full original airing duration >= 0.8. Implement the exact integer condition `5 * watched_seconds >= 4 * duration`. Never shrink the denominator at a split boundary.",
             "6. Count qualifying airings per user and programme ID. Each airing contributes at most one count per user; fragments do not add extra counts. Distinct broadcasts/channels are distinct airings.",
             "7. Validation Top-5: five distinct IDs with highest qualifying-airing counts in weeks 21–30; ties use ascending numeric ID.",
             "", "Kaggle documents the 80% threshold and frequency Top-5. Fragment union, airing-event identity and tie-breaking are explicit reconstruction choices; the hidden generator's full code was not supplied. These are **local reference labels**, not access to Kaggle's hidden answers.",
             "", "## Windows", "", "| Split | Local start, inclusive | Local end, exclusive | User–airing overlaps | Qualified airings | Users with qualified watches | Programmes with qualified watches |",
             "|---|---|---|---:|---:|---:|---:|"]
    for split, values in report["splits"].items():
        lines.append(f"| {split} | {values['window_start_local']} | {values['window_end_local_exclusive']} | {values['user_airing_pairs']:,} | {values['qualifying_watched_airings']:,} | {values['users_with_qualified_watches']:,} | {values['programmes_with_qualified_watches']:,} |")
    lines += ["", "## Sanity checks", ""]
    for key, value in report["sanity_checks"].items():
        lines.append(f"- {key}: **{value}**")
    lines += ["", "## Cohort and labels", "", "```json", json.dumps(report["validation_labels"], indent=2), "```",
              "", "Primary ground truth includes every user with at least five qualified validation programmes, including training-cold users. Users with 1–4 positives are exported separately for a broader evaluation; users with zero positives are accounted for in validation_users.csv. Nothing is padded with invented true IDs.",
              "", f"**Label uncertainty:** {report['validation_labels']['primary_users_with_fifth_sixth_count_tie']:,} primary users have a frequency tie crossing the Top-5 boundary. See `validation_boundary_ties.csv`. Membership under Kaggle's undocumented tie-break can differ; do not describe these local labels as an exact reproduction of the hidden generator.",
              "", "## Time interpretation evidence", "", "```json", json.dumps(report["time_alignment"], indent=2), "```",
              "", "## Worked example", "", f"User **{report['manual_example']['user_id']}**. See [manual_example/README.md](manual_example/README.md) for arithmetic and source-record references.",
              "", "## Reproduction", "", "```bash", "python3 -m unittest discover -s scripts -p 'test_interactions.py'",
              "python3 scripts/build_interactions.py", "python3 scripts/verify_interactions.py", "```",
              "", "Artifacts: airings.parquet, airing_interactions.parquet, user_programme_interactions.parquet under artifacts/interactions/.",
              "", f"Saved tables contain **{report['tables']['user_airing_rows']:,} user–airing rows**, **{report['tables']['user_programme_rows']:,} split/user/programme rows** including partial overlaps, and **{report['tables']['positive_user_programme_rows']:,} positive split/user/programme rows** after filtering `watched_airings > 0`.",
              "Reports: validation_top5.csv (long format; all users with positives), validation_ground_truth.csv (strictly five IDs), validation_ground_truth_partial.csv (1–4 IDs), validation_users.csv, summary.json, and the worked example.",
              "", "No recommendation model or baseline was trained. Popularity remains the only planned baseline.",
              "All automated verifications were performed by the assistant. Student personal verification is not claimed.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "sweettv-tv-program-recommender")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "artifacts" / "interactions")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "interactions")
    parser.add_argument("--chunk-size", type=int, default=250000)
    args = parser.parse_args()
    if args.chunk_size <= 0:
        parser.error("--chunk-size must be positive")
    started = time.perf_counter()
    print("Reading historical schedule and checking local-time interpretation ...", flush=True)
    airings, schedule_stats, schedule_probe = read_airings(args.data_dir)
    print("Reading viewing log and checking every elapsed duration ...", flush=True)
    views, view_stats = read_views(args.data_dir, args.chunk_size)
    template = pd.read_csv(args.data_dir / "submission.csv", dtype={"user_id": "uint64", "tv_show_id": str})
    print("Unioning view intervals by user and channel ...", flush=True)
    merged = merge_views(views)
    view_stats["merged_union_segments"] = len(merged)
    view_stats["unique_view_seconds_before_union"] = int((views.end - views.start).sum())
    view_stats["view_seconds_after_union"] = int((merged.end - merged.start).sum())
    view_stats["overlapping_seconds_removed"] = view_stats["unique_view_seconds_before_union"] - view_stats["view_seconds_after_union"]
    per_split, split_stats = [], {}
    for split in LOCAL_WINDOWS:
        print(f"Joining {split} view intervals to labelled airings ...", flush=True)
        e, stats = make_events(merged, airings, split)
        per_split.append(e)
        split_stats[split] = stats
    events = pd.concat(per_split, ignore_index=True)
    programmes = aggregate_programmes(events)
    top, ground_truth, users, label_stats, ties = make_labels(programmes, views, template, airings, events)
    # Full-data assertions. Boundaries constrain observed time, not broadcast duration.
    unique_events = not events.duplicated(["split", "user_id", "airing_id"]).any()
    event_totals = events.groupby(["user_id", "airing_id"]).watched_seconds.sum().reset_index().merge(
        airings[["airing_id", "duration"]], on="airing_id", validate="many_to_one")
    checks = {
        "all watched times positive and no larger than full programme duration": bool(((events.watched_seconds > 0) & (events.watched_seconds <= events.duration)).all()),
        "all coverage values in (0,1]": bool(events.coverage.between(0, 1, inclusive="right").all()),
        "one row per split/user/airing": bool(unique_events),
        "no ID zero in joined events": bool((events.tv_show_id != 0).all()),
        "train plus validation watched seconds do not exceed an airing duration": bool((event_totals.watched_seconds <= event_totals.duration).all()),
        "no airing counted watched in both temporal splits": bool(not events.loc[events.watched_80pct].duplicated(["user_id", "airing_id"]).any()),
        "programme counts reconcile to qualified airing counts": int(programmes.watched_airings.sum()) == int(events.watched_80pct.sum()),
        "primary ground truth always five distinct IDs": bool(ground_truth.tv_show_id.map(lambda s: len(s.split()) == len(set(s.split())) == 5).all()),
        "raw user cohort accounting closes": label_stats["users_no_validation_qualified_programmes"] + label_stats["users_one_to_four_validation_qualified_programmes"] + label_stats["primary_users_at_least_five"] == len(users),
        "zero timezone elapsed-duration mismatches": view_stats["duration_mismatches"]["timezone_elapsed"] == 0,
    }
    if not all(checks.values()):
        raise AssertionError(checks)
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    print("Writing tables and a source-traceable manual example ...", flush=True)
    export_frame(airings, args.artifact_dir / "airings.parquet")
    export_frame(events, args.artifact_dir / "airing_interactions.parquet")
    export_frame(programmes, args.artifact_dir / "user_programme_interactions.parquet")
    export_frame(top, args.report_dir / "validation_top5.csv")
    export_frame(ground_truth, args.report_dir / "validation_ground_truth.csv")
    partial_users = users.loc[users.validation_qualified_programmes.between(1, 4), "user_id"]
    partial = top.loc[top.user_id.isin(partial_users)].groupby("user_id", sort=True).tv_show_id.agg(lambda x: " ".join(map(str, x))).reset_index()
    export_frame(partial, args.report_dir / "validation_ground_truth_partial.csv")
    export_frame(users, args.report_dir / "validation_users.csv")
    ties.to_csv(args.report_dir / "validation_boundary_ties.csv", index=False)
    example = export_example(args.data_dir, args.report_dir, events, programmes, top, users, airings, args.chunk_size)
    boundary = boundary_epoch(LOCAL_WINDOWS["train"][1])
    boundary_user = views.loc[(views.start < boundary) & (views.end > boundary), "user_id"]
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "timezone_assumption": TIMEZONE,
        "watched_rule": "union watched seconds / full scheduled elapsed duration >= 0.8, tested as 5*w >= 4*d",
        "source_files_sha256": {name: sha256(args.data_dir / name) for name in [LOG] + SCHEDULES + ["submission.csv"]},
        "source_scripts_sha256": {name: sha256(Path(__file__).parent / name) for name in ["build_interactions.py", "interaction_core.py"]},
        "views": view_stats, "schedule": schedule_stats, "splits": split_stats,
        "time_alignment": {"assumed_timezone": TIMEZONE, "viewing_duration_mismatches": view_stats["duration_mismatches"], "schedule_continuity": schedule_probe},
        "validation_labels": label_stats, "sanity_checks": checks, "manual_example": example,
        "boundary_verification_user_id": str(int(boundary_user.iloc[0])) if len(boundary_user) else None,
        "tables": {"user_airing_rows": len(events), "user_programme_rows": len(programmes),
                   "positive_user_programme_rows": int((programmes.watched_airings > 0).sum())},
        "execution": {"python": sys.version, "pandas": pd.__version__, "numpy": np.__version__,
                      "pyarrow": pyarrow.__version__, "platform": platform.platform(),
                      "elapsed_seconds": time.perf_counter() - started,
                      "peak_rss_MiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform == "darwin" else 1024)},
    }
    dump_json(args.report_dir / "summary.json", report)
    (args.report_dir / "README.md").write_text(report_markdown(report), encoding="utf-8")
    print(json.dumps({"splits": split_stats, "labels": label_stats, "tables": report["tables"],
                      "example_user": example["user_id"], "execution": report["execution"]}, indent=2))


if __name__ == "__main__":
    main()
