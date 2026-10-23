#!/usr/bin/env python3
"""Verify shared-input ablations without importing the study/model/evaluator code."""

import csv
import hashlib
import itertools
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/training_study"
ART = ROOT / "artifacts/training_study"


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def rational_ap(actual, predicted):
    positions = [r for r, item in enumerate(predicted, 1) if item in actual]
    return sum((Fraction(j, r) for j, r in enumerate(positions, 1)), Fraction(0))/5


def main():
    started = time.perf_counter()
    checks = []
    def check(name, passed, evidence):
        if not passed:
            raise AssertionError(f"{name}: {evidence}")
        checks.append({"check": name, "passed": True, "evidence": evidence})
    frozen = json.loads((OUT / "frozen_inputs.json").read_text())
    for name, filename in frozen["paths"].items():
        actual = digest(ROOT / filename)
        check("Frozen input unchanged: " + name, actual == frozen["sha256"][name], actual)
    truth = {r["user_id"]: set(map(int, r["tv_show_id"].split())) for r in rows(ROOT / "reports/interactions/validation_ground_truth.csv")}
    primary = list(truth)
    template = [r["user_id"] for r in rows(ROOT / "reports/popularity/cohort_template_primary.csv")]
    pool = {int(r["tv_show_id"]) for r in rows(ROOT / "reports/popularity/validation_candidates.csv")}
    cohorts = {"all_primary": primary, "template_primary": template}
    plan = json.loads((OUT / "plan.json").read_text())
    zone = ZoneInfo("Europe/Kyiv")
    bounds = {w["id"]: (int(datetime.fromisoformat(w["start_local"]).replace(tzinfo=zone).timestamp()),
                        int(datetime.fromisoformat(w["end_local"]).replace(tzinfo=zone).timestamp())) for w in plan["windows"]}
    events_by_window = {w: pd.read_parquet(ART / "windows" / w / "events.parquet") for w in bounds}
    reference = events_by_window["full10"]
    strict = reference.loc[reference.watched_seconds*5 >= reference.duration*4]
    seen = defaultdict(set)
    observed_true = set()
    truth_pairs = {(u, item) for u, ids in truth.items() for item in ids}
    for event in reference.itertuples(index=False):
        if (event.user_id, int(event.tv_show_id)) in truth_pairs:
            observed_true.add((event.user_id, int(event.tv_show_id)))
    for event in strict.itertuples(index=False):
        seen[event.user_id].add(int(event.tv_show_id))
    global_items = set(int(x) for x in strict.tv_show_id)
    attributes = rows(OUT / "reference_analysis/true_answer_attributes.csv")
    familiar_count = 0
    for row in attributes:
        user, item = row["user_id"], int(row["tv_show_id"])
        familiar = item in seen[user]
        expected_exposure = "familiar_80pct" if familiar else "new_but_partial_training_overlap" if (user, item) in observed_true else "new_no_recorded_training_overlap"
        if row["familiarity"] != ("familiar_80pct" if familiar else "new_qualified_for_user") or row["exposure"] != expected_exposure:
            raise AssertionError("Reference familiarity changed or is misclassified")
        familiar_count += familiar
    check("Reference familiar/new answers rebuilt from strict airing events", len(attributes) == 20150 and familiar_count == 11323,
          {"familiar": familiar_count, "new": len(attributes)-familiar_count})
    selected = json.loads((ROOT / "reports/all_methods/selected_models.json").read_text())
    original_sources = {"popularity": ROOT / "reports/popularity/predictions_allow_repeats.csv"}
    for method, item in selected.items():
        directory = "models" if method in {"implicit_mf", "ppr"} else "content_rules"
        original_sources[method] = ROOT / "reports" / directory / "runs" / item["run_id"] / "predictions.csv"
    originals = {m: {r["user_id"]: list(map(int, r["tv_show_id"].split())) for r in rows(p)} for m, p in original_sources.items()}
    overlap = rows(OUT / "reference_analysis/pairwise_complementarity.csv")
    for record in overlap:
        cohort = cohorts[record["cohort"]]
        a, b = record["method_a"], record["method_b"]
        ah = {(u, i) for u in cohort for i in originals[a][u] if i in truth[u]}
        bh = {(u, i) for u in cohort for i in originals[b][u] if i in truth[u]}
        au, bu = {u for u, i in ah}, {u for u, i in bh}
        expected = {"both_hit_users": len(au&bu), "a_only_hit_users": len(au-bu), "b_only_hit_users": len(bu-au),
                    "neither_hit_users": len(cohort)-len(au|bu), "both_correct_user_item_pairs": len(ah&bh),
                    "a_only_correct_pairs": len(ah-bh), "b_only_correct_pairs": len(bh-ah), "union_correct_pairs": len(ah|bh)}
        check(f"Reference overlap {record['cohort']}/{a}/{b}", all(int(record[k]) == value for k, value in expected.items()), expected)
    novelty_rows = rows(OUT / "reference_analysis/novelty_metrics.csv")
    for method, predictions in originals.items():
        for cohort_name, users in cohorts.items():
            numerator = {"familiar_80pct": Fraction(0), "new_qualified_for_user": Fraction(0)}
            hit_counts = Counter()
            for user in users:
                j = 0
                for rank, item in enumerate(predictions[user], 1):
                    if item in truth[user]:
                        j += 1
                        label = "familiar_80pct" if item in seen[user] else "new_qualified_for_user"
                        numerator[label] += Fraction(j, rank*5)
                        hit_counts[label] += 1
            for record in [r for r in novelty_rows if r["method"] == method and r["cohort"] == cohort_name and r["axis"] == "familiarity"]:
                label = record["segment"]
                check(f"Reference AP partition {cohort_name}/{method}/{label}", int(record["hits"]) == hit_counts[label]
                      and abs(float(numerator[label]/len(users))-float(record["AP_contribution_full_cohort"])) < 1e-14, hit_counts[label])
    verified = []
    for window in plan["windows"]:
        name = window["id"]
        events = events_by_window[name]
        lo, hi = bounds[name]
        check(name + ": exact clipped positive intervals/full denominators", bool(((events.first_overlap >= lo) & (events.last_overlap <= hi)
              & (events.watched_seconds > 0) & (events.watched_seconds <= events.duration)).all()), len(events))
        for threshold in plan["thresholds_percent"]:
            setting = f"{name}_t{threshold}"
            print(f"Verifying {setting} ...", flush=True)
            # Independent Counter over airing records, not the builder's groupby.
            counts = Counter((r.user_id, int(r.tv_show_id)) for r in events.itertuples(index=False)
                             if r.watched_seconds*100 >= threshold*r.duration)
            saved = pd.read_parquet(ART / setting / "training_counts.parquet")
            actual = {(r.user_id, int(r.tv_show_id)): int(r.watched_airings) for r in saved.itertuples(index=False)}
            check(setting + ": training aggregation/threshold exact", dict(counts) == actual and saved.split.eq("train").all(),
                  {"positive_pairs": len(counts), "positive_airings": sum(counts.values())})
            indices = json.loads((ART / setting / "indices.json").read_text())
            matrix = sparse.load_npz(ART / setting / "counts.npz").tocoo()
            restored = {(indices["users"][r], indices["items"][c]): int(n) for r, c, n in zip(matrix.row, matrix.col, matrix.data)}
            check(setting + ": sparse matrix/ID indices preserve exact counts", restored == actual, list(matrix.shape))
            by_item = Counter()
            active_users = set()
            for (user, item), count in counts.items():
                by_item[item] += count
                active_users.add(user)
            popularity_order = sorted(pool, key=lambda item: (-by_item[item], item))
            candidate_rows = rows(OUT / setting / "candidate_scores.csv")
            check(setting + ": same pool and training-only popularity ranking", {int(r["tv_show_id"]) for r in candidate_rows} == pool
                  and [int(r["tv_show_id"]) for r in candidate_rows] == popularity_order
                  and all(int(r["training_watched_airings"]) == by_item[int(r["tv_show_id"])] for r in candidate_rows), len(candidate_rows))
            for method in originals:
                folder = OUT / setting / "runs" / method
                result = json.loads((folder / "summary.json").read_text())
                raw_predictions = rows(folder / "predictions.csv")
                predictions = {r["user_id"]: list(map(int, r["tv_show_id"].split())) for r in raw_predictions}
                check(setting + "/" + method + ": fixed cohort/candidates/five distinct IDs", len(raw_predictions) == len(predictions) == len(primary)
                      and set(predictions) == set(truth) and all(len(ids) == len(set(ids)) == 5 and set(ids).issubset(pool) for ids in predictions.values()), len(predictions))
                check(setting + "/" + method + ": common setting-specific cold fallback", all(predictions[u] == popularity_order[:5] for u in primary if u not in active_users),
                      sum(u not in active_users for u in primary))
                if method == "popularity":
                    check(setting + ": popularity predictions reconstruct from counts", all(ids == popularity_order[:5] for ids in predictions.values()), popularity_order[:5])
                if setting == "full10_t80":
                    check(method + ": strict/full reproduces original predictions exactly", predictions == originals[method], len(predictions))
                exact = {u: rational_ap(truth[u], predictions[u]) for u in primary}
                user_scores = {r["user_id"]: float(r["ap_at_5"]) for r in rows(folder / "per_user_metrics.csv")}
                max_error = max(abs(float(exact[u])-user_scores[u]) for u in primary)
                check(setting + "/" + method + ": every AP verified exactly", max_error < 1e-15, max_error)
                for metric in result["metrics"]:
                    users = cohorts[metric["cohort"]]
                    mean = sum((exact[u] for u in users), Fraction(0))/len(users)
                    check(setting + "/" + method + "/" + metric["cohort"] + ": fixed-label exact MAP", abs(float(mean)-metric["map_at_5"]) < 1e-15,
                          {"users": len(users), "MAP_fraction": str(mean)})
                if method == "ppr":
                    check(setting + ": PPR mass/fixed-point assertions passed for all warm users", result["diagnostics"]["solver"]["max_L1_fixed_point_residual"] < 1e-9
                          and result["diagnostics"]["solver"]["users_above_1e_9_residual"] == 0, result["diagnostics"]["solver"]["max_L1_fixed_point_residual"])
                verified.append({"setting": setting, "method": method, "verified": True})
    # Independently rejoin raw view fragments for a few users at each window's
    # exact boundaries. Schedule times come from the previously verified airing table.
    print("Checking early/recent clipping against original raw viewing fragments ...", flush=True)
    example_users = json.loads((ROOT / "reports/models/example_users.json").read_text())["users"]
    sample_users = {r["user_id"] for r in example_users}
    sample_users.add("12466582247545246052")  # observed spring-clock-change session
    for name, events in events_by_window.items():
        lo, hi = bounds[name]
        edge = events.loc[(events.first_overlap == lo) | (events.last_overlap == hi), "user_id"]
        if len(edge):
            sample_users.add(str(edge.iloc[0]))
    raw_views = defaultdict(list)
    with (ROOT / "sweettv-tv-program-recommender/dataset11-30.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["user_id"] in sample_users:
                a = int(datetime.fromisoformat(row["start_time"]).replace(tzinfo=zone).timestamp())
                b = int(datetime.fromisoformat(row["stop_time"]).replace(tzinfo=zone).timestamp())
                raw_views[row["user_id"]].append((int(row["vsetv_id"]), a, b))
    airings = pd.read_parquet(ROOT / "artifacts/interactions/airings.parquet")
    by_channel = {int(channel): [(int(r.airing_id), int(r.start), int(r.end)) for r in group.sort_values("start").itertuples(index=False)]
                  for channel, group in airings.groupby("channel_id")}
    for name, (lo, hi) in bounds.items():
        expected = defaultdict(list)
        for user in sample_users:
            for channel, a, b in raw_views[user]:
                a, b = max(a, lo), min(b, hi)
                if a >= b:
                    continue
                for airing, x, y in by_channel.get(channel, []):
                    if x >= b:
                        break
                    if y > a:
                        expected[(user, airing)].append((max(a, x), min(b, y)))
        totals = {}
        for key, pieces in expected.items():
            union = []
            for a, b in sorted(pieces):
                if union and a <= union[-1][1]:
                    union[-1] = (union[-1][0], max(union[-1][1], b))
                else:
                    union.append((a, b))
            totals[key] = (sum(b-a for a, b in union), union[0][0], union[-1][1])
        actual = {(r.user_id, int(r.airing_id)): (int(r.watched_seconds), int(r.first_overlap), int(r.last_overlap))
                  for r in events_by_window[name].loc[events_by_window[name].user_id.isin(sample_users)].itertuples(index=False)}
        check(name + ": clipped union overlaps independently match raw views", totals == actual, {"users": len(sample_users), "user_airing_pairs": len(totals)})
    result = {"passed": True, "checks": checks, "verified_runs": verified,
              "elapsed_seconds": time.perf_counter()-started,
              "scope": "Frozen truth/cohort/candidates/content vectors; reference novelty/AP and pairwise hits; nine threshold/window counts; all 45 model predictions/AP/MAP and cold fallbacks; raw-fragment boundary rejoin",
              "model_numerics": "Existing ALS/CBF/rule/PPR algebra independently verified in previous stage; each new ALS/PPR run also executes its numerical sanity assertions",
              "student_personal_verification": "Not claimed"}
    (OUT / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Passed {len(checks)} checks for {len(verified)} runs in {result['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    main()
