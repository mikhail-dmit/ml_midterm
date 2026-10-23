#!/usr/bin/env python3
"""Independent recency arithmetic/model checks and exact local fusion/MAP."""

import hashlib
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/refinement"
ART = ROOT / "artifacts/refinement/validation"
METHODS = ["implicit_mf", "ppr", "association_rules", "popularity"]


def exact_depth_fusion(components, user, config, pop_rank):
    terms = defaultdict(Fraction)
    for method, weight in config["weights"].items():
        for rank, item in enumerate(components[method][user][:config["depth"]], 1):
            terms[item] += Fraction(str(weight))/(config["offset"]+rank)
    return sorted(terms, key=lambda item: (-terms[item], pop_rank[item], item))[:5]


def prediction_signature(predicted):
    payload = "\n".join(u+":"+" ".join(map(str, predicted[u])) for u in sorted(predicted))
    return hashlib.sha256(payload.encode()).hexdigest()


def verify_recency(folder, source_paths, phase, check):
    """Also reused for the final refit, with a new cutoff and new past events."""
    info = json.loads((folder / "recency.json").read_text())
    from datetime import datetime
    from zoneinfo import ZoneInfo
    cutoff = int(datetime(2020, 5, 18, tzinfo=ZoneInfo("Europe/Kyiv")).timestamp()) if phase == "validation" else int(datetime(2020, 7, 27, tzinfo=ZoneInfo("Europe/Kyiv")).timestamp())
    half_life = info["half_life_weeks"]
    events = pd.read_parquet(source_paths["events"])
    selected = events.loc[events.watched_seconds*2 >= events.duration].copy()
    check(f"{phase}/h{half_life}: exact cutoff and past-only event selection", info["cutoff_epoch"] == cutoff and len(selected) == info["event_count"] and (selected.last_overlap <= cutoff).all())
    raw = np.power(.5, (cutoff-selected.last_overlap.to_numpy())/(604800*half_life))
    scale = len(selected)/np.sum(raw)
    selected["independent_weight"] = raw*scale
    expected = selected.groupby(["user_id", "tv_show_id"]).independent_weight.sum().sort_index()
    stored = pd.read_parquet(folder / "weighted_counts.parquet")
    actual = stored.set_index(["user_id", "tv_show_id"]).watched_airings.sort_index()
    check(f"{phase}/h{half_life}: weighted counts from independent half-life formula", expected.index.equals(actual.index) and np.allclose(expected, actual, rtol=1e-12, atol=1e-12))
    check(f"{phase}/h{half_life}: positive support and globally preserved mass", (actual > 0).all() and abs(actual.sum()-len(selected)) < 1e-7 and np.isclose(scale, info["global_mass_preserving_scale"], rtol=1e-12))
    original = pd.read_parquet(source_paths["counts50"])
    original_keys = set(original[["user_id", "tv_show_id"]].itertuples(index=False, name=None))
    check(f"{phase}/h{half_life}: exact original user/item pair support", set(actual.index) == original_keys)
    weights = pd.read_parquet(folder / "event_weights.parquet")
    expected_weights = selected.set_index(["user_id", "airing_id"]).independent_weight.sort_index()
    stored_weights = weights.set_index(["user_id", "airing_id"]).recency_weight.sort_index()
    check(f"{phase}/h{half_life}: every saved event weight and membership", expected_weights.index.equals(stored_weights.index) and np.allclose(expected_weights, stored_weights, rtol=1e-12, atol=1e-12))
    indices = json.loads((folder / "training_indices.json").read_text())
    users = json.loads((folder / "users.json").read_text())
    user_index, item_index = {u: n for n, u in enumerate(indices["users"])}, {i: n for n, i in enumerate(indices["items"])}
    matrix = sparse.csr_matrix((stored.watched_airings.to_numpy(), (stored.user_id.map(user_index), stored.tv_show_id.map(item_index))), shape=(len(user_index), len(item_index)))
    archive = np.load(folder / "scores.npz", allow_pickle=False)
    factors = np.load(folder / "factors.npz", allow_pickle=False)
    rows = [n for n, u in enumerate(users) if u in user_index]
    train_rows = [user_index[users[n]] for n in rows]
    check(f"{phase}/h{half_life}: factor/score item order", indices["items"] == archive["items_implicit_mf"].astype(int).tolist() == archive["items_ppr"].astype(int).tolist())
    mf = archive["scores_implicit_mf"]
    expected_mf = np.maximum(factors["user_factors"][train_rows] @ factors["item_factors"].T, 0)
    check(f"{phase}/h{half_life}: independent MF factor score reconstruction", np.allclose(mf[rows], expected_mf, rtol=1e-12, atol=1e-12))
    curve = pd.read_csv(folder / "learning_curve.csv")
    check(f"{phase}/h{half_life}: fifteen fixed MF epochs and decreasing objective", curve.epoch.tolist() == list(range(16)) and (np.diff(curve.training_objective) <= 1e-7).all())
    check(f"{phase}/h{half_life}: original graph reuse path", ROOT / info["graph_reused"] == source_paths["transition"])
    transition = sparse.load_npz(source_paths["transition"])
    restart = matrix[train_rows].copy()
    restart.data = np.log1p(restart.data)
    restart = restart.toarray()
    restart /= restart.sum(axis=1, keepdims=True)
    mass = archive["scores_ppr"][rows]
    dangling = np.asarray(transition.sum(axis=1)).ravel() == 0
    rhs = .5*(transition.T @ mass.T).T+(.5+.5*mass[:, dangling].sum(axis=1))[:, None]*restart
    check(f"{phase}/h{half_life}: PPR stationarity for independently weighted restarts", np.min(mass) >= 0 and np.allclose(mass.sum(axis=1), 1, atol=1e-12) and np.max(np.abs(mass-rhs).sum(axis=1)) < 1e-9)
    original_scores = np.load(source_paths["scores"], allow_pickle=False)
    check(f"{phase}/h{half_life}: rule scores and indices unchanged", np.array_equal(archive["scores_association_rules"], original_scores["scores_association_rules"]) and np.array_equal(archive["items_association_rules"], original_scores["items_association_rules"]))
    cold = {u for u in users if u not in user_index}
    check(f"{phase}/h{half_life}: original cold users and zero collaborative signal", cold == set(json.loads((folder / "cold_users.json").read_text())) and all(not mf[n].any() and not archive["scores_ppr"][n].any() for n, u in enumerate(users) if u in cold))


def verify_component_orders(folder, check):
    users = json.loads((folder / "users.json").read_text())
    pop = [int(r["tv_show_id"]) for r in read_csv(folder / "candidate_scores.csv")]
    pool_array = np.array(sorted(pop), dtype=np.int64)
    pool = set(pop)
    cold = set(json.loads((folder / "cold_users.json").read_text()))
    model = np.load(folder / "scores.npz", allow_pickle=False)
    components = {m: rankings(folder / f"component_{m}_top20.csv") for m in METHODS}
    for method in METHODS:
        output = components[method]
        check(f"{folder.name}: twenty unique eligible IDs/cohort for {method}", set(output) == set(users) and all(len(ids) == len(set(ids)) == 20 and set(ids) <= pool for ids in output.values()))
        if method == "popularity":
            check(f"{folder.name}: original popularity component", all(ids == pop[:20] for ids in output.values()))
            continue
        ids = model[f"items_{method}"].astype(int).tolist()
        supported = [(n, np.searchsorted(pool_array, item)) for n, item in enumerate(ids) if item in pool]
        model_positions = np.array([a for a, b in supported])
        pool_positions = np.array([b for a, b in supported])
        values = model[f"scores_{method}"]
        for row, user in enumerate(users):
            full_values = np.zeros(len(pool_array))
            full_values[pool_positions] = values[row, model_positions]
            positive = np.flatnonzero(full_values > 0)
            ordered = pool_array[positive[np.argsort(-full_values[positive], kind="stable")]].astype(int).tolist()
            used = set(ordered)
            ordered.extend(i for i in pop if i not in used)
            assert output[user] == (pop[:20] if user in cold else ordered[:20])
        check(f"{folder.name}: full-pool independent order for {method}", True)
    return users, pop, cold, components


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    frozen = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in frozen["paths"].items()}
    for name, path in paths.items():
        check(f"unchanged local source: {name}", sha256(path) == frozen["sha256"][name])
    check("selector inputs contain no submission score ledger or Kaggle CSV", all("submissions/" not in str(p.relative_to(ROOT)) for p in paths.values()))
    plan = json.loads((OUT / "plan.json").read_text())
    check("declared source plan equals executed plan", plan == json.loads(paths["plan"].read_text()) and len(plan["runs"]) == 11 and len(plan["controls"]) == 2)
    truth = rankings(paths["truth"])
    cohorts = {"all_primary": [r["user_id"] for r in read_csv(paths["primary"])], "template_primary": [r["user_id"] for r in read_csv(paths["template"])]}
    check("original complete 4030/1150 cohorts and five-ID truth", len(cohorts["all_primary"]) == 4030 and len(cohorts["template_primary"]) == 1150 and set(cohorts["template_primary"]) <= set(cohorts["all_primary"]) == set(truth) and all(len(ids) == len(set(ids)) == 5 for ids in truth.values()))
    comparison = {(r["run_id"], r["cohort"]): r for r in read_csv(OUT / "comparison.csv")}
    configs = plan["controls"]+plan["runs"]
    aps, predictions = {}, {}
    for variant in ["base", "h4", "h8"]:
        folder = ART / variant
        if variant != "base":
            verify_recency(folder, paths, "validation", check)
        users, pop, cold, components = verify_component_orders(folder, check)
        check(f"{variant}: fixed users/pool/cold fallback", set(users) == set(truth) and len(pop) == 6384 and len(cold) == 43)
        if variant != "base":
            check(f"{variant}: original popularity and strict history unchanged", (folder / "candidate_scores.csv").read_bytes() == (ART / "base/candidate_scores.csv").read_bytes() and json.loads((folder / "history.json").read_text()) == json.loads((ART / "base/history.json").read_text()))
        pop_rank = {i: n for n, i in enumerate(pop)}
        for config in [c for c in configs if ("base" if c["half_life_weeks"] is None else f"h{c['half_life_weeks']}") == variant]:
            name = config["id"]
            predicted = rankings(OUT / "runs" / name / "predictions.csv")
            predictions[name] = predicted
            check(f"{name}: every fusion rank reconstructed with exact rational scores", set(predicted) == set(users) and all(predicted[u] == exact_depth_fusion(components, u, config, pop_rank) for u in users))
            check(f"{name}: valid Top-5 and common fallback", all(len(ids) == len(set(ids)) == 5 and set(ids) <= set(pop) for ids in predicted.values()) and all(predicted[u] == pop[:5] for u in cold))
            result = {u: exact_ap(set(truth[u]), predicted[u]) for u in users}
            aps[name] = {u: value[0] for u, value in result.items()}
            for cohort, ids in cohorts.items():
                row = comparison[(name, cohort)]
                mean = sum((aps[name][u] for u in ids), Fraction(0))/len(ids)
                hits = sum(result[u][1] for u in ids)
                check(f"{name}/{cohort}: exact MAP, hits and denominator", int(row["users"]) == len(ids) and close(mean, row["map_at_5"]) and int(row["total_hits"]) == hits and close(row["precision_at_5"], Fraction(hits, 5*len(ids))))
            stored = read_csv(OUT / "runs" / name / "per_user_metrics.csv")
            check(f"{name}: all per-user APs", len(stored) == len(users) and all(close(r["ap_at_5"], aps[name][r["user_id"]]) for r in stored))
            summary = json.loads((OUT / "runs" / name / "summary.json").read_text())
            check(f"{name}: config/code provenance", summary["config"] == config and all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    for identifier in ["001", "002"]:
        check(f"control_{identifier}: exact original predictions reproduced", predictions[f"control_{identifier}"] == rankings(paths["prior_"+identifier]))
    old_signatures = {prediction_signature(rankings(paths["prior_"+i])) for i in ["001", "002", "003", "004", "005"]}
    eligible = [c["id"] for c in plan["runs"] if prediction_signature(predictions[c["id"]]) not in old_signatures]
    expected_selection = min(eligible, key=lambda name: (-float(comparison[(name, "all_primary")]["map_at_5"]), name))
    selection = json.loads((OUT / "selection.json").read_text())
    check("selection uses primary MAP only and excludes already uploaded rankings", selection["selected_id"] == expected_selection and selection["selected_config"] == next(c for c in plan["runs"] if c["id"] == expected_selection) and selection["public_private_scores_used_by_selector"] is False)
    rng = np.random.default_rng(plan["seed"])
    for record in read_csv(OUT / "paired_selected.csv"):
        users, control = cohorts[record["cohort"]], record["reference"]
        delta = np.array([float(aps[expected_selection][u])-float(aps[control][u]) for u in users])
        samples = delta[rng.integers(0, len(users), size=(plan["bootstrap_resamples"], len(users)))].mean(axis=1)
        check(f"paired difference/seeded interval: {record['cohort']}/{control}", close(delta.mean(), record["mean_MAP_difference"]) and close(np.quantile(samples, .025), record["conditional_95pct_lower"]) and close(np.quantile(samples, .975), record["conditional_95pct_upper"]))
    output_paths = [OUT / "selection.json", OUT / "comparison.csv"]+[OUT / "runs" / c["id"] / "predictions.csv" for c in configs]+[ART / v / "scores.npz" for v in ["base", "h4", "h8"]]
    report = {"status": "passed", "checks": checks, "verified_runs": [c["id"] for c in configs], "verifier_sha256": sha256(Path(__file__)),
              "verified_outputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in output_paths}, "meaning": "Assistant numerical verification; conditional single-holdout selection"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Passed {len(checks)} independent checks for 11 new configurations and both controls.")


if __name__ == "__main__":
    main()
