#!/usr/bin/env python3
"""Run the declared compact hybrid study on immutable saved component Top-5s."""

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from hybrid_models import history_switch, reciprocal_rank_fusion
from ranking_metrics import evaluate_rankings
from run_model_experiments import digest, dump, load_data
from segment_analysis import history_metrics, novelty_metrics, true_hit_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/hybrids"
SCRIPTS = Path(__file__).parent


def load_inputs(plan):
    data = load_data()
    paths = dict(data["paths"])
    paths.update({
        "plan": SCRIPTS / "hybrid_plan.json",
        "training_counts_50": ROOT / "artifacts/training_study/full10_t50/training_counts.parquet",
        "training_popularity_50": ROOT / "reports/training_study/full10_t50/candidate_scores.csv",
        "primary_cohort": ROOT / "reports/popularity/cohort_primary.csv",
        "template_cohort": ROOT / "reports/popularity/cohort_template_primary.csv",
        "reference_features": ROOT / "reports/training_study/reference_analysis/user_features.csv",
        "reference_truth_types": ROOT / "reports/training_study/reference_analysis/true_answer_attributes.csv",
    })
    components = {}
    for method, folder in plan["sources"].items():
        paths[f"component_{method}"] = ROOT / folder / "predictions.csv"
        paths[f"component_summary_{method}"] = ROOT / folder / "summary.json"
        summary = json.loads(paths[f"component_summary_{method}"].read_text())
        for key in ["truth", "users", "protocol"]:
            if summary["source_hashes"][key] != digest(data["paths"][key]):
                raise AssertionError(f"{method}: inconsistent frozen {key}")
        components[method] = read_rankings(paths[f"component_{method}"])
        if set(components[method]) != set(data["eval_users"]):
            raise AssertionError(f"{method}: inconsistent users")
        pool = set(data["pool"])
        if any(len(ids) != 5 or len(set(ids)) != 5 or not set(ids) <= pool for ids in components[method].values()):
            raise AssertionError(f"{method}: invalid component Top-5")
    train = pd.read_parquet(paths["training_counts_50"])
    if not train.split.eq("train").all() or train.duplicated(["user_id", "tv_show_id"]).any():
        raise AssertionError("Switch history must be unique training-only positive pairs")
    history_sizes = train.groupby("user_id").size().to_dict()
    candidates = pd.read_csv(paths["training_popularity_50"], keep_default_na=False).sort_values("rank")
    popularity = candidates.tv_show_id.astype(int).tolist()
    if set(popularity) != set(data["pool"]) or len(popularity) != len(data["pool"]):
        raise AssertionError("Changed candidate eligibility")
    if any(ids != popularity[:5] for ids in components["popularity"].values()):
        raise AssertionError("Popularity component differs from its training counts")
    cold = [u for u in data["eval_users"] if history_sizes.get(u, 0) == 0]
    if any(components[m][u] != popularity[:5] for m in components for u in cold):
        raise AssertionError("Components do not share the same cold fallback")
    features = pd.read_csv(paths["reference_features"], dtype={"user_id": str})
    truth_meta = pd.read_csv(paths["reference_truth_types"], dtype={"user_id": str})
    cohorts = {"all_primary": data["eval_users"], "template_primary": data["template_users"]}
    return data, paths, components, history_sizes, popularity, cold, features, truth_meta, cohorts


def make_predictions(config, components, users, history_sizes, popularity):
    """Inference is independent of truth, AP values and validation annotations."""
    predictions, details, routing = {}, [], []
    pop_rank = {item: rank for rank, item in enumerate(popularity)}
    for user in users:
        lists = {method: rankings[user] for method, rankings in components.items()}
        if config["type"] == "rrf":
            # Only union items have positive fusion scores; global Top-5 is
            # sufficient for any zero-score backfill. Relative tie order matches
            # the complete 6,384-item popularity ordering exactly.
            retrieval = set(popularity[:5]).union(*(lists[m] for m in config["weights"]))
            local_popularity = sorted(retrieval, key=pop_rank.__getitem__)
            predicted, scores = reciprocal_rank_fusion(lists, config["weights"], local_popularity, config["offset"])
            route = "rrf"
        else:
            predicted, route = history_switch(lists, history_sizes.get(user, 0), config["max_sparse_history"],
                                               config["sparse_method"], config["warm_method"])
            scores = {}
        predictions[user] = predicted
        routing.append({"user_id": user, "training_distinct_50pct": history_sizes.get(user, 0), "route": route})
        for rank, item in enumerate(predicted, 1):
            row = {"user_id": user, "rank": rank, "tv_show_id": item, "fusion_score": scores.get(item), "route": route}
            row.update({f"{m}_rank": ids.index(item)+1 if item in ids else 0 for m, ids in lists.items()})
            details.append(row)
    return predictions, details, routing


def main():
    plan = json.loads((SCRIPTS / "hybrid_plan.json").read_text())
    if len({r["id"] for r in plan["runs"]}) != len(plan["runs"]):
        raise AssertionError("Duplicate run IDs")
    data, paths, components, sizes, popularity, cold, features, truth_meta, cohorts = load_inputs(plan)
    OUT.mkdir(parents=True, exist_ok=True)
    dump(OUT / "plan.json", plan)
    before = {name: digest(path) for name, path in paths.items()}
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    code_hashes = {name: digest(SCRIPTS / name) for name in ["hybrid_models.py", "run_hybrid_experiments.py", "ranking_metrics.py", "segment_analysis.py"]}
    dump(OUT / "environment.json", {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__})
    overall, novel, history, aps = [], [], [], {}
    all_predictions = dict(components)
    runtime_rows = []
    for method, predicted in components.items():
        _, per_user = evaluate_rankings(data["truth"], predicted, users=data["eval_users"])
        aps[method] = {r["user_id"]: r["ap_at_5"] for r in per_user}
        for cohort, users in cohorts.items():
            metric, _ = evaluate_rankings(data["truth"], predicted, users=users)
            overall.append({"run_id": method, "kind": "component", "cohort": cohort, **metric})
        n = novelty_metrics(true_hit_rows(truth_meta, predicted), cohorts)
        n["run_id"] = method
        novel.append(n)
        h = history_metrics(pd.DataFrame(per_user), features[["user_id", "history_distinct", "history_volume", "active_week_span", "last_activity_age"]], cohorts)
        h["run_id"] = method
        history.append(h)
    for config in plan["runs"]:
        started = time.perf_counter()
        predicted, details, routing = make_predictions(config, components, data["eval_users"], sizes, popularity)
        inference_seconds = time.perf_counter()-started
        if any(predicted[u] != popularity[:5] for u in cold):
            raise AssertionError("Hybrid changed common cold fallback")
        folder = OUT / "runs" / config["id"]
        folder.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"user_id": data["eval_users"], "tv_show_id": [" ".join(map(str, predicted[u])) for u in data["eval_users"]]}).to_csv(folder / "predictions.csv", index=False)
        dump(folder / "config.json", config)
        metrics, records = evaluate_rankings(data["truth"], predicted, users=data["eval_users"])
        aps[config["id"]] = {r["user_id"]: r["ap_at_5"] for r in records}
        all_predictions[config["id"]] = predicted
        per_user = pd.DataFrame(records).merge(pd.DataFrame(routing), on="user_id", validate="one_to_one")
        for method in ["popularity", "implicit_mf", "ppr"]:
            per_user[f"delta_vs_{method}"] = per_user.ap_at_5-per_user.user_id.map(aps[method])
        per_user.to_csv(folder / "per_user_metrics.csv", index=False)
        recommendations = pd.DataFrame(details)
        recommendations["in_true_top5"] = [i in data["truth_sets"][u] for u, i in recommendations[["user_id", "tv_show_id"]].itertuples(index=False, name=None)]
        recommendations = recommendations.merge(data["candidates"][["tv_show_id", "tv_show_title", "tv_show_category"]], on="tv_show_id", validate="many_to_one")
        recommendations.to_csv(folder / "recommendations.csv", index=False)
        recommendations.loc[recommendations.user_id.isin([r["user_id"] for r in data["examples"]])].to_csv(folder / "example_recommendations.csv", index=False)
        run_metrics = []
        for cohort, users in cohorts.items():
            metric, _ = evaluate_rankings(data["truth"], predicted, users=users)
            row = {"run_id": config["id"], "kind": config["type"], "cohort": cohort, **metric}
            overall.append(row)
            run_metrics.append(row)
        n = novelty_metrics(true_hit_rows(truth_meta, predicted), cohorts)
        n.to_csv(folder / "fixed_novelty_metrics.csv", index=False)
        n["run_id"] = config["id"]
        novel.append(n)
        h = history_metrics(per_user, features[["user_id", "history_distinct", "history_volume", "active_week_span", "last_activity_age"]], cohorts)
        h.to_csv(folder / "fixed_history_metrics.csv", index=False)
        h["run_id"] = config["id"]
        history.append(h)
        diagnostics = {"cold_fallback_users": len(cold), "route_counts": per_user.route.value_counts().to_dict(),
                       "mean_shared_top5_with_mf": float(np.mean([len(set(predicted[u]) & set(components["implicit_mf"][u])) for u in predicted])),
                       "mean_shared_top5_with_ppr": float(np.mean([len(set(predicted[u]) & set(components["ppr"][u])) for u in predicted]))}
        dump(folder / "summary.json", {"config": config, "metrics": run_metrics, "diagnostics": diagnostics,
             "runtime": {"fusion_inference_seconds_excludes_component_fits": inference_seconds}, "code_hashes": code_hashes})
        runtime_rows.append({"run_id": config["id"], "inference_seconds": inference_seconds})
        print(f"{config['id']}: all={metrics['map_at_5']:.8f}; template={run_metrics[1]['map_at_5']:.8f}", flush=True)
    comparison = pd.DataFrame(overall)
    for method in ["popularity", "implicit_mf", "ppr"]:
        reference = comparison.loc[comparison.run_id == method].set_index("cohort").map_at_5
        comparison[f"delta_vs_{method}"] = comparison.map_at_5-comparison.cohort.map(reference)
    comparison.to_csv(OUT / "comparison.csv", index=False)
    pd.concat(novel, ignore_index=True).to_csv(OUT / "novelty_metrics.csv", index=False)
    pd.concat(history, ignore_index=True).to_csv(OUT / "history_metrics.csv", index=False)
    pd.DataFrame(runtime_rows).to_csv(OUT / "runtime.csv", index=False)
    best_hybrid = comparison.loc[(comparison.cohort == "all_primary") & (comparison.kind != "component")].sort_values(["map_at_5", "run_id"], ascending=[False, True]).iloc[0]
    best_overall = comparison.loc[comparison.cohort == "all_primary"].sort_values(["map_at_5", "run_id"], ascending=[False, True]).iloc[0]
    dump(OUT / "selection.json", {"selection_metric": plan["selection_metric"], "best_hybrid": best_hybrid.run_id,
         "best_overall": best_overall.run_id, "status": "Local validation selection only; conditional on this declared search"})
    rng = np.random.default_rng(plan["seed"])
    paired = []
    selected = best_hybrid.run_id
    for cohort, users in cohorts.items():
        for method in components:
            delta = np.array([aps[selected][u]-aps[method][u] for u in users])
            samples = delta[rng.integers(0, len(users), size=(plan["bootstrap_resamples"], len(users)))].mean(axis=1)
            paired.append({"cohort": cohort, "hybrid": selected, "reference": method, "mean_MAP_difference": float(delta.mean()),
                           "conditional_95pct_lower": float(np.quantile(samples, .025)), "conditional_95pct_upper": float(np.quantile(samples, .975)),
                           "better_users": int((delta > 1e-14).sum()), "worse_users": int((delta < -1e-14).sum()), "equal_users": int((np.abs(delta) <= 1e-14).sum())})
    pd.DataFrame(paired).to_csv(OUT / "selected_paired_comparisons.csv", index=False)
    # Save actual per-user additions/losses versus both strong components.
    changes = []
    for user in data["eval_users"]:
        actual = data["truth_sets"][user]
        hybrid_hits = set(all_predictions[selected][user]) & actual
        for method in ["implicit_mf", "ppr"]:
            base_hits = set(components[method][user]) & actual
            changes.append({"user_id": user, "hybrid": selected, "reference": method,
                            "added_correct_ids": " ".join(map(str, sorted(hybrid_hits-base_hits))),
                            "lost_correct_ids": " ".join(map(str, sorted(base_hits-hybrid_hits))),
                            "added_hits": len(hybrid_hits-base_hits), "lost_hits": len(base_hits-hybrid_hits),
                            "delta_AP": aps[selected][user]-aps[method][user]})
    pd.DataFrame(changes).to_csv(OUT / "selected_hit_changes.csv", index=False)
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Frozen inputs changed during hybrid study")
    print(f"Best declared hybrid: {selected}; best including components: {best_overall.run_id}")


if __name__ == "__main__":
    main()
