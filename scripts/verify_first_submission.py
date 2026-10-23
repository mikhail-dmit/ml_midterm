#!/usr/bin/env python3
"""Check exact template format, full-history training evidence and final fusion."""

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import sparse

from verify_hybrid_experiments import close, rankings, read_csv, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/final_11_30"
ART = ROOT / "artifacts/final_11_30"


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    manifest = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in manifest["paths"].items()}
    for name, path in paths.items():
        check(f"original input unchanged: {name}", sha256(path) == manifest["sha256"][name])
    summary = json.loads((OUT / "summary.json").read_text())
    selection = json.loads(paths["selected_strategy"].read_text())
    check("strategy/weights frozen before all-history refit", summary["selected_config"] == selection["selected_config"] and json.loads((OUT / "selected_strategy.json").read_text()) == selection)
    check("training/inference code fingerprints", all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    submission = ROOT / summary["submission_path"]
    template = read_csv(paths["template"])
    users = [r["user_id"] for r in template]
    with submission.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.reader(stream))
    check("exact template header and exactly two columns, no index", raw[0] == ["user_id", "tv_show_id"] and all(len(r) == 2 for r in raw[1:]))
    check("1260 users in exact original template order", len(raw)-1 == len(users) == len(set(users)) == 1260 and [r[0] for r in raw[1:]] == users)
    check("user IDs remain exact decimal strings, including uint64-sized IDs", all(u.isdecimal() and str(int(u)) == u for u in users))
    predicted = rankings(submission)
    check("exactly five distinct canonical nonzero integer IDs per cell", all(len(r[1].split()) == 5 and len(set(r[1].split())) == 5 and all(i.isdecimal() and int(i) > 0 and str(int(i)) == i for i in r[1].split()) and r[1] == " ".join(r[1].split()) for r in raw[1:]))
    check("submission file SHA-256 matches training manifest", sha256(submission) == summary["submission_sha256"])
    tz = ZoneInfo("Europe/Kyiv")
    start = datetime(2020, 3, 9, tzinfo=tz)
    cutoff = datetime(2020, 7, 27, tzinfo=tz)
    end = datetime(2020, 10, 19, tzinfo=tz)
    # Independent stdlib schedule pass; ignore all descriptive metadata.
    eligible, all_schedule_ids = set(), set()
    with paths["schedule_31_42"].open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            item, duration = int(row["tv_show_id"]), int(row["duration"])
            if item == 0:
                continue
            all_schedule_ids.add(item)
            airing_start = datetime.strptime(row["start_time"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=tz)
            if duration > 0 and airing_start < end and airing_start+timedelta(seconds=duration) > cutoff:
                eligible.add(item)
    stored_candidates = {int(r["tv_show_id"]) for r in read_csv(OUT / "test_candidates.csv")}
    check("test availability independently reconstructed from channel/time schedule", eligible == stored_candidates and len(eligible) == summary["test_candidates"])
    check("all submitted IDs air within weeks 31-42", all(set(ids) <= eligible for ids in predicted.values()))
    events = pd.read_parquet(ART / "training_events.parquet")
    check("refit includes full weeks 11-30 and no post-cutoff observations", events.split.eq("refit_11_30").all() and (events.first_overlap >= int(start.timestamp())).all() and (events.last_overlap <= int(cutoff.timestamp())).all() and not events.duplicated(["user_id", "airing_id"]).any())
    check("whole-airing coverage denominator and positive interval union", ((events.watched_seconds > 0) & (events.watched_seconds <= events.duration)).all())
    # The previous folds partition time. Summing their raw overlap seconds by
    # airing is an independent reconciliation, unlike concatenating watch flags.
    old = pd.read_parquet(ROOT / "artifacts/interactions/airing_interactions.parquet", columns=["user_id", "airing_id", "watched_seconds", "duration", "first_overlap", "last_overlap"])
    recovered = old.groupby(["user_id", "airing_id"], sort=True).agg(watched_seconds=("watched_seconds", "sum"), duration=("duration", "first"), first_overlap=("first_overlap", "min"), last_overlap=("last_overlap", "max"))
    fresh = events.set_index(["user_id", "airing_id"])[["watched_seconds", "duration", "first_overlap", "last_overlap"]].sort_index()
    check("fresh raw full-window join reconciles with independently combined fragment seconds", fresh.equals(recovered))
    reconciliation = []
    training = {}
    for percent in [50, 80]:
        wanted = events.loc[events.watched_seconds*100 >= events.duration*percent]
        expected = wanted.groupby(["user_id", "tv_show_id"]).size().to_dict()
        counts = pd.read_parquet(ART / f"training_counts_{percent}.parquet")
        actual = {(u, int(i)): int(n) for u, i, n in counts.itertuples(index=False, name=None)}
        check(f"all {percent}% training counts reconstructed from whole-window union", actual == expected and len(actual) == len(counts))
        training[percent] = counts
        split_qualified = int((old.watched_seconds*100 >= old.duration*percent).sum())
        reconciliation.append({"threshold_percent": percent, "separate_fold_qualified_events": split_qualified,
                               "whole_20week_qualified_events": len(wanted), "difference_due_to_internal_boundary": len(wanted)-split_qualified})
    pd.DataFrame(reconciliation).to_csv(OUT / "internal_boundary_reconciliation.csv", index=False)
    all_users50 = json.loads((ART / "indices_50.json").read_text())["users"]
    items50 = json.loads((ART / "indices_50.json").read_text())["items"]
    all_users80 = json.loads((ART / "indices_80.json").read_text())["users"]
    items80 = json.loads((ART / "indices_80.json").read_text())["items"]
    def matrix(counts, all_users, items):
        ui, ii = {u: n for n, u in enumerate(all_users)}, {i: n for n, i in enumerate(items)}
        return sparse.csr_matrix((counts.watched_airings.to_numpy(dtype=float), (counts.user_id.map(ui), counts.tv_show_id.map(ii))), shape=(len(all_users), len(items)))
    c50 = matrix(training[50], all_users50, items50)
    c80 = matrix(training[80], all_users80, items80)
    total_pop = training[50].groupby("tv_show_id").watched_airings.sum().to_dict()
    pop_rows = read_csv(ART / "candidate_scores.csv")
    pop = [int(r["tv_show_id"]) for r in pop_rows]
    check("final popularity uses all training users, current test availability", pop == sorted(eligible, key=lambda i: (-total_pop.get(i, 0), i)) and all(int(r["training_watched_airings"]) == total_pop.get(int(r["tv_show_id"]), 0) for r in pop_rows))
    cold = {u for u in users if u not in set(all_users50)}
    check("four actual cold template users retained", len(cold) == summary["test_cold_users_50pct"] == 4 and cold == set(json.loads((ART / "cold_users.json").read_text())))
    check("same exact template order in component score arrays", json.loads((ART / "users.json").read_text()) == users)
    scored = np.load(ART / "scores.npz", allow_pickle=False)
    values = {m: scored[f"scores_{m}"] for m in ["implicit_mf", "ppr", "association_rules"]}
    item_ids = {m: scored[f"items_{m}"].astype(int).tolist() for m in values}
    check("score item indices match complete fitted catalogue", item_ids["implicit_mf"] == item_ids["ppr"] == items50 and item_ids["association_rules"] == items80)
    factors = np.load(ART / "factors.npz", allow_pickle=False)
    ui50, ui80 = {u: n for n, u in enumerate(all_users50)}, {u: n for n, u in enumerate(all_users80)}
    rows = [n for n, u in enumerate(users) if u in ui50]
    expected_mf = np.maximum(factors["user_factors"][[ui50[users[n]] for n in rows]] @ factors["item_factors"].T, 0)
    check("MF scores independently reconstructed from refitted factors", np.allclose(values["implicit_mf"][rows], expected_mf, atol=1e-12) and all(not values["implicit_mf"][n].any() for n, u in enumerate(users) if u in cold))
    curve = pd.read_csv(ART / "learning_curve.csv")
    check("fixed fifteen MF epochs, no validation early stopping", curve.epoch.tolist() == list(range(16)) and (np.diff(curve.training_objective) <= 1e-7).all() and close(curve.training_objective.iloc[-1], summary["final_MF_objective"]))
    transition = sparse.load_npz(ART / "transition.npz")
    binary = c50.copy()
    binary.data[:] = 1
    joint = (binary.T @ binary).tocsr()
    joint.setdiag(0)
    joint.eliminate_zeros()
    degrees = np.asarray(joint.sum(axis=1)).ravel()
    expected_transition = sparse.diags(1/degrees) @ joint
    error = (expected_transition-transition).tocsr()
    check("raw programme co-view graph rebuilt from full-history users", not error.nnz or np.max(np.abs(error.data)) < 1e-12)
    restart = c50[[ui50[users[n]] for n in rows]].copy()
    restart.data = np.log1p(restart.data)
    restart = restart.toarray()
    restart /= restart.sum(axis=1, keepdims=True)
    mass = values["ppr"][rows]
    dangling = np.asarray(transition.sum(axis=1)).ravel() == 0
    rhs = .5*(transition.T @ mass.T).T + (.5+.5*mass[:, dangling].sum(axis=1))[:, None]*restart
    check("PPR full-catalogue probability mass and independent fixed point", np.allclose(mass.sum(axis=1), 1, atol=1e-12) and np.max(np.abs(mass-rhs).sum(axis=1)) < 1e-9 and np.min(mass) >= 0)
    weights = sparse.load_npz(ART / "rule_weights.npz")
    hist = c80.copy()
    hist.data = np.log1p(hist.data)
    query_rows = [n for n, u in enumerate(users) if u in ui80]
    check("rule query scores independently reconstructed", np.allclose(values["association_rules"][query_rows], (hist[[ui80[users[n]] for n in query_rows]] @ weights).toarray(), atol=1e-12))
    baskets = sparse.load_npz(ART / "baskets.npz")
    totals = np.asarray(baskets.sum(axis=0)).ravel()
    pair_counts = (baskets.T @ baskets).tocoo()
    keep = (pair_counts.row != pair_counts.col) & (pair_counts.data >= 5) & (10*pair_counts.data >= totals[pair_counts.row]) & (pair_counts.data*baskets.shape[0] > totals[pair_counts.row]*totals[pair_counts.col])
    expected_rules = sparse.csr_matrix((pair_counts.data[keep]/totals[pair_counts.row[keep]], (pair_counts.row[keep], pair_counts.col[keep])), shape=weights.shape)
    rule_error = (expected_rules-weights).tocsr()
    check("all weekly rules satisfy exact support/confidence/lift criteria", expected_rules.nnz == weights.nnz == summary["rules"] and (not rule_error.nnz or np.max(np.abs(rule_error.data)) < 1e-12))
    components = {}
    for method in values:
        output = rankings(OUT / f"component_{method}.csv")
        for row, user in enumerate(users):
            positive = [(i, float(values[method][row, n])) for n, i in enumerate(item_ids[method]) if i in eligible and values[method][row, n] > 0]
            positive.sort(key=lambda pair: (-pair[1], pair[0]))
            prefix = [i for i, score in positive]
            used = set(prefix)
            ordered = prefix+[i for i in pop if i not in used]
            assert output[user] == (pop[:5] if user in cold else ordered[:5])
        components[method] = output
        check(f"all component Top-5 independently reconstructed: {method}", True)
    config = summary["selected_config"]
    check("first submission uses the observed validation winner RRF", config["type"] == "rrf" and config["id"] == selection["selected_id"])
    pop_rank = {i: n for n, i in enumerate(pop)}
    for user in users:
        utility = defaultdict(Fraction)
        for method, weight in config["weights"].items():
            for rank, item in enumerate(components[method][user], 1):
                utility[item] += Fraction(str(weight))/(config["offset"]+rank)
        expected = sorted(utility, key=lambda i: (-utility[i], pop_rank[i], i))[:5]
        assert predicted[user] == expected
    check("all 1260 final lists independently reconstructed using exact rational fusion", True)
    check("actual cold users use the common popularity fallback", all(predicted[u] == pop[:5] for u in cold))
    report = {"status": "passed", "submission_path": str(submission.relative_to(ROOT)), "submission_sha256": sha256(submission),
              "rows": len(users), "columns": raw[0], "candidate_ids": len(eligible), "all_nonzero_schedule_ids": len(all_schedule_ids),
              "outside_prediction_window_ids": sorted(all_schedule_ids-eligible), "cold_users": len(cold), "checks": checks,
              "verifier_sha256": sha256(Path(__file__)), "kaggle_score": None,
              "meaning": "Assistant verification only; actual Kaggle score awaits user upload"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n")
    print(f"Passed {len(checks)} checks. READY TO UPLOAD: {submission}")
    print(f"SHA-256: {sha256(submission)}")
    print(pd.DataFrame(reconciliation).to_string(index=False))


if __name__ == "__main__":
    main()
