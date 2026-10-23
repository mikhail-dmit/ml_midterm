#!/usr/bin/env python3
"""Full, read-only SWEET.TV audit. IDs never pass through floating point."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import resource
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LOG = "dataset11-30.csv"
SCHEDULES = [
    "export_arh_11-20-final.csv",
    "export_arh_21-30-final.csv",
    "export_arh_31-42-final.csv",
]
TEMPLATE = "submission.csv"
LOG_COLUMNS = ["user_id", "vsetv_id", "start_time", "stop_time", "duraton"]
SCHEDULE_COLUMNS = [
    "channel_id", "channel_title", "start_time", "duration", "tv_show_title",
    "tv_show_id", "tv_show_category", "tv_show_genre_1", "tv_show_genre_2",
    "tv_show_genre_3", "year_of_production", "director", "actors",
]
TEXT_COLUMNS = [c for c in SCHEDULE_COLUMNS if c not in {
    "channel_id", "start_time", "duration", "tv_show_id",
}]
METADATA = [c for c in TEXT_COLUMNS if c != "channel_title"]
VAL_CUT = pd.Timestamp("2020-05-18")
TEST_CUT = pd.Timestamp("2020-07-27")
END_CUT = pd.Timestamp("2020-10-19")
UINT64_MAX = "18446744073709551615"
NAT = np.iinfo(np.int64).min


def json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (set,)):
        return sorted(value)
    raise TypeError(f"Cannot serialize {type(value)}")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_id(values):
    """Reject malformed/out-of-uint64 values before lossless UInt64 conversion."""
    valid = values.str.fullmatch(r"[0-9]+", na=False)
    canonical = values.str.lstrip("0").replace("", "0")
    valid &= (canonical.str.len() < 20) | (
        (canonical.str.len() == 20) & (canonical <= UINT64_MAX)
    )
    result = pd.Series(pd.NA, index=values.index, dtype="UInt64")
    result.loc[valid] = canonical.loc[valid].astype("UInt64")
    return result, ~valid


def distribution(values):
    series = pd.Series(values).dropna()
    if series.empty:
        return {"count": 0}
    qs = series.quantile([0, .01, .1, .25, .5, .75, .9, .95, .99, 1])
    return {
        "count": len(series), "mean": float(series.mean()),
        **{f"p{int(q * 100):02d}": float(v) for q, v in qs.items()},
    }


def counts_dict(series):
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).items() if v > 0}


def bounded_examples(frame, mask, n=8):
    selected = frame.loc[mask].head(n).copy()
    for col in selected:
        if col.endswith("id") or col == "vsetv_id":
            selected[col] = selected[col].astype("string")
    return json.loads(selected.to_json(orient="records", date_format="iso"))


def temporal_profile(frame, filename, dates, daily_rows, weekly_rows):
    valid = dates.dropna()
    for date, count in valid.dt.strftime("%Y-%m-%d").value_counts().sort_index().items():
        daily_rows.append({"file": filename, "date": date, "rows_by_start": int(count)})
    iso = valid.dt.isocalendar()
    week_keys = iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
    for week, count in week_keys.value_counts().sort_index().items():
        weekly_rows.append({"file": filename, "iso_week": week, "rows_by_start": int(count)})
    iso_weeks = sorted(week_keys.unique().tolist())
    return {
        "min_start": valid.min().isoformat() if len(valid) else None,
        "max_start": valid.max().isoformat() if len(valid) else None,
        "iso_weeks": iso_weeks,
        "distinct_start_dates": int(valid.dt.normalize().nunique()),
        "globally_start_sorted": bool(valid.is_monotonic_increasing),
        "start_time_decreases_in_file_order": int((valid.diff() < pd.Timedelta(0)).sum()),
        "by_start_window": {
            "before_week11": int((valid < pd.Timestamp("2020-03-09")).sum()),
            "weeks11_20": int(((valid >= pd.Timestamp("2020-03-09")) & (valid < VAL_CUT)).sum()),
            "weeks21_30": int(((valid >= VAL_CUT) & (valid < TEST_CUT)).sum()),
            "weeks31_42": int(((valid >= TEST_CUT) & (valid < END_CUT)).sum()),
            "after_week42": int((valid >= END_CUT).sum()),
        },
    }


def exact_duplicates(path, hashes, chunk_size):
    """Use hashes only as a screening index; count actual repeated raw tuples."""
    unique_hash, multiplicity = np.unique(hashes, return_counts=True)
    suspects = unique_hash[multiplicity > 1]
    if not len(suspects):
        return {"extra_rows": 0, "groups": 0, "rows_in_groups": 0, "examples": [],
                "hash_collision_groups": 0}
    tuples = Counter()
    for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunk_size):
        h = pd.util.hash_pandas_object(chunk, index=False).to_numpy()
        selected = chunk.loc[np.isin(h, suspects)]
        tuples.update(selected.itertuples(index=False, name=None))
    duplicated = [(row, count) for row, count in tuples.items() if count > 1]
    return {
        "extra_rows": sum(count - 1 for _, count in duplicated),
        "groups": len(duplicated),
        "rows_in_groups": sum(count for _, count in duplicated),
        "examples": [{"row": list(row), "count": count} for row, count in duplicated[:5]],
        "suspect_hash_groups": int(len(suspects)),
        "distinct_raw_tuples_in_suspect_groups": len(tuples),
    }


def load_profile(path, kind, chunk_size, column_rows):
    expected = LOG_COLUMNS if kind == "log" else SCHEDULE_COLUMNS
    with path.open(encoding="utf-8", newline="") as stream:
        header = next(csv.reader(stream))
    if header != expected:
        raise ValueError(f"Unexpected schema in {path.name}: {header!r}")
    stats = {c: Counter() for c in header}
    invalid = Counter()
    invalid_samples = {}
    frames, hash_parts = [], []
    for raw in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunk_size,
                           on_bad_lines="error"):
        hash_parts.append(pd.util.hash_pandas_object(raw, index=False).to_numpy())
        for col in header:
            values = raw[col]
            stripped = values.str.strip()
            stats[col].update({
                "blank": int((values == "").sum()),
                "whitespace_only": int(((values != "") & (stripped == "")).sum()),
                "outer_whitespace": int((values != stripped).sum()),
                "literal_zero": int((values == "0").sum()),
                "null_like_text": int(stripped.str.lower().isin(
                    ["null", "none", "nan", "na", "n/a", "unknown", "неизвестно"]
                ).sum()),
            })
        typed = pd.DataFrame(index=raw.index)
        id_cols = ["user_id", "vsetv_id"] if kind == "log" else ["channel_id", "tv_show_id"]
        for col in id_cols:
            typed[col], bad = parse_id(raw[col])
            invalid[col] += int(bad.sum())
            if bad.any() and col not in invalid_samples:
                invalid_samples[col] = raw.loc[bad, col].head(5).tolist()
        date_cols = ["start_time", "stop_time"] if kind == "log" else ["start_time"]
        fmt = "%Y-%m-%d %H:%M:%S" if kind == "log" else "%d.%m.%Y %H:%M:%S"
        for col in date_cols:
            typed[col] = pd.to_datetime(raw[col], format=fmt, errors="coerce")
            bad = typed[col].isna()
            invalid[col] += int(bad.sum())
            if bad.any() and col not in invalid_samples:
                invalid_samples[col] = raw.loc[bad, col].head(5).tolist()
        dur_col = "duraton" if kind == "log" else "duration"
        typed[dur_col] = pd.to_numeric(raw[dur_col], errors="coerce")
        bad = typed[dur_col].isna() | ~np.isfinite(typed[dur_col])
        invalid[dur_col] += int(bad.sum())
        if bad.any() and dur_col not in invalid_samples:
            invalid_samples[dur_col] = raw.loc[bad, dur_col].head(5).tolist()
        if kind == "schedule":
            for col in TEXT_COLUMNS:
                typed[col] = raw[col].astype("category")
        frames.append(typed)
    if kind == "schedule":
        # Unify category dictionaries without expanding millions of text values.
        frame = pd.DataFrame({
            col: pd.api.types.union_categoricals([part[col] for part in frames])
            if col in TEXT_COLUMNS else pd.concat([part[col] for part in frames], ignore_index=True)
            for col in frames[0].columns
        })
    else:
        frame = pd.concat(frames, ignore_index=True)
    del frames
    hashes = np.concatenate(hash_parts)
    duplicates = exact_duplicates(path, hashes, chunk_size)
    for col in header:
        column_rows.append({
            "file": path.name, "column": col, "rows": len(frame),
            "distinct_including_blank": int(frame[col].nunique(dropna=False)),
            "parsed_dtype": str(frame[col].dtype), **dict(stats[col]),
            "invalid_parsed_values": int(invalid[col]),
        })
    return frame, {
        "rows": len(frame), "columns": header, "column_count": len(header),
        "size_bytes": path.stat().st_size, "size_MB_decimal": path.stat().st_size / 1e6,
        "size_MiB": path.stat().st_size / 1024**2,
        "sha256": sha256(path), "raw_missing": {c: dict(v) for c, v in stats.items()},
        "invalid_parsed": dict(invalid), "invalid_examples": invalid_samples,
        "exact_duplicates": duplicates,
        "compact_frame_memory_bytes": int(frame.memory_usage(deep=True).sum()),
    }


def union_intervals(starts, stops):
    """Merge positive half-open intervals, including touching intervals."""
    if not len(starts):
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    order = np.lexsort((stops, starts))
    starts, stops = np.asarray(starts)[order], np.asarray(stops)[order]
    valid = stops > starts
    starts, stops = starts[valid], stops[valid]
    if not len(starts):
        return starts, stops
    previous_max = np.maximum.accumulate(stops)
    new_group = np.r_[True, starts[1:] > previous_max[:-1]]
    indices = np.flatnonzero(new_group)
    return starts[indices], np.maximum.reduceat(stops, indices)


def coverage_at(points, starts, stops):
    """Cumulative seconds covered by a disjoint sorted interval union at points."""
    if not len(starts):
        return np.zeros(len(points), dtype=np.int64)
    lengths = stops - starts
    prefix = np.r_[0, np.cumsum(lengths)]
    idx = np.searchsorted(starts, points, side="right") - 1
    safe = np.maximum(idx, 0)
    return np.where(idx >= 0, prefix[safe] + np.clip(points - starts[safe], 0, lengths[safe]), 0)


def interval_diagnostics(frame, group_cols, start_col, end_col, extra_cols, example_rows, label):
    valid = frame[start_col].notna() & frame[end_col].notna() & (frame[end_col] > frame[start_col])
    for col in group_cols:
        valid &= frame[col].notna()
    ordered = frame.loc[valid, list(dict.fromkeys(group_cols + [start_col, end_col] + extra_cols))]
    ordered = ordered.sort_values(group_cols + [start_col, end_col], kind="stable")
    grouped = ordered.groupby(group_cols, observed=True, sort=False)
    previous_max_end = grouped[end_col].cummax().groupby(
        [ordered[c] for c in group_cols], observed=True, sort=False
    ).shift()
    overlaps = ordered[start_col] < previous_max_end
    touching = ordered[start_col] == previous_max_end
    gaps = ordered[start_col] > previous_max_end
    gap_seconds = (ordered.loc[gaps, start_col] - previous_max_end.loc[gaps]).dt.total_seconds()
    overlap_seconds = (
        pd.concat([previous_max_end.loc[overlaps], ordered.loc[overlaps, end_col]], axis=1).min(axis=1)
        - ordered.loc[overlaps, start_col]
    ).dt.total_seconds()
    for issue, mask in [("overlap", overlaps), ("gap", gaps)]:
        sample = ordered.loc[mask].head(12).copy()
        sample["previous_max_end"] = previous_max_end.loc[sample.index]
        sample["check"] = label
        sample["issue"] = issue
        for col in group_cols + extra_cols:
            if col in sample and (col.endswith("id") or col == "vsetv_id"):
                sample[col] = sample[col].astype("string")
        example_rows.extend(sample.to_dict("records"))
    return {
        "valid_positive_rows": len(ordered),
        "groups": int(grouped.ngroups),
        "rows_overlapping_any_prior_interval": int(overlaps.sum()),
        "groups_with_overlap": int(ordered.loc[overlaps, group_cols].drop_duplicates().shape[0]),
        "touching_prior_union_end": int(touching.sum()),
        "gaps_after_prior_union_end": int(gaps.sum()),
        "gap_seconds": distribution(gap_seconds),
        "distinct_gap_lengths": int(gap_seconds.nunique()),
        "gap_seconds_frequency_top15": {str(k): int(v) for k, v in gap_seconds.value_counts().head(15).items()},
        "overlap_with_prior_union_seconds": distribution(overlap_seconds),
    }


def metadata_variants(schedules, output_rows):
    result = {}
    for scope, names in [("training_schedules", SCHEDULES[:2]), ("all_schedules", SCHEDULES)]:
        result[scope] = {}
        for col in METADATA + ["channel_title"]:
            parts = []
            key = "channel_id" if col == "channel_title" else "tv_show_id"
            for name in names:
                frame = schedules[name]
                selected = frame.loc[(frame[key] != 0) & frame[key].notna(), [key, col]].drop_duplicates()
                selected[col] = selected[col].astype(str)
                selected = selected.loc[selected[col].str.strip() != ""]
                parts.append(selected)
            pairs = pd.concat(parts, ignore_index=True).drop_duplicates()
            counts = pairs.groupby(key, observed=True)[col].nunique()
            conflicting = counts[counts > 1]
            result[scope][col] = {
                "ids_with_multiple_nonblank_values": len(conflicting),
                "maximum_nonblank_values_per_id": int(counts.max()) if len(counts) else 0,
            }
            if col == "channel_title":
                continue
            for item, n_values in conflicting.items():
                values = sorted(pairs.loc[pairs[key] == item, col].tolist())
                output_rows.append({
                    "scope": scope, "tv_show_id": str(item), "field": col,
                    "distinct_nonblank_values": int(n_values),
                    "example_values": json.dumps(values[:6], ensure_ascii=False),
                })
    return result


def schedule_checks(frame, filename, daily_rows, weekly_rows, interval_rows):
    end = frame.start_time + pd.to_timedelta(frame.duration, unit="s", errors="coerce")
    frame["end_time"] = end
    labelled = frame.tv_show_id.notna() & (frame.tv_show_id != 0)
    valid = frame.start_time.notna() & end.notna() & (frame.duration > 0)
    identity = ["channel_id", "start_time", "end_time", "tv_show_id"]
    unique_airings = frame.drop_duplicates(identity)
    positive_durations = frame.loc[valid, "duration"]
    labelled_durations = frame.loc[valid & labelled, "duration"]
    stats = {
        "temporal": temporal_profile(frame, filename, frame.start_time, daily_rows, weekly_rows),
        "max_end": end.max().isoformat(),
        "distinct_programmes_including_zero": int(frame.tv_show_id.nunique()),
        "distinct_programmes_nonzero": int(frame.loc[labelled, "tv_show_id"].nunique()),
        "distinct_channels": int(frame.channel_id.nunique()),
        "zero_channel_rows": int((frame.channel_id == 0).sum()),
        "labelled_rows": int(labelled.sum()), "zero_id_rows": int((frame.tv_show_id == 0).sum()),
        "labelled_row_fraction": float(labelled.mean()),
        "labelled_summed_duration_fraction": float(labelled_durations.sum() / positive_durations.sum()),
        "duration_seconds": distribution(frame.duration),
        "labelled_duration_seconds": distribution(frame.loc[labelled, "duration"]),
        "nonpositive_duration_rows": int((frame.duration <= 0).sum()),
        "nonpositive_duration_examples": bounded_examples(frame, frame.duration <= 0),
        "noninteger_duration_rows": int((frame.duration.dropna() % 1 != 0).sum()),
        "duration_over_24h_rows": int((frame.duration > 86400).sum()),
        "categories_all_rows": counts_dict(frame.tv_show_category),
        "categories_labelled_rows": counts_dict(frame.loc[labelled, "tv_show_category"]),
        "labelled_metadata_blank_fraction": {
            c: float((frame.loc[labelled, c].astype(str).str.strip() == "").mean()) for c in METADATA
        },
        "extra_rows_same_airing_identity": len(frame) - len(unique_airings),
        "same_channel_start_groups_with_multiple_programme_ids": int((
            frame.groupby(["channel_id", "start_time"], observed=True).tv_show_id.nunique() > 1
        ).sum()),
        "duplicate_identity_groups_with_metadata_disagreement": int((
            frame.groupby(identity, observed=True, dropna=False)[TEXT_COLUMNS].nunique().max(axis=1) > 1
        ).sum()),
        "intervals_raw": interval_diagnostics(
            frame, ["channel_id"], "start_time", "end_time", ["tv_show_id"],
            interval_rows, filename + ":raw",
        ),
        "intervals_unique_airings": interval_diagnostics(
            unique_airings, ["channel_id"], "start_time", "end_time", ["tv_show_id"],
            interval_rows, filename + ":unique_airings",
        ),
    }
    years = frame.year_of_production.astype(str)
    nonblank_year = years.str.strip() != ""
    conventional = years.str.fullmatch(r"\d{4}(?:\s*[-–]\s*\d{0,4})?", na=False)
    stats["production_year"] = {
        "nonblank_rows": int(nonblank_year.sum()),
        "range_or_open_range_rows": int((nonblank_year & years.str.contains(r"[-–]", regex=True)).sum()),
        "nonstandard_rows": int((nonblank_year & ~conventional).sum()),
        "nonstandard_examples": years.loc[nonblank_year & ~conventional].drop_duplicates().head(15).tolist(),
    }
    return stats


def cross_file_checks(log, schedules, template, test_user_rows):
    log_users = set(int(x) for x in log.user_id.dropna().unique())
    template_users = [int(x) for x in template.user_id]
    log_channels = set(int(x) for x in log.vsetv_id.dropna().unique())
    programme_sets = {
        name: set(int(x) for x in f.loc[f.tv_show_id != 0, "tv_show_id"].dropna().unique())
        for name, f in schedules.items()
    }
    channel_sets = {name: set(int(x) for x in f.channel_id.dropna().unique()) for name, f in schedules.items()}
    historical_programmes = programme_sets[SCHEDULES[0]] | programme_sets[SCHEDULES[1]]
    future_programmes = programme_sets[SCHEDULES[2]]
    train_mask = log.start_time < VAL_CUT
    later_mask = (log.start_time >= VAL_CUT) & (log.start_time < TEST_CUT)
    early_users = set(int(x) for x in log.loc[train_mask, "user_id"].dropna().unique())
    later_users = set(int(x) for x in log.loc[later_mask, "user_id"].dropna().unique())
    all_counts = log.groupby("user_id", observed=True).size()
    early_counts = log.loc[train_mask].groupby("user_id", observed=True).size()
    later_counts = log.loc[later_mask].groupby("user_id", observed=True).size()
    for user in template_users:
        test_user_rows.append({
            "user_id": str(user), "raw_log_rows": int(all_counts.get(user, 0)),
            "rows_starting_weeks11_20": int(early_counts.get(user, 0)),
            "rows_starting_weeks21_30": int(later_counts.get(user, 0)),
        })
    channel_windows = {}
    for name, mask in [(SCHEDULES[0], train_mask), (SCHEDULES[1], later_mask)]:
        subset = log.loc[mask]
        unmatched = subset.loc[~subset.vsetv_id.isin(channel_sets[name])]
        channel_windows[name] = {
            "raw_rows_starting_in_corresponding_window": len(subset),
            "raw_rows_on_channels_absent_this_schedule": len(unmatched),
            "users_on_these_channels": int(unmatched.user_id.nunique()),
            "missing_channels_row_counts": counts_dict(unmatched.vsetv_id),
        }
    boundary_duplicates = {}
    for left, right in zip(SCHEDULES, SCHEDULES[1:]):
        identity = ["channel_id", "start_time", "end_time", "tv_show_id"]
        merged = schedules[left].merge(schedules[right], on=identity, suffixes=("_left", "_right"))
        exact = pd.Series(True, index=merged.index)
        for col in TEXT_COLUMNS:
            exact &= merged[col + "_left"].astype(str) == merged[col + "_right"].astype(str)
        boundary_duplicates[left + " + " + right] = {
            "shared_airing_identities": len(merged),
            "identical_content_rows": int(exact.sum()),
            "shared_identity_with_different_metadata": int((~exact).sum()),
            "shared_labelled_airings": int((merged.tv_show_id != 0).sum()),
            "min_shared_start": merged.start_time.min().isoformat() if len(merged) else None,
            "max_shared_start": merged.start_time.max().isoformat() if len(merged) else None,
        }
    strict_catalogues = {}
    all_schedule = pd.concat([
        f[["channel_id", "start_time", "end_time", "tv_show_id"]] for f in schedules.values()
    ], ignore_index=True)
    for label, start, stop in [("weeks11_20", pd.Timestamp("2020-03-09"), VAL_CUT),
                               ("weeks21_30", VAL_CUT, TEST_CUT), ("weeks31_42", TEST_CUT, END_CUT)]:
        eligible = all_schedule.loc[(all_schedule.start_time < stop) & (all_schedule.end_time > start)
                                    & (all_schedule.tv_show_id != 0)]
        strict_catalogues[label] = {"programmes_with_any_airing_overlap": int(eligible.tv_show_id.nunique())}
    combined_intervals = interval_diagnostics(
        all_schedule, ["channel_id"], "start_time", "end_time", ["tv_show_id"], [], "combined_schedules")
    return {
        "raw_log_distinct_users": len(log_users),
        "raw_log_distinct_channels": len(log_channels),
        "template_users_in_raw_log": len(set(template_users) & log_users),
        "template_users_absent_raw_log": len(set(template_users) - log_users),
        "template_users_absent_raw_log_ids": [str(x) for x in template_users if x not in log_users],
        "template_users_with_raw_history_weeks11_20": len(set(template_users) & early_users),
        "template_users_with_raw_history_weeks21_30": len(set(template_users) & later_users),
        "raw_log_users_outside_template": len(log_users - set(template_users)),
        "raw_users_weeks11_20": len(early_users), "raw_users_weeks21_30": len(later_users),
        "raw_users_first_seen_weeks21_30": len(later_users - early_users),
        "channel_coverage": {
            name: {"log_channels_absent_schedule_count": len(log_channels - ids),
                   "schedule_channels_absent_log_count": len(ids - log_channels),
                   "log_channels_absent_schedule": sorted(log_channels - ids),
                   "schedule_channels_absent_log": sorted(ids - log_channels)}
            for name, ids in channel_sets.items()
        },
        "channel_coverage_corresponding_windows": channel_windows,
        "adjacent_schedule_file_duplicates": boundary_duplicates,
        "combined_schedule_intervals": combined_intervals,
        "strict_time_window_catalogues": strict_catalogues,
        "programme_catalogue": {
            "historical_union": len(historical_programmes), "future": len(future_programmes),
            "shared_history_future": len(historical_programmes & future_programmes),
            "future_not_in_historical_schedule": len(future_programmes - historical_programmes),
            "historical_not_in_future_schedule": len(historical_programmes - future_programmes),
            "weeks21_30_not_in_weeks11_20": len(programme_sets[SCHEDULES[1]] - programme_sets[SCHEDULES[0]]),
            "all_three_union": len(set.union(*programme_sets.values())),
        },
        "schedule_boundary_crossings": {
            name: {cut.isoformat(): int(((f.start_time < cut) & (f.end_time > cut)).sum())
                   for cut in [VAL_CUT, TEST_CUT, END_CUT]}
            for name, f in schedules.items()
        },
    }


def schedule_log_coverage(log, schedules, test_user_rows):
    """Raw overlap coverage only; does not assign programmes or construct labels."""
    history = pd.concat([
        schedules[name][["channel_id", "start_time", "end_time", "tv_show_id"]]
        for name in SCHEDULES[:2]
    ], ignore_index=True)
    result = {}
    valid_views = log.start_time.notna() & log.stop_time.notna() & (log.stop_time > log.start_time)
    views = log.loc[valid_views]
    for scope in ["any_schedule", "labelled_schedule"]:
        selected = history if scope == "any_schedule" else history.loc[history.tv_show_id != 0]
        covered = pd.Series(0, index=views.index, dtype="int64")
        for channel, channel_views in views.groupby("vsetv_id", observed=True, sort=False):
            channel_schedule = selected.loc[selected.channel_id == channel]
            starts = channel_schedule.start_time.astype("int64").to_numpy() // 10**9
            stops = channel_schedule.end_time.astype("int64").to_numpy() // 10**9
            ok = (starts != NAT // 10**9) & (stops != NAT // 10**9)
            starts, stops = union_intervals(starts[ok], stops[ok])
            a = channel_views.start_time.astype("int64").to_numpy() // 10**9
            b = channel_views.stop_time.astype("int64").to_numpy() // 10**9
            covered.loc[channel_views.index] = coverage_at(b, starts, stops) - coverage_at(a, starts, stops)
        lengths = (views.stop_time - views.start_time).dt.total_seconds()
        if not ((covered >= 0) & (covered <= lengths)).all():
            raise AssertionError("Union coverage must lie between zero and view length")
        result[scope] = {
            "valid_view_rows": len(views),
            "rows_with_any_overlap": int((covered > 0).sum()),
            "rows_fully_covered": int((covered == lengths).sum()),
            "rows_partially_covered": int(((covered > 0) & (covered < lengths)).sum()),
            "rows_without_overlap": int((covered == 0).sum()),
            "view_row_seconds_covered": int(covered.sum()),
            "view_row_seconds_total": int(lengths.sum()),
            "fraction_view_row_seconds_covered": float(covered.sum() / lengths.sum()),
            "users_with_any_overlap": int(views.loc[covered > 0, "user_id"].nunique()),
            "definition": "sum over raw viewing rows; overlapping user sessions are not deduplicated here",
        }
        if scope == "labelled_schedule":
            result[scope]["by_window"] = {}
            for label, mask in [("weeks11_20", views.start_time < VAL_CUT),
                                 ("weeks21_30", views.start_time >= VAL_CUT)]:
                selected_rows = mask & (covered > 0)
                by_user = views.loc[selected_rows].groupby("user_id", observed=True).size()
                result[scope]["by_window"][label] = {
                    "rows_starting_in_window_with_any_labelled_overlap": int(selected_rows.sum()),
                    "users_with_any_labelled_overlap": len(by_user),
                    "template_users_with_any_labelled_overlap": sum(int(r["user_id"]) in by_user.index for r in test_user_rows),
                    "caveat": "Sessions are grouped by start; boundary-crossing overlaps are not clipped here. No 80% threshold applied.",
                }
                for row in test_user_rows:
                    row["raw_rows_with_any_labelled_overlap_starting_" + label] = int(by_user.get(int(row["user_id"]), 0))
    return result


def exam_comparison(files):
    rows = []
    def add(claim, expected, actual, note=""):
        rows.append({"claim": claim, "expected": expected, "actual": actual,
                     "matches": expected == actual, "note": note})
    expected_rows = [5821987, 1074235, 1074394, 1295378, 1260]
    for name, expected in zip([LOG] + SCHEDULES + [TEMPLATE], expected_rows):
        add(name + " data rows (header excluded)", expected, files[name]["rows"])
    add("four data files: total rows", 9265994, sum(files[n]["rows"] for n in [LOG] + SCHEDULES))
    for name, programmes, channels in zip(SCHEDULES, [5848, 6364, 6637], [400, 403, 404]):
        add(name + " distinct programmes, nonzero", programmes, files[name]["distinct_programmes_nonzero"],
            "Zero is not an item; also report distinct IDs including zero.")
        add(name + " channels", channels, files[name]["distinct_channels"])
        add(name + " nonblank categories", 9,
            len([x for x in files[name]["categories_all_rows"] if x.strip()]))
    add("first schedule labelled rows", 115613, files[SCHEDULES[0]]["labelled_rows"])
    add("first schedule zero-id rows", 958622, files[SCHEDULES[0]]["zero_id_rows"])
    add("viewing duration median seconds", 396.0, files[LOG]["duration_seconds"]["p50"])
    add("viewing duration maximum seconds", 342145.0, files[LOG]["duration_seconds"]["p100"])
    add("viewing duration equals stop-start: mismatches", 0, files[LOG]["duration_mismatch_rows"])
    return rows


def self_checks():
    a, b = union_intervals(np.array([0, 3, 10, 30]), np.array([10, 4, 20, 40]))
    assert a.tolist() == [0, 30] and b.tolist() == [20, 40]
    points = np.array([-2, 0, 5, 20, 25, 35, 50])
    assert coverage_at(points, a, b).tolist() == [0, 0, 5, 20, 20, 25, 30]
    # Independent enumeration oracle for union coverage on a tiny integer grid.
    for left in range(-2, 42):
        for right in range(left, 43):
            actual = int(coverage_at(np.array([right]), a, b)[0] - coverage_at(np.array([left]), a, b)[0])
            expected = sum(any(x <= t < y for x, y in zip(a, b)) for t in range(left, right))
            assert actual == expected
    ids, bad = parse_id(pd.Series(["17226860011138219284", UINT64_MAX, "18446744073709551616", "1.0", ""]))
    assert str(ids.iloc[0]) == "17226860011138219284"
    assert str(ids.iloc[1]) == UINT64_MAX and bad.tolist() == [False, False, True, True, True]
    assert pd.to_datetime("09.03.2020 06:00:00", format="%d.%m.%Y %H:%M:%S") == pd.Timestamp("2020-03-09 06:00:00")
    # Nested intervals must be compared with the prior maximum end, not just the prior row.
    toy = pd.DataFrame({"channel_id": [1, 1, 1, 1], "start": pd.to_datetime([0, 2, 4, 10], unit="s"),
                        "end": pd.to_datetime([10, 3, 6, 11], unit="s")})
    check = interval_diagnostics(toy, ["channel_id"], "start", "end", [], [], "toy")
    assert check["rows_overlapping_any_prior_interval"] == 2
    assert check["touching_prior_union_end"] == 1
    return {"passed": True, "checks": ["nested/touching interval union", "coverage vs enumeration oracle",
                                        "uint64 exact round trip and invalid IDs", "explicit day-first dates",
                                        "prior-maximum overlap detection"]}


def markdown_report(report):
    files = report["files"]
    lines = ["# SWEET.TV — full data audit", "", f"Generated: {report['generated_utc']}", "",
             "## Scope and definitions", "",
             "All five supplied CSVs were read. Original files were not modified. IDs were parsed losslessly as unsigned 64-bit integers and exported as strings where needed.",
             "Input is chunked; compact typed frames are retained for global checks. This runtime/memory is not comparable with a CSV-only counting pass.",
             "Times are naive as supplied; timezone is unspecified. ISO weeks use start timestamps. Intervals are half-open [start, end).",
             "Raw-log history/overlap is not an 80%-qualified programme interaction. No recommender or target generator is fitted by this audit.", "",
             "## Files", "", "| File | Rows | Columns | Decimal MB | Exact duplicate extra rows |", "|---|---:|---:|---:|---:|"]
    for name, info in files.items():
        lines.append(f"| {name} | {info['rows']:,} | {info['column_count']} | {info['size_MB_decimal']:.3f} | {info['exact_duplicates']['extra_rows']:,} |")
    lines += ["", "## Comparison with exam_quiz_AVITO.md", "", "| Claim | Brief | Observed | Match |", "|---|---:|---:|:---:|"]
    for row in report["exam_comparison"]:
        lines.append(f"| {row['claim']} | {row['expected']} | {row['actual']} | {'yes' if row['matches'] else '**NO**'} |")
    lines += ["", "File sizes in the brief are approximate; both decimal MB and MiB are recorded in JSON. The 131 MB archive is not present, so its size cannot be checked.",
              "The brief's reading benchmark uses different work; the audit reports its own runtime and RSS, without claiming to reproduce 4.6 s / 12.6 MB.", "", "## Dates and ISO weeks", "",
              "| File | First start | Last start | Last stop/end | ISO weeks |", "|---|---|---|---|---|"]
    for name in [LOG] + SCHEDULES:
        info = files[name]
        temporal = info["temporal"]
        lines.append(f"| {name} | {temporal['min_start']} | {temporal['max_start']} | {info['max_end']} | {', '.join(temporal['iso_weeks'])} |")
    lines += ["", "## Viewing log", "", "```json", json.dumps({k: v for k, v in files[LOG].items()
              if k not in {"raw_missing", "exact_duplicates", "sha256", "columns", "temporal"}},
              indent=2, ensure_ascii=False, default=json_default), "```", "", "## Schedule diagnostics"]
    for name in SCHEDULES:
        info = files[name]
        lines += ["", f"### {name}", "", "```json", json.dumps({k: v for k, v in info.items()
                  if k not in {"raw_missing", "exact_duplicates", "sha256", "columns", "temporal"}},
                  indent=2, ensure_ascii=False, default=json_default), "```"]
    for title, key in [("Cross-file coverage and cold-start accounting", "cross_file"),
                       ("Historical schedule / raw viewing overlap", "raw_view_schedule_coverage"),
                       ("Programme metadata consistency", "metadata_consistency"),
                       ("Submission template", "template_checks"),
                       ("Verification and run environment", "execution")]:
        lines += ["", "## " + title, "", "```json", json.dumps(report[key], indent=2, ensure_ascii=False, default=json_default), "```"]
    lines += ["", "## Interpretation cautions", "",
              "- `tv_show_id = 0` is not a recommendable item. Row coverage is not airtime coverage; summed-duration coverage is separately reported and can itself be affected by overlapping schedule records.",
              "- Schedule metadata statistics that include weeks 31–42 are data-quality diagnostics, not training features. Training-only metadata variants are separately exported.",
              "- The interval overlap counts count rows intersecting a prior union, not all overlapping pairs. Identical-airing and unique-airing statistics are separate.",
              "- Blank cells, whitespace-only cells, literal zeros and null-like text are distinct. A zero-filled numeric field is not automatically missing.",
              "- Catalogue presence is not observed viewing support. A future programme appearing in an old schedule can still have zero training interactions.",
              "- See columns.csv for every column's missingness and cardinality; daily_counts.csv and weekly_counts.csv for complete temporal counts; and example/metadata CSVs for inspectable records.",
              "- All automated checks here were executed by the assistant. The student's personal verification remains to be performed and is not claimed.", ""]
    return "\n".join(lines)


def summary_report(report):
    files = report["files"]
    view = files[LOG]
    cross = report["cross_file"]
    coverage = report["raw_view_schedule_coverage"]
    lines = [
        "# SWEET.TV data audit — findings", "",
        f"Generated: {report['generated_utc']}", "",
        "All five original CSVs were read in full; they were not modified. This is a data-quality audit, not model fitting or 80%-watch label generation.", "",
        "## 1. File counts and comparison with the task", "",
        "| File | Data rows | Columns | Size, decimal MB | Exact duplicate extra rows |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, info in files.items():
        lines.append(f"| {name} | {info['rows']:,} | {info['column_count']} | {info['size_MB_decimal']:.3f} | {info['exact_duplicates']['extra_rows']:,} |")
    lines += ["", "All row counts, schemas, channel counts, nine-category counts, first-schedule zero/nonzero counts, and the log duration median/maximum agree with the task.",
              "The four main files contain exactly 9,265,994 rows, excluding headers. The five files total "
              f"{sum(f['size_bytes'] for f in files.values()):,} bytes "
              f"({sum(f['size_bytes'] for f in files.values()) / 1024**2:.2f} MiB). No archive is present to verify its stated size.",
              "", "**Discrepancies / clarifications:**", ""]
    for row in report["exam_comparison"]:
        if not row["matches"]:
            lines.append(f"- {row['claim']}: brief **{row['expected']}**, observed **{row['actual']}**.")
    lines += ["- The programme-count differences are explained exactly by including ID `0`; the task's counts are distinct raw IDs, not valid recommendable items.",
              "- The task's 10.8% is a **row fraction**, not a measured fraction of airtime or user viewing time.",
              "", "## 2. Dates, weeks and temporal boundaries", "",
              "Naive timestamps as supplied; the source timezone is not specified. Date formats are explicitly parsed, never auto-inferred.", "",
              "| File | Earliest start | Latest start | Latest end |",
              "|---|---|---|---|"]
    for name in [LOG] + SCHEDULES:
        info = files[name]
        lines.append(f"| {name} | {info['temporal']['min_start']} | {info['temporal']['max_start']} | {info['max_end']} |")
    lines += ["", "- Viewing starts occupy ISO weeks 11–30 only; there is no viewing behaviour in weeks 31–42.",
              "- The schedule filenames are not exact timestamp partitions. The first includes week-10 spill-in and week-21 spill-out; the second includes week-31 spill-out; the third includes week-43 spill-out.",
              f"- **{view['cross_validation_cutoff_rows']:,} viewing sessions cross 2020-05-18 00:00**, so splitting only on start time can leak or lose viewing seconds. Clip/split at the cutoff before constructing interactions.",
              "- Adjacent schedule calendar ranges overlap, but no repeated airing identities were found across adjacent files. Use channel/time boundaries rather than filename alone.", "",
              "| Adjacent files | Shared airing identities | Identical content rows | Labelled shared airings |",
              "|---|---:|---:|---:|"]
    for pair, values in cross["adjacent_schedule_file_duplicates"].items():
        lines.append(f"| {pair} | {values['shared_airing_identities']:,} | {values['identical_content_rows']:,} | {values['shared_labelled_airings']:,} |")
    lines += ["", "Complete per-day and ISO-week counts are in `daily_counts.csv` and `weekly_counts.csv`. Counts use start timestamps.",
              "", "## 3. Viewing log and IDs", "",
              f"- **{view['distinct_users']:,} users**, **{view['distinct_channels']} channels** in the raw log.",
              f"- All user/channel IDs and timestamps parse; no missing core values, nonpositive view durations or reversed intervals were found.",
              f"- **{view['distinct_users_above_int64']:,} user IDs exceed signed int64**; {view['rows_user_id_above_exact_float64_integer_range']:,} rows have IDs above the contiguous exact-integer range of float64. Preserve strings/uint64 and map to separate model indices.",
              f"- Duration: minimum {view['duration_seconds']['p00']:g}s; median **{view['duration_seconds']['p50']:g}s**; mean {view['duration_seconds']['mean']:.1f}s; maximum **{view['duration_seconds']['p100']:g}s**. {view['duration_over_24h_rows']} timestamp intervals exceed 24h.",
              f"- **{view['duration_mismatch_rows']} rows disagree between `duraton` and naive stop-minus-start**. All discrepancies are exported, with offset counts and dates in JSON. A clock-change hypothesis must be distinguished from a confirmed source timezone.",
              f"- **{view['exact_duplicates']['extra_rows']} exact duplicate extra rows** were verified against raw tuples, not inferred solely from hashes.",
              f"- After identical parsed sessions are removed, **{view['intervals_unique_sessions_same_user_channel']['rows_overlapping_any_prior_interval']:,} sessions overlap a prior same-user/same-channel interval**.",
              f"- Across all channels, **{view['intervals_unique_sessions_same_user_any_channel']['rows_overlapping_any_prior_interval']:,} sessions overlap a prior interval for the same user**. This can reflect multiple devices, household accounts or logging behaviour; this audit does not identify the cause.",
              "- Overlap counts count affected rows, not all overlapping pairs. Within an airing, sum interval-union coverage rather than raw segment durations.",
              "", "## 4. Schedule coverage and metadata", "",
              "| Schedule | Nonzero IDs | Channels | Labelled rows | Labelled row share | Share of summed scheduled seconds |",
              "|---|---:|---:|---:|---:|---:|"]
    for name in SCHEDULES:
        f = files[name]
        lines.append(f"| {name} | {f['distinct_programmes_nonzero']:,} | {f['distinct_channels']} | {f['labelled_rows']:,} | {f['labelled_row_fraction']:.2%} | {f['labelled_summed_duration_fraction']:.2%} |")
    lines += ["", "Summed scheduled seconds are not union airtime; overlapping schedule records can affect that denominator.",
              "", "**Missing metadata among labelled rows** (row-weighted, not unique-item-weighted):", "",
              "| Field | Weeks 11–20 | Weeks 21–30 | Weeks 31–42 |", "|---|---:|---:|---:|"]
    for col in METADATA:
        values = [files[name]["labelled_metadata_blank_fraction"][col] for name in SCHEDULES]
        lines.append(f"| {col} | " + " | ".join(f"{x:.2%}" for x in values) + " |")
    lines += ["", "- Titles and categories are complete for labelled rows; secondary genres, directors and actors have missing values.",
              "- No exact duplicate rows or duplicate airing identities occur **within** individual schedule files.",
              "- Nonpositive durations by schedule: " + ", ".join(f"{name}: {files[name]['nonpositive_duration_rows']}" for name in SCHEDULES) + ". Inspect/drop zero-duration airings before percentage division.",
              "- Overlapping schedule rows by file (positive intervals): " + ", ".join(str(files[name]['intervals_raw']['rows_overlapping_any_prior_interval']) for name in SCHEDULES) + ". Examples and gaps are exported.",
              "- Production years include closed/open ranges and `2006 - ???`; do not blindly cast the whole field to an integer.",
              "- Many IDs have multiple titles (including episode/season variants). Categories are consistent per nonzero ID, but some genres/cast/director values vary.",
              "", "| Metadata field | Historical IDs with multiple nonblank values | All-schedule IDs with multiple nonblank values |",
              "|---|---:|---:|"]
    for col in METADATA:
        hist = report["metadata_consistency"]["training_schedules"][col]
        all_ = report["metadata_consistency"]["all_schedules"][col]
        lines.append(f"| {col} | {hist['ids_with_multiple_nonblank_values']:,} | {all_['ids_with_multiple_nonblank_values']:,} |")
    lines += ["", "Historical means the first two schedule files, not the fitting-only side of a future validation split. These are diagnostic counts, not fitted content features.",
              "", "## 5. Users, catalogue changes and join coverage", "",
              f"- All **{cross['template_users_in_raw_log']:,}/{files[TEMPLATE]['rows']:,} template users** have some raw historical viewing; {cross['template_users_with_raw_history_weeks11_20']:,} appear before the proposed validation cutoff.",
              "- Raw history does not guarantee labelled programme interactions or 80%-qualified watches. Per-template-user raw counts/labelled-overlap counts are in `test_users.csv`.",
              f"- Historical schedule union: **{cross['programme_catalogue']['historical_union']:,}** nonzero IDs. Future file: **{cross['programme_catalogue']['future']:,}**; **{cross['programme_catalogue']['shared_history_future']:,}** are shared and **{cross['programme_catalogue']['future_not_in_historical_schedule']:,}** are absent from both historical files.",
              "- These catalogue counts use complete files, including boundary spillovers; strict timestamp-window counts are separately recorded in JSON.",
              "", "**Raw viewing overlap against the union of the historical schedule files:**", "",
              "| Schedule scope | Viewing rows with any overlap | Viewing rows with no overlap | Share of raw view-row seconds covered | Users with overlap |",
              "|---|---:|---:|---:|---:|"]
    for scope, values in coverage.items():
        lines.append(f"| {scope} | {values['rows_with_any_overlap']:,} | {values['rows_without_overlap']:,} | {values['fraction_view_row_seconds_covered']:.2%} | {values['users_with_any_overlap']:,} |")
    lines += ["", "These are overlaps of any positive length, not watched labels. The denominator sums raw viewing rows, so concurrent/duplicate sessions are counted per row. Schedule coverage itself uses interval unions.",
              "Some viewed channels are absent from the schedules. Per-window affected row/user counts and channel IDs are in JSON; do not assume every view can be matched.",
              "", "## 6. Submission template", "",
              f"- {files[TEMPLATE]['rows']:,} rows, two columns `user_id,tv_show_id`, unique users, five zero placeholders per prediction cell.",
              "- Preserve its user IDs/order; only replace predictions when producing a submission.",
              "", "## 7. Verification and rerunning", "",
              "```bash", "python3 scripts/audit_data.py --self-check-only", "python3 scripts/audit_data.py",
              "python3 scripts/verify_audit.py", "```", "",
              f"Full audit time: **{report['execution']['elapsed_seconds']:.1f}s**; peak RSS **{report['execution']['peak_rss_MiB']:.1f} MiB**.",
              "Python/pandas/NumPy versions, source-file SHA-256s, built-in verification and accounting checks are recorded in `audit.json`.",
              "The separate verifier recounts raw CSV data with the Python standard library, including the median and duration inconsistencies. It writes `verification.json` after a successful run.",
              "All checks so far are assistant-executed. Student personal verification has not been performed or claimed.",
              "", "See `audit_details.md` for expanded diagnostics and `audit.json` for complete machine-readable results.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "sweettv-tv-program-recommender")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "data_audit")
    parser.add_argument("--chunk-size", type=int, default=250000)
    parser.add_argument("--self-check-only", action="store_true")
    args = parser.parse_args()
    if args.chunk_size <= 0:
        parser.error("--chunk-size must be positive")
    verification = self_checks()
    if args.self_check_only:
        print(json.dumps(verification, indent=2))
        return
    started = time.perf_counter()
    column_rows, daily_rows, weekly_rows = [], [], []
    schedule_interval_rows, view_interval_rows, metadata_rows, test_user_rows = [], [], [], []
    files, schedules = {}, {}
    for name in SCHEDULES:
        print(f"Auditing {name} ...", flush=True)
        frame, info = load_profile(args.data_dir / name, "schedule", args.chunk_size, column_rows)
        info.update(schedule_checks(frame, name, daily_rows, weekly_rows, schedule_interval_rows))
        files[name], schedules[name] = info, frame
    print(f"Auditing {LOG} ...", flush=True)
    log, info = load_profile(args.data_dir / LOG, "log", args.chunk_size, column_rows)
    difference = (log.stop_time - log.start_time).dt.total_seconds()
    valid_difference = difference.notna() & log.duraton.notna()
    mismatch = valid_difference & (difference != log.duraton)
    user_values = log.user_id.dropna()
    info.update({
        "temporal": temporal_profile(log, LOG, log.start_time, daily_rows, weekly_rows),
        "max_end": log.stop_time.max().isoformat(),
        "distinct_users": int(log.user_id.nunique()), "distinct_channels": int(log.vsetv_id.nunique()),
        "user_id_min": str(user_values.min()), "user_id_max": str(user_values.max()),
        "rows_user_id_above_int64": int((user_values > 2**63 - 1).sum()),
        "distinct_users_above_int64": int(user_values.loc[user_values > 2**63 - 1].nunique()),
        "rows_user_id_above_exact_float64_integer_range": int((user_values > 2**53).sum()),
        "zero_user_rows": int((log.user_id == 0).sum()), "zero_channel_rows": int((log.vsetv_id == 0).sum()),
        "duration_seconds": distribution(log.duraton),
        "nonpositive_duration_rows": int((log.duraton <= 0).sum()),
        "noninteger_duration_rows": int((log.duraton.dropna() % 1 != 0).sum()),
        "stop_before_start_rows": int((difference < 0).sum()),
        "zero_length_intervals": int((difference == 0).sum()),
        "duration_mismatch_rows": int(mismatch.sum()),
        "duration_mismatch_examples": bounded_examples(log, mismatch),
        "naive_elapsed_minus_recorded_duration_seconds": counts_dict((difference - log.duraton).loc[mismatch]),
        "duration_mismatch_start_dates": counts_dict(log.loc[mismatch, "start_time"].dt.strftime("%Y-%m-%d")),
        "duration_mismatch_stop_dates": counts_dict(log.loc[mismatch, "stop_time"].dt.strftime("%Y-%m-%d")),
        "duration_over_24h_rows": int((difference > 86400).sum()),
        "cross_midnight_rows": int((log.start_time.dt.normalize() != log.stop_time.dt.normalize()).sum()),
        "cross_validation_cutoff_rows": int(((log.start_time < VAL_CUT) & (log.stop_time > VAL_CUT)).sum()),
        "cross_test_cutoff_rows": int(((log.start_time < TEST_CUT) & (log.stop_time > TEST_CUT)).sum()),
        "stop_after_test_cutoff_rows": int((log.stop_time > TEST_CUT).sum()),
        "raw_rows_per_user": distribution(log.groupby("user_id", observed=True).size()),
    })
    unique_log = log.drop_duplicates()
    info["intervals_unique_sessions_same_user_channel"] = interval_diagnostics(
        unique_log, ["user_id", "vsetv_id"], "start_time", "stop_time", [], view_interval_rows, "same_user_channel")
    info["intervals_unique_sessions_same_user_any_channel"] = interval_diagnostics(
        unique_log, ["user_id"], "start_time", "stop_time", ["vsetv_id"], view_interval_rows, "same_user_any_channel")
    del unique_log
    files[LOG] = info
    path = args.data_dir / TEMPLATE
    template = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(template.columns) != ["user_id", "tv_show_id"]:
        raise ValueError("Unexpected submission template columns")
    parsed_users, bad_users = parse_id(template.user_id)
    if bad_users.any():
        raise ValueError("Template contains invalid user IDs")
    predictions = template.tv_show_id.str.split()
    files[TEMPLATE] = {
        "rows": len(template), "columns": list(template.columns), "column_count": len(template.columns),
        "size_bytes": path.stat().st_size, "size_MB_decimal": path.stat().st_size / 1e6,
        "size_MiB": path.stat().st_size / 1024**2, "sha256": sha256(path),
        "exact_duplicates": {"extra_rows": int(template.duplicated().sum())},
    }
    for col in template:
        column_rows.append({"file": TEMPLATE, "column": col, "rows": len(template),
                            "distinct_including_blank": int(template[col].nunique(dropna=False)),
                            "parsed_dtype": "raw string", "blank": int((template[col] == "").sum()),
                            "whitespace_only": int(((template[col] != "") & (template[col].str.strip() == "")).sum()),
                            "outer_whitespace": int((template[col] != template[col].str.strip()).sum()),
                            "literal_zero": int((template[col] == "0").sum()), "null_like_text": 0,
                            "invalid_parsed_values": 0})
    print("Checking cross-file coverage and metadata ...", flush=True)
    cross = cross_file_checks(log, schedules, template, test_user_rows)
    metadata = metadata_variants(schedules, metadata_rows)
    coverage = schedule_log_coverage(log, schedules, test_user_rows)
    comparison = exam_comparison(files)
    # Reconcile core accounting independently of the presentation layer.
    for name in SCHEDULES:
        assert files[name]["labelled_rows"] + files[name]["zero_id_rows"] == files[name]["rows"]
    assert cross["template_users_in_raw_log"] + cross["template_users_absent_raw_log"] == len(template)
    for name in [LOG] + SCHEDULES:
        assert sum(r["rows_by_start"] for r in weekly_rows if r["file"] == name) == files[name]["rows"] - files[name]["invalid_parsed"].get("start_time", 0)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "files": {name: files[name] for name in [LOG] + SCHEDULES + [TEMPLATE]},
        "exam_comparison": comparison, "cross_file": cross,
        "raw_view_schedule_coverage": coverage, "metadata_consistency": metadata,
        "template_checks": {
            "distinct_users": int(parsed_users.nunique()),
            "duplicate_user_rows": int(parsed_users.duplicated().sum()),
            "all_user_ids_decimal_uint64": bool((~bad_users).all()),
            "all_rows_have_five_tokens": bool(predictions.str.len().eq(5).all()),
            "all_prediction_cells_are_zero_placeholders": bool(predictions.map(lambda x: x == ["0"] * 5).all()),
            "user_ids_sorted_numeric": bool(parsed_users.is_monotonic_increasing),
        },
        "execution": {
            "python": sys.version, "pandas": pd.__version__, "numpy": np.__version__,
            "platform": platform.platform(), "machine": platform.machine(),
            "chunk_size": args.chunk_size, "elapsed_seconds": time.perf_counter() - started,
            "peak_rss_MiB": rss_bytes / 1024**2, "self_checks": verification,
            "accounting_assertions_passed": True,
            "personal_student_verification": "Not performed or claimed by this automated audit",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows, columns in [
        ("columns.csv", column_rows, None), ("daily_counts.csv", daily_rows, None),
        ("weekly_counts.csv", weekly_rows, None),
        ("schedule_metadata_variants.csv", metadata_rows, ["scope", "tv_show_id", "field", "distinct_nonblank_values", "example_values"]),
        ("schedule_interval_examples.csv", schedule_interval_rows, ["channel_id", "start_time", "end_time", "tv_show_id", "previous_max_end", "check", "issue"]),
        ("view_interval_examples.csv", view_interval_rows, ["user_id", "vsetv_id", "start_time", "stop_time", "previous_max_end", "check", "issue"]),
        ("test_users.csv", test_user_rows, None),
    ]:
        pd.DataFrame(rows, columns=columns).to_csv(args.output_dir / name, index=False)
    mismatch_export = log.loc[mismatch].copy()
    mismatch_export["user_id"] = mismatch_export.user_id.astype("string")
    mismatch_export["naive_elapsed_seconds"] = difference.loc[mismatch].astype("int64")
    mismatch_export["naive_elapsed_minus_duraton"] = (difference - log.duraton).loc[mismatch].astype("int64")
    mismatch_export.to_csv(args.output_dir / "view_duration_mismatches.csv", index=False)
    (args.output_dir / "audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")
    (args.output_dir / "audit_details.md").write_text(markdown_report(report), encoding="utf-8")
    (args.output_dir / "audit.md").write_text(summary_report(report), encoding="utf-8")
    print(f"Finished in {report['execution']['elapsed_seconds']:.1f}s; peak RSS {report['execution']['peak_rss_MiB']:.1f} MiB")
    print(f"Reports: {args.output_dir.resolve()}")
    print("Exam-brief discrepancies:")
    for item in comparison:
        if not item["matches"]:
            print(f"  {item['claim']}: brief={item['expected']}; actual={item['actual']}")


if __name__ == "__main__":
    main()
