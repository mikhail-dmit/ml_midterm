#!/usr/bin/env python3
"""Independently reconstruct popularity/predictions and exact-rational AP@5.

No evaluator or popularity implementation is imported. Popularity is recounted
from the separate airing-level table (rather than the programme aggregates used
to fit the baseline). AP uses Fraction arithmetic over relevant hit positions.
"""

import argparse
import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interaction-dir", type=Path, default=ROOT / "artifacts" / "interactions")
    parser.add_argument("--label-dir", type=Path, default=ROOT / "reports" / "interactions")
    parser.add_argument("--result-dir", type=Path, default=ROOT / "reports" / "popularity")
    args = parser.parse_args()
    started = time.perf_counter()
    summary = json.loads((args.result_dir / "summary.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, passed, evidence):
        if not passed:
            raise AssertionError(f"{name}: {evidence}")
        checks.append({"check": name, "passed": True, "evidence": evidence})

    def read_csv(name, directory=args.result_dir):
        with (directory / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    for filename, expected in summary["source_files_sha256"].items():
        h = hashlib.sha256()
        with Path(ROOT / filename).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
        check("Input fingerprint unchanged: " + filename, h.hexdigest() == expected, h.hexdigest())
    print("Recounting training popularity from qualifying airing-level events ...", flush=True)
    events = pd.read_parquet(args.interaction_dir / "airing_interactions.parquet",
                             columns=["split", "user_id", "tv_show_id", "watched_80pct", "first_overlap", "last_overlap"])
    qualified = events.loc[(events.split == "train") & events.watched_80pct]
    counts = Counter()
    seen = defaultdict(set)
    item_viewers = defaultdict(set)
    for user, item in qualified[["user_id", "tv_show_id"]].itertuples(index=False, name=None):
        counts[int(item)] += 1
        seen[user].add(int(item))
        item_viewers[int(item)].add(user)
    saved_counts = {int(row["tv_show_id"]): int(row["training_watched_airings"]) for row in read_csv("training_popularity.csv")}
    check("Training popularity agrees across airing and programme tables", saved_counts == dict(counts),
          {"qualified_airings": sum(counts.values()), "users": len(seen), "items": len(counts)})
    zone = ZoneInfo("Europe/Kyiv")
    lower = int(datetime(2020, 5, 18, tzinfo=zone).timestamp())
    upper = int(datetime(2020, 7, 27, tzinfo=zone).timestamp())
    check("All fitted counts precede the validation cutoff", bool((qualified.last_overlap <= lower).all()), int(qualified.last_overlap.max()))
    airings = pd.read_parquet(args.interaction_dir / "airings.parquet", columns=["start", "end", "duration", "tv_show_id"])
    candidates = {int(row.tv_show_id) for row in airings.itertuples(index=False)
                  if row.tv_show_id != 0 and row.duration > 0 and row.start < upper and row.end > lower}
    saved_candidates = read_csv("validation_candidates.csv")
    ranked = sorted(candidates, key=lambda item: (-counts[item], item))
    check("Candidate pool and global ranking reconstructed independently", ranked == [int(row["tv_show_id"]) for row in saved_candidates], len(ranked))
    check("Candidate popularity scores and distinct-viewer counts match training", all(
        int(row["training_watched_airings"]) == counts[int(row["tv_show_id"])] and
        int(row["training_distinct_viewers"]) == len(item_viewers[int(row["tv_show_id"])])
        for row in saved_candidates), len(saved_candidates))
    truth = {row["user_id"]: list(map(int, row["tv_show_id"].split()))
             for row in read_csv("validation_ground_truth.csv", args.label_dir)}
    cohort_rows = read_csv("validation_users.csv", args.label_dir)
    primary = [row["user_id"] for row in cohort_rows if row["primary_validation_eligible"] == "True"]
    template = [row["user_id"] for row in cohort_rows if row["primary_validation_eligible"] == "True" and row["is_test_user"] == "True"]
    check("Requested cohorts are fixed and nested", len(primary) == 4030 and len(template) == 1150
          and set(template).issubset(primary) and set(primary) == set(truth), {"primary": len(primary), "template": len(template)})
    check("All original truth has five IDs inside the shared pool", all(len(ids) == len(set(ids)) == 5 and set(ids).issubset(candidates)
          for ids in truth.values()), len(truth))
    per_user_saved = {(row["policy"], row["user_id"]): row for row in read_csv("per_user_metrics.csv")}
    exact_scores, hit_counts, max_error = {}, {}, 0.0
    for policy in ["allow_repeats", "exclude_repeats"]:
        raw_predictions = read_csv(f"predictions_{policy}.csv")
        predictions = {row["user_id"]: list(map(int, row["tv_show_id"].split())) for row in raw_predictions}
        check(policy + ": all and only primary users predicted exactly once", len(raw_predictions) == len(predictions) == 4030
              and set(predictions) == set(primary), len(raw_predictions))
        exact_scores[policy], hit_counts[policy] = {}, {}
        for user in primary:
            expected = [item for item in ranked if policy == "allow_repeats" or item not in seen[user]][:5]
            actual = predictions[user]
            if actual != expected or len(set(actual)) != 5:
                raise AssertionError({"user": user, "policy": policy, "expected": expected, "actual": actual})
            hits = [rank for rank, item in enumerate(actual, start=1) if item in set(truth[user])]
            # Each first hit contributes j/r, then divide by five original true IDs.
            ap = sum((Fraction(j, rank) for j, rank in enumerate(hits, start=1)), Fraction(0)) / 5
            exact_scores[policy][user] = ap
            hit_counts[policy][user] = len(hits)
            saved = per_user_saved[(policy, user)]
            error = abs(float(ap) - float(saved["ap_at_5"]))
            max_error = max(max_error, error)
            if error > 1e-15 or int(saved["hits_at_5"]) != len(hits):
                raise AssertionError({"user": user, "policy": policy, "exact_ap": str(ap), "saved": saved})
        check(policy + ": every prediction and per-user AP independently reproduced", True, {"users": len(primary), "max_AP_error_so_far": max_error})
    independently_scored = []
    for metric in summary["metrics"]:
        policy, cohort_name = metric["policy"], metric["cohort"]
        selected = primary if cohort_name == "all_primary" else template
        exact_map = sum((exact_scores[policy][u] for u in selected), Fraction(0)) / len(selected)
        total_hits = sum(hit_counts[policy][u] for u in selected)
        hit_users = sum(hit_counts[policy][u] > 0 for u in selected)
        repeat_truth = sum(len(set(truth[u]) & seen[u]) for u in selected)
        no_repeat_empty_users = sum(set(truth[u]).issubset(seen[u]) for u in selected)
        ceiling = Fraction(1) if policy == "allow_repeats" else Fraction(5 * len(selected) - repeat_truth, 5 * len(selected))
        expected_values = {"users": len(selected), "map_at_5": float(exact_map), "total_hits": total_hits,
                           "users_with_hits": hit_users, "precision_at_5": total_hits / (5 * len(selected)),
                           "recall_at_5": total_hits / (5 * len(selected)), "hit_rate_at_5": hit_users / len(selected),
                           "truth_items_previously_watched": repeat_truth, "policy_oracle_map_ceiling": float(ceiling),
                           "users_all_truth_unreachable": 0 if policy == "allow_repeats" else no_repeat_empty_users}
        check(cohort_name + " / " + policy + ": cohort metrics and repeat diagnostics", all(
            abs(metric[key] - value) <= 1e-15 for key, value in expected_values.items()),
              {"exact_MAP_fraction": str(exact_map), **expected_values})
        independently_scored.append({"cohort": cohort_name, "policy": policy, "exact_MAP_fraction": str(exact_map), **expected_values})
    example = summary["example_user"]
    result = {"passed": True, "checks": checks, "metrics": independently_scored,
              "teacher_slide_arithmetic": {"method_X": str((Fraction(1) + Fraction(1) + Fraction(3, 4)) / 3),
                                            "method_Y": str((Fraction(1, 2) + Fraction(1, 2) + Fraction(3, 5)) / 3)},
              "example_user": example, "example_AP_exact": {p: str(exact_scores[p][example]) for p in exact_scores},
              "per_user_AP_max_absolute_error": max_error,
              "elapsed_seconds": time.perf_counter() - started,
              "method": "Independent Counter over training airing events, schedule-derived candidate pool, full prediction reconstruction, Fraction AP over hit positions; no evaluator/popularity helpers imported",
              "student_personal_verification": "Not claimed; exact arithmetic and example contribution CSV are available for a later student check"}
    (args.result_dir / "verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Passed {len(checks)} independent checks in {result['elapsed_seconds']:.2f}s; every per-user AP and all four cohort scores match")
    print(json.dumps(independently_scored, indent=2))


if __name__ == "__main__":
    main()
