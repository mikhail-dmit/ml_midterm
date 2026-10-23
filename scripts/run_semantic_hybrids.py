#!/usr/bin/env python3
"""Compare predeclared role-based hybrids to the unchanged selected RRF."""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from ranking_metrics import evaluate_rankings
from recommender_bundle import METHODS, restore_validation
from run_model_experiments import digest, dump
from segment_analysis import history_metrics, novelty_metrics, true_hit_rows
from semantic_hybrids import predict_user

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/semantic_hybrids"
ART = ROOT / "artifacts/semantic_hybrids"


def declared_configs(plan):
    return [{"id": m, "type": "single", "method": m} for m in METHODS] + [plan["rrf_control"]] + plan["runs"]


def predict_all(bundle, config):
    predictions, trace = {}, []
    for row, user in enumerate(bundle.users):
        ids, routes = predict_user(config, bundle.queues[row], lambda method, item: bundle.score(method, row, item),
                                   len(bundle.seen.get(user, set())), user not in bundle.warm, bundle.popularity)
        if len(ids) != len(set(ids)) or len(ids) != 5 or not set(ids) <= set(bundle.pool):
            raise AssertionError("Invalid Top-5")
        predictions[user] = ids
        for rank, (item, route) in enumerate(zip(ids, routes), 1):
            record = {"user_id": user, "rank": rank, "tv_show_id": item, "route": route,
                      "familiar_training_80pct": item in bundle.seen.get(user, set()),
                      "history_distinct_80pct": len(bundle.seen.get(user, set())), "cold_50pct": user not in bundle.warm}
            record.update({f"{m}_score": bundle.score(m, row, item) for m in METHODS})
            trace.append(record)
    return predictions, pd.DataFrame(trace)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    plan_path = Path(__file__).parent / "semantic_hybrid_plan.json"
    plan = json.loads(plan_path.read_text())
    dump(OUT / "plan.json", plan)
    paths = {"plan": plan_path, "truth": ROOT / "reports/interactions/validation_ground_truth.csv",
             "primary": ROOT / "reports/popularity/cohort_primary.csv", "template": ROOT / "reports/popularity/cohort_template_primary.csv",
             "candidates": ROOT / "reports/popularity/validation_candidates.csv",
             "features": ROOT / "reports/training_study/reference_analysis/user_features.csv",
             "truth_types": ROOT / "reports/training_study/reference_analysis/true_answer_attributes.csv",
             "rrf_predictions": ROOT / "reports/hybrids/runs/rrf_mf_ppr_rules_k0/predictions.csv"}
    for setting in ["full10_t50", "full10_t80"]:
        paths[f"counts_{setting}"] = ROOT / "artifacts/training_study" / setting / "training_counts.parquet"
    for label, file in {"MF": "full10_t50/implicit_mf/factors.npz", "PPR": "full10_t50/ppr/transition.npz", "rules": "full10_t80/association_rules/rule_weights.npz"}.items():
        paths[label] = ROOT / "artifacts/training_study" / file
    before = {k: digest(p) for k, p in paths.items()}
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    users = pd.read_csv(paths["primary"], dtype=str).user_id.tolist()
    template = pd.read_csv(paths["template"], dtype=str).user_id.tolist()
    candidates = pd.read_csv(paths["candidates"], keep_default_na=False)
    bundle, diagnostics = restore_validation(users, candidates.tv_show_id.astype(int).tolist())
    started = time.perf_counter()
    bundle.prepare_queues()
    diagnostics["queue_preparation_seconds"] = time.perf_counter()-started
    bundle.save(ART)
    dump(OUT / "component_diagnostics.json", diagnostics)
    # Exact reproduction is required before evaluating any new strategy.
    for method, setting in [("implicit_mf", "full10_t50"), ("ppr", "full10_t50"), ("association_rules", "full10_t80"), ("popularity", "full10_t50")]:
        source = ROOT / "reports/training_study" / setting / "runs" / method / "predictions.csv"
        predicted = {u: bundle.queues[n][method]["global"][:5] for n, u in enumerate(users)}
        if predicted != read_rankings(source):
            raise AssertionError(f"Restored component does not reproduce saved {method}")
    truth = read_rankings(paths["truth"])
    features = pd.read_csv(paths["features"], dtype={"user_id": str})
    truth_meta = pd.read_csv(paths["truth_types"], dtype={"user_id": str})
    cohorts = {"all_primary": users, "template_primary": template}
    comparison, novel, history, aps = [], [], [], {}
    for config in declared_configs(plan):
        started = time.perf_counter()
        predicted, trace = predict_all(bundle, config)
        if config["id"] == plan["rrf_control"]["id"] and predicted != read_rankings(paths["rrf_predictions"]):
            raise AssertionError("RRF control changed")
        seconds = time.perf_counter()-started
        folder = OUT / "runs" / config["id"]
        folder.mkdir(parents=True, exist_ok=True)
        dump(folder / "config.json", config)
        pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predicted[u])) for u in users]}).to_csv(folder / "predictions.csv", index=False)
        trace["in_true_top5"] = [int(i) in truth[u] for u, i in trace[["user_id", "tv_show_id"]].itertuples(index=False, name=None)]
        trace = trace.merge(candidates[["tv_show_id", "tv_show_title", "tv_show_category"]], on="tv_show_id", validate="many_to_one")
        trace.to_csv(folder / "recommendations.csv", index=False)
        metrics, records = evaluate_rankings(truth, predicted, users=users)
        aps[config["id"]] = {r["user_id"]: r["ap_at_5"] for r in records}
        pd.DataFrame(records).to_csv(folder / "per_user_metrics.csv", index=False)
        run_metrics = []
        for cohort, ids in cohorts.items():
            metric, _ = evaluate_rankings(truth, predicted, users=ids)
            row = {"run_id": config["id"], "type": config["type"], "cohort": cohort, **metric}
            comparison.append(row)
            run_metrics.append(row)
        n = novelty_metrics(true_hit_rows(truth_meta, predicted), cohorts)
        n["run_id"] = config["id"]
        novel.append(n)
        n.to_csv(folder / "novelty_metrics.csv", index=False)
        h = history_metrics(pd.DataFrame(records), features[["user_id", "history_distinct", "history_volume", "active_week_span", "last_activity_age"]], cohorts)
        h["run_id"] = config["id"]
        history.append(h)
        h.to_csv(folder / "history_metrics.csv", index=False)
        dump(folder / "summary.json", {"config": config, "metrics": run_metrics, "inference_seconds": seconds,
             "actual_cold_users": sum(u not in bundle.warm for u in users), "routing_slots": trace.route.value_counts().to_dict(),
             "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["semantic_hybrids.py", "recommender_bundle.py", "run_semantic_hybrids.py"]}})
        print(f"{config['id']}: all={metrics['map_at_5']:.8f}; template={run_metrics[1]['map_at_5']:.8f}", flush=True)
    comparison = pd.DataFrame(comparison)
    control = comparison.loc[comparison.run_id == plan["rrf_control"]["id"]].set_index("cohort").map_at_5
    comparison["delta_vs_rrf"] = comparison.map_at_5-comparison.cohort.map(control)
    comparison.to_csv(OUT / "comparison.csv", index=False)
    pd.concat(novel, ignore_index=True).to_csv(OUT / "novelty_metrics.csv", index=False)
    pd.concat(history, ignore_index=True).to_csv(OUT / "history_metrics.csv", index=False)
    primary = comparison.loc[comparison.cohort == "all_primary"].sort_values(["map_at_5", "run_id"], ascending=[False, True])
    selected = primary.iloc[0].run_id
    semantic_ids = {r["id"] for r in plan["runs"]}
    best_semantic = primary.loc[primary.run_id.isin(semantic_ids)].iloc[0].run_id
    selection = {"selected_id": selected, "selected_config": next(c for c in declared_configs(plan) if c["id"] == selected),
                 "best_semantic_id": best_semantic, "selection_metric": plan["selection"], "primary_MAP": float(primary.iloc[0].map_at_5),
                 "template_MAP": float(comparison.loc[(comparison.run_id == selected) & (comparison.cohort == "template_primary"), "map_at_5"].iloc[0])}
    dump(OUT / "selection.json", selection)
    paired = []
    rng = np.random.default_rng(plan["seed"])
    for cohort, ids in cohorts.items():
        for name in [r["id"] for r in plan["runs"]]:
            delta = np.array([aps[name][u]-aps[plan["rrf_control"]["id"]][u] for u in ids])
            samples = delta[rng.integers(0, len(ids), size=(2000, len(ids)))].mean(axis=1)
            paired.append({"cohort": cohort, "run_id": name, "delta_MAP_vs_rrf": float(delta.mean()), "conditional_95pct_lower": float(np.quantile(samples, .025)),
                           "conditional_95pct_upper": float(np.quantile(samples, .975)), "better_users": int((delta > 1e-14).sum()), "worse_users": int((delta < -1e-14).sum())})
    pd.DataFrame(paired).to_csv(OUT / "paired_vs_rrf.csv", index=False)
    if before != {k: digest(p) for k, p in paths.items()}:
        raise AssertionError("Frozen validation inputs changed")
    print(f"Selected overall: {selected}; best semantic: {best_semantic}")


if __name__ == "__main__":
    main()
