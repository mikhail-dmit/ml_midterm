#!/usr/bin/env python3
"""Explain the fixed local extension study and verified submission 007."""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/recency_extension"
FINAL = ROOT / "reports/submission_007"


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    selection = json.loads((OUT / "selection.json").read_text())
    local_check = json.loads((OUT / "verification.json").read_text())
    final = json.loads((FINAL / "summary.json").read_text())
    final_check = json.loads((FINAL / "verification.json").read_text())
    assert local_check["status"] == final_check["status"] == "passed"
    frame = pd.read_csv(OUT / "comparison.csv")
    primary = frame.loc[frame.cohort == "all_primary"].set_index("run_id")
    template = frame.loc[frame.cohort == "template_primary"].set_index("run_id")
    paired = pd.read_csv(OUT / "paired_selected.csv")
    novelty = pd.read_csv(OUT / "novelty_metrics.csv")
    history = pd.read_csv(OUT / "history_metrics.csv")
    ledger = json.loads((ROOT / "submissions/results.json").read_text())
    recorded_007 = next((r for r in ledger["results"] if r["submission_id"] == "submission_007" and r["csv_sha256"] == final["submission_sha256"]), None)
    upload_status = (f"**Final user-selected submission: public {recorded_007['public_score']:.5f}, private {recorded_007['private_score']:.5f}. Experiments are closed.** Result/screenshot evidence is in kaggle_result.json and submissions/results.json."
                     if recorded_007 else "**Upload `submissions/submission_007.csv`. Its returned Kaggle score is pending.**")
    selected, config = selection["selected_id"], selection["selected_config"]
    lines = ["# One further validation-only refinement around submission 006", "",
             f"**Primary-validation selection: `{selected}`.** Only the existing MF, PPR, association rules and popularity components are used.",
             "", "## Recorded baseline and selection discipline", "",
             "006 returned **public 0.43662 / private 0.42340**, supported by the user's screenshot and exact-CSV hash. It exceeds 002 by **0.00303 public / 0.00851 private**, becoming best on both returned scores. That motivates another experiment, but does not enter the selector's criterion.",
             "The complete thirteen-new-configuration grid was declared before scoring. The runner loads no Kaggle score ledger or test-submission CSV. It ranks previously unsubmitted configurations by the original 4,030-user primary MAP@5; template metrics and paired intervals are descriptive. No grid expansion occurred after seeing results.",
             "All original >=80% labels, 4,030/1,150 users, 6,384 candidates, repeats, AP denominator and method hyperparameters stay fixed. The eight-week baseline reproduces all previous 006 validation recommendations exactly.",
             "", "## What was tested", "",
             "- Common collaborative half-lives 6/12/16 weeks versus the fixed 8-week control.",
             "- MF-only and PPR-only recency, and crossed 4/8-week memories, reusing previously fitted components where possible.",
             "- Eight-week decay for strict-80% antecedent query counts, with the same mined weekly rules matrix.",
             "- Eight-week decay for popularity votes only, retaining the original unweighted tie-break, positive-signal backfill and common cold fallback.",
             "- Two modest MF/PPR weight shifts and a rules/popularity auxiliary-budget shift, using the unchanged eight-week models.",
             "", "## All results", "",
             "| Configuration | Primary MAP@5 | Template MAP@5 | Primary delta vs 006 |", "|---|---:|---:|---:|"]
    for cfg in [plan["control"]]+plan["runs"]:
        name = cfg["id"]
        label = "**"+name+"**" if name == selected else name
        lines.append(f"| {label} | {primary.loc[name, 'map_at_5']:.8f} | {template.loc[name, 'map_at_5']:.8f} | {primary.loc[name, 'delta_vs_006']:+.8f} |")
    lines += ["", "The highest primary score comes from a small auxiliary-budget reallocation, not a new recency model. Six weeks has the highest template-subset MAP, but it is not selected because the declared rule uses primary MAP. Weighted popularity changes no predictions at depth five here: its first five vote IDs/order remain unchanged. Combining it with rule-query decay therefore duplicates rule-query-only predictions. Previous-upload duplicates are excluded from eligibility.",
              "", "## Exact selected change and why it may help", "",
              "| Component / parameter | 006 | 007 |", "|---|---:|---:|",
              "| MF weight | 0.5 | 0.5 |", "| PPR weight | 0.5 | 0.5 |",
              "| Rules weight | 0.125 | 0.1875 |", "| Popularity weight | 0.125 | 0.0625 |",
              "| MF/PPR half-life | 8 weeks | 8 weeks |", "| Component depth / RRF offset | 5 / 0 | 5 / 0 |", "",
              "Total auxiliary weight stays .25. Personalized rules use each user's history, whereas popularity offers the same global list to warm users. Giving the conditional association signal more influence can improve ordering where generic popularity and personalized evidence disagree. This is an input/rank-fusion change within existing methods, not a new recommender.",
              "The selection is supported only by a modest observed MAP increase. It is a ranking-quality trade-off, not better discovery or coverage: the selected primary lists have six more familiar true hits but nine fewer new-to-user hits (three fewer total). Correct-hit positions nevertheless yield higher AP.",
              "", "### Fixed truth decomposition", "",
              "| Strategy | Familiar hits | New hits | Familiar AP credit | New AP credit |", "|---|---:|---:|---:|---:|"]
    n = novelty.loc[(novelty.cohort == "all_primary") & (novelty.axis == "familiarity")].set_index(["run_id", "segment"])
    for name in ["control_006", selected]:
        fam, new = n.loc[(name, "familiar_80pct")], n.loc[(name, "new_qualified_for_user")]
        lines.append(f"| {name} | {int(fam.hits):,} | {int(new.hits):,} | {fam.AP_contribution_full_cohort:.8f} | {new.AP_contribution_full_cohort:.8f} |")
    lines += ["", "### Paired conditional evidence", "",
              "| Cohort | Mean MAP difference vs 006 | Conditional 95% interval | Better / worse / tied users |", "|---|---:|---|---|"]
    for row in paired.itertuples(index=False):
        lines.append(f"| {row.cohort} | {row.mean_MAP_difference:+.8f} | [{row.conditional_95pct_lower:+.6f}, {row.conditional_95pct_upper:+.6f}] | {row.better_users:,} / {row.worse_users:,} / {row.equal_users:,} |")
    lines += ["", "Both intervals include zero. The small gain does not establish a clear improvement, and these 2,000 paired-user resamples do not account for selecting among thirteen settings, earlier tuning, unknown fifth-place tie policy or temporal drift. This is the same repeatedly used temporal hold-out. The upload is a cautious validation-chosen attempt; no actual 007 Kaggle gain is claimed.",
              "", "### Original strict distinct-history bins", "",
              "| History | Users | 006 | Selected |", "|---|---:|---:|---:|"]
    h = history.loc[(history.cohort == "all_primary") & (history.axis == "history_distinct")].set_index(["run_id", "segment"])
    for segment in ["0 (cold)", "1-5", "6-20", "21-50", "51+"]:
        lines.append(f"| {segment} | {int(h.loc[(selected, segment), 'users']):,} | {h.loc[('control_006', segment), 'map_at_5']:.6f} | {h.loc[(selected, segment), 'map_at_5']:.6f} |")
    lines += ["", "The effect is not uniform across users/history strata. All familiarity and history definitions stay fixed; actual cold fallbacks remain identical. Full novelty, volume, activity and last-activity tables are retained.",
              "", "## Verification and reproduction", "",
              f"Two targeted tests and **{len(local_check['checks'])} independent checks** passed across the fixed local grid. Checks include all new/cached collaborative half-life arithmetic and MF/PPR equations, mixed model indices, strict-80% rule-query weights and matrix products, vote-only popularity, preserved unweighted tie/cold policy, full-pool component orders, exact rational fusion/AP/MAP, control reproduction and primary-only selection.",
              "", "```bash", "python3 -m unittest discover -s scripts -p 'test_recency_extension.py'", "python3 scripts/run_recency_extension.py", "python3 scripts/verify_recency_extension.py", "python3 scripts/prepare_submission_007.py", "python3 scripts/verify_submission_007.py", "python3 scripts/summarize_recency_extension.py", "```", "",
              "All plans, source/code hashes, weaker trials, per-user predictions/scores and model/query/vote artifacts remain saved. No new baseline or method outside the previously implemented four methods is introduced. The student's personal verification is not claimed.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    upload = ["# Submission 007: more rules and less popularity in the 006 fusion", "",
              upload_status, "",
              f"Selected by primary local validation: `{selected}`. The full thirteen-candidate study and uncertainty are in reports/recency_extension/README.md. No Kaggle score enters the selection rule.",
              "", "## What changes", "",
              "The exact same all-weeks 11–30 eight-week MF/PPR models, unweighted weekly-rule scores and unweighted popularity lists from 006 are reused. Every numerical component score, item index and Top-20 list is independently confirmed identical. No component is retrained for this weight-only winner.",
              "Only RRF weights change: MF/PPR stay .5/.5, rules increase .125 -> .1875, popularity decreases .125 -> .0625. Total auxiliary weight stays .25, component depth stays five and offset stays zero. Missing component IDs contribute zero, mathematical ties use original training popularity, and all four actual cold users retain their exact common fallback.",
              "", "## Local evidence", "",
              "| Strategy | Primary MAP@5 | Template MAP@5 |", "|---|---:|---:|",
              "| 006 | 0.37601075 | 0.41099420 |", f"| 007 candidate | {selection['primary_MAP']:.8f} | {selection['template_MAP']:.8f} |", "",
              "Expected mechanism: rules provide history-conditioned associations, so reallocating part of the generic-popularity budget can rank correct familiar preferences earlier. Local primary AP improves for 128 users and worsens for 88; 3,814 tie. Total true hits slightly decrease, so the measured gain is rank quality rather than discovery/coverage. Both paired conditional intervals include zero, and no Kaggle improvement is guaranteed.",
              "", "## Scored uploads", "",
              "| Submission | Public | Private |", "|---|---:|---:|"]
    for result in ledger["results"]:
        upload.append(f"| {result['submission_id']} | {result['public_score']:.5f} | {result['private_score']:.5f} |")
    result_context = ("007 improves over 006 by **0.00045 public / 0.00132 private**. The user designated 007 as final best and stopped experiments. The final file/configuration are frozen in submissions/final_selection.json; report examples are in reports/final_examples/."
                      if recorded_007 else "006 is the best recorded upload on both scores, exceeding 002 by **0.00303 public / 0.00851 private**. Its exact file hash and user-provided screenshot are recorded in submissions/results.json.")
    upload += ["", result_context,
               "", "## Actual recommendation changes", "",
               "| Reference | Changed lists | Changed sets | Order only | Unchanged | Mean shared Top-5 |", "|---|---:|---:|---:|---:|---:|"]
    for row in final["comparisons"]:
        upload.append(f"| {row['reference']} | {row['changed_ordered_users']:,} | {row['changed_set_users']:,} | {row['order_only_users']:,} | {row['unchanged_users']:,} | {row['mean_shared_top5']:.4f}/5 |")
    upload += ["", "No hidden per-user Kaggle targets are available: these are list changes, not known relevance gains/losses. All six earlier CSVs/screenshots remain intact.",
               "", "## Verified format and inference", "",
               f"**{len(final_check['checks'])} final independent checks passed**, in addition to {len(local_check['checks'])} local checks and two unit tests. They verify exact template schema/order and 1,260 user strings, five unique nonzero eligible IDs each, full-history source model/recency equations, unchanged 006 components and cold policy, exact RRF ranks and per-user comparison tables.",
               "", "SHA-256:", "", "```text", final["submission_sha256"], "```", "",
               "```bash", "python3 scripts/prepare_submission_007.py", "python3 scripts/verify_submission_007.py", "python3 scripts/summarize_recency_extension.py", "```", "",
               "Configuration, frozen local selection, model/input hashes, score-feedback snapshot, recommendation traces and checks are retained here. Model arrays and component lists are in artifacts/submission_007/. No 008 CSV is generated.", ""]
    (FINAL / "README.md").write_text("\n".join(upload), encoding="utf-8")
    print(f"Wrote {OUT / 'README.md'} and {FINAL / 'README.md'}.")


if __name__ == "__main__":
    main()
