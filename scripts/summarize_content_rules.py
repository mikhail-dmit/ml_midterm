#!/usr/bin/env python3
"""Create report-ready CBF/rule diagnoses and the full four-method comparison."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/content_rules"
ALL = ROOT / "reports/all_methods"


def main():
    runs = {p.parent.name: json.loads(p.read_text()) for p in (OUT / "runs").glob("*/summary.json")}
    plan = json.loads((OUT / "experiment_plan.json").read_text())
    selected = json.loads((ALL / "selected_models.json").read_text())
    comparison = pd.read_csv(ALL / "selected_comparison.csv")
    verification = json.loads((OUT / "verification.json").read_text())
    examples = pd.read_csv(ALL / "recommendation_examples.csv", dtype={"user_id": str})
    cbf, ar = selected["content_based"]["run_id"], selected["association_rules"]["run_id"]
    details = pd.read_csv(OUT / "runs" / cbf / "recommendations.csv", dtype={"user_id": str})
    zero_support = details.training_watched_airings == 0
    metadata_snapshot = json.loads((ROOT / "artifacts/content_rules/metadata_snapshot.json").read_text())
    metadata_ids = {doc["tv_show_id"] for doc in metadata_snapshot["items"]}
    trained_ids = set(pd.read_csv(ROOT / "reports/popularity/training_popularity.csv").tv_show_id)
    true_ids = pd.read_csv(ROOT / "reports/interactions/validation_ground_truth.csv", dtype=str).tv_show_id
    unseen_truth = [int(item) for cell in true_ids for item in cell.split() if int(item) not in trained_ids]
    new_item_findings = {"recommendation_slots_without_any_qualified_training_view": int(zero_support.sum()),
                         "hits_among_these_slots": int(details.loc[zero_support, "in_true_top5"].sum()),
                         "true_slots_without_collaborative_training_support": len(unseen_truth),
                         "true_slots_without_collaborative_support_but_with_frozen_metadata": sum(item in metadata_ids for item in unseen_truth),
                         "true_slots_without_collaborative_support_or_frozen_metadata": sum(item not in metadata_ids for item in unseen_truth),
                         "scope": "CBF can score past-schedule items lacking collaborative history; a novel item is not automatically useful discovery"}
    (OUT / "content_new_item_diagnostics.json").write_text(json.dumps(new_item_findings, indent=2) + "\n")
    feature_contributions = pd.read_csv(OUT / "runs" / cbf / "example_feature_contributions.csv", dtype={"user_id": str})
    feature_contributions["family"] = feature_contributions.feature.str.split(":", n=1).str[0]
    feature_contributions.groupby(["user_id", "rank", "tv_show_id", "family"], as_index=False).score_contribution.sum().to_csv(
        OUT / "selected_content_family_contributions.csv", index=False)
    # Report one real rule using all its raw counts and basket definition.
    rules = pd.read_parquet(ROOT / "artifacts/content_rules" / ar / "rules.parquet")
    example_rule = rules.sort_values(["confidence", "joint_count"], ascending=False).iloc[0]
    manual_rule = {key: int(example_rule[key]) for key in ["antecedent_id", "consequent_id", "antecedent_count", "consequent_count", "joint_count", "baskets", "distinct_training_users_joint"]}
    manual_rule.update({"basket_definition": runs[ar]["config"]["baskets"],
                        "support": float(example_rule.support), "confidence": float(example_rule.confidence), "lift": float(example_rule.lift),
                        "student_verification": "Not performed or claimed; raw counts are provided for a later hand calculation"})
    (OUT / "manual_rule_calculation.json").write_text(json.dumps(manual_rule, indent=2) + "\n")
    baseline = pd.read_csv(ROOT / "reports/popularity/per_user_metrics.csv", dtype={"user_id": str})
    baseline = baseline.loc[baseline.policy == "allow_repeats"].set_index("user_id").ap_at_5
    ap = {"popularity": baseline}
    for method, item in selected.items():
        folder = ROOT / "reports/models" if method in {"implicit_mf", "ppr"} else OUT
        ap[item["run_id"]] = pd.read_csv(folder / "runs" / item["run_id"] / "per_user_metrics.csv", dtype={"user_id": str}).set_index("user_id").ap_at_5
    template = pd.read_csv(ROOT / "reports/popularity/cohort_template_primary.csv", dtype=str).user_id.tolist()
    rng = np.random.default_rng(20261023)
    pairs = [(cbf, "popularity"), (ar, "popularity"), (ar, selected["implicit_mf"]["run_id"]), (ar, selected["ppr"]["run_id"])]
    intervals = []
    for cohort, ids in [("all_primary", baseline.index.tolist()), ("template_primary", template)]:
        for a, b in pairs:
            delta = (ap[a].loc[ids] - ap[b].loc[ids]).to_numpy()
            means = delta[rng.integers(0, len(ids), size=(2000, len(ids)))].mean(axis=1)
            intervals.append({"cohort": cohort, "model_a": a, "model_b": b, "users": len(ids),
                              "mean_MAP_difference": float(delta.mean()), "conditional_95pct_lower": float(np.quantile(means, .025)),
                              "conditional_95pct_upper": float(np.quantile(means, .975))})
    pd.DataFrame(intervals).to_csv(ALL / "paired_comparisons.csv", index=False)
    def score(run, cohort=0):
        return runs[run]["metrics"][cohort]["map_at_5"]
    lines = ["# Content-based filtering and association rules", "",
             "## Fixed protocol and result", "",
             "Training weeks 11–20, validation weeks 21–30, original >=80%-watch labels, repeats allowed, all 6,384 schedule-available candidates, original MAP@5 evaluator. All-primary (4,030) selects settings; template-primary (1,150) is reporting only.",
             "", "| Method | Selected run | MAP@5 all primary | MAP@5 template primary |", "|---|---|---:|---:|"]
    for method, run_id in [("Popularity", "popularity")] + [(method, info["run_id"]) for method, info in selected.items()]:
        rows = comparison.loc[comparison.run_id == run_id].set_index("cohort")
        lines.append(f"| {method} | {run_id} | {rows.loc['all_primary', 'map_at_5']:.8f} | {rows.loc['template_primary', 'map_at_5']:.8f} |")
    lines += ["", "PPR remains the highest observed standalone result. Weekly association rules beat popularity but remain below MF/PPR. The improved content method remains below popularity; that negative result is retained.",
              "", "## All new experiments", "", "| Configuration | MAP@5 all 4,030 | MAP@5 template 1,150 |", "|---|---:|---:|"]
    for config in plan["initial"] + plan["diagnostic"]:
        lines.append(f"| {config['id']} | {score(config['id']):.8f} | {score(config['id'], 1):.8f} |")
    lines += ["", "## Content method and leakage boundary", "",
              "- The metadata snapshot contains 5,842 labelled programme IDs from 115,316 positive-duration airings starting before the validation cutoff. The second schedule contributes zero rows to feature fitting. Source hashes and cutoff timestamps are in metadata_provenance.json.",
              "- This deliberately conservative policy freezes item attributes as well as vocabulary/IDF before validation. Of the fixed 6,384 candidates, 3,993 have frozen metadata. The others keep zero content score; none are removed from the pool. This is a coverage choice of this implementation, not an inherent inability of content methods to describe new items when their metadata is permitted.",
              "- Category is the deterministic most frequent training value; genres, actors/directors, production-start decades and (when enabled) title words are unioned across training airings of the same ID. Missing fields add no artificial unknown token. Year ranges use their starting year.",
              "- Binary multi-hot tokens are weighted with training-item smoothed IDF, `log((1+N)/(1+df))+1`, where configured. Each feature family is L2-normalized before applying the declared family weight; the concatenated item vector is normalized again.",
              "- User profiles are weighted sums of watched-item content vectors, using log counts or counts, then L2-normalized. Scoring is cosine. No programme-ID feature, personal-frequency ranker or popularity score fusion is introduced.",
              "", "### What was strange and what the checks established", "",
              f"1. Genre/category CBF reaches only MAP {score('cbf_genre_log'):.8f}. It has 518 unique vectors for 5,842 IDs; 5,609 items share a vector with another ID and the largest group contains 460 programmes. Around 32 candidates tie at the fifth score on average. Generic genre matching cannot uniquely identify a user's favourite show.",
              f"2. Richer TF-IDF metadata removes most exact collisions (5,766 unique vectors), but MAP stays at {score('cbf_rich_tfidf_log'):.8f}. Higher Precision@5 without an MAP gain shows that representation uniqueness alone does not fix ranking of the exact favourite IDs.",
              f"3. Changing only profile weights from log counts to counts raises rich CBF MAP to {score('cbf_rich_tfidf_count'):.8f}. The heavy viewer's profile shifts from films to news. This supports the hypothesis that many occasional items were overwhelming a few recurring favourites after log compression.",
              f"4. Adding supplied past-schedule title-word features raises MAP to {score('cbf_title_tfidf_count'):.8f}, with only 26 items remaining in nonunique vector groups. Numeric episode/season labels and boilerplate are stripped; tokens remain actual metadata, not item IDs. Titles help distinguish programmes sharing broad genres.",
              "5. The selected content model is still below popularity. The light user has one entertainment-programme watch and gets an entertainment-only list, while later favourites include news. Metadata similarity cannot infer that change from a single seed. The heavy user gets the right broad category but still includes occasional news programmes outside their exact favourite Top-5.",
              f"6. Selected CBF recommends {new_item_findings['recommendation_slots_without_any_qualified_training_view']:,} slots with zero collaborative training support; {new_item_findings['hits_among_these_slots']} are actual Top-5 hits. Of {len(unseen_truth):,} true slots without collaborative training support, only {new_item_findings['true_slots_without_collaborative_support_but_with_frozen_metadata']} have metadata in the frozen snapshot. This coverage limit must be separated from ranking quality; these counts do not establish a general failure of content-based item-cold-start handling. See content_new_item_diagnostics.json.",
              "", "## Association-rule method", "",
              "A basket is a set of distinct qualified programme IDs. Initial baskets are nonempty user histories; diagnostic baskets are nonempty user/ISO-week histories, assigned by the local week of the first in-window watched overlap. No validation event enters any basket.",
              "The implementation exactly enumerates frequent singletons and pairs using a binary basket-item matrix. It mines singleton A->B rules (not an unrestricted full Apriori search), requiring A!=B, joint count >=5 or >=20, confidence >=0.10 and lift>1.",
              "For N baskets: support=n_AB/N; confidence=n_AB/n_A; lift=(n_AB/n_A)/(n_B/N). Lift>1 is filtered using exact integer cross-products. Repeated watches never inflate a basket's item indicator.",
              "Candidate score = sum over watched antecedents A of history_weight(u,A)*rule_weight(A->B). Rule weight is confidence or lift. Consequents already watched in training are allowed. Self-rules are excluded because A->A is tautological. Scores are not calibrated probabilities and are not causal effects.",
              "", "### Why history/confidence, lift and weekly baskets differ", "",
              f"- Whole-history confidence rules get {score('ar_user_s5_conf'):.8f}, below popularity, and concentrate recommendations on only 24 IDs. Many weakly related antecedents point to ubiquitous news, while ten weeks of viewing mix different interests and schedules.",
              f"- Raising the joint floor to 20 does not repair that: MAP is {score('ar_user_s20_conf'):.8f}. This is evidence against treating support tuning alone as the solution.",
              f"- Changing only aggregation from confidence to lift collapses MAP to {score('ar_user_s5_lift'):.8f}. Lift divides by consequent prevalence, strongly amplifying niche associations. One observed rule has n_A=6, n_B=11, n_AB=5, N=4,737: support=5/4737, confidence=5/6, lift=358.86. It addresses only six observed antecedent-user baskets; extreme enrichment is neither broad actionable reach nor proof of future favourite frequency.",
              f"- Raw-count antecedent weights also fail to help (MAP {score('ar_user_s5_conf_count'):.8f}). Stronger historical frequency alone does not make a cross-programme conditional association a direct persistence model.",
              f"- Weekly baskets produce 37,403 baskets and 16,126 retained rules, improving MAP to {score('ar_week_s5_conf'):.8f}. This is consistent with more local co-view context being useful, but basket definition also changes prevalence and support semantics; it is not proof that locality alone causes the improvement.",
              "- The support floor is still five baskets, now user-weeks rather than users. Twelve weekly rules have fewer than five distinct joint users; their distinct-user counts remain exported rather than hidden behind repeated weeks.",
              "- Weekly rules require three popularity-backfilled slots for one warm user, in addition to the shared 59 cold-user fallbacks. This cannot explain a cohort MAP improvement of about 0.0565: at most one user's AP changes from that extra backfill.",
              "", "## Common fallback and tie policy", "",
              "All methods retain exactly five unique candidates. Positive content/rule scores rank descending with numeric-ID ties; slots with no positive model signal are filled from the same training popularity order. Cold-user output is identical across all methods. Every previous warm MF/PPR Top-5 score is positive, so this backfill convention leaves all saved MF/PPR predictions unchanged. The verifier checks new fallback provenance explicitly.",
              "Local true-ID tie uncertainty remains unchanged (2,630 of 4,030 primary users). No truth pruning or method-specific denominator is used.",
              "", "## Same two users", "", "| User role | Programme history | Popularity AP | MF AP | PPR AP | CBF AP | Rules AP |",
              "|---|---|---:|---:|---:|---:|---:|"]
    roles = json.loads((ROOT / "reports/models/example_users.json").read_text())["users"]
    methods = ["popularity", selected["implicit_mf"]["run_id"], selected["ppr"]["run_id"], cbf, ar]
    for user in roles:
        vals = [examples.loc[(examples.user_id == user["user_id"]) & (examples.model == model), "user_AP_at_5"].iloc[0] for model in methods]
        lines.append(f"| {user['role']}: {user['user_id']} | {user['train_watched_airings']} airings / {user['train_qualified_programmes']} IDs | " + " | ".join(f"{value:.8f}" for value in vals) + " |")
    lines += ["", "The users were selected from training-history extremes before any model runs; they are not flattering examples selected after comparing algorithms. Full ordered IDs, titles, categories, history counts and actual validation matches are in reports/all_methods/recommendation_examples.csv.",
              "", "## Verification, reproducibility and later report", "",
              f"Independent verification passed **{len(verification['checks'])} checks across {len(verification['runs'])} runs**. It reconstructs all frozen documents from raw CSVs, item weights/IDF/profile algebra, user-week baskets, frequent-pair filters, rule metrics, full predictions, fallbacks and exact per-user AP/MAP. Eight unit tests cover hand cosine, IDF, family balancing, title parsing, directional confidence, self-rule removal and backfill.",
              "Complete feature and matched-rule contributions are saved for the same example users. manual_rule_calculation.json contains one real rule with all counts for a later student calculation. These are assistant-executed checks; personal verification is not claimed.",
              "", "```bash", "python3 -m unittest discover -s scripts -p 'test_content_rules.py'",
              "python3 scripts/run_content_rules.py --stage all", "python3 scripts/verify_content_rules.py",
              "python3 scripts/summarize_content_rules.py", "```", "",
              "The previous MF diagnosis is preserved in reports/models/README.md and diagnostic_plan.md. reports/all_methods/report_notes.md collects the four method-specific findings to use in the later PDF. No final exam PDF, test-period refit, hybrid, Kaggle submission or online-effect claim is generated here.",
              "", "## Sources consulted", "",
              "- Supplied content/association-rule lectures, exam brief and teacher feedback/answers, including the distinction between high lift and actionable reach.",
              "- scikit-learn feature extraction documentation: multi-valued categorical encoding, smoothed IDF and cosine normalization. Used as formula reference; implementation uses NumPy/SciPy. https://scikit-learn.org/1.5/modules/feature_extraction.html#text-feature-extraction",
              "- mlxtend association-rule documentation: support, confidence and lift definitions. Used as formula reference, not as the mining implementation. https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    all_lines = ["# Four-method SWEET.TV validation comparison", "",
                 "The complete CBF/rule diagnosis is in [../content_rules/README.md](../content_rules/README.md); MF/PPR analysis remains in [../models/README.md](../models/README.md).", "",
                 "| Method | Selected configuration | All-primary MAP@5 | Template-primary MAP@5 |", "|---|---|---:|---:|"]
    for method, run_id in [("popularity", "popularity")] + [(m, x["run_id"]) for m, x in selected.items()]:
        f = comparison.loc[comparison.run_id == run_id].set_index("cohort")
        all_lines.append(f"| {method} | {run_id} | {f.loc['all_primary', 'map_at_5']:.8f} | {f.loc['template_primary', 'map_at_5']:.8f} |")
    all_lines += ["", "All use the same original 4,030 users, 1,150-user reporting subset, 6,384 candidates, repeats allowed, training-only history, ground truth, MAP@5 evaluator and cold popularity fallback. Full configurations are retained in all_configurations.csv; no weak run is hidden.",
                 "", "Selection is based only on all-primary MAP@5. Conditional paired-user intervals are in paired_comparisons.csv; they do not account for selection or unknown label tie-breaking.",
                 "", "PPR remains the leading observed standalone method; count-target MF is second, weekly association rules third, popularity fourth and metadata CBF fifth. This is a result for this temporal favourite-frequency task, not a universal algorithm ranking.",
                 "", "The same training-selected heavy/light user examples with all ordered IDs, titles/categories and validation matches are in recommendation_examples.csv.",
                 "", "MF/PPR verification: ../models/verification.json (95 checks over nine runs). CBF/rule verification: ../content_rules/verification.json (120 checks over ten runs).", ""]
    (ALL / "README.md").write_text("\n".join(all_lines), encoding="utf-8")
    notes = ["# Findings to preserve in the later exam PDF", "",
             "These are report notes linked to actual runs, not a completed student-authored PDF or a claim of student verification.", "",
             "## MF — keep this diagnosis", "",
             "Binary implicit ALS improved its own objective but missed the frequency Top-5. For the heavy user, occasional programmes displaced favourites. A controlled switch to log-count targets raised MAP@5 from 0.27097767 to 0.35298677 and improved count/score alignment. Preserve the initial weak runs, checkpoint evidence and before/after recommendation example. Source: ../models/diagnostic_plan.md and ../models/README.md.",
             "", "## PPR — diffusion is a modelling choice", "",
             "More link-following washed out personalised restart and moved rankings toward global hubs. Alpha .50 won over .85/.95; normalized edges broadened coverage but did not improve MAP. PPR scores are stationary visit mass, not watch probabilities.",
             "", "## CBF — content resemblance is not favourite identity", "",
             "Coarse vectors collapsed many programmes. Rich metadata removed collisions without fixing the weighted centroid; count weighting and title tokens improved frequency/identity alignment. The best tested CBF still lost to popularity and failed the thin-profile example. Report that outcome rather than asserting that extra metadata must improve quality.",
             "", "## Rules — neither high confidence nor high lift is sufficient", "",
             "Full-history confidence rules over-promoted common news; lift scoring amplified niche associations with tiny reach and collapsed ranking quality. Weekly baskets improved prediction while changing the statistical unit. Quote both basket and distinct-user counts. Association is not intervention lift, enjoyment or revenue.",
             "", "## Shared evidence and limitations", "",
             "Use selected_comparison.csv, full candidate/cohort definitions, unchanged local label tie policy, cold-user accounting and same-two-user recommendation_examples.csv. Keep student personal verification separate from assistant tests. The user plans to check the original interaction example later; do not claim that has happened.", ""]
    (ALL / "report_notes.md").write_text("\n".join(notes), encoding="utf-8")
    print(comparison[["method", "run_id", "cohort", "map_at_5"]].to_string(index=False))
    print(json.dumps(new_item_findings, indent=2))
    print(f"Wrote {OUT / 'README.md'} and {ALL / 'README.md'}")


if __name__ == "__main__":
    main()
