#!/usr/bin/env python3
"""Independently rejoin raw views/schedules and verify all report example facts."""

import bisect
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from scipy import sparse

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/final_examples"
TZ = ZoneInfo("Europe/Kyiv")


def stamp(text, schedule=False):
    parsed = datetime.strptime(text, "%d.%m.%Y %H:%M:%S") if schedule else datetime.fromisoformat(text)
    return int(parsed.replace(tzinfo=TZ).timestamp())


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    manifest = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in manifest["paths"].items()}
    for name, path in paths.items():
        check(f"source unchanged: {name}", sha256(path) == manifest["sha256"][name])
    summary = json.loads((OUT / "summary.json").read_text())
    check("builder code matches generated evidence", summary["code_sha256"] == sha256(ROOT / "scripts/build_final_examples.py"))
    final = json.loads(paths["final_selection"].read_text())
    check("007 frozen as final, correct submitted bytes and scores", final["status"] == "final_selected_by_user_experiments_closed" and sha256(ROOT / final["csv_path"]) == final["csv_sha256"] and final["public_score"] == .43707 and final["private_score"] == .42472)
    selection = json.loads((OUT / "selection.json").read_text())
    choices = selection["users"]
    users = list(choices.values())
    primary = {r["user_id"] for r in read_csv(paths["primary_cohort"])}
    metadata = [r for r in read_csv(paths["user_metadata"]) if r["user_id"] in primary and int(r["train_watched_airings"]) > 0]
    low = min(metadata, key=lambda r: (int(r["train_watched_airings"]), r["user_id"]))
    high = min(metadata, key=lambda r: (-int(r["train_watched_airings"]), r["user_id"]))
    check("heavy/light chosen by training counts only within the fixed cohort", choices == {"heavy": high["user_id"], "light": low["user_id"]} and len(primary) == 4030 and set(users) <= primary)
    check("selection ties are honestly reported", selection["light_tie_count"] == sum(int(r["train_watched_airings"]) == int(low["train_watched_airings"]) for r in metadata) == 18 and selection["heavy_tie_count"] == sum(int(r["train_watched_airings"]) == int(high["train_watched_airings"]) for r in metadata) == 1)
    # Independent standard-library source rejoin, without interaction_core or
    # the saved watch flags. IDs are exact strings throughout.
    views, raw_rows = defaultdict(list), []
    with paths["dataset11-30.csv"].open(newline="", encoding="utf-8") as stream:
        for record, row in enumerate(csv.DictReader(stream), 2):
            if row["user_id"] not in users:
                continue
            a, b, channel = stamp(row["start_time"]), stamp(row["stop_time"]), int(row["vsetv_id"])
            assert b-a == int(row["duraton"])
            views[(row["user_id"], channel)].append((a, b))
            raw_rows.append({**row, "source_csv_record": record})
    with (OUT / "raw_selected_views.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(raw_rows[0]))
        writer.writeheader()
        writer.writerows(raw_rows)
    windows = {"train": (stamp("2020-03-09 00:00:00"), stamp("2020-05-18 00:00:00")),
               "validation": (stamp("2020-05-18 00:00:00"), stamp("2020-07-27 00:00:00"))}
    unions = {}
    for split, (lower, upper) in windows.items():
        for key, intervals in views.items():
            merged = []
            for a, b in sorted(set((max(a, lower), min(b, upper)) for a, b in intervals if a < upper and b > lower)):
                if merged and a <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
                else:
                    merged.append((a, b))
            unions[(split, *key)] = (merged, [b for a, b in merged])
    channels = {channel for user, channel in views}
    recs = read_csv(OUT / "recommendations.csv")
    actual = read_csv(OUT / "validation_watches.csv")
    target_ids = {int(r["tv_show_id"]) for r in recs+actual}
    referenced = {(r["latest_schedule_source_file"], int(r["latest_schedule_source_record"])) for r in actual}
    schedule, reference_rows, old_labels = {}, {}, set()
    for filename in ["export_arh_11-20-final.csv", "export_arh_21-30-final.csv"]:
        with paths[filename].open(newline="", encoding="utf-8") as stream:
            for record, row in enumerate(csv.DictReader(stream), 2):
                item, duration, channel = int(row["tv_show_id"]), int(row["duration"]), int(row["channel_id"])
                if not item or duration <= 0 or (channel not in channels and item not in target_ids):
                    continue
                a = stamp(row["start_time"], schedule=True)
                b = a+duration  # elapsed seconds, including the March DST change
                identity = (channel, item, a, b)
                if item in target_ids and a < windows["train"][1] and b > windows["train"][0]:
                    old_labels.add((item, row["tv_show_title"], row["tv_show_category"]))
                if (filename, record) in referenced:
                    reference_rows[(filename, record)] = (identity, row["tv_show_title"], row["tv_show_category"])
                if channel in channels:
                    schedule.setdefault(identity, (duration, filename, record))
    joined, counts, observed = [], defaultdict(int), {}
    weighted50 = defaultdict(float)
    scale = json.loads(paths["recency_metadata"].read_text())["global_mass_preserving_scale"]
    for (channel, item, a, b), (duration, filename, record) in schedule.items():
        for split in windows:
            for user in users:
                intervals, ends = unions.get((split, user, channel), ([], []))
                start_index = bisect.bisect_right(ends, a)
                seconds, last = 0, None
                for x, y in intervals[start_index:]:
                    if x >= b:
                        break
                    s, e = max(a, x), min(b, y)
                    if e > s:
                        seconds += e-s
                        last = max(last or e, e)
                if not seconds:
                    continue
                key = (split, user, channel, item, a, b)
                observed[key] = seconds
                for threshold in [50, 80]:
                    if 100*seconds >= threshold*duration:
                        counts[(split, user, item, threshold)] += 1
                if split == "train" and 2*seconds >= duration:
                    weighted50[(user, item)] += .5**((windows["train"][1]-last)/(8*604800))*scale
                joined.append({"split": split, "user_id": user, "channel_id": channel, "tv_show_id": item,
                               "start": a, "end": b, "duration": duration, "watched_seconds": seconds,
                               "watched_80pct": 5*seconds >= 4*duration, "source_file": filename, "source_csv_record": record})
    with (OUT / "independent_raw_airing_matches.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(joined[0]))
        writer.writeheader()
        writer.writerows(joined)
    check("raw log durations agree with declared elapsed-time timezone", bool(raw_rows))
    saved_overlaps = read_csv(OUT / "validation_all_overlaps_airings.csv")
    saved_seconds = {("validation", r["user_id"], int(r["channel_id"]), int(r["tv_show_id"]), int(r["start"]), int(r["end"])): int(r["watched_seconds"]) for r in saved_overlaps}
    check("every validation airing union independently reconstructed from raw CSVs", saved_seconds == {key: seconds for key, seconds in observed.items() if key[0] == "validation"})
    truth = rankings(paths["truth"])
    selected_stats = {r["role"]: r for r in read_csv(OUT / "selected_users.csv")}
    for role, user in choices.items():
        independent = {item: n for (split, u, item, threshold), n in counts.items() if split == "validation" and u == user and threshold == 80}
        order = sorted(independent, key=lambda item: (-independent[item], item))
        check(f"{role}: exact raw-source frequency Top-5 equals fixed truth", order[:5] == truth[user])
        rows = [r for r in actual if r["user_id"] == user]
        check(f"{role}: complete actual-watch table and all frequencies", [int(r["tv_show_id"]) for r in rows] == order and all(int(r["qualified_validation_airings"]) == independent[int(r["tv_show_id"])] for r in rows))
        stats = selected_stats[role]
        check(f"{role}: heavy/light training and validation totals independently reconstructed", int(stats["train_airings_80pct"]) == sum(n for (split, u, item, t), n in counts.items() if split == "train" and u == user and t == 80) and int(stats["train_programmes_80pct"]) == sum(1 for split, u, item, t in counts if split == "train" and u == user and t == 80) and int(stats["train_airings_50pct"]) == sum(n for (split, u, item, t), n in counts.items() if split == "train" and u == user and t == 50) and int(stats["validation_airings_80pct"]) == sum(independent.values()))
        tied = len(order) > 5 and independent[order[4]] == independent[order[5]]
        check(f"{role}: fifth-place tie disclosed correctly", (stats["validation_fifth_sixth_count_tie"] == "True") == tied)
    for row in actual:
        identity, title, category = reference_rows[(row["latest_schedule_source_file"], int(row["latest_schedule_source_record"]))]
        channel, item, a, b = identity
        user = row["user_id"]
        assert item == int(row["tv_show_id"]) and title == row["latest_watched_title"] and category == row["latest_watched_category"]
        assert 5*observed[("validation", user, channel, item, a, b)] >= 4*(b-a)
    check("all actual episode titles/categories trace to genuinely qualified raw schedule rows", True)
    check("every prediction title/category exists in pre-cutoff schedule evidence", all((int(r["tv_show_id"]), r["title"], r["category"]) in old_labels for r in recs))
    profiles = read_csv(OUT / "training_profiles.csv")
    for row in profiles:
        user, item = row["user_id"], int(row["tv_show_id"])
        assert int(row["train_airings_80pct"]) == counts[("train", user, item, 80)]
        assert int(row["train_airings_50pct"]) == counts[("train", user, item, 50)]
        assert math.isclose(float(row["train_weighted_airings_h8"]), weighted50[(user, item)], rel_tol=1e-12, abs_tol=1e-12)
    check("all strict/soft training profiles and h8 counts independently reconstructed", True)
    sources = {"cbf": rankings(paths["cbf_predictions"]), "hybrid_007": rankings(paths["hybrid_predictions"])}
    for method, component in [("mf", "implicit_mf"), ("ppr", "ppr"), ("association_rules", "association_rules"), ("popularity", "popularity")]:
        sources[method] = {u: ids[:5] for u, ids in rankings(paths[f"component_{component}"]).items()}
    check("exactly sixty recommendations: two users, six methods, five each", len(recs) == 60 and {(r["user_id"], r["method"]) for r in recs} == {(u, m) for u in users for m in sources})
    results = {}
    for user in users:
        for method, predictions in sources.items():
            rows = [r for r in recs if r["user_id"] == user and r["method"] == method]
            ids = [int(r["tv_show_id"]) for r in rows]
            check(f"source ranks reproduced: {user}/{method}", ids == predictions[user] and len(set(ids)) == 5)
            ap, hit_count, _ = exact_ap(set(truth[user]), ids)
            results[(user, method)] = (ap, hit_count)
            for row in rows:
                item = int(row["tv_show_id"])
                qualified_count = counts[("validation", user, item, 80)]
                overlap = sum(seconds for (split, u, channel, i, a, b), seconds in observed.items() if split == "validation" and u == user and i == item)
                hit = item in truth[user]
                marker = "✓" if hit else "○" if qualified_count else "~" if overlap else "—"
                assert (row["hit_true_top5"] == "True") == hit and row["hit_marker"] == marker and int(row["qualified_validation_airings"]) == qualified_count and int(row["validation_observed_seconds"]) == overlap and close(row["user_AP_at_5"], ap)
    check("every hit/partial/watch status and per-user AP matches raw evidence", True)
    for row in read_csv(OUT / "method_metrics.csv"):
        ap, hits = results[(row["user_id"], row["method"])]
        assert close(row["AP_at_5"], ap) and int(row["hits_at_5"]) == hits
    check("all displayed AP and hit totals exact", True)
    actual_by_rank = {(r["user_id"], int(r["actual_rank"])): r for r in actual}
    side = read_csv(OUT / "side_by_side.csv")
    for row in side:
        target = actual_by_rank[(row["user_id"], int(row["actual_top5_rank"]))]
        assert row["actual_tv_show_id"] == target["tv_show_id"] and row["actual_latest_watched_title"] == target["latest_watched_title"] and row["actual_latest_watched_category"] == target["latest_watched_category"] and int(row["actual_qualified_airings"]) == int(target["qualified_validation_airings"])
    check("all side-by-side actual rows carry correct IDs/titles/categories/counts", len(side) == 60)
    vectors, query = sparse.load_npz(paths["cbf_vectors"]), sparse.load_npz(paths["cbf_profiles"])
    cbf_ids = np.load(paths["cbf_items"], allow_pickle=False).astype(int).tolist()
    cbf_users = np.load(paths["cbf_users"], allow_pickle=False).tolist()
    feature_parts = read_csv(OUT / "cbf_feature_contributions.csv")
    for user in users:
        expected_profile = np.zeros(vectors.shape[1])
        for n, item in enumerate(cbf_ids):
            count = counts[("train", user, item, 80)]
            if count:
                expected_profile += count*vectors.getrow(n).toarray().ravel()
        expected_profile /= np.linalg.norm(expected_profile)
        check(f"{user}: CBF profile rebuilt from independent pre-cutoff strict counts", np.allclose(expected_profile, query.getrow(cbf_users.index(user)).toarray().ravel(), atol=1e-12))
        for row in [r for r in recs if r["user_id"] == user and r["method"] == "cbf"]:
            item = int(row["tv_show_id"])
            expected_score = float(expected_profile @ vectors.getrow(cbf_ids.index(item)).toarray().ravel())
            pieces = sum(float(p["score_contribution"]) for p in feature_parts if p["user_id"] == user and int(p["tv_show_id"]) == item)
            assert close(row["model_score"], expected_score) and close(pieces, expected_score)
    check("all CBF explanatory feature contributions sum to actual cosine", True)
    rule_parts = read_csv(OUT / "association_rule_contributions.csv")
    for row in [r for r in recs if r["method"] == "association_rules"]:
        expected_score = 0.
        for part in rule_parts:
            if part["user_id"] == row["user_id"] and part["consequent_id"] == row["tv_show_id"]:
                n = counts[("train", row["user_id"], int(part["antecedent_id"]), 80)]
                assert n == int(part["train_antecedent_count"]) and n > 0
                expected_score += math.log1p(n)*float(part["confidence"])
        assert math.isclose(float(row["model_score"]), expected_score, rel_tol=1e-12, abs_tol=1e-12)
    check("every rule score explained by genuine independently qualified antecedents", True)
    hybrid = json.loads(paths["hybrid_config"].read_text())
    check("final hybrid validation configuration matches the designated 007 recipe", hybrid == json.loads(ROOT.joinpath(final["configuration"]).read_text()))
    pop_order = [int(r["tv_show_id"]) for r in read_csv(paths["pop_order"])]
    pop_rank = {i: n for n, i in enumerate(pop_order)}
    for user in users:
        terms = defaultdict(Fraction)
        for method, weight in hybrid["weights"].items():
            key = "mf" if method == "implicit_mf" else method
            for rank, item in enumerate(sources[key][user], 1):
                terms[item] += Fraction(str(weight))/rank
        predicted = sorted(terms, key=lambda item: (-terms[item], pop_rank[item], item))[:5]
        assert predicted == sources["hybrid_007"][user]
    check("both 007 lists independently reconstructed with exact rational rank fusion", True)
    verified = {"status": "passed", "checks": checks, "raw_view_rows_for_selected_users": len(raw_rows), "independent_positive_airing_overlaps": len(joined),
                "verifier_sha256": sha256(Path(__file__)), "meaning": "Assistant-executed source/numerical verification only; student personal review is not claimed"}
    (OUT / "verification.json").write_text(json.dumps(verified, indent=2)+"\n", encoding="utf-8")
    print(f"Passed {len(checks)} checks, including raw-CSV interval rejoin for both users and all sixty recommendations.")
    print(f"Independent evidence: {len(raw_rows)} raw view rows and {len(joined)} positive user-airing overlaps.")


if __name__ == "__main__":
    main()
