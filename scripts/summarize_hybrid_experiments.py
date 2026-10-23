#!/usr/bin/env python3
"""Write the compact hybrid study report and retain the existing example users."""

import json
from pathlib import Path

import pandas as pd

from evaluate_rankings import read_rankings
from ranking_metrics import average_precision_at_k

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/hybrids"
LABELS = {"popularity": "Popularity (50%)", "implicit_mf": "MF (50%)", "ppr": "PPR (50%)",
          "content_based": "CBF (80%)", "association_rules": "Weekly rules (80%)"}


def main():
    plan = json.loads((OUT / "plan.json").read_text())
    verification = json.loads((OUT / "verification.json").read_text())
    assert verification["status"] == "passed"
    assert verification["verified_runs"] == [r["id"] for r in plan["runs"]]
    comparison = pd.read_csv(OUT / "comparison.csv")
    novelty = pd.read_csv(OUT / "novelty_metrics.csv")
    history = pd.read_csv(OUT / "history_metrics.csv")
    paired = pd.read_csv(OUT / "selected_paired_comparisons.csv")
    selection = json.loads((OUT / "selection.json").read_text())
    selected = selection["best_hybrid"]
    configs = {r["id"]: r for r in plan["runs"]}
    selected_config = configs[selected]
    primary = comparison.loc[comparison.cohort == "all_primary"].set_index("run_id")
    template = comparison.loc[comparison.cohort == "template_primary"].set_index("run_id")
    changes = pd.read_csv(OUT / "selected_hit_changes.csv", dtype={"user_id": str}, keep_default_na=False)
    template_users = set(pd.read_csv(ROOT / "reports/popularity/cohort_template_primary.csv", dtype=str).user_id)
    gain_loss = []
    for cohort in ["all_primary", "template_primary"]:
        subset = changes if cohort == "all_primary" else changes.loc[changes.user_id.isin(template_users)]
        for method, group in subset.groupby("reference", sort=False):
            gain_loss.append({"cohort": cohort, "reference": method, "added_correct_pairs": int(group.added_hits.sum()),
                              "lost_correct_pairs": int(group.lost_hits.sum()), "net_correct_pairs": int((group.added_hits-group.lost_hits).sum()),
                              "gained_any_hits_users": int((group.added_hits > 0).sum()), "lost_any_hits_users": int((group.lost_hits > 0).sum())})
    pd.DataFrame(gain_loss).to_csv(OUT / "selected_gain_loss_summary.csv", index=False)
    # Keep the same earlier light/heavy examples, without choosing on hybrid AP.
    earlier = pd.read_csv(ROOT / "reports/all_methods/recommendation_examples.csv", dtype={"user_id": str})
    examples = earlier[["role", "user_id"]].drop_duplicates()
    assert len(examples) == 2 and examples.user_id.nunique() == 2
    truth = read_rankings(ROOT / "reports/interactions/validation_ground_truth.csv")
    candidates = pd.read_csv(ROOT / "reports/popularity/validation_candidates.csv", keep_default_na=False).set_index("tv_show_id")
    prediction_paths = {m: ROOT / path / "predictions.csv" for m, path in plan["sources"].items()}
    prediction_paths[selected] = OUT / "runs" / selected / "predictions.csv"
    example_rows = []
    for method, path in prediction_paths.items():
        predicted = read_rankings(path)
        for role, user in examples.itertuples(index=False, name=None):
            for rank, item in enumerate(predicted[user], 1):
                example_rows.append({"run_id": method, "role": role, "user_id": user, "rank": rank, "tv_show_id": item,
                                     "title": candidates.loc[item, "tv_show_title"], "category": candidates.loc[item, "tv_show_category"],
                                     "in_true_validation_top5": item in truth[user], "user_AP_at_5": average_precision_at_k(truth[user], predicted[user])})
    pd.DataFrame(example_rows).to_csv(OUT / "recommendation_examples.csv", index=False)
    lines = ["# Compact hybrid experiment: do complementary hits improve Top-5?", "",
             "## Protocol and declared search", "",
             "The source plan was saved before scoring thirteen hybrid configurations. This follows the shared training-input study; its selected components use full weeks 11–20: MF/PPR at 50% training coverage, weekly rules/CBF at 80%, and the common 50%-training popularity fallback. No component is refitted here.",
             "Validation remains the original >=80% frequency Top-5, with all 4,030 primary users, the nested 1,150-user template subset, all 6,384 eligible programme IDs and repeats allowed. The primary cohort alone selects a configuration; the template subset is descriptive reporting.",
             "", "### Rank fusion", "",
             "For each candidate, `score = sum_m weight_m / (offset + rank_m)`. Component ranks are one-based. Each component supplies its saved Top-5; an absent item contributes zero. These utilities are not calibrated watch probabilities. The retrieval shortlist is the union of those lists, bounded by the unchanged candidate eligibility pool.",
             "Offsets 0 and 10 contrast first-rank emphasis with stronger consensus emphasis on these short lists. Ties use the full 50%-training popularity order, then numeric ID; exact rational keys prevent rounding from breaking mathematical ties. Popularity supplies any missing slots. All 43 users without 50%-qualified training history retain exactly the same popularity Top-5 across every component and hybrid.",
             "The configurations compare MF+PPR; adding a modest popularity or weekly-rule contribution; adding both; equal fusion of all five methods; and MF/popularity or PPR/popularity alone. The complete weights and offsets are in plan.json and each run's config.json.",
             "", "### Training-only switching", "",
             "Two additional configurations return popularity when a user has <=5 distinct programmes under the 50% training definition, otherwise MF or PPR. The threshold is a fixed coarse-history boundary motivated by the earlier diagnostic, not fitted per user. Validation answers, their familiar/new composition and per-user AP never enter inference.",
             "", "## All results", "",
             "| Strategy | MAP@5: all 4,030 | MAP@5: template 1,150 | Delta vs MF: all |", "|---|---:|---:|---:|"]
    order = list(plan["sources"]) + [r["id"] for r in plan["runs"]]
    for name in order:
        label = LABELS.get(name, name)
        if name == selection["best_overall"]:
            label = "**" + label + "**"
        lines.append(f"| {label} | {primary.loc[name, 'map_at_5']:.8f} | {template.loc[name, 'map_at_5']:.8f} | {primary.loc[name, 'delta_vs_implicit_mf']:+.8f} |")
    lines += ["", "## Selected local strategy", "",
              f"**Primary-cohort selection: `{selection['best_overall']}`.** Best hybrid: `{selected}`. Its exact configuration is:",
              "", "```json", json.dumps(selected_config, indent=2), "```", "",
              "All candidate configurations, including failures, remain in comparison.csv; this stage does not extend the declared search after inspecting its scores.", "",
              "| Reference component | Primary MAP difference | Conditional 95% interval | Users better / worse / tied |", "|---|---:|---|---|"]
    for row in paired.loc[paired.cohort == "all_primary"].itertuples(index=False):
        lines.append(f"| {LABELS[row.reference]} | {row.mean_MAP_difference:+.8f} | [{row.conditional_95pct_lower:+.6f}, {row.conditional_95pct_upper:+.6f}] | {row.better_users:,} / {row.worse_users:,} / {row.equal_users:,} |")
    lines += ["", "Intervals use 2,000 paired user resamples with seed 20261023. They describe uncertainty conditional on this fitted-model/label/hold-out choice; they do not correct for the thirteen-way hybrid selection, earlier model/input selection, temporal drift or the unresolved organiser tie policy. They are not an untouched-test generalisation estimate.",
              "", "### What changed in the actual answers?", "",
              "| Reference | Correct pairs added | Correct pairs lost | Net correct pairs |", "|---|---:|---:|---:|"]
    for row in gain_loss:
        if row["cohort"] == "all_primary":
            lines.append(f"| {LABELS[row['reference']]} | {row['added_correct_pairs']:,} | {row['lost_correct_pairs']:,} | {row['net_correct_pairs']:+,} |")
    lines += ["", "The saved selected_hit_changes.csv identifies the added/lost IDs and delta AP for every user. Some users lose relevance or rank quality even when the macro average improves.",
              "", "## Familiar versus new-to-user", "",
              "Definitions remain those from the original strict/full history, including in the softer-input components. These are micro recalls within each true-answer type; AP contributions retain the full original denominator.",
              "", "| Strategy | Familiar recall: all | New recall: all | Familiar recall: template | New recall: template |", "|---|---:|---:|---:|---:|"]
    for name in ["popularity", "implicit_mf", "ppr", "association_rules", selected]:
        group = novelty.loc[(novelty.run_id == name) & (novelty.axis == "familiarity")].set_index(["cohort", "segment"])
        values = [group.loc[(c, s), "recall_of_true_type_micro"] for c in ["all_primary", "template_primary"] for s in ["familiar_80pct", "new_qualified_for_user"]]
        lines.append(f"| {LABELS.get(name, name)} | " + " | ".join(f"{v:.2%}" for v in values) + " |")
    lines += ["", "New-to-user does not imply never seen or enjoyed. Partial prior exposure is separately recorded. The selected hybrid remains much stronger at repeated preferences than new-to-user truth; this is not an exploration or satisfaction experiment.",
              "", "## Original history segments", ""]
    strategies = ["popularity", "implicit_mf", "ppr", selected]
    for cohort in ["all_primary", "template_primary"]:
        lines += [f"### {cohort}", "", "| Original strict distinct history | Users | Popularity | MF 50% | PPR 50% | Selected hybrid |", "|---|---:|---:|---:|---:|---:|"]
        group = history.loc[(history.cohort == cohort) & (history.axis == "history_distinct")].set_index(["run_id", "segment"])
        for segment in ["0 (cold)", "1-5", "6-20", "21-50", "51+"]:
            count = int(group.loc[(selected, segment), "users"])
            values = [group.loc[(name, segment), "map_at_5"] for name in strategies]
            lines.append(f"| {segment} | {count:,} | " + " | ".join(f"{v:.6f}" for v in values) + " |")
        lines.append("")
    lines += ["The original cold bin contains 59 users; 16 acquire qualifying history at 50%, leaving 43 actual cold users. The fixed 59-user bin therefore can differ across strategies even though every actual cold fallback is identical. Both the fixed-history diagnostic and the actual 50% routing feature are saved.",
              "", "## Evidence-backed interpretation", "",
              f"- Equal MF/PPR fusion already improves the primary MAP from {primary.loc['implicit_mf', 'map_at_5']:.6f} to {primary.loc['rrf_mf_ppr_k0', 'map_at_5']:.6f}. With the same offset and MF/PPR weights, adding weekly rules raises it to {primary.loc['rrf_mf_ppr_rules_k0', 'map_at_5']:.6f}. This is a realised Top-5 gain, beyond the earlier up-to-25-item union diagnostic.",
              "- Weighted rules contribute differently from the collaborative pair. In this plan, making all five methods equally influential performs worse than the strongest standalone models on the primary cohort. This is evidence for the tested weighting, not proof that CBF can never help a hybrid.",
              "- Adding popularity can increase any-hit coverage without maximising MAP: how correct IDs are ranked matters. The sparse-history switches offer only small macro gains over their respective standalone components.",
              "- The selected hybrid improves the average, but popularity remains ahead in the original-cold primary bin and the small template 1–5-history bin. Gains are not uniform across users.",
              f"- The highest template-subset score is {template.map_at_5.max():.8f}, from `{template.map_at_5.idxmax()}`; it does not replace the primary-cohort selection.",
              "- Source models and earlier input choices were already selected on this same temporal hold-out. Lower-ranked candidates beyond component Top-5 are untested by this fusion study. The unknown fifth-place truth tie policy and sparse labelled-airtime coverage remain limitations.",
              "", "## Examples and cost", "",
              "recommendation_examples.csv keeps the same earlier light/heavy viewers and shows all five current components plus the selected hybrid, with ordered IDs, pre-cutoff schedule titles/categories and true-Top-5 matches. These are assistant-produced examples awaiting the student's own review.", "",
              "| Example | User ID | Popularity AP | MF AP | PPR AP | CBF AP | Rules AP | Hybrid AP |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    example_frame = pd.DataFrame(example_rows)
    for role, user in examples.itertuples(index=False, name=None):
        values = example_frame.loc[example_frame.user_id == user].groupby("run_id").user_AP_at_5.first()
        lines.append(f"| {role} | {user} | " + " | ".join(f"{values[name]:.6f}" for name in [*plan["sources"], selected]) + " |")
    lines += ["", "The light viewer illustrates a local loss versus PPR despite the macro gain; the heavy viewer still favours popularity. The examples were retained from the earlier training-based choice rather than picked to flatter the hybrid.",
              "The selected fusion inference took " + f"{json.loads((OUT / 'runs' / selected / 'summary.json').read_text())['runtime']['fusion_inference_seconds_excludes_component_fits']:.3f}" + " seconds for 4,030 users in this run. This excludes component fitting/inference and all evaluation/report writing. Environment and per-configuration times are saved; the hybrid adds the cost of retaining and operating its component models.",
              "", "## Verification and reproduction", "",
              f"Five targeted unit tests passed. Independent verification passed {len(verification['checks'])} checks for all thirteen hybrids and five components: frozen inputs/provenance, 50% counts reconstructed from airing-level training evidence, common cold fallback, exact-rational ranks/AP/MAP, fixed segments/novelty, explanation ranks, per-user answer changes, and reproducible paired intervals.",
              "", "```bash", "python3 -m unittest discover -s scripts -p 'test_hybrids.py'", "python3 scripts/run_hybrid_experiments.py", "python3 scripts/verify_hybrid_experiments.py", "python3 scripts/summarize_hybrid_experiments.py", "```", "",
              "The source plan, component paths, input SHA-256s, code fingerprints, environment, every prediction and per-user score are saved. selection.json records a local-validation strategy selection. Final refitting, Kaggle scoring and the student's personal verification are later steps.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT / 'README.md'} and same-user recommendation examples.")
    print(pd.DataFrame(gain_loss).to_string(index=False))


if __name__ == "__main__":
    main()
