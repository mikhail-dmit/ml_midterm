#!/usr/bin/env python3
"""Evaluate the sole baseline (global popularity) with repeats allowed/excluded."""

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from interaction_core import LOCAL_WINDOWS, boundary_epoch
from popularity_core import available_candidates, fit_popularity, rank_candidates, recommend_popularity
from ranking_metrics import evaluate_rankings, rank_contributions

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interaction-dir", type=Path, default=ROOT / "artifacts" / "interactions")
    parser.add_argument("--label-dir", type=Path, default=ROOT / "reports" / "interactions")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "popularity")
    args = parser.parse_args()
    started = time.perf_counter()
    truth_path = args.label_dir / "validation_ground_truth.csv"
    truth = read_rankings(truth_path)
    cohort_users = pd.read_csv(args.label_dir / "validation_users.csv", dtype={"user_id": str})
    primary = cohort_users.loc[cohort_users.primary_validation_eligible].copy()
    cohort = primary.user_id.tolist()
    template = primary.loc[primary.is_test_user, "user_id"].tolist()
    if len(cohort) != 4030 or len(template) != 1150 or set(cohort) != set(truth):
        raise AssertionError("Expected the previously constructed 4,030 / 1,150 cohorts")
    programmes = pd.read_parquet(args.interaction_dir / "user_programme_interactions.parquet")
    airings = pd.read_parquet(args.interaction_dir / "airings.parquet")
    train = programmes.loc[programmes.split == "train"].copy()
    # Only this training frame is passed into fitting/history construction.
    fit_started = time.perf_counter()
    scores, seen = fit_popularity(train)
    fit_seconds = time.perf_counter() - fit_started
    lower, upper = [boundary_epoch(x) for x in LOCAL_WINDOWS["validation"]]
    candidate_ids = available_candidates(airings, lower, upper)
    ranked = rank_candidates(scores, candidate_ids)
    ranked_ids = [int(x) for x in ranked.tv_show_id]
    candidate_set = set(candidate_ids)
    if any(not set(ids).issubset(candidate_set) for ids in truth.values()):
        raise AssertionError("A fixed validation truth ID is missing from the schedule pool")
    # Explanatory labels from the most recent pre-cutoff scheduled airing only.
    train_start = boundary_epoch(LOCAL_WINDOWS["train"][0])
    lookup = airings.loc[(airings.start < lower) & (airings.end > train_start)].sort_values(
        ["start", "channel_id", "airing_id"], kind="stable").drop_duplicates("tv_show_id", keep="last")
    ranked = ranked.merge(lookup[["tv_show_id", "tv_show_title", "tv_show_category"]], on="tv_show_id", how="left", validate="one_to_one")
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    ranked["tv_show_title"] = ranked.tv_show_title.fillna("")
    ranked["tv_show_category"] = ranked.tv_show_category.fillna("")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(args.output_dir / "validation_candidates.csv", index=False)
    scores.sort_values(["training_watched_airings", "tv_show_id"], ascending=[False, True]).to_csv(args.output_dir / "training_popularity.csv", index=False)
    pd.DataFrame({"user_id": cohort}).to_csv(args.output_dir / "cohort_primary.csv", index=False)
    pd.DataFrame({"user_id": template}).to_csv(args.output_dir / "cohort_template_primary.csv", index=False)
    results, predictions, all_records, policy_times = [], {}, [], {}
    cohorts = {"all_primary": cohort, "template_primary": template}
    for policy, allow in [("allow_repeats", True), ("exclude_repeats", False)]:
        pred_started = time.perf_counter()
        predictions[policy] = {u: recommend_popularity(ranked_ids, u, seen, allow) for u in cohort}
        policy_times[policy] = time.perf_counter() - pred_started
        pd.DataFrame({"user_id": cohort, "tv_show_id": [" ".join(map(str, predictions[policy][u])) for u in cohort]}).to_csv(
            args.output_dir / f"predictions_{policy}.csv", index=False)
        for label, selected_users in cohorts.items():
            metric, records = evaluate_rankings(truth, predictions[policy], users=selected_users)
            available_true = [len(set(truth[u]) - (set() if allow else seen.get(u, set()))) for u in selected_users]
            repeat_true = [len(set(truth[u]) & seen.get(u, set())) for u in selected_users]
            available_sizes = [len(candidate_set - (set() if allow else seen.get(u, set()))) for u in selected_users]
            metric.update({"policy": policy, "cohort": label,
                           "training_cold_users": sum(not seen.get(u) for u in selected_users),
                           "mean_available_candidates": float(np.mean(available_sizes)),
                           "min_available_candidates": min(available_sizes),
                           "truth_items_previously_watched": sum(repeat_true),
                           "truth_items_total": 5 * len(selected_users),
                           "truth_repeat_fraction": sum(repeat_true) / (5 * len(selected_users)),
                           "unreachable_truth_items_under_policy": sum(5 - n for n in available_true),
                           "users_all_truth_unreachable": sum(n == 0 for n in available_true),
                           "policy_oracle_map_ceiling": sum(available_true) / (5 * len(selected_users))})
            results.append(metric)
            if label == "all_primary":
                for row in records:
                    u = row["user_id"]
                    row.update({"policy": policy, "is_template_user": u in set(template),
                                "training_cold_start": not bool(seen.get(u)),
                                "truth_previously_watched": len(set(truth[u]) & seen.get(u, set())),
                                "true_ids": " ".join(map(str, truth[u])),
                                "predicted_ids": " ".join(map(str, predictions[policy][u])),
                                "hits_that_repeat_training": len(set(predictions[policy][u]) & set(truth[u]) & seen.get(u, set()))})
                    all_records.append(row)
    pd.DataFrame(results).to_csv(args.output_dir / "metrics.csv", index=False)
    per_user = pd.DataFrame(all_records)
    per_user.to_csv(args.output_dir / "per_user_metrics.csv", index=False)
    repeats = {}
    for label, selected_users in cohorts.items():
        selected = per_user.loc[per_user.user_id.isin(selected_users)]
        pivot = selected.pivot(index="user_id", columns="policy", values="ap_at_5")
        repeat_hits = selected.loc[selected.policy == "allow_repeats", "hits_that_repeat_training"].sum()
        hits = selected.loc[selected.policy == "allow_repeats", "hits_at_5"].sum()
        repeats[label] = {"users_allow_better": int((pivot.allow_repeats > pivot.exclude_repeats).sum()),
                          "users_exclude_better": int((pivot.exclude_repeats > pivot.allow_repeats).sum()),
                          "users_equal": int((pivot.exclude_repeats == pivot.allow_repeats).sum()),
                          "allow_hits_from_previously_watched_items": int(repeat_hits),
                          "allow_total_hits": int(hits)}
    interaction_summary = json.loads((args.label_dir / "summary.json").read_text(encoding="utf-8"))
    example_user = interaction_summary["manual_example"]["user_id"]
    examples = []
    title_map = ranked.set_index("tv_show_id").tv_show_title.to_dict()
    for policy in predictions:
        for row in rank_contributions(truth[example_user], predictions[policy][example_user]):
            row.update({"user_id": example_user, "policy": policy, "title": title_map[row["tv_show_id"]],
                        "previously_watched": row["tv_show_id"] in seen.get(example_user, set())})
            examples.append(row)
    pd.DataFrame(examples).to_csv(args.output_dir / "example_rank_contributions.csv", index=False)
    config = {
        "metric": "MAP@5 = macro mean of sum(precision@r * first relevant hit at r) / min(5, number of distinct true IDs)",
        "empty_truth": "AP helper returns zero; cohort evaluator rejects empty truth to prevent silent cohort changes",
        "prediction_validation": "Exactly five distinct positive programme IDs per user; missing users are errors",
        "truth_order": "Ignored by AP: relevant-ID membership matters; prediction order matters",
        "training_window_local": list(LOCAL_WINDOWS["train"]), "validation_window_local": list(LOCAL_WINDOWS["validation"]),
        "candidate_pool": "All nonzero, positive-duration programme IDs with any airing overlap with the validation window, from supplied historical schedules",
        "candidate_pool_size": len(candidate_ids),
        "candidate_items_with_positive_training_score": int((ranked.training_watched_airings > 0).sum()),
        "candidate_items_with_zero_training_score": int((ranked.training_watched_airings == 0).sum()),
        "popularity_score": "Total qualifying training user-airing watches per programme, summed over all training users, not only evaluation users",
        "training_users_with_qualified_watches": len(seen), "training_qualified_airings": int(scores.training_watched_airings.sum()),
        "training_items_with_qualified_watches": len(scores),
        "ranking_ties": "Descending training popularity count, then ascending numeric programme ID; zero-score items remain in pool",
        "already_watched_definition": "At least one >=80%-qualified training airing of that programme ID; partial-only overlaps do not trigger the mask",
        "ground_truth_under_exclude_repeats": "Unchanged original five IDs; no pruning, relabelling, denominator reduction or user exclusion",
        "cold_start": "Same global training-popularity list; empty seen set gives identical output under both policies",
        "recommended_shared_policy": "allow_repeats",
        "label_uncertainty": "Local labels use numeric-ID tie-break; 2630/4030 users have a fifth/sixth frequency tie",
    }
    summary = {"protocol": config, "metrics": results, "paired_policy_comparison": repeats,
               "example_user": example_user,
               "source_files_sha256": {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): digest(p) for p in [truth_path,
                   args.label_dir / "validation_users.csv", args.interaction_dir / "user_programme_interactions.parquet", args.interaction_dir / "airings.parquet"]},
               "source_scripts_sha256": {name: digest(Path(__file__).parent / name) for name in ["ranking_metrics.py", "popularity_core.py", "evaluate_popularity.py"]},
               "runtime": {"fit_seconds": fit_seconds, "prediction_seconds": policy_times,
                           "total_seconds": time.perf_counter() - started, "python_platform": platform.platform(), "pandas": pd.__version__},
               "verification": "See verify_popularity.py and verification.json; student personal verification not claimed"}
    dump_json(args.output_dir / "summary.json", summary)
    dump_json(args.output_dir / "protocol.json", config)
    lines = ["# Popularity baseline and MAP@5", "", "## Shared evaluation protocol", "",
             "- Training: weeks 11–20. Validation: weeks 21–30; original five-ID local truth is unchanged under both repeat policies.",
             f"- Candidate pool: **{len(candidate_ids):,} nonzero programme IDs** with positive-duration airings overlapping validation. Selection uses schedule availability, not validation viewing.",
             f"- Popularity: sum of qualifying training airing counts over **all {len(seen):,} training users**. Total qualifying training watches: **{int(scores.training_watched_airings.sum()):,}**.",
             "- Repeats excluded means masking only programmes with a qualifying training watch for that user. Partial-only viewing is not called watched.",
             "- Missing items get popularity zero; count ties are broken by numeric ID. Cold users receive the common popularity fallback.",
             "- Exactly five distinct predictions per user. No ground-truth pruning, denominator changes, warm-user filtering or silent exclusions.",
             "", "## Formula", "",
             "AP@5 = sum over ranks 1..5 of [precision@rank × first-relevant-hit indicator] / min(5, number of distinct true IDs). MAP@5 is the unweighted mean across the explicit cohort. Here each user's truth has five IDs, so the AP denominator is always five.",
             "Prediction duplicates cannot earn credit twice; strict CSV evaluation rejects duplicate or short lists. Truth order is not a graded relevance level.",
             "", "## Results", "", "| Cohort | Users | Repeat policy | MAP@5 | Precision@5 | Hit rate@5 |", "|---|---:|---|---:|---:|---:|"]
    for row in results:
        lines.append(f"| {row['cohort']} | {row['users']:,} | {row['policy']} | {row['map_at_5']:.8f} | {row['precision_at_5']:.8f} | {row['hit_rate_at_5']:.8f} |")
    lines += ["", "Recall@5 equals Precision@5 here because both the predicted and true lists have five distinct IDs.",
              "", "## Why repeat filtering changes the task", "",
              "| Cohort | True IDs previously watched in training | Share | No-repeat oracle MAP@5 ceiling | Users with all five true IDs masked |",
              "|---|---:|---:|---:|---:|"]
    for row in results:
        if row["policy"] == "exclude_repeats":
            lines.append(f"| {row['cohort']} | {row['truth_items_previously_watched']:,} / {row['truth_items_total']:,} | {row['truth_repeat_fraction']:.2%} | {row['policy_oracle_map_ceiling']:.8f} | {row['users_all_truth_unreachable']:,} |")
    lines += ["", "The ceiling is a diagnostic bound, not a trained method: rank every still-eligible true ID first. With five original truth IDs it is the retained true count / 5, averaged over users.",
              "", "## Decision", "",
              "Use the schedule-availability pool and **allow repeats** for the shared protocol. This task predicts future favourite programmes, not exclusively discovery of programmes absent from recorded training history. The no-repeat run remains a documented policy comparison.",
              "", "## Reproducing and inspecting", "", "```bash", "python3 -m unittest discover -s scripts -p 'test_ranking.py'",
              "python3 scripts/evaluate_popularity.py", "python3 scripts/verify_popularity.py", "```", "",
              "`validation_candidates.csv` fixes the shared pool/ranking; `predictions_*.csv` contain predictions for all 4030 primary users; `cohort_template_primary.csv` identifies the 1150-user subset. See metrics.csv, per_user_metrics.csv and example_rank_contributions.csv for traceable results.",
              "The teacher's two AP@5 examples are unit-tested (11/12 and 8/15). No Kaggle submission or remote-score verification was performed by this local evaluation.",
              "Local label uncertainty remains: the organiser's fifth-place frequency tie-break is unspecified. This evaluation retains the already documented local labels.", ""]
    (args.output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(pd.DataFrame(results)[["cohort", "users", "policy", "map_at_5", "precision_at_5", "hit_rate_at_5"]].to_string(index=False))
    print(json.dumps({"protocol": config, "paired_policy_comparison": repeats, "runtime": summary["runtime"]}, indent=2))


if __name__ == "__main__":
    main()
