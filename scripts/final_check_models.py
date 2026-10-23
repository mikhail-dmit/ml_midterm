#!/usr/bin/env python3
"""Fit the frozen selected models using only raw CSVs and newly rebuilt tables."""

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import sparse
from threadpoolctl import threadpool_info, threadpool_limits

from build_interactions import read_views
from collaborative_models import build_coview_graph, fit_implicit_als, personalized_pagerank, restart_profiles
from content_rule_models import content_scores, content_vectors, count_weights, mine_pair_rules, rank_positive_with_backfill
from evaluate_rankings import read_rankings
from interaction_core import boundary_epoch, local_epoch, merge_views
from ranking_metrics import evaluate_rankings
from recommender_bundle import Bundle, counts_from_events, matrix_from_counts
from refinement_models import fuse_bundle, recency_training_counts
from run_content_rules import metadata_snapshot
from run_model_experiments import dump
from training_study import clip_join_training_window, weekly_baskets


def save_predictions(path, users, predictions):
    pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predictions[u])) for u in users]}).to_csv(path, index=False)


def fit_phase(events, users, candidates, cutoff, config, output):
    output.mkdir(parents=True, exist_ok=True)
    raw50, _ = counts_from_events(events, 50)
    raw80, strict_events = counts_from_events(events, 80)
    weighted, event_weights, scale = recency_training_counts(events, cutoff, config["mf_half_life"])
    if config["mf_half_life"] != config["ppr_half_life"] or config["rules_half_life"] is not None or config["pop_half_life"] is not None:
        raise AssertionError("This scratch replay is for the frozen final 007 recipe")
    c50, train50, items50 = matrix_from_counts(raw50)
    c80, train80, items80 = matrix_from_counts(raw80)
    weighted_matrix, weighted_users, weighted_items = matrix_from_counts(weighted)
    if weighted_users != train50 or weighted_items != items50 or (weighted_matrix > 0).astype(int).nnz != c50.nnz:
        raise AssertionError("Recency changed original binary support")
    raw50.to_parquet(output / "counts50.parquet", index=False)
    raw80.to_parquet(output / "counts80.parquet", index=False)
    weighted.to_parquet(output / "weighted_counts.parquet", index=False)
    event_weights[["user_id", "airing_id", "tv_show_id", "last_overlap", "raw_recency_weight", "recency_weight"]].to_parquet(output / "recency_events.parquet", index=False)
    dump(output / "indices50.json", {"users": train50, "items": items50})
    dump(output / "indices80.json", {"users": train80, "items": items80})
    map50, map80 = {u: n for n, u in enumerate(train50)}, {u: n for n, u in enumerate(train80)}
    rows50 = [n for n, u in enumerate(users) if u in map50]
    rows80 = [n for n, u in enumerate(users) if u in map80]
    query50 = [map50[users[n]] for n in rows50]
    query80 = [map80[users[n]] for n in rows80]
    with threadpool_limits(limits=1):
        x, y, curve = fit_implicit_als(weighted_matrix, factors=16, confidence_scale=1, regularization=1,
                                      weighting="log1p", preference="log1p", epochs=15, seed=20261023)
        # Build this graph afresh; do not load the original transition matrix.
        adjacency, transition, _, graph = build_coview_graph(c50, "raw")
        mf = np.zeros((len(users), len(items50)))
        ppr = np.zeros_like(mf)
        ar = np.zeros((len(users), len(items80)))
        mf[rows50] = np.maximum(x[query50] @ y.T, 0)
        mass, solver = personalized_pagerank(transition, restart_profiles(weighted_matrix)[query50], .5)
        ppr[rows50] = mass
        baskets, keys = weekly_baskets(strict_events, items80)
        rules, table, binary, _, _ = mine_pair_rules(baskets, items80, 5, .1, "confidence")
        ar[rows80] = (count_weights(c80[query80], "log1p") @ rules).toarray()
    np.savez_compressed(output / "factors.npz", user_factors=x, item_factors=y)
    pd.DataFrame(curve).to_csv(output / "learning_curve.csv", index=False)
    sparse.save_npz(output / "transition.npz", transition)
    sparse.save_npz(output / "adjacency.npz", adjacency)
    sparse.save_npz(output / "rule_weights.npz", rules)
    sparse.save_npz(output / "baskets.npz", binary)
    dump(output / "basket_keys.json", keys)
    table.to_parquet(output / "rules.parquet", index=False)
    scores = {"implicit_mf": mf, "ppr": ppr, "association_rules": ar}
    item_ids = {"implicit_mf": items50, "ppr": items50, "association_rules": items80}
    bundle = Bundle(users, candidates, raw50, raw80, scores, item_ids)
    bundle.prepare_queues(depth=20)
    bundle.save(output)
    all_predictions = {}
    for method in ["popularity", "implicit_mf", "ppr", "association_rules"]:
        predicted = {u: bundle.queues[n][method]["global"][:5] for n, u in enumerate(users)}
        all_predictions[method] = predicted
        save_predictions(output / f"predictions_{method}.csv", users, predicted)
    all_predictions["hybrid_007"] = fuse_bundle(bundle, config)
    save_predictions(output / "predictions_hybrid_007.csv", users, all_predictions["hybrid_007"])
    dump(output / "summary.json", {"users": len(users), "training_users50": len(train50), "training_items50": len(items50),
         "training_pairs50": len(raw50), "training_airings50": int(raw50.watched_airings.sum()),
         "training_pairs80": len(raw80), "training_airings80": int(raw80.watched_airings.sum()),
         "recency_cutoff_epoch": cutoff, "recency_half_life": 8, "mass_preserving_scale": scale,
         "weighted_total": float(weighted_matrix.sum()), "weekly_baskets": len(keys), "rules": len(table),
         "candidate_count": len(candidates), "cold_users": len(users)-len(rows50), "graph": graph, "ppr_solver": solver,
         "seed": 20261023, "MF_epochs": 15, "cached_models_loaded": False})
    return bundle, all_predictions, (c80, train80, items80)


def fit_cbf(bundle, strict_inputs, cbf_config, output):
    documents, provenance = metadata_snapshot()  # reads the two original raw historical CSVs only
    vectors, feature_names, idf = content_vectors(documents, cbf_config["family_weights"], cbf_config["idf"], cbf_config["family_balance"])
    items = [int(doc["tv_show_id"]) for doc in documents]
    item_map = {i: n for n, i in enumerate(items)}
    counts, users, count_items = strict_inputs
    mapping = np.array([item_map[i] for i in count_items])
    aligned = sparse.csr_matrix((counts.data.copy(), mapping[counts.indices], counts.indptr.copy()), shape=(len(users), len(items)))
    user_map = {u: n for n, u in enumerate(users)}
    rows = [n for n, u in enumerate(bundle.users) if u in user_map]
    training_rows = [user_map[bundle.users[n]] for n in rows]
    with threadpool_limits(limits=1):
        scores_warm, profiles = content_scores(aligned[training_rows], vectors, cbf_config["history_weighting"])
    scores = np.zeros((len(bundle.users), len(items)))
    scores[rows] = scores_warm
    predicted, _ = rank_positive_with_backfill(scores, bundle.users, user_map, items, bundle.pool, bundle.popularity)
    save_predictions(output / "predictions_content_based.csv", bundle.users, predicted)
    sparse.save_npz(output / "cbf_item_vectors.npz", vectors)
    sparse.save_npz(output / "cbf_profiles.npz", profiles)
    np.save(output / "cbf_item_ids.npy", np.array(items, dtype=np.int64))
    np.save(output / "cbf_profile_users.npy", np.array([bundle.users[n] for n in rows], dtype="U20"))
    np.save(output / "cbf_idf.npy", idf)
    dump(output / "cbf_features.json", feature_names)
    dump(output / "cbf_metadata.json", {"documents": documents, "provenance": provenance, "configuration": cbf_config})
    return predicted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    frozen = json.loads((work / "configuration.json").read_text())
    config = frozen["hybrid"]
    interaction = work / "interactions"
    reports = work / "interaction_reports"
    events = pd.read_parquet(interaction / "airing_interactions.parquet")
    airings = pd.read_parquet(interaction / "airings.parquet")
    metadata = pd.read_csv(reports / "validation_users.csv", dtype={"user_id": str})
    eligible = metadata.loc[metadata.primary_validation_eligible]
    users = eligible.user_id.tolist()
    validation_pool = sorted(int(i) for i in airings.loc[(airings.start < boundary_epoch("2020-07-27")) & (airings.end > boundary_epoch("2020-05-18")), "tv_show_id"].unique())
    train = events.loc[events.split == "train"].copy()
    val_bundle, predicted, strict_inputs = fit_phase(train, users, validation_pool, boundary_epoch("2020-05-18"), config, work / "validation")
    predicted["content_based"] = fit_cbf(val_bundle, strict_inputs, frozen["cbf"], work / "validation")
    truth = read_rankings(reports / "validation_ground_truth.csv")
    template_users = eligible.loc[eligible.is_test_user, "user_id"].tolist()
    metrics = []
    for method, ids in predicted.items():
        for cohort, population in [("all_primary", users), ("template_primary", template_users)]:
            result, records = evaluate_rankings(truth, ids, users=population)
            metrics.append({"method": method, "cohort": cohort, **result})
            if cohort == "all_primary":
                pd.DataFrame(records).to_csv(work / "validation" / f"per_user_{method}.csv", index=False)
    pd.DataFrame(metrics).to_csv(work / "validation/metrics.csv", index=False)
    del events, val_bundle, predicted, strict_inputs, train
    print("Validation models rebuilt from new tables; reconstructing the full twenty-week window ...", flush=True)
    views, view_stats = read_views(args.data_dir, 250000)
    merged = merge_views(views)
    del views
    full_events = clip_join_training_window(merged, airings, boundary_epoch("2020-03-09"), boundary_epoch("2020-07-27"))
    del merged
    full_events["split"] = "refit_11_30"
    full_events.to_parquet(work / "full_training_events.parquet", index=False, compression="zstd")
    template = pd.read_csv(args.data_dir / "submission.csv", dtype=str, keep_default_na=False)
    raw_schedule = pd.read_csv(args.data_dir / "export_arh_31-42-final.csv", usecols=["channel_id", "start_time", "duration", "tv_show_id"],
                               dtype={"channel_id": "int32", "duration": "int32", "tv_show_id": "int64"}, keep_default_na=False)
    raw_schedule["start"] = local_epoch(raw_schedule.start_time, "%d.%m.%Y %H:%M:%S")
    keep = (raw_schedule.tv_show_id != 0) & (raw_schedule.duration > 0) & (raw_schedule.start < boundary_epoch("2020-10-19")) & (raw_schedule.start+raw_schedule.duration > boundary_epoch("2020-07-27"))
    pool = sorted(int(i) for i in raw_schedule.loc[keep, "tv_show_id"].unique())
    final_bundle, final_predictions, _ = fit_phase(full_events, template.user_id.tolist(), pool, boundary_epoch("2020-07-27"), config, work / "final")
    save_predictions(work / "final/submission_007.csv", final_bundle.users, final_predictions["hybrid_007"])
    dump(work / "environment.json", {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
         "pandas": pd.__version__, "scipy": scipy.__version__, "BLAS_threads_during_fit": 1, "threadpools": threadpool_info(), "view_stats": view_stats,
         "scope": "Frozen selected six validation strategies and all-history final007 recipe; fresh weights/factors/graph/rules/CBF metadata, no cached derived input"})
    print("All-history final 007 refit completed using fresh events, factors, graph and rules.", flush=True)


if __name__ == "__main__":
    main()
