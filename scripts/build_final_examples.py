#!/usr/bin/env python3
"""Export training-selected heavy/light validation evidence for the final report."""

import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from evaluate_rankings import read_rankings
from ranking_metrics import average_precision_at_k
from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/final_examples"
CF = ROOT / "artifacts/recency_extension/validation/mf8_ppr8_rulesraw_popraw"
METHODS = ["popularity", "cbf", "association_rules", "mf", "ppr", "hybrid_007"]
LABELS = {"popularity": "Popularity", "cbf": "CBF", "association_rules": "Association rules", "mf": "MF", "ppr": "PPR", "hybrid_007": "Final 007 hybrid"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = {
        "final_selection": ROOT / "submissions/final_selection.json",
        "user_metadata": ROOT / "reports/interactions/validation_users.csv",
        "primary_cohort": ROOT / "reports/popularity/cohort_primary.csv",
        "truth": ROOT / "reports/interactions/validation_ground_truth.csv",
        "canonical_metadata": ROOT / "reports/popularity/validation_candidates.csv",
        "airings": ROOT / "artifacts/interactions/airings.parquet",
        "events": ROOT / "artifacts/interactions/airing_interactions.parquet",
        "programme_interactions": ROOT / "artifacts/interactions/user_programme_interactions.parquet",
        "counts50": ROOT / "artifacts/training_study/full10_t50/training_counts.parquet",
        "counts80": ROOT / "artifacts/training_study/full10_t80/training_counts.parquet",
        "recency_counts": ROOT / "artifacts/refinement/validation/h8/weighted_counts.parquet",
        "recency_metadata": ROOT / "artifacts/refinement/validation/h8/recency.json",
        "cf_scores": CF / "scores.npz", "cf_users": CF / "users.json", "pop_order": CF / "candidate_scores.csv",
        "hybrid_config": ROOT / "reports/recency_extension/runs/h8_rules01875_pop00625/config.json",
        "hybrid_predictions": ROOT / "reports/recency_extension/runs/h8_rules01875_pop00625/predictions.csv",
        "cbf_predictions": ROOT / "reports/content_rules/runs/cbf_title_tfidf_count/predictions.csv",
        "cbf_vectors": ROOT / "artifacts/content_rules/cbf_title_tfidf_count/item_vectors.npz",
        "cbf_profiles": ROOT / "artifacts/content_rules/cbf_title_tfidf_count/query_profiles.npz",
        "cbf_items": ROOT / "artifacts/content_rules/cbf_title_tfidf_count/item_ids.npy",
        "cbf_users": ROOT / "artifacts/content_rules/cbf_title_tfidf_count/profile_user_ids.npy",
        "cbf_features": ROOT / "artifacts/content_rules/cbf_title_tfidf_count/feature_names.json",
        "rules": ROOT / "artifacts/training_study/full10_t80/association_rules/rules.parquet",
        "earlier_examples": ROOT / "reports/all_methods/recommendation_examples.csv",
    }
    for method in ["implicit_mf", "ppr", "association_rules", "popularity"]:
        paths[f"component_{method}"] = CF / f"component_{method}_top20.csv"
    for filename in ["dataset11-30.csv", "export_arh_11-20-final.csv", "export_arh_21-30-final.csv"]:
        paths[filename] = ROOT / "sweettv-tv-program-recommender" / filename
    before = {key: digest(path) for key, path in paths.items()}
    meta = pd.read_csv(paths["user_metadata"], dtype={"user_id": str})
    primary = set(pd.read_csv(paths["primary_cohort"], dtype=str).user_id)
    eligible = meta.loc[meta.user_id.isin(primary)].copy()
    warm = eligible.loc[eligible.train_watched_airings > 0]
    light = warm.sort_values(["train_watched_airings", "user_id"], kind="stable").iloc[0]
    heavy = warm.sort_values(["train_watched_airings", "user_id"], ascending=[False, True], kind="stable").iloc[0]
    choices = {"heavy": heavy.user_id, "light": light.user_id}
    users = list(choices.values())
    earlier = pd.read_csv(paths["earlier_examples"], dtype={"user_id": str})[["role", "user_id"]].drop_duplicates()
    if dict(earlier.itertuples(index=False, name=None)) != choices:
        raise AssertionError("Training rule no longer reproduces the earlier example users")
    rule = "Within the fixed 4030-user validation cohort, choose maximum/minimum nonzero original >=80% training-airing count; ties use ascending exact decimal user-ID string. No predictions/AP or validation behaviour beyond cohort eligibility are used."
    dump(OUT / "selection.json", {"selection_rule": rule, "users": choices, "cohort_users": len(eligible),
         "light_tie_count": int((warm.train_watched_airings == light.train_watched_airings).sum()),
         "heavy_tie_count": int((warm.train_watched_airings == heavy.train_watched_airings).sum()),
         "earlier_users_retained": True, "scope": "Assistant-selected boundary examples, not representative sample or student-personal verification"})
    truth = read_rankings(paths["truth"])
    metadata = pd.read_csv(paths["canonical_metadata"], keep_default_na=False).set_index("tv_show_id")
    interactions = pd.read_parquet(paths["programme_interactions"], filters=[("user_id", "in", users)])
    train80 = pd.read_parquet(paths["counts80"], filters=[("user_id", "in", users)])
    train50 = pd.read_parquet(paths["counts50"], filters=[("user_id", "in", users)])
    weighted = pd.read_parquet(paths["recency_counts"], filters=[("user_id", "in", users)])
    counts80 = {(u, int(i)): int(n) for u, i, n in train80[["user_id", "tv_show_id", "watched_airings"]].itertuples(index=False, name=None)}
    counts50 = {(u, int(i)): int(n) for u, i, n in train50[["user_id", "tv_show_id", "watched_airings"]].itertuples(index=False, name=None)}
    counts8 = {(u, int(i)): float(n) for u, i, n in weighted.itertuples(index=False, name=None)}
    events = pd.read_parquet(paths["events"], filters=[("user_id", "in", users), ("split", "==", "validation")])
    qualified = events.loc[events.watched_seconds*5 >= events.duration*4].copy()
    airings = pd.read_parquet(paths["airings"])
    train_lower = int(pd.Timestamp("2020-03-09", tz="Europe/Kyiv").timestamp())
    train_upper = int(pd.Timestamp("2020-05-18", tz="Europe/Kyiv").timestamp())
    precut_labels = airings.loc[(airings.start < train_upper) & (airings.end > train_lower)].sort_values(
        ["start", "source_file", "source_csv_record"], kind="stable").drop_duplicates("tv_show_id", keep="last").set_index("tv_show_id")
    watched = qualified.merge(airings[["airing_id", "tv_show_title", "tv_show_category", "source_file", "source_csv_record"]], on="airing_id", validate="many_to_one")
    watched.to_csv(OUT / "validation_qualified_airings.csv", index=False)
    events.to_csv(OUT / "validation_all_overlaps_airings.csv", index=False)
    profile_rows, actual_rows, selection_rows = [], [], []
    actual_lookup, actual_rank = {}, {}

    def canonical(item, fallback=None):
        title = str(metadata.loc[item, "tv_show_title"]) if item in metadata.index else ""
        category = str(metadata.loc[item, "tv_show_category"]) if item in metadata.index else ""
        if title:
            return title, category, "pre-cutoff catalogue representative"
        if item in precut_labels.index and str(precut_labels.loc[item, "tv_show_title"]):
            return str(precut_labels.loc[item, "tv_show_title"]), str(precut_labels.loc[item, "tv_show_category"]), "pre-cutoff historical schedule representative"
        if fallback is not None:
            return str(fallback.tv_show_title), str(fallback.tv_show_category), "latest qualified validation airing, descriptive lookup only"
        return f"Programme {item}", category, "ID only: no pre-cutoff label"

    for role, user in choices.items():
        future = watched.loc[watched.user_id == user]
        counts = future.groupby("tv_show_id").size().to_dict()
        ranked = sorted(counts, key=lambda item: (-counts[item], int(item)))
        if ranked[:5] != truth[user]:
            raise AssertionError("Actual independently aggregated Top-5 differs from frozen truth")
        actual_rank[user] = {int(item): n for n, item in enumerate(ranked, 1)}
        for n, item in enumerate(ranked, 1):
            group = future.loc[future.tv_show_id == item]
            latest = group.sort_values(["last_overlap", "start", "airing_id"], kind="stable").iloc[-1]
            title, category, source = canonical(item, latest)
            record = {"role": role, "user_id": user, "actual_rank": n, "tv_show_id": int(item), "title": title, "category": category,
                      "qualified_validation_airings": len(group), "qualified_watched_seconds": int(group.watched_seconds.sum()),
                      "in_true_top5": n <= 5, "latest_watched_title": latest.tv_show_title, "latest_watched_category": latest.tv_show_category,
                      "display_label_source": source, "latest_schedule_source_file": latest.source_file,
                      "latest_schedule_source_record": int(latest.source_csv_record), "latest_airing_id": int(latest.airing_id)}
            actual_rows.append(record)
            actual_lookup[(user, int(item))] = record
        past = interactions.loc[(interactions.user_id == user) & (interactions.split == "train")]
        restart_total = sum(np.log1p(n) for (u, item), n in counts8.items() if u == user)
        for row in past.itertuples(index=False):
            item = int(row.tv_show_id)
            title, category, label_source = canonical(item)
            profile_rows.append({"role": role, "user_id": user, "tv_show_id": item, "title": title, "category": category,
                                 "train_airings_80pct": counts80.get((user, item), 0), "train_airings_50pct": counts50.get((user, item), 0),
                                 "train_weighted_airings_h8": counts8.get((user, item), 0),
                                 "ppr_restart_share_h8": float(np.log1p(counts8.get((user, item), 0))/restart_total),
                                 "training_observed_seconds": int(row.total_watched_seconds), "last_training_overlap": int(row.last_overlap)})
        original = eligible.loc[eligible.user_id == user].iloc[0]
        selection_rows.append({"role": role, "user_id": user, "is_template_user": bool(original.is_test_user),
                               "train_airings_80pct": int(original.train_watched_airings), "train_programmes_80pct": int(original.train_qualified_programmes),
                               "train_airings_50pct": int(train50.loc[train50.user_id == user].watched_airings.sum()),
                               "train_programmes_50pct": int((train50.user_id == user).sum()),
                               "validation_airings_80pct": len(future), "validation_programmes_80pct": len(ranked),
                               "validation_fifth_sixth_count_tie": len(ranked) > 5 and counts[ranked[4]] == counts[ranked[5]]})
    pd.DataFrame(selection_rows).to_csv(OUT / "selected_users.csv", index=False)
    profiles = pd.DataFrame(profile_rows).sort_values(["role", "train_airings_80pct", "train_airings_50pct", "tv_show_id"], ascending=[True, False, False, True])
    profiles.to_csv(OUT / "training_profiles.csv", index=False)
    actual = pd.DataFrame(actual_rows)
    actual.to_csv(OUT / "validation_watches.csv", index=False)
    actual.loc[actual.in_true_top5].to_csv(OUT / "validation_true_top5.csv", index=False)
    interactions.loc[interactions.split == "validation"].to_csv(OUT / "validation_programme_overlaps.csv", index=False)
    predicted = {"cbf": read_rankings(paths["cbf_predictions"]), "hybrid_007": read_rankings(paths["hybrid_predictions"])}
    for method, source in [("popularity", "popularity"), ("association_rules", "association_rules"), ("mf", "implicit_mf"), ("ppr", "ppr")]:
        predicted[method] = {u: ids[:5] for u, ids in read_rankings(paths[f"component_{source}"]).items()}
    cf = np.load(paths["cf_scores"], allow_pickle=False)
    cf_users = json.loads(paths["cf_users"].read_text())
    cf_index = {u: n for n, u in enumerate(cf_users)}
    rows, metrics, side_by_side = [], [], []
    val_interactions = interactions.loc[interactions.split == "validation"].set_index(["user_id", "tv_show_id"])
    pop_counts = pd.read_csv(paths["pop_order"]).set_index("tv_show_id").training_watched_airings.to_dict()
    vectors = sparse.load_npz(paths["cbf_vectors"])
    cbf_profiles = sparse.load_npz(paths["cbf_profiles"])
    cbf_items = np.load(paths["cbf_items"], allow_pickle=False).astype(int).tolist()
    cbf_users = np.load(paths["cbf_users"], allow_pickle=False).tolist()
    cbf_index, cbf_user_index = {i: n for n, i in enumerate(cbf_items)}, {u: n for n, u in enumerate(cbf_users)}
    features = json.loads(paths["cbf_features"].read_text())
    feature_rows = []
    for role, user in choices.items():
        for method in METHODS:
            ids = predicted[method][user]
            ap = average_precision_at_k(truth[user], ids)
            metrics.append({"role": role, "user_id": user, "method": method, "method_label": LABELS[method], "hits_at_5": len(set(ids)&set(truth[user])), "AP_at_5": ap})
            for rank, item in enumerate(ids, 1):
                label, category, source = canonical(item)
                real = actual_lookup.get((user, item))
                count = real["qualified_validation_airings"] if real else 0
                overlap_seconds = int(val_interactions.loc[(user, item), "total_watched_seconds"]) if (user, item) in val_interactions.index else 0
                truth_position = actual_rank[user].get(item, 0)
                hit = item in truth[user]
                marker = "✓" if hit else "○" if count else "~" if overlap_seconds else "—"
                score = None
                if method == "popularity":
                    score = pop_counts.get(item, 0)
                elif method in ["mf", "ppr", "association_rules"]:
                    key = "implicit_mf" if method == "mf" else method
                    item_ids = cf[f"items_{key}"].astype(int).tolist()
                    score = float(cf[f"scores_{key}"][cf_index[user], item_ids.index(item)]) if item in item_ids else 0.
                elif method == "cbf":
                    product = cbf_profiles.getrow(cbf_user_index[user]).multiply(vectors.getrow(cbf_index[item])).tocsr()
                    score = float(product.sum())
                    for feature_index, value in zip(product.indices, product.data):
                        feature_rows.append({"role": role, "user_id": user, "rank": rank, "tv_show_id": item,
                                             "feature": features[feature_index], "feature_family": features[feature_index].split(":", 1)[0], "score_contribution": float(value)})
                record = {"role": role, "user_id": user, "method": method, "method_label": LABELS[method], "predicted_rank": rank,
                          "tv_show_id": item, "title": label, "category": category, "hit_marker": marker, "hit_true_top5": hit,
                          "qualified_validation_airings": count, "actual_frequency_rank": truth_position,
                          "validation_observed_seconds": overlap_seconds, "train_airings_80pct": counts80.get((user, item), 0),
                          "train_airings_50pct": counts50.get((user, item), 0), "train_weighted_airings_h8": counts8.get((user, item), 0),
                          "model_score": score, "user_AP_at_5": ap, "label_source": source}
                rows.append(record)
                true_row = actual_lookup[(user, truth[user][rank-1])]
                side_by_side.append({**record, "actual_top5_rank": rank, "actual_tv_show_id": true_row["tv_show_id"],
                                     "actual_title": true_row["title"], "actual_category": true_row["category"],
                                     "actual_latest_watched_title": true_row["latest_watched_title"], "actual_latest_watched_category": true_row["latest_watched_category"],
                                     "actual_qualified_airings": true_row["qualified_validation_airings"]})
    recs = pd.DataFrame(rows)
    recs.to_csv(OUT / "recommendations.csv", index=False)
    pd.DataFrame(side_by_side).to_csv(OUT / "side_by_side.csv", index=False)
    pd.DataFrame(metrics).to_csv(OUT / "method_metrics.csv", index=False)
    pd.DataFrame(feature_rows).to_csv(OUT / "cbf_feature_contributions.csv", index=False)
    for role in choices:
        recs.loc[recs.role == role].to_csv(OUT / f"{role}_recommendations.csv", index=False)
        actual.loc[actual.role == role].to_csv(OUT / f"{role}_validation_watches.csv", index=False)
    rule_table = pd.read_parquet(paths["rules"])
    rule_rows = []
    for role, user in choices.items():
        antecedents = train80.loc[train80.user_id == user].set_index("tv_show_id").watched_airings.to_dict()
        targets = set(predicted["association_rules"][user])
        for rule_row in rule_table.loc[rule_table.antecedent_id.isin(antecedents) & rule_table.consequent_id.isin(targets)].itertuples(index=False):
            count = int(antecedents[rule_row.antecedent_id])
            rule_rows.append({"role": role, "user_id": user, "antecedent_id": int(rule_row.antecedent_id), "antecedent_title": canonical(rule_row.antecedent_id)[0],
                              "consequent_id": int(rule_row.consequent_id), "consequent_title": canonical(rule_row.consequent_id)[0],
                              "train_antecedent_count": count, "joint_count": int(rule_row.joint_count), "confidence": float(rule_row.confidence), "lift": float(rule_row.lift),
                              "score_contribution": float(np.log1p(count)*rule_row.score_weight)})
    pd.DataFrame(rule_rows).to_csv(OUT / "association_rule_contributions.csv", index=False)
    hybrid = json.loads(paths["hybrid_config"].read_text())
    full_components = {m: read_rankings(paths[f"component_{m}"]) for m in hybrid["weights"]}
    pop_order = pd.read_csv(paths["pop_order"]).tv_show_id.astype(int).tolist()
    pop_rank = {i: n for n, i in enumerate(pop_order)}
    fusion_rows = []
    for role, user in choices.items():
        lists = {m: source[user][:5] for m, source in full_components.items()}
        union = set().union(*lists.values())
        exact_scores = {}
        for item in union:
            terms = {m: Fraction(str(hybrid["weights"][m]))/(ids.index(item)+1) if item in ids else Fraction(0) for m, ids in lists.items()}
            exact_scores[item] = sum(terms.values(), Fraction(0))
            row = {"role": role, "user_id": user, "tv_show_id": item, "title": canonical(item)[0], "category": canonical(item)[1],
                   "fusion_score": float(exact_scores[item]), "exact_fraction": str(exact_scores[item]), "selected": item in predicted["hybrid_007"][user], "hit_true_top5": item in truth[user]}
            for method, term in terms.items():
                row[f"{method}_rank"] = lists[method].index(item)+1 if item in lists[method] else 0
                row[f"{method}_contribution"] = float(term)
            fusion_rows.append(row)
        full_order = sorted(exact_scores, key=lambda item: (-exact_scores[item], pop_rank[item], item))
        for record in fusion_rows:
            if record["user_id"] == user:
                record["fusion_rank"] = full_order.index(record["tv_show_id"])+1
                record["training_popularity_rank"] = pop_rank[record["tv_show_id"]]+1
        rebuilt = full_order[:5]
        if rebuilt != predicted["hybrid_007"][user]:
            raise AssertionError("Example hybrid does not reproduce the final recipe")
    pd.DataFrame(fusion_rows).sort_values(["role", "fusion_rank"]).to_csv(OUT / "hybrid_score_contributions.csv", index=False)
    fused_scores = {(r["user_id"], r["tv_show_id"]): r["fusion_score"] for r in fusion_rows}
    for record in rows:
        if record["method"] == "hybrid_007":
            record["model_score"] = fused_scores[(record["user_id"], record["tv_show_id"])]
    for record in side_by_side:
        if record["method"] == "hybrid_007":
            record["model_score"] = fused_scores[(record["user_id"], record["tv_show_id"])]
    recs = pd.DataFrame(rows)
    recs.to_csv(OUT / "recommendations.csv", index=False)
    pd.DataFrame(side_by_side).to_csv(OUT / "side_by_side.csv", index=False)
    for role in choices:
        recs.loc[recs.role == role].to_csv(OUT / f"{role}_recommendations.csv", index=False)
    definitions = [
        {"method": "popularity", "configuration": "Unweighted full-training >=50% qualified-airing popularity", "prediction_source": str(paths["component_popularity"].relative_to(ROOT))},
        {"method": "cbf", "configuration": "Selected rich+title TF-IDF cosine/count profile; original >=80% history and pre-May18 metadata", "prediction_source": str(paths["cbf_predictions"].relative_to(ROOT))},
        {"method": "association_rules", "configuration": "Unweighted strict80 weekly rules, joint>=5/confidence>=.1/lift>1, log-count query", "prediction_source": str(paths["component_association_rules"].relative_to(ROOT))},
        {"method": "mf", "configuration": "Final007 component: 50% history, eight-week mass-preserving counts, f16/log-target/confidence1/reg1/15 epochs", "prediction_source": str(paths["component_implicit_mf"].relative_to(ROOT))},
        {"method": "ppr", "configuration": "Final007 component: raw graph alpha .5, eight-week 50% log-count restarts", "prediction_source": str(paths["component_ppr"].relative_to(ROOT))},
        {"method": "hybrid_007", "configuration": "Final007 recipe: RRF MF=.5/PPR=.5/rules=.1875/pop=.0625, depth5/offset0", "prediction_source": str(paths["hybrid_predictions"].relative_to(ROOT))},
    ]
    pd.DataFrame(definitions).to_csv(OUT / "method_definitions.csv", index=False)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    dump(OUT / "summary.json", {"selection_rule": rule, "selected_users": choices, "methods": definitions,
         "training_window_local": ["2020-03-09", "2020-05-18"], "validation_window_local": ["2020-05-18", "2020-07-27"],
         "time_policy": "Half-open Europe/Kyiv boundaries; interval arithmetic UTC; full airing-duration denominator; exact >=80% truth",
         "labels": "Canonical pre-cutoff ID-level representative labels; episode titles may vary. Actual latest watched titles and schedule records are saved separately.",
         "hits": "A hit is membership anywhere in the frozen five-ID truth, not rank-aligned equality. Watched-but-outside-Top5 is not a hit.",
         "markers": {"✓": "True Top-5 hit", "○": "Qualified validation watch, outside true Top-5", "~": "Only partial observed overlap; no >=80% watch", "—": "No recorded validation programme overlap"},
         "numerical_verification": "Assistant checks only; student's personal review remains pending", "experiments": "Closed; report evidence only, no fitting or tuning",
         "code_sha256": digest(Path(__file__))})
    if before != {key: digest(path) for key, path in paths.items()}:
        raise AssertionError("Source data/predictions changed")
    print(pd.DataFrame(selection_rows).to_string(index=False))
    print(pd.DataFrame(metrics).to_string(index=False))
    print(f"Saved example facts under {OUT}")


if __name__ == "__main__":
    main()
