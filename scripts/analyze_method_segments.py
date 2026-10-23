#!/usr/bin/env python3
"""Analyze selected methods on fixed strict-history segments before hybrids."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from interaction_core import boundary_epoch
from ranking_metrics import evaluate_rankings
from segment_analysis import complementarity, distinct_bucket, history_metrics, novelty_metrics, true_hit_rows, volume_bucket

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/training_study/reference_analysis"


def build_reference_tables():
    truth = read_rankings(ROOT / "reports/interactions/validation_ground_truth.csv")
    user_features = pd.read_csv(ROOT / "reports/interactions/validation_users.csv", dtype={"user_id": str})
    user_features = user_features.loc[user_features.primary_validation_eligible].copy()
    programmes = pd.read_parquet(ROOT / "artifacts/interactions/user_programme_interactions.parquet")
    train = programmes.loc[programmes.split == "train"]
    rows = [{"user_id": user, "truth_rank": rank, "tv_show_id": item} for user, ids in truth.items() for rank, item in enumerate(ids, 1)]
    meta = pd.DataFrame(rows).merge(train[["user_id", "tv_show_id", "watched_airings", "overlap_airings", "total_watched_seconds"]],
                                    on=["user_id", "tv_show_id"], how="left", validate="one_to_one")
    for col in ["watched_airings", "overlap_airings", "total_watched_seconds"]:
        meta[col] = meta[col].fillna(0).astype("int64")
    meta["familiarity"] = np.where(meta.watched_airings > 0, "familiar_80pct", "new_qualified_for_user")
    meta["exposure"] = np.where(meta.watched_airings > 0, "familiar_80pct", np.where(meta.overlap_airings > 0, "new_but_partial_training_overlap", "new_no_recorded_training_overlap"))
    globally_seen = set(train.loc[train.watched_airings > 0, "tv_show_id"])
    meta["global_support"] = np.where(meta.tv_show_id.isin(globally_seen), "has_global_strict_training_support", "no_global_strict_training_support")
    events = pd.read_parquet(ROOT / "artifacts/interactions/airing_interactions.parquet",
                             columns=["split", "user_id", "first_overlap", "last_overlap", "watched_80pct"])
    events = events.loc[(events.split == "train") & events.watched_80pct].copy()
    times = pd.to_datetime(events.first_overlap, unit="s", utc=True).dt.tz_convert("Europe/Kyiv")
    iso = times.dt.isocalendar()
    events["week"] = iso.year.astype(str) + "-" + iso.week.astype(str)
    activity = events.groupby("user_id").agg(active_weeks=("week", "nunique"), last_active=("last_overlap", "max"))
    user_features["active_weeks"] = user_features.user_id.map(activity.active_weeks).fillna(0).astype(int)
    user_features["last_activity_age_days"] = (boundary_epoch("2020-05-18")-user_features.user_id.map(activity.last_active))/86400
    user_features["history_distinct"] = user_features.train_qualified_programmes.map(distinct_bucket)
    user_features["history_volume"] = user_features.train_watched_airings.map(volume_bucket)
    user_features["active_week_span"] = user_features.active_weeks.map(lambda n: "0 (cold)" if n==0 else "1-3" if n<=3 else "4-7" if n<=7 else "8-10")
    user_features["last_activity_age"] = user_features.last_activity_age_days.map(lambda n: "cold" if pd.isna(n) else "0-7 days" if n<=7 else "8-28 days" if n<=28 else "29+ days")
    cohorts = {"all_primary": user_features.user_id.tolist(), "template_primary": user_features.loc[user_features.is_test_user, "user_id"].tolist()}
    return truth, meta, user_features, cohorts


def prediction_sources():
    selected = json.loads((ROOT / "reports/all_methods/selected_models.json").read_text())
    sources = {"popularity": ROOT / "reports/popularity/predictions_allow_repeats.csv"}
    for method, info in selected.items():
        folder = "models" if method in {"implicit_mf", "ppr"} else "content_rules"
        sources[method] = ROOT / "reports" / folder / "runs" / info["run_id"] / "predictions.csv"
    return sources


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    truth, meta, user_features, cohorts = build_reference_tables()
    meta.to_csv(OUT / "true_answer_attributes.csv", index=False)
    user_features.to_csv(OUT / "user_features.csv", index=False)
    novelty, history, overall, predictions, aps = [], [], [], {}, {}
    for method, source in prediction_sources().items():
        predicted = read_rankings(source)
        predictions[method] = predicted
        metrics, records = evaluate_rankings(truth, predicted, users=cohorts["all_primary"])
        aps[method] = {r["user_id"]: r["ap_at_5"] for r in records}
        hit_rows = true_hit_rows(meta, predicted)
        if abs(hit_rows.AP_contribution.sum()/len(truth)-metrics["map_at_5"]) > 1e-14:
            raise AssertionError("AP decomposition must preserve the original metric")
        n = novelty_metrics(hit_rows, cohorts)
        n["method"] = method
        novelty.append(n)
        h = history_metrics(pd.DataFrame(records), user_features[["user_id", "history_distinct", "history_volume", "active_week_span", "last_activity_age"]], cohorts)
        h["method"] = method
        history.append(h)
        for cohort, users in cohorts.items():
            metric, _ = evaluate_rankings(truth, predicted, users=users)
            overall.append(dict(method=method, cohort=cohort, **metric))
    pd.concat(novelty, ignore_index=True).to_csv(OUT / "novelty_metrics.csv", index=False)
    pd.concat(history, ignore_index=True).to_csv(OUT / "history_metrics.csv", index=False)
    pd.DataFrame(overall).to_csv(OUT / "overall_metrics.csv", index=False)
    pair, unique, distribution = complementarity(predictions, truth, aps, cohorts)
    pair.to_csv(OUT / "pairwise_complementarity.csv", index=False)
    unique.to_csv(OUT / "exclusive_hits.csv", index=False)
    distribution.to_csv(OUT / "hit_overlap_distribution.csv", index=False)
    definitions = {"familiar": "At least one original >=80% qualifying training airing over full weeks 11-20",
                   "new": "No such qualifying training watch; may still have partial recorded exposure",
                   "history_bins": "Fixed original strict/full history, not redefined after soft/recent experiments",
                   "AP_decomposition": "Credit from original AP@5 assigned to the true hit's type; retain all hit precisions and denominator five",
                   "overlap": "Separate any-hit user overlap, correct (user,programme) pair overlap and recommendation-list overlap; no hybrid trained"}
    (OUT / "definitions.json").write_text(json.dumps(definitions, indent=2) + "\n")
    print(pd.concat(novelty).query("cohort == 'all_primary' and axis == 'familiarity'")[["method", "segment", "true_slots", "hits", "recall_of_true_type_micro"]].to_string(index=False))
    print(pair.query("cohort == 'all_primary' and method_a == 'implicit_mf' and method_b == 'ppr'").to_string(index=False))


if __name__ == "__main__":
    main()
