#!/usr/bin/env python3
"""Report semantic hybrid findings and the verified first submission."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/semantic_hybrids"
FINAL = ROOT / "reports/final_11_30"
LABELS = {
    "implicit_mf": "MF 50%", "ppr": "PPR 50%", "association_rules": "Weekly rules 80%", "popularity": "Popularity 50%",
    "rrf_mf_ppr_rules_k0": "RRF control: MF + PPR + rules",
    "slots_ppr4_rules1": "4 PPR familiar + 1 rules new", "slots_ppr3_rules2": "3 PPR familiar + 2 rules new",
    "slots_ppr4_pop1": "4 PPR familiar + 1 popular new", "slots_ppr3_pop2": "3 PPR familiar + 2 popular new",
    "slots_mf4_rules1": "4 MF familiar + 1 rules new", "switch_ppr_strict5": "Popularity if history <=5, else PPR",
    "switch_mf_strict5": "Popularity if history <=5, else MF", "switch_roles_strict5": "Popularity if history <=5, else 4 PPR + 1 rules",
    "ppr20_rerank_mf": "PPR Top-20 -> MF reranking", "mf20_rerank_ppr": "MF Top-20 -> PPR reranking",
    "slots_ppr4_rules20_pop1": "4 PPR familiar + 1 new from rules Top-20 reranked by popularity",
}


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    selection = json.loads((OUT / "selection.json").read_text())
    verification = json.loads((OUT / "verification.json").read_text())
    final = json.loads((FINAL / "summary.json").read_text())
    final_check = json.loads((FINAL / "verification.json").read_text())
    ledger_path = ROOT / "submissions/results.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {"results": []}
    scored = next((r for r in ledger["results"] if r["submission_id"] == "submission_001" and r["csv_sha256"] == final["submission_sha256"]), None)
    score_status = (f"The user reported returned Kaggle public **{scored['public_score']:.5f}** and private **{scored['private_score']:.5f}** for this exact CSV. The record and screenshot reference are in submissions/results.json and kaggle_result.json. Scores are user-supplied, not fetched through the API."
                    if scored else "Kaggle upload is to be performed by the user; the actual returned score is pending and will be recorded against this exact CSV/hash.")
    assert verification["status"] == final_check["status"] == "passed"
    comparison = pd.read_csv(OUT / "comparison.csv")
    novelty = pd.read_csv(OUT / "novelty_metrics.csv")
    history = pd.read_csv(OUT / "history_metrics.csv")
    paired = pd.read_csv(OUT / "paired_vs_rrf.csv")
    primary = comparison.loc[comparison.cohort == "all_primary"].set_index("run_id")
    template = comparison.loc[comparison.cohort == "template_primary"].set_index("run_id")
    control = plan["rrf_control"]["id"]
    selected = selection["selected_id"]
    best_semantic = selection["best_semantic_id"]
    lines = ["# Method-role hybrids versus the fixed RRF control", "",
             f"**Selected overall: {LABELS[selected]}. Best semantic hybrid: {LABELS[best_semantic]}.**", "",
             "## Frozen experiment", "",
             "Eleven configurations were declared before scoring: five familiar/new quotas; popularity switching to MF, PPR or a role-based warm branch; two collaborative candidate/reranker directions; and a rules-generated new-candidate shortlist reranked by popularity. The existing RRF is a fixed control, alongside the individual methods.",
             "The exact original >=80% validation Top-5 labels, 4,030-user primary cohort, 1,150-user template subset, 6,384 eligible IDs, repeats, and denominator five are retained. Restored MF/PPR 50% and weekly-rule 80% models reproduce every original component Top-5 exactly. The RRF control reproduces every previous recommendation exactly.",
             "", "### Meaning of the role rules", "",
             "- Familiar: the user had >=1 original >=80% qualifying training watch. New: no such qualifying watch; partial-only prior exposure remains new. Neither definition uses validation answers.",
             "- History size: all distinct >=80%-qualified training programmes, including IDs unavailable later. Popularity switching applies at <=5; there is no oracle routing by future truth composition.",
             "- Fixed quotas place familiar slots first and new slots last. Positive component scores are sorted within roles; zero-signal slots use the shared 50%-training popularity backfill. If one role lacks enough eligible items, its unused slots are borrowed by the other role.",
             "- Filtering into roles occurs over the complete eligible component order before keeping the first 20 candidates. The role queues are not restricted to each component's original Top-5.",
             "- Two-stage strategies retrieve 20 IDs, then order them by the other method's raw score. Ties preserve generator order. Different methods' raw scores are never added.",
             "- Every actual cold user receives identical popularity fallback. The original 59-user cold diagnostic bin is kept fixed; 16 are warm under 50%, leaving 43 actual cold users.",
             "", "## Full comparison", "", "| Strategy | MAP@5 all | MAP@5 template | Delta vs RRF: all |", "|---|---:|---:|---:|"]
    for name in primary.index:
        label = LABELS[name]
        if name == selected:
            label = "**"+label+"**"
        lines.append(f"| {label} | {primary.loc[name, 'map_at_5']:.8f} | {template.loc[name, 'map_at_5']:.8f} | {primary.loc[name, 'delta_vs_rrf']:+.8f} |")
    lines += ["", "All configurations are retained. Selection uses primary MAP only and includes the controls, so a semantic hybrid is not forced to win.",
              "", "## Why the fixed-slot intuition did not improve MAP", "",
              "The diagnostic identifies different average strengths, but a global role budget ignores each user's relative candidate quality. Making room for a weak new prediction can displace a correct recurring favourite. Strict familiarity also separates partial prior interests that the softer collaborative models can already use.",
              "", "| Strategy | Familiar hits | New hits | Familiar recall | New recall | Familiar AP credit | New AP credit |", "|---|---:|---:|---:|---:|---:|---:|"]
    n = novelty.loc[(novelty.cohort == "all_primary") & (novelty.axis == "familiarity")].set_index(["run_id", "segment"])
    for name in [control, "slots_ppr4_rules1", "slots_ppr3_rules2", best_semantic]:
        fam = n.loc[(name, "familiar_80pct")]
        new = n.loc[(name, "new_qualified_for_user")]
        lines.append(f"| {LABELS[name]} | {int(fam.hits):,} | {int(new.hits):,} | {fam.recall_of_true_type_micro:.2%} | {new.recall_of_true_type_micro:.2%} | {fam.AP_contribution_full_cohort:.6f} | {new.AP_contribution_full_cohort:.6f} |")
    fam_delta = int(n.loc[("slots_ppr4_rules1", "familiar_80pct"), "hits"]-n.loc[(control, "familiar_80pct"), "hits"])
    new_delta = int(n.loc[("slots_ppr4_rules1", "new_qualified_for_user"), "hits"]-n.loc[(control, "new_qualified_for_user"), "hits"])
    lines += ["", f"The 4+1 rules allocation has {new_delta:+,} new-type hits but {fam_delta:+,} familiar hits relative to RRF. The increased new recall does not compensate for lost familiar relevance and ranking quality. Even its new-type AP contribution is lower because hits generally occupy later positions and depend on earlier hit precision. AP-credit partitions preserve the original metric exactly.",
              "", "## Switching and reranking", "",
              "Popularity remains useful for some sparse users, but the strict-history <=5 switch does not improve primary MAP over its softer-input standalone counterpart. The earlier reference diagnostic used strict-input models; it does not guarantee a beneficial gate after those models change to 50%-qualified inputs. The template subgroup's improvement does not override primary selection.",
              f"The best semantic method, {LABELS[best_semantic]}, reaches {primary.loc[best_semantic, 'map_at_5']:.8f}. Candidate generation changes MF's eligible shortlist and improves over unrestricted MF, but remains below the {primary.loc[control, 'map_at_5']:.8f} RRF control. MF/PPR ranked lists plus the rules contribution preserve more useful information than these particular hard constraints.",
              "", "### History breakdown: primary cohort", "",
              "| Strict distinct history | Users | Popularity | MF | PPR | RRF | PPR20 -> MF | Switch to MF |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    h = history.loc[(history.cohort == "all_primary") & (history.axis == "history_distinct")].set_index(["run_id", "segment"])
    for segment in ["0 (cold)", "1-5", "6-20", "21-50", "51+"]:
        names = ["popularity", "implicit_mf", "ppr", control, "ppr20_rerank_mf", "switch_mf_strict5"]
        lines.append(f"| {segment} | {int(h.loc[(control, segment), 'users']):,} | " + " | ".join(f"{h.loc[(name, segment), 'map_at_5']:.6f}" for name in names)+" |")
    p = paired.loc[(paired.cohort == "all_primary") & (paired.run_id == best_semantic)].iloc[0]
    lines += ["", f"Best semantic minus RRF: {p.delta_MAP_vs_rrf:+.8f}; conditional paired 95% interval [{p.conditional_95pct_lower:+.6f}, {p.conditional_95pct_upper:+.6f}]. Intervals use 2,000 user resamples, seed 20261023; they are conditional diagnostics, not corrected for selection on the repeatedly used temporal hold-out or unknown truth tie policy.",
              "", "## Examples and verification", "",
              "runs/NAME/recommendations.csv records each item's strict familiarity, routing/role, history count, all four source scores, title/category and true-hit status. recommendation_examples.csv retains the earlier light/heavy users across all tested strategies, with ordered IDs and matches.",
              f"Five targeted unit tests and {len(verification['checks'])} independent checks passed. Verification rebuilds full eligible orders from saved scores, applies masks before truncation, reconstructs every slot/switch/rerank/RRF prediction, and checks exact-rational AP/MAP, fixed users, fallback and feature provenance. The student's own verification remains pending.",
              "", "## Reproduce", "", "```bash", "python3 -m unittest discover -s scripts -p 'test_semantic_hybrids.py'", "python3 scripts/run_semantic_hybrids.py", "python3 scripts/verify_semantic_hybrids.py", "python3 scripts/make_first_submission.py", "python3 scripts/verify_first_submission.py", "python3 scripts/summarize_semantic_hybrids.py", "```", "",
              "Source plans, input/code SHA-256s, component scores, predictions, per-user metrics, all-segment tables and paired comparisons are retained. The earlier MF binary-target diagnosis remains in reports/models/README.md and reports/all_methods/report_notes.md.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    old_examples = pd.read_csv(ROOT / "reports/all_methods/recommendation_examples.csv", dtype={"user_id": str})[["role", "user_id"]].drop_duplicates()
    example_parts = []
    for name in primary.index:
        trace = pd.read_csv(OUT / "runs" / name / "recommendations.csv", dtype={"user_id": str})
        sample = trace.merge(old_examples, on="user_id", how="inner", validate="many_to_one")
        sample["run_id"] = name
        example_parts.append(sample)
    pd.concat(example_parts, ignore_index=True).to_csv(OUT / "recommendation_examples.csv", index=False)
    boundary = pd.read_csv(FINAL / "internal_boundary_reconciliation.csv")
    final_lines = ["# First Kaggle submission: frozen winner refitted on weeks 11–30", "",
                   f"**Upload: `{final['submission_path']}`**", "",
                   f"Selected strategy: `{final['selected_id']}`. The semantic-hybrid study did not beat the fixed RRF control. Its earlier local MAP@5 is {selection['primary_MAP']:.8f} on 4,030 users and {selection['template_MAP']:.8f} on the template validation subset; these are not Kaggle scores or scores of the all-history refit.",
                   "", "## Frozen training and inference", "",
                   "- Training observations: [2020-03-09, 2020-07-27), Europe/Kyiv. Former validation-period behaviour is now past training data, after freezing the strategy and all parameters. The validation Top-5 target CSV is not used in refitting.",
                   "- MF: 50% watch qualification, 16 factors, log(1+count) target and confidence increment, regularisation 1, 15 epochs, seed 20261023.",
                   "- PPR: the same 50% counts, raw distinct-user co-view graph, log-count restart, link probability .5.",
                   "- Rules: 80% qualification, user/ISO-week baskets, joint count >=5, confidence >=.1, lift >1, log-count query weights.",
                   "- RRF: each component's available Top-5, weights MF=.5/PPR=.5/rules=.25, offset 0; absent item contributes zero. Ties and all cold/insufficient-signal backfills use 50%-training popularity.",
                   "- Availability: [2020-07-27, 2020-10-19). The test schedule contributes programme ID/channel/time/duration only, never future viewing or descriptive training features.",
                   "", "## Full-window interaction reconstruction", "",
                   "Raw views were deduplicated, unioned per user/channel, clipped to the complete twenty-week training window and rejoined to historical airings. Full airing durations remain the denominators. A watch spanning the former May18 split is evaluated once, using its combined observed fragments.", "",
                   "| Qualification | Separate-fold qualified events | Full-window qualified events | Boundary difference |", "|---|---:|---:|---:|"]
    for row in boundary.itertuples(index=False):
        final_lines.append(f"| {row.threshold_percent}% | {row.separate_fold_qualified_events:,} | {row.whole_20week_qualified_events:,} | {row.difference_due_to_internal_boundary:+,} |")
    final_lines += ["", "The independent verifier reconciles every fresh full-window user/airing overlap with the sum of the earlier disjoint folds' raw overlap seconds, then reconstructs counts after applying thresholds. It does not concatenate the old qualified-watch flags.",
                    "", "## Fitted data and submission", "",
                    f"- MF/PPR training matrix: **{final['training_users_50']:,} users × {final['training_items_50']:,} items**, {final['training_pairs_50']:,} positive pairs, {final['training_airings_50']:,} qualifying airing watches.",
                    f"- Weekly rule model: **{final['weekly_baskets']:,} baskets**, **{final['rules']:,} retained rules**.",
                    f"- Submission: **{final['template_users']:,} users × five distinct nonzero IDs**, **{final['test_candidates']:,} eligible programmes**, **{final['test_cold_users_50pct']} actual cold users** receiving identical popularity fallback.",
                    f"- The source test-schedule file has {final_check['all_nonzero_schedule_ids']:,} nonzero IDs, but {len(final_check['outside_prediction_window_ids'])} have no positive-duration airing overlapping weeks 31–42. Availability is reconstructed by time, not file membership alone; excluded IDs are saved in verification.json.",
                    f"- {final['new_to_training_items_in_test_pool']:,} available IDs have no learned MF/PPR training representation. They remain eligible with zero collaborative score; this hybrid does not solve globally unsupported catalogue cold start.",
                    f"- Component fitting plus component scoring: {final['fit_and_component_scoring_seconds']:.2f} seconds; full generation including raw join, saving models and predictions: {final['total_seconds']:.2f} seconds in the recorded environment.",
                    "", "## Independent verification", "",
                    f"**{len(final_check['checks'])} checks passed**: immutable inputs and strategy/code fingerprints; template header, count, exact uint64-safe user strings and row order; five distinct canonical nonzero IDs; test-period availability; all twenty-week event/count reconstruction; MF factor scores and fixed epochs; raw co-view graph and PPR stationarity; rule/query algebra; every component Top-5; and every final RRF rank with exact rational arithmetic.",
                    "", "SHA-256:", "", "```text", final['submission_sha256'], "```", "",
                    "The original template and validation artifacts remain intact. " + score_status + " The assistant's checks do not claim the student's personal verification.",
                    "", "## Reproduction and evidence", "",
                    "```bash", "python3 scripts/make_first_submission.py", "python3 scripts/verify_first_submission.py", "python3 scripts/summarize_semantic_hybrids.py", "```", "",
                    "See summary.json, frozen_inputs.json, selected_strategy.json, verification.json, component_*.csv, recommendations.csv and test_candidates.csv here. Complete event/count matrices, model factors, transitions, rules, baskets and scores are under artifacts/final_11_30/. Model selection is documented in reports/semantic_hybrids/README.md.", ""]
    (FINAL / "README.md").write_text("\n".join(final_lines), encoding="utf-8")
    print(f"Wrote {OUT / 'README.md'}, same-user examples and {FINAL / 'README.md'}.")


if __name__ == "__main__":
    main()
