#!/usr/bin/env python3
"""Small reproducible MF/PPR validation experiments under the frozen protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import sparse
from scipy.stats import spearmanr
from threadpoolctl import threadpool_info, threadpool_limits

from collaborative_models import (
    build_coview_graph, fit_implicit_als, personalized_pagerank,
    rank_model_scores, restart_profiles,
)
from evaluate_rankings import read_rankings
from ranking_metrics import evaluate_rankings

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                               default=lambda x: x.item() if isinstance(x, np.generic) else x) + "\n", encoding="utf-8")


def quantiles(values):
    return {str(q): float(np.quantile(values, q)) for q in [0, .25, .5, .75, 1]} if len(values) else {}


def load_data():
    paths = {
        "interactions": ROOT / "artifacts/interactions/user_programme_interactions.parquet",
        "truth": ROOT / "reports/interactions/validation_ground_truth.csv",
        "users": ROOT / "reports/interactions/validation_users.csv",
        "candidates": ROOT / "reports/popularity/validation_candidates.csv",
        "baseline": ROOT / "reports/popularity/predictions_allow_repeats.csv",
        "protocol": ROOT / "reports/popularity/protocol.json",
    }
    programmes = pd.read_parquet(paths["interactions"])
    train = programmes.loc[(programmes.split == "train") & (programmes.watched_airings > 0)].copy()
    val_positive = programmes.loc[(programmes.split == "validation") & (programmes.watched_airings > 0), ["user_id", "tv_show_id"]]
    truth = read_rankings(paths["truth"])
    metadata = pd.read_csv(paths["users"], dtype={"user_id": str})
    eval_metadata = metadata.loc[metadata.primary_validation_eligible].copy()
    eval_users = eval_metadata.user_id.tolist()
    template_users = eval_metadata.loc[eval_metadata.is_test_user, "user_id"].tolist()
    user_ids = sorted(train.user_id.unique())
    item_ids = sorted(int(x) for x in train.tv_show_id.unique())
    user_map, item_map = {u: i for i, u in enumerate(user_ids)}, {item: i for i, item in enumerate(item_ids)}
    counts = sparse.csr_matrix((train.watched_airings.to_numpy(dtype=np.float64),
                                (train.user_id.map(user_map).to_numpy(), train.tv_show_id.map(item_map).to_numpy())),
                               shape=(len(user_ids), len(item_ids)))
    candidates = pd.read_csv(paths["candidates"], keep_default_na=False)
    pool = sorted(int(x) for x in candidates.tv_show_id)
    popularity = candidates.sort_values("rank").tv_show_id.astype(int).tolist()
    baseline = read_rankings(paths["baseline"])
    assert len(eval_users) == 4030 and len(template_users) == 1150 and len(pool) == 6384
    assert set(eval_users) == set(truth) == set(baseline)
    assert int(counts.sum()) == 316413 and counts.shape == (4737, 2490)
    assert train.split.eq("train").all() and not train.duplicated(["user_id", "tv_show_id"]).any()
    any_validation = {u: set(int(x) for x in f.tv_show_id) for u, f in val_positive.groupby("user_id")}
    history = {u: set(int(x) for x in f.tv_show_id) for u, f in train.groupby("user_id")}
    own_counts = {(u, int(i)): int(n) for u, i, n in train[["user_id", "tv_show_id", "watched_airings"]].itertuples(index=False, name=None)}
    light = eval_metadata.loc[eval_metadata.train_qualified_programmes > 0].sort_values(["train_watched_airings", "user_id"], kind="stable").iloc[0]
    heavy = eval_metadata.sort_values(["train_watched_airings", "user_id"], ascending=[False, True], kind="stable").iloc[0]
    examples = [{"role": role, "user_id": row.user_id, "train_qualified_programmes": int(row.train_qualified_programmes),
                 "train_watched_airings": int(row.train_watched_airings)} for role, row in [("light", light), ("heavy", heavy)]]
    return dict(paths=paths, train=train, counts=counts, user_ids=user_ids, item_ids=item_ids, user_map=user_map,
                eval_users=eval_users, template_users=template_users, eval_metadata=eval_metadata,
                truth=truth, truth_sets={u: set(v) for u, v in truth.items()}, candidates=candidates, pool=pool,
                popularity=popularity, baseline=baseline, any_validation=any_validation, history=history,
                own_counts=own_counts, examples=examples)


def evaluate_scores(scores, data):
    predictions, details = rank_model_scores(scores, data["eval_users"], data["user_map"], data["item_ids"],
                                             data["pool"], data["popularity"])
    all_metric, per_user = evaluate_rankings(data["truth"], predictions, users=data["eval_users"])
    template_metric, _ = evaluate_rankings(data["truth"], predictions, users=data["template_users"])
    return predictions, details, [dict(cohort="all_primary", **all_metric), dict(cohort="template_primary", **template_metric)], per_user


def scoring_als(x, y, data):
    result = np.zeros((len(data["eval_users"]), len(data["item_ids"])))
    warm = [(row, data["user_map"][user]) for row, user in enumerate(data["eval_users"]) if user in data["user_map"]]
    rows, indices = zip(*warm)
    result[list(rows)] = x[list(indices)] @ y.T
    return result


def save_run(run_dir, artifact_dir, config, data, predictions, details, metrics, per_user, diagnostics, runtime):
    run_dir.mkdir(parents=True, exist_ok=True)
    dump(run_dir / "config.json", config)
    pd.DataFrame({"user_id": data["eval_users"], "tv_show_id": [" ".join(map(str, predictions[u])) for u in data["eval_users"]]}).to_csv(run_dir / "predictions.csv", index=False)
    per_user = pd.DataFrame(per_user).merge(data["eval_metadata"][["user_id", "is_test_user", "train_qualified_programmes", "train_watched_airings"]],
                                           on="user_id", validate="one_to_one")
    per_user["history_bucket"] = per_user.train_qualified_programmes.map(
        lambda n: "0 (cold)" if n == 0 else "1-5" if n <= 5 else "6-20" if n <= 20 else "21-50" if n <= 50 else "51+")
    per_user.to_csv(run_dir / "per_user_metrics.csv", index=False)
    details = pd.DataFrame(details)
    details["training_user_watch_count"] = [data["own_counts"].get((u, int(i)), 0) for u, i in details[["user_id", "tv_show_id"]].itertuples(index=False, name=None)]
    details["in_true_top5"] = [int(i) in data["truth_sets"][u] for u, i in details[["user_id", "tv_show_id"]].itertuples(index=False, name=None)]
    details["any_qualified_validation_watch"] = [int(i) in data["any_validation"].get(u, set()) for u, i in details[["user_id", "tv_show_id"]].itertuples(index=False, name=None)]
    details = details.merge(data["candidates"][["tv_show_id", "training_watched_airings", "training_distinct_viewers", "tv_show_title", "tv_show_category"]],
                            on="tv_show_id", validate="many_to_one")
    details.to_csv(run_dir / "recommendations.csv", index=False)
    details.loc[details.user_id.isin([r["user_id"] for r in data["examples"]])].to_csv(run_dir / "example_recommendations.csv", index=False)
    segments = []
    for cohort, subset in [("all_primary", per_user), ("template_primary", per_user.loc[per_user.is_test_user])]:
        for bucket, f in subset.groupby("history_bucket", sort=True):
            segments.append({"cohort": cohort, "history_bucket": bucket, "users": len(f), "map_at_5": float(f.ap_at_5.mean())})
    pd.DataFrame(segments).to_csv(run_dir / "history_segments.csv", index=False)
    repeated = details.training_user_watch_count > 0
    diagnostics.update({
        "recommended_slots": len(details), "share_slots_previously_watched": float(repeated.mean()),
        "mean_training_popularity_of_recommendations": float(details.training_watched_airings.mean()),
        "median_training_distinct_viewers_of_recommendations": float(details.training_distinct_viewers.median()),
        "unique_recommended_programmes": int(details.tv_show_id.nunique()),
        "zero_training_support_recommendations": int((details.training_watched_airings == 0).sum()),
        "cold_fallback_users": int(details.loc[details.fallback, "user_id"].nunique()),
        "mean_top5_overlap_with_popularity": float(np.mean([len(set(predictions[u]) & set(data["baseline"][u])) for u in predictions])),
        "max_share_users_receiving_one_item": float(details.groupby("tv_show_id").size().max() / len(predictions)),
    })
    paired = pd.DataFrame(per_user[["user_id", "ap_at_5"]])
    _, base_records = evaluate_rankings(data["truth"], data["baseline"], users=data["eval_users"])
    baseline_ap = {r["user_id"]: r["ap_at_5"] for r in base_records}
    paired["popularity_ap"] = paired.user_id.map(baseline_ap)
    paired["delta_vs_popularity"] = paired.ap_at_5 - paired.popularity_ap
    paired.to_csv(run_dir / "paired_vs_popularity.csv", index=False)
    diagnostics["users_better_than_popularity"] = int((paired.delta_vs_popularity > 0).sum())
    diagnostics["users_worse_than_popularity"] = int((paired.delta_vs_popularity < 0).sum())
    diagnostics["users_equal_to_popularity"] = int((paired.delta_vs_popularity == 0).sum())
    summary = {"config": config, "metrics": metrics, "diagnostics": diagnostics, "runtime": runtime,
               "artifact_directory": str(artifact_dir.relative_to(ROOT)),
               "source_hashes": {name: digest(path) for name, path in data["paths"].items()},
               "code_hashes": {name: digest(Path(__file__).parent / name) for name in ["collaborative_models.py", "run_model_experiments.py"]}}
    dump(run_dir / "summary.json", summary)
    print(f"  {config['id']}: all MAP@5={metrics[0]['map_at_5']:.8f}; template={metrics[1]['map_at_5']:.8f}", flush=True)


def run_mf(config, plan, data, output, artifacts):
    started = time.perf_counter()
    best = {"map": -1.0}
    checkpoint_rows = []
    validation_seconds = 0.0
    def callback(epoch, x, y):
        nonlocal validation_seconds
        if epoch not in plan["mf_checkpoints"]:
            return {}
        clock = time.perf_counter()
        _, _, metrics, _ = evaluate_scores(scoring_als(x, y, data), data)
        validation_seconds += time.perf_counter() - clock
        score = metrics[0]["map_at_5"]
        checkpoint_rows.append({"epoch": epoch, "all_primary_map_at_5": score, "template_primary_map_at_5": metrics[1]["map_at_5"]})
        if score > best["map"]:
            best.update(map=score, epoch=epoch, x=x.copy(), y=y.copy())
        print(f"    epoch {epoch}: MAP@5={score:.8f}", flush=True)
        return {"validation_map_at_5": score}
    kwargs = {key: config[key] for key in ["factors", "confidence_scale", "regularization", "weighting", "epochs"]}
    kwargs["preference"] = config.get("preference", "binary")
    _, _, history = fit_implicit_als(data["counts"], **kwargs, seed=plan["seed"], callback=callback)
    fit_elapsed = time.perf_counter() - started - validation_seconds
    if "x" not in best:
        raise AssertionError("No validation checkpoint selected")
    x, y = best["x"], best["y"]
    clock = time.perf_counter()
    scores = scoring_als(x, y, data)
    predictions, details, metrics, per_user = evaluate_scores(scores, data)
    prediction_seconds = time.perf_counter() - clock
    if abs(metrics[0]["map_at_5"] - best["map"]) > 1e-14:
        raise AssertionError("Restored checkpoint does not reproduce its validation score")
    artifact = artifacts / config["id"]
    artifact.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(artifact / "factors.npz", user_factors=x, item_factors=y,
                        user_ids=np.asarray(data["user_ids"], dtype="U20"), item_ids=np.asarray(data["item_ids"], dtype=np.int64))
    run_dir = output / "runs" / config["id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(history).to_csv(run_dir / "learning_curve.csv", index=False)
    pd.DataFrame(checkpoint_rows).to_csv(run_dir / "validation_checkpoints.csv", index=False)
    observed = data["counts"].tocoo()
    dots = np.einsum("ij,ij->i", x[observed.row], y[observed.col])
    user_correlations = []
    for u in range(data["counts"].shape[0]):
        a, b = data["counts"].indptr[u:u+2]
        raw = data["counts"].data[a:b]
        if len(raw) >= 3 and len(np.unique(raw)) > 1:
            estimates = y[data["counts"].indices[a:b]] @ x[u]
            corr = spearmanr(raw, estimates).statistic
            if np.isfinite(corr):
                user_correlations.append(float(corr))
    support = np.asarray((data["counts"] > 0).sum(axis=0)).ravel()
    diagnostics = {
        "selected_epoch": best["epoch"], "selection_metric": plan["selection_metric"],
        "initial_objective": history[0]["training_objective"], "last_objective": history[-1]["training_objective"],
        "objective_monotonically_nonincreasing": True,
        "positive_training_pair_dot_score_quantiles": quantiles(dots),
        "share_positive_training_pairs_score_above_095": float(np.mean(dots > .95)),
        "median_within_user_count_score_spearman": float(np.median(user_correlations)),
        "users_in_count_score_correlation": len(user_correlations),
        "item_norm_support_spearman": float(spearmanr(np.linalg.norm(y, axis=1), support).statistic),
        "user_factor_norm_quantiles": quantiles(np.linalg.norm(x, axis=1)),
        "item_factor_norm_quantiles": quantiles(np.linalg.norm(y, axis=1)),
        "score_semantics": "Implicit binary-preference reconstruction score, not a rating or calibrated watch probability" if config.get("preference", "binary") == "binary"
                           else "Weighted log(1+qualified airing count) reconstruction score; implicit count target, not star ratings/probabilities",
    }
    save_run(run_dir, artifact, config, data, predictions, details, metrics, per_user, diagnostics,
             {"training_seconds_excluding_validation": fit_elapsed, "checkpoint_validation_seconds": validation_seconds,
              "final_scoring_and_ranking_seconds": prediction_seconds, "total_seconds": time.perf_counter() - started})


def run_ppr(config, data, output, artifacts):
    started = time.perf_counter()
    adjacency, transition, dangling, graph_checks = build_coview_graph(data["counts"], config["normalization"])
    profiles = restart_profiles(data["counts"], config["weighting"])
    warm_rows = [r for r, u in enumerate(data["eval_users"]) if u in data["user_map"]]
    training_rows = [data["user_map"][data["eval_users"][r]] for r in warm_rows]
    warm_profiles = profiles[training_rows]
    graph_seconds = time.perf_counter() - started
    clock = time.perf_counter()
    masses, solver_checks = personalized_pagerank(transition, warm_profiles, config["alpha"])
    solve_seconds = time.perf_counter() - clock
    scores = np.zeros((len(data["eval_users"]), len(data["item_ids"])))
    scores[warm_rows] = masses
    clock = time.perf_counter()
    predictions, details, metrics, per_user = evaluate_scores(scores, data)
    ranking_seconds = time.perf_counter() - clock
    artifact = artifacts / config["id"]
    artifact.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(artifact / "adjacency.npz", adjacency)
    sparse.save_npz(artifact / "transition.npz", transition)
    np.save(artifact / "item_ids.npy", np.asarray(data["item_ids"], dtype=np.int64))
    own_binary = data["counts"][training_rows].copy()
    own_binary.data[:] = 1
    history_mass = np.asarray(own_binary.multiply(masses).sum(axis=1)).ravel()
    available = np.array([item in set(data["pool"]) for item in data["item_ids"]])
    degrees = np.asarray(adjacency.sum(axis=1)).ravel()
    global_pop = np.asarray(data["counts"].sum(axis=0)).ravel()
    diagnostics = {
        "graph": graph_checks, "solver_checks": solver_checks,
        "graph_weighted_degree_training_popularity_spearman": float(spearmanr(degrees, global_pop).statistic),
        "mean_stationary_mass_on_own_history": float(history_mass.mean()),
        "mean_stationary_mass_on_unavailable_programmes": float(masses[:, ~available].sum(axis=1).mean()),
        "mean_L1_distance_from_restart": float(np.mean(np.abs(masses - warm_profiles.toarray()).sum(axis=1))),
        "score_semantics": "Stationary programme-node visit mass, not probability of watching; unnormalized after availability filtering",
    }
    save_run(output / "runs" / config["id"], artifact, config, data, predictions, details, metrics, per_user, diagnostics,
             {"graph_and_profiles_seconds": graph_seconds, "linear_solve_seconds": solve_seconds,
              "final_scoring_and_ranking_seconds": ranking_seconds, "total_seconds": time.perf_counter() - started})


def refresh_comparison(output, data):
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((output / "runs").glob("*/summary.json"))]
    rows = []
    for cohort, users in [("all_primary", data["eval_users"]), ("template_primary", data["template_users"])]:
        metric, _ = evaluate_rankings(data["truth"], data["baseline"], users=users)
        rows.append(dict(run_id="popularity", method="popularity", cohort=cohort, **metric))
    for result in summaries:
        for metric in result["metrics"]:
            rows.append(dict(run_id=result["config"]["id"], method=result["config"]["method"],
                             selected_epoch=result["diagnostics"].get("selected_epoch"),
                             runtime_seconds=result["runtime"]["total_seconds"], **metric))
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output / "comparison.csv", index=False)
    best = {}
    for method in ["implicit_mf", "ppr"]:
        eligible = [r for r in summaries if r["config"]["method"] == method]
        if eligible:
            chosen = max(eligible, key=lambda r: r["metrics"][0]["map_at_5"])
            best[method] = {"run_id": chosen["config"]["id"], "metrics": chosen["metrics"],
                            "selection": "Highest all-primary validation MAP@5; template subset not used for separate selection"}
    dump(output / "selected_models.json", best)
    example_rows = []
    sources = [("popularity", ROOT / "reports/popularity/predictions_allow_repeats.csv")]
    for method, selected in best.items():
        sources.append((selected["run_id"], output / "runs" / selected["run_id"] / "predictions.csv"))
    metadata = data["candidates"].set_index("tv_show_id")
    for model, path in sources:
        predictions = read_rankings(path)
        for example in data["examples"]:
            user = example["user_id"]
            ap = evaluate_rankings(data["truth"], predictions, users=[user])[0]["map_at_5"]
            for rank, item in enumerate(predictions[user], 1):
                row = metadata.loc[item]
                example_rows.append({"model": model, "role": example["role"], "user_id": user, "rank": rank,
                                     "tv_show_id": item, "title": row.tv_show_title, "category": row.tv_show_category,
                                     "training_user_airings": data["own_counts"].get((user, item), 0),
                                     "in_true_validation_top5": item in data["truth_sets"][user],
                                     "qualified_validation_watch": item in data["any_validation"].get(user, set()), "user_AP_at_5": ap})
    pd.DataFrame(example_rows).to_csv(output / "selected_recommendation_examples.csv", index=False)
    print("\nCurrent comparison:", flush=True)
    print(comparison[["run_id", "cohort", "map_at_5", "precision_at_5"]].to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["initial", "diagnostic", "all"], default="initial")
    parser.add_argument("--run-id", help="Run one declared configuration")
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    plan = json.loads((Path(__file__).parent / "model_experiments.json").read_text(encoding="utf-8"))
    configs = plan["initial"] + plan["diagnostic"] if args.stage == "all" else plan[args.stage]
    if args.run_id:
        configs = [config for config in plan["initial"] + plan["diagnostic"] if config["id"] == args.run_id]
    if not configs:
        parser.error("No matching declared experiment")
    output, artifacts = ROOT / "reports/models", ROOT / "artifacts/models"
    output.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    data = load_data()
    dump(output / "training_data.json", {
        "users": data["counts"].shape[0], "programmes": data["counts"].shape[1],
        "positive_user_programme_pairs": data["counts"].nnz,
        "qualifying_airings": int(data["counts"].sum()),
        "density": data["counts"].nnz / np.prod(data["counts"].shape),
        "candidate_pool": len(data["pool"]),
        "candidate_programmes_with_training_vector": len(set(data["pool"]) & set(data["item_ids"])),
        "primary_users": len(data["eval_users"]), "template_primary_users": len(data["template_users"]),
        "primary_cold_users": sum(u not in data["user_map"] for u in data["eval_users"]),
        "primary_true_ids_without_training_vector": sum(i not in set(data["item_ids"]) for ids in data["truth"].values() for i in ids),
    })
    sparse.save_npz(artifacts / "training_counts.npz", data["counts"])
    dump(artifacts / "training_indices.json", {"users": data["user_ids"], "items": data["item_ids"]})
    dump(output / "example_users.json", {"selection": "Primary-cohort light/heavy users chosen only by training qualified-airing counts before model runs", "users": data["examples"]})
    dump(output / "experiment_plan.json", plan)
    dump(output / "environment.json", {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                                       "pandas": pd.__version__, "platform": platform.platform(), "threads_requested": args.threads,
                                       "threadpools": threadpool_info()})
    with threadpool_limits(limits=args.threads):
        for config in configs:
            print(f"Running {config['id']} ...", flush=True)
            if config["method"] == "implicit_mf":
                run_mf(config, plan, data, output, artifacts)
            else:
                run_ppr(config, data, output, artifacts)
            refresh_comparison(output, data)


if __name__ == "__main__":
    main()
