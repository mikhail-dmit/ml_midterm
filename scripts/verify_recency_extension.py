#!/usr/bin/env python3
"""Independent verification of model mixing, strict rule queries and vote-only decay."""

import json
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import sparse

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256
from verify_refinement_study import exact_depth_fusion, prediction_signature, verify_recency

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/recency_extension"
ART = ROOT / "artifacts/recency_extension/validation"
METHODS = ["implicit_mf", "ppr", "association_rules", "popularity"]
SPEC_KEYS = ["mf_half_life", "ppr_half_life", "rules_half_life", "pop_half_life"]


def verify_extension_bundle(folder, paths, phase, check):
    info = json.loads((folder / "extension.json").read_text())
    spec = info["component_spec"]
    users = json.loads((folder / "users.json").read_text())
    model = np.load(folder / "scores.npz", allow_pickle=False)
    original = np.load(paths["scores"], allow_pickle=False)
    for short, method in [("mf", "implicit_mf"), ("ppr", "ppr")]:
        source = ROOT / info[f"{short}_source"]
        archived = np.load(source / "scores.npz", allow_pickle=False)
        check(f"{folder.name}: {method} source identity/index/user alignment", sha256(source / "scores.npz") == info["source_scores_sha256"][short] and np.array_equal(model[f"scores_{method}"], archived[f"scores_{method}"]) and np.array_equal(model[f"items_{method}"], archived[f"items_{method}"]) and users == json.loads((source / "users.json").read_text()))
        requested = spec[f"{short}_half_life"]
        if requested is None:
            check(f"{folder.name}: {method} genuinely undecayed", source == paths["scores"].parent)
        else:
            check(f"{folder.name}: {method} exact declared half-life", json.loads((source / "recency.json").read_text())["half_life_weeks"] == requested)
    raw50 = pd.read_parquet(paths["counts50"])
    raw80 = pd.read_parquet(paths["counts80"])
    warm = set(raw50.user_id)
    cold = set(users)-warm
    check(f"{folder.name}: original actual cold users", cold == set(json.loads((folder / "cold_users.json").read_text())))
    seen = {u: sorted(int(i) for i in f.tv_show_id) for u, f in raw80.groupby("user_id", sort=False)}
    check(f"{folder.name}: strict-history masks unchanged", json.loads((folder / "history.json").read_text()) == {u: seen.get(u, []) for u in users})
    pop = [int(r["tv_show_id"]) for r in read_csv(folder / "candidate_scores.csv")]
    raw_pop = raw50.groupby("tv_show_id").watched_airings.sum().to_dict()
    pool = set(pop)
    check(f"{folder.name}: original unweighted tie and backfill order", pop == sorted(pool, key=lambda i: (-raw_pop.get(i, 0), i)) and pop == [int(r["tv_show_id"]) for r in read_csv(paths["popularity"])])
    matrix_path = ROOT / info["original_rules_matrix"]
    check(f"{folder.name}: original mined rules matrix unchanged", sha256(matrix_path) == info["original_rules_matrix_sha256"])
    if spec["rules_half_life"] is None:
        check(f"{folder.name}: original rule-query scores unchanged", np.array_equal(model["scores_association_rules"], original["scores_association_rules"]))
    else:
        cutoff = int(datetime(2020, 5, 18, tzinfo=ZoneInfo("Europe/Kyiv")).timestamp()) if phase == "validation" else int(datetime(2020, 7, 27, tzinfo=ZoneInfo("Europe/Kyiv")).timestamp())
        events = pd.read_parquet(paths["events"])
        selected = events.loc[5*events.watched_seconds >= 4*events.duration].copy()
        weights = np.power(.5, (cutoff-selected.last_overlap.to_numpy())/(604800*spec["rules_half_life"]))
        scale = len(selected)/weights.sum()
        selected["independent_weight"] = weights*scale
        expected = selected.groupby(["user_id", "tv_show_id"]).independent_weight.sum().sort_index()
        stored = pd.read_parquet(folder / "rule_query_counts.parquet")
        actual = stored.set_index(["user_id", "tv_show_id"]).watched_airings.sort_index()
        check(f"{folder.name}: strict80 recency query membership and arithmetic", (selected.last_overlap <= cutoff).all() and actual.index.equals(expected.index) and np.allclose(actual, expected, rtol=1e-12, atol=1e-12) and abs(actual.sum()-len(selected)) < 1e-7)
        check(f"{folder.name}: strict80 support unchanged", set(actual.index) == set(raw80[["user_id", "tv_show_id"]].itertuples(index=False, name=None)))
        metadata = info["rules_query"]
        check(f"{folder.name}: rule-query metadata and global scale", metadata["strict_events"] == len(selected) and metadata["cutoff"] == cutoff and close(metadata["global_scale"], scale) and metadata["matrix_sha256"] == sha256(matrix_path))
        idx = json.loads((folder / "rule_query_indices.json").read_text())
        ui, ii = {u: n for n, u in enumerate(idx["users"])}, {i: n for n, i in enumerate(idx["items"])}
        query = sparse.csr_matrix((np.log1p(stored.watched_airings.to_numpy()), (stored.user_id.map(ui), stored.tv_show_id.map(ii))), shape=(len(ui), len(ii)))
        rows = [n for n, u in enumerate(users) if u in ui]
        expected_scores = np.zeros_like(model["scores_association_rules"])
        expected_scores[rows] = (query[[ui[users[n]] for n in rows]] @ sparse.load_npz(matrix_path)).toarray()
        check(f"{folder.name}: recency rule scores independently reconstructed", idx["items"] == model["items_association_rules"].astype(int).tolist() and np.allclose(expected_scores, model["scores_association_rules"], rtol=1e-12, atol=1e-12))
    votes = read_csv(folder / "popularity_votes.csv")
    if spec["pop_half_life"] is None:
        expected_counts = raw_pop
        check(f"{folder.name}: undecayed popularity source", info["pop_source"] is None)
    else:
        source = ROOT / info["pop_source"]
        check(f"{folder.name}: popularity exact declared decay", json.loads((source / "recency.json").read_text())["half_life_weeks"] == spec["pop_half_life"])
        expected_counts = pd.read_parquet(source / "weighted_counts.parquet").groupby("tv_show_id").watched_airings.sum().to_dict()
    vote_order = sorted(pool, key=lambda i: (-expected_counts.get(i, 0), i))
    check(f"{folder.name}: vote-only popularity counts and ranking", [int(r["tv_show_id"]) for r in votes] == vote_order and all(close(r["vote_count"], expected_counts.get(int(r["tv_show_id"]), 0)) for r in votes))
    components = {m: rankings(folder / f"component_{m}_top20.csv") for m in METHODS}
    for method in METHODS:
        output = components[method]
        check(f"{folder.name}: twenty unique eligible {method} IDs and exact cohort", set(output) == set(users) and all(len(ids) == len(set(ids)) == 20 and set(ids) <= pool for ids in output.values()))
        if method == "popularity":
            check(f"{folder.name}: warm vote list and fixed cold popularity", all(output[u] == (pop[:20] if u in cold else vote_order[:20]) for u in users))
            continue
        items, values = model[f"items_{method}"].astype(int).tolist(), model[f"scores_{method}"]
        candidates = np.array(sorted(pool), dtype=np.int64)
        pairs = [(n, np.searchsorted(candidates, i)) for n, i in enumerate(items) if i in pool]
        source_positions, destination = np.array([a for a, b in pairs]), np.array([b for a, b in pairs])
        for row, user in enumerate(users):
            scores = np.zeros(len(candidates))
            scores[destination] = values[row, source_positions]
            positive = np.flatnonzero(scores > 0)
            order = candidates[positive[np.argsort(-scores[positive], kind="stable")]].astype(int).tolist()
            used = set(order)
            order += [i for i in pop if i not in used]
            assert output[user] == (pop[:20] if user in cold else order[:20])
        check(f"{folder.name}: independent full-pool {method} order", True)
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
        check(f"unchanged local input: {name}", sha256(path) == frozen["sha256"][name])
    check("selector has no Kaggle ledger/submission CSV input", all("submissions/" not in str(p.relative_to(ROOT)) for p in paths.values()))
    plan = json.loads((OUT / "plan.json").read_text())
    check("executed plan equals predeclared thirteen-candidate grid", plan == json.loads(paths["plan"].read_text()) and len(plan["runs"]) == 13)
    truth = rankings(paths["truth"])
    cohorts = {"all_primary": [r["user_id"] for r in read_csv(paths["primary"])], "template_primary": [r["user_id"] for r in read_csv(paths["template"])]}
    check("unchanged 4030/1150 cohorts and original five-ID truth", len(cohorts["all_primary"]) == 4030 and len(cohorts["template_primary"]) == 1150 and set(cohorts["all_primary"]) == set(truth) and set(cohorts["template_primary"]) <= set(truth) and all(len(ids) == len(set(ids)) == 5 for ids in truth.values()))
    for h in [4, 6, 8, 12, 16]:
        folder = ROOT / "artifacts/refinement/validation" / f"h{h}" if h in [4, 8] else ART / "cf_cache" / f"cf_h{h}"
        verify_recency(folder, paths, "validation", check)
    comparison = {(r["run_id"], r["cohort"]): r for r in read_csv(OUT / "comparison.csv")}
    configs = [plan["control"]]+plan["runs"]
    ap, predicted_all, variant_components = {}, {}, {}
    for config in configs:
        name = config["id"]
        summary = json.loads((OUT / "runs" / name / "summary.json").read_text())
        variant = summary["variant"]
        if variant not in variant_components:
            variant_components[variant] = verify_extension_bundle(ART / variant, paths, "validation", check)
        users, pop, cold, components = variant_components[variant]
        info = json.loads((ART / variant / "extension.json").read_text())
        check(f"{name}: exact component specification", info["component_spec"] == {k: config[k] for k in SPEC_KEYS})
        predicted = rankings(OUT / "runs" / name / "predictions.csv")
        predicted_all[name] = predicted
        pop_rank = {i: n for n, i in enumerate(pop)}
        check(f"{name}: independently reconstructed exact-rational fusion", set(predicted) == set(users) and all(predicted[u] == exact_depth_fusion(components, u, config, pop_rank) for u in users))
        check(f"{name}: valid fixed-cohort Top-5 and cold fallback", len(users) == 4030 and len(pop) == 6384 and len(cold) == 43 and all(len(ids) == len(set(ids)) == 5 and set(ids) <= set(pop) for ids in predicted.values()) and all(predicted[u] == pop[:5] for u in cold))
        result = {u: exact_ap(set(truth[u]), predicted[u]) for u in users}
        ap[name] = {u: value[0] for u, value in result.items()}
        for cohort, ids in cohorts.items():
            row = comparison[(name, cohort)]
            mean = sum((ap[name][u] for u in ids), Fraction(0))/len(ids)
            hits = sum(result[u][1] for u in ids)
            check(f"{name}/{cohort}: exact AP/MAP, hits and denominator", int(row["users"]) == len(ids) and close(mean, row["map_at_5"]) and int(row["total_hits"]) == hits and close(row["precision_at_5"], Fraction(hits, 5*len(ids))))
        check(f"{name}: all saved per-user APs", all(close(r["ap_at_5"], ap[name][r["user_id"]]) for r in read_csv(OUT / "runs" / name / "per_user_metrics.csv")))
        check(f"{name}: config/code provenance", summary["config"] == config and all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    check("006 control reproduces every previous validation prediction", predicted_all["control_006"] == rankings(paths["prior_006"]))
    old = {prediction_signature(rankings(paths[f"prior_{i:03d}"])) for i in range(1, 7)}
    eligible = [c["id"] for c in plan["runs"] if prediction_signature(predicted_all[c["id"]]) not in old]
    selected = min(eligible, key=lambda name: (-float(comparison[(name, "all_primary")]["map_at_5"]), name))
    selection = json.loads((OUT / "selection.json").read_text())
    check("primary-only unsubmitted selection, no Kaggle score criterion", selection["selected_id"] == selected and selection["selected_config"] == next(c for c in plan["runs"] if c["id"] == selected) and selection["public_private_scores_used_by_selector"] is False)
    rng = np.random.default_rng(plan["seed"])
    for row in read_csv(OUT / "paired_selected.csv"):
        users = cohorts[row["cohort"]]
        delta = np.array([float(ap[selected][u])-float(ap["control_006"][u]) for u in users])
        samples = delta[rng.integers(0, len(users), size=(plan["bootstrap_resamples"], len(users)))].mean(axis=1)
        check(f"reproducible conditional paired interval: {row['cohort']}", close(delta.mean(), row["mean_MAP_difference"]) and close(np.quantile(samples, .025), row["conditional_95pct_lower"]) and close(np.quantile(samples, .975), row["conditional_95pct_upper"]))
    outputs = [OUT / "selection.json", OUT / "comparison.csv"]+[OUT / "runs" / c["id"] / "predictions.csv" for c in configs]
    outputs += [ART / variant / filename for variant in variant_components for filename in ["scores.npz", "extension.json", "popularity_votes.csv"]]
    record = {"status": "passed", "checks": checks, "verified_runs": [c["id"] for c in configs], "verifier_sha256": sha256(Path(__file__)),
              "verified_outputs_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in outputs}, "meaning": "Assistant numerical checks on a repeatedly used temporal hold-out"}
    (OUT / "verification.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(f"Passed {len(checks)} checks across thirteen new configurations and the exact 006 control.")


if __name__ == "__main__":
    main()
