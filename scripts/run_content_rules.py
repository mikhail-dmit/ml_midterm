#!/usr/bin/env python3
"""Run metadata CBF and pair-rule experiments without changing the protocol."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

from content_rule_models import (
    content_scores, content_vectors, count_weights, metadata_document,
    mine_pair_rules, rank_positive_with_backfill,
)
from interaction_core import LOCAL_WINDOWS, boundary_epoch, local_epoch
from ranking_metrics import evaluate_rankings
from run_model_experiments import digest, dump, load_data, save_run

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/content_rules"
ARTIFACTS = ROOT / "artifacts/content_rules"
SCHEDULES = ["export_arh_11-20-final.csv", "export_arh_21-30-final.csv"]


def metadata_snapshot():
    lower, cutoff = [boundary_epoch(x) for x in LOCAL_WINDOWS["train"]]
    fields = ["tv_show_id", "start_time", "duration", "tv_show_title", "tv_show_category", "tv_show_genre_1",
              "tv_show_genre_2", "tv_show_genre_3", "year_of_production", "director", "actors"]
    frames, sources = [], {}
    for filename in SCHEDULES:
        path = ROOT / "sweettv-tv-program-recommender" / filename
        selected_rows = []
        for raw in pd.read_csv(path, usecols=fields, dtype=str, keep_default_na=False, chunksize=250000):
            start = local_epoch(raw.start_time, "%d.%m.%Y %H:%M:%S")
            duration = raw.duration.astype("int64").to_numpy()
            keep = (raw.tv_show_id != "0") & (duration > 0) & (start < cutoff) & (start + duration > lower)
            part = raw.loc[keep].copy()
            part["start_epoch"] = start[keep]
            part["source_csv_record"] = part.index + 2
            part["source_file"] = filename
            selected_rows.append(part)
        frame = pd.concat(selected_rows, ignore_index=True)
        frames.append(frame)
        sources[filename] = {"sha256": digest(path), "used_airing_rows": len(frame)}
    rows = pd.concat(frames, ignore_index=True)
    rows["tv_show_id"] = rows.tv_show_id.astype("int64")
    documents = []
    for item, group in rows.groupby("tv_show_id", sort=True):
        doc = metadata_document(group, item)
        representative = group.sort_values(["start_epoch", "source_file", "source_csv_record"], kind="stable").iloc[-1]
        doc.update({"representative_title": representative.tv_show_title,
                    "representative_category": representative.tv_show_category,
                    "first_training_airing_start": int(group.start_epoch.min()),
                    "last_training_airing_start": int(group.start_epoch.max()),
                    "representative_source_file": representative.source_file,
                    "representative_source_record": int(representative.source_csv_record)})
        documents.append(doc)
    provenance = {"sources": sources, "training_start_utc_epoch": lower, "cutoff_utc_epoch_exclusive": cutoff,
                  "max_airing_start_used": int(rows.start_epoch.max()), "unique_programmes": len(documents),
                  "used_airing_rows": len(rows),
                  "policy": "All attributes, vocabulary and IDF frozen from pre-cutoff schedule airings; no validation metadata features"}
    return documents, provenance


def warm_query_rows(data):
    eval_rows = [r for r, u in enumerate(data["eval_users"]) if u in data["user_map"]]
    train_rows = [data["user_map"][data["eval_users"][r]] for r in eval_rows]
    return eval_rows, train_rows


def evaluate_and_save(config, scores, item_ids, data, diagnostics, started, fit_seconds, scoring_seconds):
    clock = time.perf_counter()
    predictions, details = rank_positive_with_backfill(scores, data["eval_users"], data["user_map"], item_ids,
                                                       data["pool"], data["popularity"])
    metric, records = evaluate_rankings(data["truth"], predictions, users=data["eval_users"])
    template_metric, _ = evaluate_rankings(data["truth"], predictions, users=data["template_users"])
    metrics = [dict(cohort="all_primary", **metric), dict(cohort="template_primary", **template_metric)]
    fallback_users = {r["user_id"] for r in details if r["fallback"]}
    diagnostics.update({"users_with_popularity_backfill": len(fallback_users),
                        "warm_users_with_popularity_backfill": sum(u in data["user_map"] for u in fallback_users),
                        "popularity_backfilled_slots": sum(r["fallback"] for r in details)})
    run_dir, artifact_dir = OUTPUT / "runs" / config["id"], ARTIFACTS / config["id"]
    save_run(run_dir, artifact_dir, config, data, predictions, details, metrics, records, diagnostics,
             {"fit_seconds": fit_seconds, "scoring_seconds": scoring_seconds,
              "ranking_and_evaluation_seconds": time.perf_counter() - clock,
              "total_seconds": time.perf_counter() - started})
    saved = json.loads((run_dir / "summary.json").read_text())
    saved["diagnostics"]["cold_fallback_users"] = sum(u not in data["user_map"] for u in data["eval_users"])
    saved["code_hashes"].update({name: digest(Path(__file__).parent / name) for name in ["content_rule_models.py", "run_content_rules.py", "ranking_metrics.py"]})
    dump(run_dir / "summary.json", saved)
    return predictions, details


def run_content(config, data, documents, provenance):
    started = time.perf_counter()
    vectors, names, idfs = content_vectors(documents, config["family_weights"], config["idf"], config["family_balance"])
    item_ids = [doc["tv_show_id"] for doc in documents]
    item_map = {item: i for i, item in enumerate(item_ids)}
    mapping = np.array([item_map[item] for item in data["item_ids"]])
    base = data["counts"]
    counts = sparse.csr_matrix((base.data.copy(), mapping[base.indices], base.indptr.copy()), shape=(base.shape[0], len(documents)))
    eval_rows, training_rows = warm_query_rows(data)
    fit_seconds = time.perf_counter() - started
    clock = time.perf_counter()
    warm_scores, profiles = content_scores(counts[training_rows], vectors, config["history_weighting"])
    scores = np.zeros((len(data["eval_users"]), len(item_ids)))
    scores[eval_rows] = warm_scores
    del warm_scores
    scoring_seconds = time.perf_counter() - clock
    lengths = np.sqrt(np.asarray(vectors.multiply(vectors).sum(axis=1)).ravel())
    profile_lengths = np.sqrt(np.asarray(profiles.multiply(profiles).sum(axis=1)).ravel())
    if not np.allclose(lengths[lengths > 0], 1, atol=1e-12) or not np.allclose(profile_lengths[profile_lengths > 0], 1, atol=1e-12):
        raise AssertionError("Content cosine vectors/profiles must be normalized")
    if scores.min() < -1e-12 or scores.max() > 1 + 1e-12:
        raise AssertionError("Cosine score outside [0,1]")
    signatures = defaultdict(list)
    for r, item in enumerate(item_ids):
        a, b = vectors.indptr[r:r+2]
        signature = (tuple(vectors.indices[a:b]), tuple(np.round(vectors.data[a:b], 12)))
        signatures[signature].append(item)
    collapsed = [ids for ids in signatures.values() if len(ids) > 1]
    available_positions = [item_map[item] for item in data["pool"] if item in item_map]
    ties = []
    for row in eval_rows:
        values = scores[row, available_positions]
        fifth = np.partition(values, -5)[-5]
        ties.append(int(np.isclose(values, fifth, rtol=0, atol=1e-12).sum()))
    diagnostics = {"metadata_snapshot": provenance, "metadata_programmes": len(item_ids), "features": len(names),
                   "features_by_family": dict(Counter(name.split(":", 1)[0] for name in names)),
                   "candidate_items_with_frozen_metadata": len(available_positions),
                   "unique_item_feature_vectors": len(signatures), "items_in_nonunique_feature_groups": sum(map(len, collapsed)),
                   "largest_identical_vector_group": max(map(len, signatures.values())),
                   "mean_candidates_tied_at_fifth_score": float(np.mean(ties)),
                   "max_item_norm_error": float(np.max(np.abs(lengths[lengths > 0] - 1))),
                   "score_semantics": "Cosine between training-history content profile and programme metadata vector, not watch probability"}
    artifact = ARTIFACTS / config["id"]
    artifact.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(artifact / "item_vectors.npz", vectors)
    sparse.save_npz(artifact / "query_profiles.npz", profiles)
    sparse.save_npz(artifact / "training_counts_metadata_indices.npz", counts)
    np.save(artifact / "item_ids.npy", np.asarray(item_ids, dtype=np.int64))
    np.save(artifact / "profile_user_ids.npy", np.asarray([data["eval_users"][r] for r in eval_rows], dtype="U20"))
    dump(artifact / "feature_names.json", names)
    np.save(artifact / "feature_idf.npy", idfs)
    run_dir = OUTPUT / "runs" / config["id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"programmes": len(ids), "ids": " ".join(map(str, ids))} for ids in sorted(collapsed, key=lambda x: (-len(x), x[0]))]).to_csv(run_dir / "identical_item_vectors.csv", index=False)
    predictions, _ = evaluate_and_save(config, scores, item_ids, data, diagnostics, started, fit_seconds, scoring_seconds)
    profile_map = {data["eval_users"][r]: i for i, r in enumerate(eval_rows)}
    explanations = []
    for example in data["examples"]:
        user = example["user_id"]
        profile = profiles.getrow(profile_map[user])
        for rank, item in enumerate(predictions[user], 1):
            if item not in item_map:
                continue
            product = profile.multiply(vectors.getrow(item_map[item])).tocsr()
            for index, value in zip(product.indices, product.data):
                explanations.append({"user_id": user, "rank": rank, "tv_show_id": item,
                                     "feature": names[index], "user_profile_value": float(profile[0, index]),
                                     "item_feature_value": float(vectors[item_map[item], index]), "score_contribution": float(value)})
    pd.DataFrame(explanations).to_csv(run_dir / "example_feature_contributions.csv", index=False)


def weekly_baskets(data):
    events = pd.read_parquet(ROOT / "artifacts/interactions/airing_interactions.parquet",
                             columns=["split", "user_id", "tv_show_id", "first_overlap", "watched_80pct"])
    events = events.loc[(events.split == "train") & events.watched_80pct].copy()
    iso = pd.to_datetime(events.first_overlap, unit="s", utc=True).dt.tz_convert("Europe/Kyiv").dt.isocalendar()
    events["basket"] = events.user_id + "|" + iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
    events = events.drop_duplicates(["basket", "tv_show_id"])
    keys = sorted(events.basket.unique())
    key_map = {key: i for i, key in enumerate(keys)}
    item_map = {item: i for i, item in enumerate(data["item_ids"])}
    baskets = sparse.csr_matrix((np.ones(len(events), dtype=np.int64),
                                 (events.basket.map(key_map), events.tv_show_id.map(item_map))), shape=(len(keys), len(item_map)))
    return baskets, keys


def run_rules(config, data, documents):
    started = time.perf_counter()
    if config["baskets"] == "user":
        baskets, basket_keys = data["counts"], data["user_ids"]
    else:
        baskets, basket_keys = weekly_baskets(data)
    weights, rules, binary, joint, totals = mine_pair_rules(baskets, data["item_ids"], config["min_joint_count"],
                                                           config["min_confidence"], config["score_metric"])
    binary_users = data["counts"].copy()
    binary_users.data[:] = 1
    user_joint = (binary_users.T @ binary_users).tocsr()
    rules["distinct_training_users_joint"] = np.asarray(user_joint[
        rules.antecedent_index.to_numpy(), rules.consequent_index.to_numpy()]).ravel().astype("int64")
    fit_seconds = time.perf_counter() - started
    eval_rows, train_rows = warm_query_rows(data)
    history_weights = count_weights(data["counts"], config["history_weighting"])
    clock = time.perf_counter()
    warm_scores = (history_weights[train_rows] @ weights).toarray()
    scores = np.zeros((len(data["eval_users"]), len(data["item_ids"])))
    scores[eval_rows] = warm_scores
    scoring_seconds = time.perf_counter() - clock
    available = [i for i, item in enumerate(data["item_ids"]) if item in set(data["pool"])]
    positive_candidates = (scores[:, available] > 0).sum(axis=1)
    diagnostics = {"baskets": binary.shape[0], "basket_definition": config["baskets"], "rules": len(rules),
                   "min_support_fraction": config["min_joint_count"] / binary.shape[0],
                   "rule_confidence_quantiles": rules.confidence.quantile([0, .5, .9, 1]).to_dict(),
                   "rule_lift_quantiles": rules.lift.quantile([0, .5, .9, 1]).to_dict(),
                   "rule_joint_count_quantiles": rules.joint_count.quantile([0, .5, .9, 1]).to_dict(),
                   "warm_users_without_applicable_candidate_rule": sum(positive_candidates[r] == 0 for r in eval_rows),
                   "warm_users_with_fewer_than_five_rule_candidates": sum(positive_candidates[r] < 5 for r in eval_rows),
                   "mean_positive_rule_candidates": float(positive_candidates[eval_rows].mean()),
                   "self_rules": int((rules.antecedent_id == rules.consequent_id).sum()),
                   "rules_with_fewer_than_five_distinct_joint_users": int((rules.distinct_training_users_joint < 5).sum()),
                   "score_semantics": "Sum of matched directional rule weights times training-history weights; not a calibrated probability"}
    artifact = ARTIFACTS / config["id"]
    artifact.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(artifact / "baskets.npz", binary)
    sparse.save_npz(artifact / "rule_weights.npz", weights)
    np.save(artifact / "item_ids.npy", np.asarray(data["item_ids"], dtype=np.int64))
    dump(artifact / "basket_keys.json", basket_keys)
    rules.to_parquet(artifact / "rules.parquet", index=False)
    run_dir = OUTPUT / "runs" / config["id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    top_rules = pd.concat([rules.sort_values(["confidence", "joint_count"], ascending=False).head(20),
                           rules.sort_values(["lift", "joint_count"], ascending=False).head(20)]).drop_duplicates(["antecedent_id", "consequent_id"])
    title_map = {doc["tv_show_id"]: doc["representative_title"] for doc in documents}
    top_rules["antecedent_title"] = top_rules.antecedent_id.map(title_map)
    top_rules["consequent_title"] = top_rules.consequent_id.map(title_map)
    top_rules.to_csv(run_dir / "top_rules.csv", index=False)
    predictions, _ = evaluate_and_save(config, scores, data["item_ids"], data, diagnostics, started, fit_seconds, scoring_seconds)
    item_map = {item: i for i, item in enumerate(data["item_ids"])}
    explanations = []
    for example in data["examples"]:
        user = example["user_id"]
        history = history_weights.getrow(data["user_map"][user])
        for rank, item in enumerate(predictions[user], 1):
            if item not in item_map:
                continue
            j = item_map[item]
            for i, history_weight in zip(history.indices, history.data):
                rule_weight = float(weights[i, j])
                if not rule_weight:
                    continue
                n = int(joint[i, j])
                explanations.append({"user_id": user, "rank": rank, "consequent_id": item,
                                     "antecedent_id": data["item_ids"][i], "antecedent_title": title_map.get(data["item_ids"][i], ""),
                                     "antecedent_count": int(totals[i]), "consequent_count": int(totals[j]),
                                     "joint_count": n, "baskets": binary.shape[0], "support": n/binary.shape[0],
                                     "confidence": n/totals[i], "lift": n*binary.shape[0]/(totals[i]*totals[j]),
                                     "history_weight": float(history_weight), "rule_weight": rule_weight,
                                     "score_contribution": float(history_weight * rule_weight)})
    pd.DataFrame(explanations).to_csv(run_dir / "example_rule_contributions.csv", index=False)


def refresh(data):
    summaries = [json.loads(p.read_text()) for p in sorted((OUTPUT / "runs").glob("*/summary.json"))]
    rows = []
    old = pd.read_csv(ROOT / "reports/models/comparison.csv")
    for summary in summaries:
        rows.extend(dict(run_id=summary["config"]["id"], method=summary["config"]["method"], **m) for m in summary["metrics"])
    comparison = pd.DataFrame(rows)
    comparison.to_csv(OUTPUT / "comparison.csv", index=False)
    chosen = {}
    for method in ["content_based", "association_rules"]:
        options = [r for r in summaries if r["config"]["method"] == method]
        if options:
            best = max(options, key=lambda r: r["metrics"][0]["map_at_5"])
            chosen[method] = {"run_id": best["config"]["id"], "metrics": best["metrics"], "selection": "Highest all-primary MAP@5 only"}
    dump(OUTPUT / "selected_models.json", chosen)
    all_output = ROOT / "reports/all_methods"
    all_output.mkdir(parents=True, exist_ok=True)
    pd.concat([old, comparison], ignore_index=True).to_csv(all_output / "all_configurations.csv", index=False)
    previous = json.loads((ROOT / "reports/models/selected_models.json").read_text())
    selected = {**previous, **chosen}
    dump(all_output / "selected_models.json", selected)
    selected_ids = ["popularity"] + [r["run_id"] for r in selected.values()]
    full = pd.concat([old, comparison], ignore_index=True)
    full.loc[full.run_id.isin(selected_ids)].to_csv(all_output / "selected_comparison.csv", index=False)
    example_rows = []
    sources = [("popularity", ROOT / "reports/popularity/predictions_allow_repeats.csv")]
    for method, value in selected.items():
        folder = ROOT / "reports/models" if method in previous else OUTPUT
        sources.append((value["run_id"], folder / "runs" / value["run_id"] / "predictions.csv"))
    from evaluate_rankings import read_rankings
    labels = data["candidates"].set_index("tv_show_id")
    for model, path in sources:
        predictions = read_rankings(path)
        for example in data["examples"]:
            user = example["user_id"]
            ap = evaluate_rankings(data["truth"], predictions, users=[user])[0]["map_at_5"]
            for rank, item in enumerate(predictions[user], 1):
                label = labels.loc[item]
                example_rows.append({"model": model, "role": example["role"], "user_id": user, "rank": rank,
                                     "tv_show_id": item, "title": label.tv_show_title, "category": label.tv_show_category,
                                     "training_user_airings": data["own_counts"].get((user, item), 0),
                                     "in_true_validation_top5": item in data["truth_sets"][user],
                                     "qualified_validation_watch": item in data["any_validation"].get(user, set()), "user_AP_at_5": ap})
    pd.DataFrame(example_rows).to_csv(all_output / "recommendation_examples.csv", index=False)
    print(comparison[["run_id", "cohort", "map_at_5", "precision_at_5"]].to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["initial", "diagnostic", "all"], default="initial")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    plan = json.loads((Path(__file__).parent / "content_rule_experiments.json").read_text())
    configs = plan["initial"] + plan["diagnostic"] if args.stage == "all" else plan[args.stage]
    if args.run_id:
        configs = [c for c in plan["initial"] + plan["diagnostic"] if c["id"] == args.run_id]
    if not configs:
        parser.error("No declared configuration selected")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    data = load_data()
    # Existing MF/PPR warm Top-5s all have positive scores; the positive-signal
    # backfill convention therefore leaves their saved predictions unchanged.
    for path in (ROOT / "reports/models/runs").glob("*/recommendations.csv"):
        recs = pd.read_csv(path, dtype={"user_id": str})
        if not (recs.loc[~recs.fallback, "model_score"] > 0).all():
            raise AssertionError("Previous model needs explicit zero-signal policy reconciliation")
    documents, provenance = metadata_snapshot()
    dump(ARTIFACTS / "metadata_snapshot.json", {"provenance": provenance, "items": documents})
    dump(OUTPUT / "experiment_plan.json", plan)
    dump(OUTPUT / "metadata_provenance.json", provenance)
    with threadpool_limits(limits=1):
        for config in configs:
            print(f"Running {config['id']} ...", flush=True)
            if config["method"] == "content_based":
                run_content(config, data, documents, provenance)
            else:
                run_rules(config, data, documents)
            refresh(data)


if __name__ == "__main__":
    main()
