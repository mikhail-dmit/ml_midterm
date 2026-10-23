#!/usr/bin/env python3
"""Report all refinement trials, the frozen selection and verified upload 006."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/refinement"
FINAL = ROOT / "reports/submission_006"


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    selected = json.loads((OUT / "selection.json").read_text())
    verification = json.loads((OUT / "verification.json").read_text())
    final = json.loads((FINAL / "summary.json").read_text())
    final_check = json.loads((FINAL / "verification.json").read_text())
    assert verification["status"] == final_check["status"] == "passed"
    comparison = pd.read_csv(OUT / "comparison.csv")
    primary = comparison.loc[comparison.cohort == "all_primary"].set_index("run_id")
    template = comparison.loc[comparison.cohort == "template_primary"].set_index("run_id")
    paired = pd.read_csv(OUT / "paired_selected.csv")
    novelty = pd.read_csv(OUT / "novelty_metrics.csv")
    history = pd.read_csv(OUT / "history_metrics.csv")
    ledger = json.loads((ROOT / "submissions/results.json").read_text())
    best_recorded = max(ledger["results"], key=lambda r: r["public_score"])
    recorded_006 = next((r for r in ledger["results"] if r["submission_id"] == "submission_006" and r["csv_sha256"] == final["submission_sha256"]), None)
    upload_status = (f"**Scored: public {recorded_006['public_score']:.5f}, private {recorded_006['private_score']:.5f}.** The user's result and screenshot reference are saved in kaggle_result.json and submissions/results.json."
                     if recorded_006 else "**Upload `submissions/submission_006.csv`. Returned Kaggle scores are pending.**")
    recency = json.loads((ROOT / "artifacts/submission_006/recency.json").read_text())
    config = selected["selected_config"]
    chosen = selected["selected_id"]
    lines = ["# Local-validation refinement for submission 006", "",
             f"**Selected by primary local MAP only: `{chosen}`.** The eleven new configurations and two fixed controls were declared before scoring. All candidates are retained below; the grid was not extended after viewing results.",
             "", "## What was fixed", "",
             "Original strict >=80% validation Top-5 labels; 4,030 primary users; nested 1,150 template users; 6,384 eligible IDs; repeats allowed; standard MAP@5 denominator five. MF/PPR use 50%-qualified training history and the original hyperparameters; weekly rules remain the selected strict-80% model. Every actual cold user receives identical unweighted training popularity.",
             "After seeing five aggregate Kaggle results, the user requested improvements around 002. That motivated the study, but the validation runner loads no score ledger or test-submission CSV. Selection uses primary MAP only; template scores and bootstrap intervals do not choose parameters. Controls reproduce 001/002 exactly on the earlier hold-out.",
             "", "## Declared candidates", "",
             "- Five changes to the rules/popularity split or total auxiliary budget, with MF/PPR fixed at .5/.5.",
             "- Four deeper-list RRF configurations: depth 10/20 × offset 0/10, with the original 002 weights.",
             "- Two gradual-recency configurations: 4- and 8-week half-life, keeping 002's weights/depth/offset and retaining all training history.",
             "", "## All results", "",
             "| Configuration | Primary MAP@5 | Template MAP@5 | Primary delta vs 002 |", "|---|---:|---:|---:|"]
    for record in plan["controls"]+plan["runs"]:
        name = record["id"]
        label = "**"+name+"**" if name == chosen else name
        lines.append(f"| {label} | {primary.loc[name, 'map_at_5']:.8f} | {template.loc[name, 'map_at_5']:.8f} | {primary.loc[name, 'delta_vs_control_002']:+.8f} |")
    lines += ["", "The best weight-split change yields only a small primary gain over 002 and remains slightly below 001. Deeper lists with offset zero improve primary MAP modestly but reduce template MAP; offset ten is weaker here. Both gradual-recency recipes outperform these variants on the two reported cohorts. Eight weeks wins the declared primary criterion; the small 4-versus-8-week difference does not establish a precisely optimal half-life.",
              "", "## Exact recency definition", "",
              "For every >=50%-qualified training airing, raw weight is `2 ** (-age_weeks / half_life)`, where age is from the last observed overlap second to the current training cutoff. A single scale, computed using training events only, preserves their total mass: `scale = number_of_qualifying_airings / sum(raw_weights)`. Sum the scaled weights into user/programme counts.",
              "The MF log-count target and confidence use these weighted counts. PPR restarts use normalized log(1+weighted_count). Every positive pair remains, so the distinct-user binary co-view graph is unchanged and reused. Rule mining/query scores, popularity votes, popularity tie-break, warm/cold status and strict-history diagnostic bins remain fixed.",
              "This is the combined decay-plus-mass-preservation recipe. The normalisation keeps overall count scale comparable; the current study does not separately identify its effect from time decay. There is no hard history truncation or use of future observations.",
              "", "## Paired evidence and limitations", "",
              "| Cohort | Reference | Selected MAP difference | Conditional 95% interval | Better / worse / tied users |", "|---|---|---:|---|---|"]
    for row in paired.itertuples(index=False):
        lines.append(f"| {row.cohort} | {row.reference} | {row.mean_MAP_difference:+.8f} | [{row.conditional_95pct_lower:+.6f}, {row.conditional_95pct_upper:+.6f}] | {row.better_users:,} / {row.worse_users:,} / {row.equal_users:,} |")
    lines += ["", "These 2,000 paired user resamples (seed 20261023) are conditional diagnostics, not adjusted for choosing among eleven new settings, earlier tuning, temporal drift or the unknown organiser tie policy. The same temporal hold-out has already been used repeatedly. Template-subset intervals include zero; its average gain is not a decisive independent confirmation. No actual 006 Kaggle improvement is claimed before the returned score.",
              "", "## Familiar versus new targets", "",
              "Original strict-history definitions and AP denominators remain fixed.", "",
              "| Strategy | Familiar hits | New hits | Familiar recall | New recall | Familiar AP credit | New AP credit |", "|---|---:|---:|---:|---:|---:|---:|"]
    novel = novelty.loc[(novelty.cohort == "all_primary") & (novelty.axis == "familiarity")].set_index(["run_id", "segment"])
    for name in ["control_002", chosen]:
        fam, new = novel.loc[(name, "familiar_80pct")], novel.loc[(name, "new_qualified_for_user")]
        lines.append(f"| {name} | {int(fam.hits):,} | {int(new.hits):,} | {fam.recall_of_true_type_micro:.2%} | {new.recall_of_true_type_micro:.2%} | {fam.AP_contribution_full_cohort:.6f} | {new.AP_contribution_full_cohort:.6f} |")
    lines += ["", "### Original strict distinct-history segments", "",
              "| Segment | Users | 002 | Selected |", "|---|---:|---:|---:|"]
    h = history.loc[(history.cohort == "all_primary") & (history.axis == "history_distinct")].set_index(["run_id", "segment"])
    for segment in ["0 (cold)", "1-5", "6-20", "21-50", "51+"]:
        lines.append(f"| {segment} | {int(h.loc[(chosen, segment), 'users']):,} | {h.loc[('control_002', segment), 'map_at_5']:.6f} | {h.loc[(chosen, segment), 'map_at_5']:.6f} |")
    lines += ["", "The selected recipe's average gain does not imply every user or sparse-history segment benefits. The fixed cold bin still includes sixteen users warmed by the softer training threshold; actual cold users retain identical fallback. All active-week, volume and last-activity tables are saved in history_metrics.csv.",
              "", "## Verification and reproduction", "",
              f"Three targeted tests and **{len(verification['checks'])} independent local checks** passed: immutable inputs, train-only event weights and globally preserved mass, original pair support/graph, MF factors and fixed epochs, PPR stationarity, unchanged rules/popularity/cold handling, every component order and fusion rank, exact AP/MAP, primary-only selection and reproducible paired intervals.",
              "", "```bash", "python3 -m unittest discover -s scripts -p 'test_refinement.py'", "python3 scripts/run_refinement_study.py", "python3 scripts/verify_refinement_study.py", "python3 scripts/prepare_submission_006.py", "python3 scripts/verify_submission_006.py", "python3 scripts/summarize_refinement.py", "```", "",
              "Plans, source/code hashes, all configurations/predictions/per-user scores, fixed novelty/history metrics and weighted model artifacts are saved. No new grid was fitted to public/private score differences. The selected configuration was frozen before the all-weeks refit. The student's own numerical verification is not claimed.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    upload = ["# Submission 006: locally selected eight-week recency recipe", "",
              upload_status, "",
              "## Why this configuration", "",
              f"Primary local validation selects `{chosen}` from a fixed eleven-new-configuration study, with 001/002 controls. All settings are in reports/refinement/README.md. Local MAP is **{selected['primary_MAP']:.8f} all / {selected['template_MAP']:.8f} template**, versus **0.37284202 / 0.40792464** for 002. The selector did not load the Kaggle score ledger or test-submission CSVs.",
              "", "Exact selected configuration:", "", "```json", json.dumps(config, indent=2), "```", "",
              "## All-history inference", "",
              "Training observations remain all weeks 11–30, ending exclusively 2020-07-27 Europe/Kyiv. Keep the same qualification thresholds and hyperparameters. Apply the selected relative-age weighting with that final cutoff, refit MF with fifteen fixed epochs, and compute PPR restarts from the newly weighted counts. Reuse the original raw co-view graph because pair support is unchanged. Weekly rules and their query scores, popularity and the RRF weighting/tie policies remain those of 002.",
              f"The final refit uses **{recency['event_count']:,}** >=50% qualifying airings, rescaling raw decay weights by **{recency['global_mass_preserving_scale']:.8f}** so the weighted total remains **{recency['weighted_count_sum']:,.0f}**. An airing observed eight weeks ago has half the raw weight of one just observed. Every original positive pair and all twenty weeks remain represented.",
              "The source test schedule contributes only the existing candidate availability. No hidden viewing or validation target labels enter final fitting. The original 002 CSV is reproduced from baseline models before the new refit. Candidate eligibility, exact 1,260 template users/order and the four actual cold users stay unchanged.",
              "", "## Completed uploads", "",
              "| Submission | Public | Private |", "|---|---:|---:|"]
    for row in ledger["results"]:
        upload.append(f"| {row['submission_id']} | {row['public_score']:.5f} | {row['private_score']:.5f} |")
    upload += ["", "Rules help in the direct 001-versus-005 ablation: +0.00184 public / +0.00413 private. Among those five uploads, public ordering is 002 > 001 > 005 > 003 > 004; private ordering swaps 003 and 005. The evidence therefore supports the specific rule/fusion comparisons, not universal ranking transfer. " + f"**{best_recorded['submission_id']} is now the best recorded public-score upload ({best_recorded['public_score']:.5f}).**", "",
               "## Recommendation changes", "",
               "| Reference | Changed lists | Changed item sets | Order only | Unchanged users | Mean shared Top-5 |", "|---|---:|---:|---:|---:|---:|"]
    for row in final["comparisons"]:
        upload.append(f"| {row['reference']} | {row['changed_ordered_users']:,} | {row['changed_set_users']:,} | {row['order_only_users']:,} | {row['unchanged_users']:,} | {row['mean_shared_top5']:.4f}/5 |")
    upload += ["", "These changes are not known gains/losses in relevance; actual per-user Kaggle targets are unavailable. Recency is supported by local means, not guaranteed to improve the returned score.",
               "", "## Verified format and models", "",
               f"**{len(final_check['checks'])} independent checks passed** in addition to {len(verification['checks'])} local checks and three unit tests. They cover exact two-column template schema/order and 1,260 user strings, five distinct nonzero eligible IDs, all-history recency event/count/factor arithmetic, PPR fixed points, unchanged rules/popularity/cold handling, each component Top-20, every final RRF rank and changes versus all five scored CSVs.",
               "", "SHA-256:", "", "```text", final["submission_sha256"], "```", "",
               "```bash", "python3 scripts/prepare_submission_006.py", "python3 scripts/verify_submission_006.py", "python3 scripts/summarize_refinement.py", "```", "",
               "See selection_frozen_before_refit.json, config.json, summary.json, verification.json, frozen_inputs.json, results_at_preparation.json, recommendations.csv and changes_vs_*.csv. Complete new model/weight artifacts are under artifacts/submission_006/. Earlier CSVs and their screenshots remain unchanged. No 007 file is generated.", ""]
    (FINAL / "README.md").write_text("\n".join(upload), encoding="utf-8")
    print(f"Wrote {OUT / 'README.md'} and {FINAL / 'README.md'}.")


if __name__ == "__main__":
    main()
