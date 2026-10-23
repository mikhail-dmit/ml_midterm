#!/usr/bin/env python3
"""Independently reconstruct fusion, training gates and exact-rational AP/MAP."""

import csv
import hashlib
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/hybrids"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def rankings(path):
    rows = read_csv(path)
    result = {r["user_id"]: [int(i) for i in r["tv_show_id"].split()] for r in rows}
    assert len(rows) == len(result), f"Duplicate users in {path}"
    return result


def exact_ap(actual, predicted):
    hits, credit = 0, Fraction(0)
    item_credit = {}
    for rank, item in enumerate(predicted, 1):
        if item in actual:
            hits += 1
            item_credit[item] = Fraction(hits, rank*5)
            credit += item_credit[item]
    return credit, hits, item_credit


def close(a, b):
    return abs(float(a)-float(b)) < 1e-13


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    manifest = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in manifest["paths"].items()}
    for name, path in paths.items():
        check(f"unchanged source: {name}", sha256(path) == manifest["sha256"][name])
    plan = json.loads(paths["plan"].read_text())
    check("saved plan matches declared source plan", plan == json.loads((OUT / "plan.json").read_text()))
    truth = rankings(paths["truth"])
    primary = [r["user_id"] for r in read_csv(paths["primary_cohort"])]
    template = [r["user_id"] for r in read_csv(paths["template_cohort"])]
    cohorts = {"all_primary": primary, "template_primary": template}
    check("fixed cohorts, exact large IDs and five-ID truth", len(primary) == len(set(primary)) == 4030 and len(template) == len(set(template)) == 1150 and set(template) <= set(primary) == set(truth) and all(len(set(v)) == len(v) == 5 for v in truth.values()))
    pool = {int(r["tv_show_id"]) for r in read_csv(paths["candidates"])}
    pop_rows = sorted(read_csv(paths["training_popularity_50"]), key=lambda r: int(r["rank"]))
    popularity = [int(r["tv_show_id"]) for r in pop_rows]
    pop_rank = {item: i for i, item in enumerate(popularity)}
    check("same 6384 candidates, no zero", len(popularity) == len(pool) == 6384 and set(popularity) == pool and 0 not in pool)
    # Recreate gate counts from airing-level training evidence, not saved routes.
    events = pd.read_parquet(ROOT / "artifacts/interactions/airing_interactions.parquet", columns=["split", "user_id", "tv_show_id", "watched_seconds", "duration"])
    events = events.loc[(events.split == "train") & (2*events.watched_seconds >= events.duration)]
    expected_counts = events.groupby(["user_id", "tv_show_id"]).size().to_dict()
    train = pd.read_parquet(paths["training_counts_50"])
    stored_counts = {(u, int(i)): int(n) for u, i, n in train[["user_id", "tv_show_id", "watched_airings"]].itertuples(index=False, name=None)}
    check("50% gate source independently reconstructed from training-only airing evidence", train.split.eq("train").all() and len(train) == len(expected_counts) and stored_counts == expected_counts)
    sizes, item_counts = defaultdict(int), defaultdict(int)
    for (user, item), count in expected_counts.items():
        sizes[user] += 1
        item_counts[item] += count
    check("complete training popularity independently reconstructed", popularity == sorted(pool, key=lambda item: (-item_counts[item], item)) and all(int(r["training_watched_airings"]) == item_counts[int(r["tv_show_id"])] for r in pop_rows))
    cold = {u for u in primary if sizes[u] == 0}
    check("43 actual 50%-history cold users retained", len(cold) == 43)
    strict = pd.read_parquet(paths["interactions"])
    strict = strict.loc[strict.split == "train"]
    own = {(u, int(i)): (int(n), int(o)) for u, i, n, o in strict[["user_id", "tv_show_id", "watched_airings", "overlap_airings"]].itertuples(index=False, name=None)}
    strict_sizes = strict.loc[strict.watched_airings > 0].groupby("user_id").size().to_dict()
    global_items = set(strict.loc[strict.watched_airings > 0, "tv_show_id"])
    features = {r["user_id"]: r for r in read_csv(paths["reference_features"])}
    def bucket(n):
        return "0 (cold)" if n == 0 else "1-5" if n <= 5 else "6-20" if n <= 20 else "21-50" if n <= 50 else "51+"
    check("strict history segment boundaries unchanged", set(features) == set(primary) and all(features[u]["history_distinct"] == bucket(strict_sizes.get(u, 0)) for u in primary))
    truth_types = {}
    for row in read_csv(paths["reference_truth_types"]):
        user, item = row["user_id"], int(row["tv_show_id"])
        count, overlap = own.get((user, item), (0, 0))
        familiar = "familiar_80pct" if count else "new_qualified_for_user"
        exposure = "familiar_80pct" if count else "new_but_partial_training_overlap" if overlap else "new_no_recorded_training_overlap"
        support = "has_global_strict_training_support" if item in global_items else "no_global_strict_training_support"
        assert (row["familiarity"], row["exposure"], row["global_support"]) == (familiar, exposure, support)
        truth_types[(user, item)] = {"familiarity": familiar, "exposure": exposure, "global_support": support}
    check("all 20150 original truth types independently reconstructed", len(truth_types) == 20150 and set(truth_types) == {(u, i) for u in primary for i in truth[u]})
    components = {m: rankings(paths[f"component_{m}"]) for m in plan["sources"]}
    for method, predicted in components.items():
        summary = json.loads(paths[f"component_summary_{method}"].read_text())
        check(f"component cohort, candidate validity and common fallback: {method}", set(predicted) == set(primary) and all(len(ids) == len(set(ids)) == 5 and set(ids) <= pool for ids in predicted.values()) and all(predicted[u] == popularity[:5] for u in cold))
        check(f"component training/protocol provenance: {method}", all(summary["source_hashes"][key] == sha256(paths[key]) for key in ["truth", "users", "protocol"]) and (method not in {"implicit_mf", "ppr", "popularity"} or summary["source_hashes"]["interactions"] == sha256(paths["training_counts_50"])))
    comparison = {(r["run_id"], r["cohort"]): r for r in read_csv(OUT / "comparison.csv")}
    all_predictions = dict(components)
    ap, hit_counts, credits = {}, {}, {}
    for config in plan["runs"]:
        name = config["id"]
        folder = OUT / "runs" / name
        check(f"declared config preserved: {name}", config == json.loads((folder / "config.json").read_text()))
        predicted = rankings(folder / "predictions.csv")
        check(f"five unique eligible IDs for every fixed user: {name}", set(predicted) == set(primary) and all(len(ids) == len(set(ids)) == 5 and set(ids) <= pool for ids in predicted.values()))
        expected_routes = {}
        for user in primary:
            if config["type"] == "switch":
                route = config["sparse_method"] if sizes[user] <= config["max_sparse_history"] else config["warm_method"]
                expected = components[route][user]
                expected_routes[user] = route
            else:
                scores = defaultdict(Fraction)
                for method, weight in config["weights"].items():
                    for rank, item in enumerate(components[method][user], 1):
                        scores[item] += Fraction(str(weight)) / (config["offset"]+rank)
                expected = sorted(scores, key=lambda item: (-scores[item], pop_rank[item], item))
                expected.extend(item for item in popularity[:5] if item not in scores)
                expected = expected[:5]
                expected_routes[user] = "rrf"
            assert predicted[user] == expected, f"Independent rank reconstruction: {name}/{user}"
        check(f"all ranks reconstructed independently using exact fractions/training gate: {name}", True)
        check(f"actual cold users retain identical fallback: {name}", all(predicted[u] == popularity[:5] for u in cold))
        all_predictions[name] = predicted
        stored = read_csv(folder / "per_user_metrics.csv")
        check(f"saved gate features and route provenance: {name}", len(stored) == len(primary) and all(int(r["training_distinct_50pct"]) == sizes[r["user_id"]] and r["route"] == expected_routes[r["user_id"]] for r in stored))
        summary = json.loads((folder / "summary.json").read_text())
        check(f"code fingerprints and cold diagnostics: {name}", summary["diagnostics"]["cold_fallback_users"] == len(cold) and all(sha256(ROOT / "scripts" / file) == value for file, value in summary["code_hashes"].items()))
    for name, predicted in all_predictions.items():
        result = {u: exact_ap(set(truth[u]), predicted[u]) for u in primary}
        ap[name] = {u: values[0] for u, values in result.items()}
        hit_counts[name] = {u: values[1] for u, values in result.items()}
        credits[name] = {u: values[2] for u, values in result.items()}
        for cohort, users in cohorts.items():
            row = comparison[(name, cohort)]
            expected_map = sum((ap[name][u] for u in users), Fraction(0)) / len(users)
            hits = sum(hit_counts[name][u] for u in users)
            hit_users = sum(hit_counts[name][u] > 0 for u in users)
            check(f"independent exact MAP/hits/recall/precision: {name}/{cohort}", int(row["users"]) == len(users) and close(row["map_at_5"], expected_map) and int(row["total_hits"]) == hits and int(row["users_with_hits"]) == hit_users and close(row["precision_at_5"], Fraction(hits, 5*len(users))) and close(row["recall_at_5"], Fraction(hits, 5*len(users))) and close(row["hit_rate_at_5"], Fraction(hit_users, len(users))))
        if name in components:
            continue
        folder = OUT / "runs" / name
        check(f"every saved per-user AP and hit count: {name}", all(close(r["ap_at_5"], ap[name][r["user_id"]]) and int(r["hits_at_5"]) == hit_counts[name][r["user_id"]] for r in read_csv(folder / "per_user_metrics.csv")))
        history_rows = read_csv(folder / "fixed_history_metrics.csv")
        for row in history_rows:
            ids = [u for u in cohorts[row["cohort"]] if features[u][row["axis"]] == row["segment"]]
            assert len(ids) == int(row["users"]) and close(row["map_at_5"], sum((ap[name][u] for u in ids), Fraction(0))/len(ids))
        check(f"history segments preserve exact AP and membership: {name}", True)
        for row in read_csv(folder / "fixed_novelty_metrics.csv"):
            users = cohorts[row["cohort"]]
            slots = [(u, i) for u in users for i in truth[u] if truth_types[(u, i)][row["axis"]] == row["segment"]]
            hits = sum(i in credits[name][u] for u, i in slots)
            credit = sum((credits[name][u].get(i, Fraction(0)) for u, i in slots), Fraction(0)) / len(users)
            assert len(slots) == int(row["true_slots"]) and int(row["hits"]) == hits and close(row["recall_of_true_type_micro"], Fraction(hits, len(slots))) and close(row["AP_contribution_full_cohort"], credit)
        check(f"familiar/new decomposition preserves original denominators: {name}", True)
        for row in read_csv(folder / "recommendations.csv"):
            user, item, rank = row["user_id"], int(row["tv_show_id"]), int(row["rank"])
            assert predicted[user][rank-1] == item and (row["in_true_top5"] == "True") == (item in truth[user])
            for method in components:
                ids = components[method][user]
                assert int(row[f"{method}_rank"]) == (ids.index(item)+1 if item in ids else 0)
        check(f"recommendation explanation ranks and true-hit annotations: {name}", True)
    selection = json.loads((OUT / "selection.json").read_text())
    hybrid_ids = [r["id"] for r in plan["runs"]]
    best_hybrid = min(hybrid_ids, key=lambda name: (-float(comparison[(name, "all_primary")]["map_at_5"]), name))
    best_overall = min(all_predictions, key=lambda name: (-float(comparison[(name, "all_primary")]["map_at_5"]), name))
    check("selection uses primary cohort only, includes standalone alternatives", selection["best_hybrid"] == best_hybrid and selection["best_overall"] == best_overall)
    for row in read_csv(OUT / "selected_hit_changes.csv"):
        user, ref = row["user_id"], row["reference"]
        added = set(credits[best_hybrid][user])-set(credits[ref][user])
        lost = set(credits[ref][user])-set(credits[best_hybrid][user])
        assert row["added_correct_ids"] == " ".join(map(str, sorted(added))) and row["lost_correct_ids"] == " ".join(map(str, sorted(lost))) and int(row["added_hits"]) == len(added) and int(row["lost_hits"]) == len(lost) and close(row["delta_AP"], ap[best_hybrid][user]-ap[ref][user])
    check("selected hybrid additions, losses and paired AP independently reconstructed", True)
    rng = np.random.default_rng(plan["seed"])
    for row in read_csv(OUT / "selected_paired_comparisons.csv"):
        users, ref = cohorts[row["cohort"]], row["reference"]
        delta = np.array([float(ap[best_hybrid][u])-float(ap[ref][u]) for u in users])
        samples = delta[rng.integers(0, len(users), size=(plan["bootstrap_resamples"], len(users)))].mean(axis=1)
        check(f"conditional paired differences and seeded intervals: {row['cohort']}/{ref}", close(row["mean_MAP_difference"], delta.mean()) and close(row["conditional_95pct_lower"], np.quantile(samples, .025)) and close(row["conditional_95pct_upper"], np.quantile(samples, .975)) and int(row["better_users"]) == int((delta > 1e-14).sum()) and int(row["worse_users"]) == int((delta < -1e-14).sum()))
    report = {"status": "passed", "verified_runs": hybrid_ids, "checks": checks,
              "verifier_sha256": sha256(Path(__file__)), "meaning": "Assistant-executed independent numerical verification; student personal verification is not claimed"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Passed {len(checks)} independent checks for {len(hybrid_ids)} hybrids and all five components.")


if __name__ == "__main__":
    main()
