#!/usr/bin/env python3
"""Independent raw-CSV rejoin for sampled users plus full artifact invariants.

Reads Parquet with pandas, but does not import the builder, its interval/time
helpers, or its aggregation code. The sampled-user join/union uses Python's
csv, datetime, zoneinfo, dictionaries and an intentionally simple nested loop.
"""

import argparse
import csv
import hashlib
import json
import random
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "sweettv-tv-program-recommender")
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / "artifacts" / "interactions")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "interactions")
    args = parser.parse_args()
    started = time.perf_counter()
    summary = json.loads((args.report_dir / "summary.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, condition, evidence):
        if not condition:
            raise AssertionError(f"{name}: {evidence}")
        checks.append({"check": name, "passed": True, "evidence": evidence})

    zone = ZoneInfo(summary["timezone_assumption"])

    def epoch(text, schedule=False):
        naive = datetime.strptime(text, "%d.%m.%Y %H:%M:%S") if schedule else datetime.fromisoformat(text)
        aware = naive.replace(tzinfo=zone)
        # Round-trip catches nonexistent local timestamps rather than shifting them.
        back = aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if back != naive:
            raise AssertionError(f"Nonexistent source timestamp: {text}")
        return int(aware.astimezone(timezone.utc).timestamp())

    windows = {
        "train": (epoch("2020-03-09 00:00:00"), epoch("2020-05-18 00:00:00")),
        "validation": (epoch("2020-05-18 00:00:00"), epoch("2020-07-27 00:00:00")),
    }
    for filename, expected in summary["source_files_sha256"].items():
        digest = hashlib.sha256()
        with (args.data_dir / filename).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        check("Input unchanged: " + filename, digest.hexdigest() == expected, digest.hexdigest())

    print("Checking full event and programme artifacts ...", flush=True)
    events = pd.read_parquet(args.artifact_dir / "airing_interactions.parquet")
    programmes = pd.read_parquet(args.artifact_dir / "user_programme_interactions.parquet")
    airings = pd.read_parquet(args.artifact_dir / "airings.parquet")
    users = pd.read_csv(args.report_dir / "validation_users.csv", dtype={"user_id": str})
    truth = pd.read_csv(args.report_dir / "validation_ground_truth.csv", dtype=str)
    long_top = pd.read_csv(args.report_dir / "validation_top5.csv", dtype={"user_id": str})
    check("All event user IDs stored as decimal strings", events.user_id.map(lambda x: isinstance(x, str) and x.isdecimal()).all(), len(events))
    check("No repeated split/user/airing keys", not events.duplicated(["split", "user_id", "airing_id"]).any(), len(events))
    check("No zero item IDs", bool((events.tv_show_id != 0).all()), int(events.tv_show_id.min()))
    check("Union watch time lies within full airing duration", bool(((events.watched_seconds > 0) & (events.watched_seconds <= events.duration)).all()),
          {"min": int(events.watched_seconds.min()), "max": int(events.watched_seconds.max()), "max_coverage": float(events.coverage.max())})
    expected_flags = events.watched_seconds.to_numpy() * 5 >= events.duration.to_numpy() * 4
    check("Every watched flag implements exact >=80%", bool(np.array_equal(expected_flags, events.watched_80pct.to_numpy())), int(expected_flags.sum()))
    check("Stored coverage equals watched/full duration", bool(np.allclose(events.coverage, events.watched_seconds / events.duration, rtol=0, atol=1e-15)), "tolerance 1e-15")
    for split, (lo, hi) in windows.items():
        f = events.loc[events.split == split]
        check(split + " observed time stays inside its window", bool(((f.first_overlap >= lo) & (f.last_overlap <= hi)).all()),
              {"min_observation": int(f.first_overlap.min()), "max_observation": int(f.last_overlap.max()), "bounds": [lo, hi]})
    observed = events[["airing_id", "channel_id", "tv_show_id", "start", "end", "duration"]].drop_duplicates()
    aligned = observed.merge(airings[["airing_id", "channel_id", "tv_show_id", "start", "end", "duration"]], on="airing_id", suffixes=("_event", "_schedule"), validate="one_to_one")
    check("Event schedule identity matches airing table", len(aligned) == len(observed) and all(
        aligned[c + "_event"].equals(aligned[c + "_schedule"]) for c in ["channel_id", "tv_show_id", "start", "end", "duration"]), len(aligned))
    aggregate_total = int(programmes.watched_airings.sum())
    check("Programme frequencies sum to qualified airings", aggregate_total == int(expected_flags.sum()), aggregate_total)

    # Reconstruct all users' frequency Top-5 in Python, independently of pandas ranking.
    counts = defaultdict(dict)
    for row in programmes.loc[(programmes.split == "validation") & (programmes.watched_airings > 0)].itertuples(index=False):
        counts[row.user_id][int(row.tv_show_id)] = int(row.watched_airings)
    expected_top = {user: [item for item, count in sorted(values.items(), key=lambda x: (-x[1], x[0]))[:5]]
                    for user, values in counts.items()}
    actual_truth = {r.user_id: list(map(int, r.tv_show_id.split())) for r in truth.itertuples(index=False)}
    expected_primary = {u: ids for u, ids in expected_top.items() if len(counts[u]) >= 5}
    check("Full primary ground truth equals independently ranked counts", actual_truth == expected_primary,
          {"users": len(actual_truth), "ids": sum(map(len, actual_truth.values()))})
    actual_long = defaultdict(list)
    for row in long_top.sort_values(["user_id", "rank"]).itertuples(index=False):
        actual_long[row.user_id].append(int(row.tv_show_id))
    check("Long Top-5 includes every user's positive truth without padding", dict(actual_long) == expected_top, len(actual_long))
    cohort_counts = Counter(min(len(counts.get(user, {})), 5) for user in users.user_id)
    check("All raw users accounted for in validation cohort", sum(cohort_counts.values()) == len(users), dict(cohort_counts))

    # Include ordinary users, the worked example, a split-boundary user and cold users.
    selected = set(random.Random(20261023).sample(sorted(users.user_id.tolist()), 8))
    selected.add(summary["manual_example"]["user_id"])
    if summary["boundary_verification_user_id"]:
        selected.add(summary["boundary_verification_user_id"])
    if summary["views"].get("clock_change_sample_user_ids"):
        selected.add(summary["views"]["clock_change_sample_user_ids"][0])
    cold = users.loc[users.primary_validation_eligible & users.training_cold_start, "user_id"]
    if len(cold):
        selected.add(cold.iloc[0])
    no_positives = users.loc[users.validation_qualified_programmes == 0, "user_id"]
    if len(no_positives):
        selected.add(no_positives.iloc[0])
    print(f"Independently rejoining all raw records for {len(selected)} users ...", flush=True)
    raw_views = defaultdict(list)
    with (args.data_dir / "dataset11-30.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["user_id"] in selected:
                raw_views[row["user_id"]].append((int(row["vsetv_id"]), epoch(row["start_time"]), epoch(row["stop_time"])))
    needed_channels = {r[0] for values in raw_views.values() for r in values}
    raw_airings = defaultdict(list)
    for filename in ["export_arh_11-20-final.csv", "export_arh_21-30-final.csv"]:
        with (args.data_dir / filename).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                channel, item, duration = int(row["channel_id"]), int(row["tv_show_id"]), int(row["duration"])
                if channel in needed_channels and item != 0 and duration > 0:
                    start = epoch(row["start_time"], schedule=True)
                    raw_airings[channel].append((start, start + duration, item, duration))
    # De-duplication mirrors the documented identity, not the builder's code.
    for channel in raw_airings:
        raw_airings[channel] = sorted(set(raw_airings[channel]))
    metadata_key = {int(r.airing_id): (int(r.channel_id), int(r.start), int(r.end), int(r.tv_show_id), int(r.duration))
                    for r in airings.itertuples(index=False)}
    sampled_results = []
    for user in sorted(selected):
        fragments = defaultdict(list)
        for channel, view_start, view_end in raw_views[user]:
            for split, (lo, hi) in windows.items():
                a, b = max(view_start, lo), min(view_end, hi)
                if a >= b:
                    continue
                for show_start, show_end, item, duration in raw_airings.get(channel, []):
                    if show_start >= b:
                        break
                    if show_end <= a:
                        continue
                    fragments[(split, channel, show_start, show_end, item, duration)].append((max(a, show_start), min(b, show_end)))
        expected_events = {}
        for key, pieces in fragments.items():
            union = []
            for a, b in sorted(pieces):
                if union and a <= union[-1][1]:
                    union[-1] = (union[-1][0], max(union[-1][1], b))
                else:
                    union.append((a, b))
            seconds = sum(b - a for a, b in union)
            expected_events[key] = (seconds, seconds * 5 >= key[-1] * 4)
        actual_events = {}
        for row in events.loc[events.user_id == user].itertuples(index=False):
            actual_events[(row.split,) + metadata_key[int(row.airing_id)]] = (int(row.watched_seconds), bool(row.watched_80pct))
        if expected_events != actual_events:
            missing = sorted(set(expected_events) - set(actual_events))[:3]
            extra = sorted(set(actual_events) - set(expected_events))[:3]
            wrong = [(key, expected_events[key], actual_events[key]) for key in expected_events.keys() & actual_events.keys()
                     if expected_events[key] != actual_events[key]][:3]
            raise AssertionError({"user": user, "missing": missing, "extra": extra, "wrong": wrong})
        sampled_results.append({"user_id": user, "raw_view_rows": len(raw_views[user]),
                                "user_airing_pairs": len(expected_events),
                                "qualified_airings": sum(flag for _, flag in expected_events.values()),
                                "exact_match": True})
    check("Independent raw-CSV nested-loop rejoin matches every sampled user's events", all(r["exact_match"] for r in sampled_results),
          {"users": len(sampled_results), "user_airing_pairs": sum(r["user_airing_pairs"] for r in sampled_results)})
    result = {"passed": True, "checks": checks, "sampled_user_results": sampled_results,
              "random_seed": 20261023, "elapsed_seconds": time.perf_counter() - started,
              "method": "Full artifact invariants + Python frequency ranking + raw-CSV nested-loop overlap/union for deterministic sampled users; no builder helpers imported",
              "student_personal_verification": "Not claimed; manual_example is provided for a later student check"}
    (args.report_dir / "verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Passed {len(checks)} verification checks; {len(sampled_results)} users independently rejoined in {result['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    main()
