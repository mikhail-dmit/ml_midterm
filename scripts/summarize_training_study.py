#!/usr/bin/env python3
"""Report method strengths/complementarity and controlled training-input effects."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/training_study"
REF = OUT / "reference_analysis"
METHODS = ["popularity", "implicit_mf", "ppr", "content_based", "association_rules"]
LABELS = {"popularity": "Popularity", "implicit_mf": "MF", "ppr": "PPR", "content_based": "CBF", "association_rules": "Rules"}


def method_table(frame, index_col, value="map_at_5", extra=None, digits=6):
    pivot = frame.pivot(index=index_col, columns="method", values=value)
    lines = ["| " + index_col + (" | Users" if extra is not None else "") + " | " + " | ".join(LABELS[m] for m in METHODS) + " |",
             "|---|" + ("---:|" if extra is not None else "") + "---:|"*len(METHODS)]
    order = list(extra) if extra is not None else sorted(pivot.index)
    for key in order:
        lines.append("| " + str(key) + (f" | {extra[key]:,}" if extra is not None else "") + " | " +
                     " | ".join(f"{pivot.loc[key, m]:.{digits}f}" for m in METHODS) + " |")
    return lines


def main():
    comparison = pd.read_csv(OUT / "comparison.csv")
    novelty = pd.read_csv(REF / "novelty_metrics.csv")
    history = pd.read_csv(REF / "history_metrics.csv")
    pairs = pd.read_csv(REF / "pairwise_complementarity.csv")
    exclusive = pd.read_csv(REF / "exclusive_hits.csv")
    overlap_distribution = pd.read_csv(REF / "hit_overlap_distribution.csv")
    overall = pd.read_csv(REF / "overall_metrics.csv")
    verification = json.loads((OUT / "verification.json").read_text())
    training = []
    for path in sorted(OUT.glob("*_t*/training_summary.json")):
        record = json.loads(path.read_text())
        setting = record.pop("setting")
        training.append({**setting, **record})
    train_stats = pd.DataFrame(training)
    train_stats.to_csv(OUT / "training_data_comparison.csv", index=False)
    # Check that history segments partition the original cohort without changing AP.
    for (cohort, method, axis), group in history.groupby(["cohort", "method", "axis"]):
        target = overall.loc[(overall.cohort == cohort) & (overall.method == method)].iloc[0]
        assert group.users.sum() == target.users
        assert abs((group.users*group.map_at_5).sum()/group.users.sum() - target.map_at_5) < 1e-14
    # These are conditional descriptive intervals, not a second selection stage.
    rng = np.random.default_rng(20261023)
    intervals = []
    cache = {}
    def user_ap(setting, method):
        key = (setting, method)
        if key not in cache:
            cache[key] = pd.read_csv(OUT / setting / "runs" / method / "per_user_metrics.csv", dtype={"user_id": str}).set_index("user_id").ap_at_5
        return cache[key]
    primary = pd.read_csv(ROOT / "reports/popularity/cohort_primary.csv", dtype=str).user_id.tolist()
    template = pd.read_csv(ROOT / "reports/popularity/cohort_template_primary.csv", dtype=str).user_id.tolist()
    comparisons = [("full10_t50", m, "full10_t80", m) for m in METHODS]
    comparisons += [("recent4_t80", m, "early4_t80", m) for m in METHODS]
    comparisons += [("full10_t80", m, "recent4_t80", m) for m in METHODS]
    comparisons += [("full10_t50", "implicit_mf", "full10_t50", "ppr")]
    for cohort, users in [("all_primary", primary), ("template_primary", template)]:
        for sa, ma, sb, mb in comparisons:
            delta = (user_ap(sa, ma).loc[users]-user_ap(sb, mb).loc[users]).to_numpy()
            resamples = delta[rng.integers(0, len(users), size=(2000, len(users)))].mean(axis=1)
            intervals.append({"cohort": cohort, "setting_a": sa, "method_a": ma, "setting_b": sb, "method_b": mb,
                              "mean_MAP_difference": float(delta.mean()), "conditional_95pct_lower": float(np.quantile(resamples, .025)),
                              "conditional_95pct_upper": float(np.quantile(resamples, .975))})
    pd.DataFrame(intervals).to_csv(OUT / "paired_input_effects.csv", index=False)
    truth_attributes = pd.read_csv(REF / "true_answer_attributes.csv", dtype={"user_id": str})
    truth_attributes["familiar"] = truth_attributes.familiarity == "familiar_80pct"
    composition = truth_attributes.groupby("user_id").familiar.sum().rename("familiar_true_count").reset_index()
    composition["new_true_count"] = 5-composition.familiar_true_count
    composition["validation_composition"] = composition.familiar_true_count.map(
        lambda n: "all_five_new" if n == 0 else "all_five_familiar" if n == 5 else "mixed")
    composition.to_csv(REF / "validation_truth_composition.csv", index=False)
    composition_rows = []
    for cohort, ids in [("all_primary", primary), ("template_primary", template)]:
        for label, group in composition.loc[composition.user_id.isin(ids)].groupby("validation_composition"):
            for method in METHODS:
                composition_rows.append({"cohort": cohort, "validation_composition": label, "users": len(group), "method": method,
                                         "map_at_5": float(user_ap("full10_t80", method).loc[group.user_id].mean()),
                                         "use": "Post-hoc diagnosis only; future truth composition is not available at serving time"})
    composition_metrics = pd.DataFrame(composition_rows)
    composition_metrics.to_csv(REF / "truth_composition_metrics.csv", index=False)
    stability = []
    for setting in sorted(comparison.setting.unique()):
        pool = pd.read_csv(OUT / setting / "candidate_scores.csv")
        stability.append({"setting": setting, "top5_ids": " ".join(map(str, pool.head(5).tv_show_id)),
                          "top5_counts": " ".join(map(str, pool.head(5).training_watched_airings)),
                          "map_primary": float(comparison.loc[(comparison.setting == setting) & (comparison.method == "popularity") & (comparison.cohort == "all_primary"), "map_at_5"].iloc[0])})
    pd.DataFrame(stability).to_csv(OUT / "popularity_top5_stability.csv", index=False)
    best = {}
    for method in METHODS:
        records = comparison.loc[(comparison.method == method) & (comparison.cohort == "all_primary")]
        row = records.sort_values("map_at_5", ascending=False, kind="stable").iloc[0]
        best[method] = {"setting": row.setting, "map_primary": float(row.map_at_5),
                        "map_template": float(comparison.loc[(comparison.setting == row.setting) & (comparison.method == method) & (comparison.cohort == "template_primary"), "map_at_5"].iloc[0]),
                        "meaning": "Study-only selection on all-primary scores; original shared protocol files not overwritten"}
    (OUT / "best_setting_by_method.json").write_text(json.dumps(best, indent=2) + "\n")
    # Retain all detailed per-setting novelty/history data in one convenient file.
    novel_all, history_all = [], []
    for folder in sorted(OUT.glob("*_t*/runs/*")):
        if not (folder / "fixed_novelty_metrics.csv").exists():
            continue
        n = pd.read_csv(folder / "fixed_novelty_metrics.csv")
        h = pd.read_csv(folder / "fixed_history_metrics.csv")
        n["setting"], n["method"] = folder.parents[1].name, folder.name
        h["setting"], h["method"] = folder.parents[1].name, folder.name
        # folder = setting/runs/method; setting is parent of runs.
        novel_all.append(n)
        history_all.append(h)
    pd.concat(novel_all, ignore_index=True).to_csv(OUT / "novelty_all_settings.csv", index=False)
    pd.concat(history_all, ignore_index=True).to_csv(OUT / "history_all_settings.csv", index=False)
    lines = ["# Where each method works, and shared training-input experiments", "",
             "## Scope and controls", "",
             "This stage is diagnosis before hybrids. No fusion, switching recommender or target-aware per-user method selection was trained. The reference analysis uses the previously selected strict/full-history models.",
             "The shared study changes only training behaviour: watched coverage threshold 80/50/20 percent × full ten / older four / recent four weeks. All five methods receive the same selected events in a setting. Validation stays the original >=80% Top-5, with the same 4,030 users, 1,150-user subset, 6,384 candidates, repeat policy and MAP@5 denominator.",
             "Method hyperparameters are frozen at their previous selections: log-count MF f16/confidence1/reg1/15 epochs; raw PPR alpha=.50/log restart; rich+title TF-IDF CBF/count profile; weekly pair rules/joint>=5/confidence>=.10/lift>1/log query weights.",
             "CBF item vectors/vocabulary/IDF remain fixed from all pre-May18 metadata. Window changes concern viewing behaviour, not erasing known catalogue attributes. Each setting fits its own training popularity, shared by all cold/insufficient-signal fallbacks. Original strict-history familiarity and user bins remain fixed across settings.",
             "", "## 1. How many true answers are familiar versus new?", "",
             "Familiar means a programme with >=1 original >=80% qualifying training watch in weeks 11–20. New means no such qualifying watch; it is not proof the person has never seen it or would enjoy discovering it.",
             "", "| Cohort | Familiar true slots | New true slots | New but partial overlap before | New with no recorded programme overlap |", "|---|---:|---:|---:|---:|"]
    for cohort in ["all_primary", "template_primary"]:
        f = novelty.loc[(novelty.method == "popularity") & (novelty.cohort == cohort)]
        def cell(axis, label):
            r = f.loc[(f.axis == axis) & (f.segment == label)].iloc[0]
            return f"{r.true_slots:,} ({r.true_slot_fraction:.2%})"
        lines.append(f"| {cohort} | {cell('familiarity', 'familiar_80pct')} | {cell('familiarity', 'new_qualified_for_user')} | {cell('exposure', 'new_but_partial_training_overlap')} | {cell('exposure', 'new_no_recorded_training_overlap')} |")
    lines += ["", "### Which types do methods retrieve?", "",
              "These are micro recalls of each true-answer type, not separately renormalized MAP scores. Familiar and new AP-credit contributions are also saved; their sum exactly reproduces original MAP@5.",
              "", "| Reference method | Familiar recall: all | New recall: all | Familiar recall: template | New recall: template |", "|---|---:|---:|---:|---:|"]
    for method in METHODS:
        f = novelty.loc[(novelty.method == method) & (novelty.axis == "familiarity")].set_index(["cohort", "segment"])
        values = [f.loc[(c, s), "recall_of_true_type_micro"] for c in ["all_primary", "template_primary"] for s in ["familiar_80pct", "new_qualified_for_user"]]
        lines.append(f"| {LABELS[method]} | " + " | ".join(f"{v:.2%}" for v in values) + " |")
    lines += ["", "PPR and MF excel at recurring favourites. Popularity and weekly rules recover substantially more new-to-user truth, despite lower overall MAP. CBF's unfamiliar outputs are not automatically relevant discoveries. In the strict reference runs all methods miss the 1,043 true slots with no global strict training support.",
              "", "### User-level target composition (post-hoc only)", "",
              "These groups use validation answers for explanation, not for training or a deployable switching rule.", ""]
    comp = composition_metrics.loc[composition_metrics.cohort == "all_primary"]
    sizes = comp.loc[comp.method == "popularity"].set_index("validation_composition").users.to_dict()
    lines += method_table(comp, "validation_composition", extra={k: int(sizes[k]) for k in ["all_five_new", "mixed", "all_five_familiar"]})
    lines += ["",
              "", "## 2. Short versus long histories", "",
              "Bins use only original training data; users never move bins when softer/recent inputs are tested. History size is shown by distinct programme count below. The files also cover qualifying-airing volume, active training weeks and age of last training activity."]
    order = ["0 (cold)", "1-5", "6-20", "21-50", "51+"]
    for cohort in ["all_primary", "template_primary"]:
        f = history.loc[(history.cohort == cohort) & (history.axis == "history_distinct")]
        sizes = f.loc[f.method == "popularity"].set_index("segment").users.to_dict()
        lines += ["", f"### {cohort}: MAP@5 by distinct-programme history", ""]
        lines += method_table(f, "segment", extra={k: int(sizes[k]) for k in order})
    lines += ["", "All truly cold reference users get the same popularity fallback. For 1–5-programme histories, popularity is competitive or better than the personal models; the template subgroup has only 39 users, so this is a small-sample observation, not a validated switching rule. MF/PPR's gains are much clearer for richer and consistently active histories.",
              "Popularity itself improves for richer-history users: cohort composition/target predictability changes too. These strata do not prove that increasing a person's history alone causes the observed gains.",
              "", "## 3. Same users or different correct programmes?", "",
              "Any-hit user overlap and correct (user,programme) pair overlap are distinct. Two methods can both hit a user while finding different favourites.",
              "", "| Reference pair | Both hit users | A-only hit users | B-only hit users | A-only correct pairs | B-only correct pairs | Mean shared Top-5 IDs | AP Spearman |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for a, b in [("implicit_mf", "ppr"), ("ppr", "association_rules"), ("popularity", "ppr")]:
        r = pairs.loc[(pairs.cohort == "all_primary") & (pairs.method_a == a) & (pairs.method_b == b)].iloc[0]
        lines.append(f"| A={LABELS[a]}, B={LABELS[b]} | {r.both_hit_users:,} | {r.a_only_hit_users:,} | {r.b_only_hit_users:,} | {r.a_only_correct_pairs:,} | {r.b_only_correct_pairs:,} | {r.mean_shared_recommended_ids:.3f} | {r.AP_spearman:.3f} |")
    lines += ["", "MF/PPR any-hit user Jaccard is 0.952, but their correct-pair Jaccard is 0.816: complementarity is more about different answers/rankings for overlapping users than two disjoint audiences.",
              "", "| Method | Users only this method hits | Correct pairs only this method finds |", "|---|---:|---:|"]
    for r in exclusive.loc[exclusive.cohort == "all_primary"].itertuples(index=False):
        lines.append(f"| {LABELS[r.method]} | {r.exclusive_hit_users} | {r.exclusive_correct_pairs} |")
    missed_users = overlap_distribution.loc[(overlap_distribution.cohort == "all_primary") & (overlap_distribution.level == "users") & (overlap_distribution.methods_hitting == 0), "count"].iloc[0]
    missed_answers = overlap_distribution.loc[(overlap_distribution.cohort == "all_primary") & (overlap_distribution.level == "true_answers") & (overlap_distribution.methods_hitting == 0), "count"].iloc[0]
    lines += ["", f"Across the five separate lists, {4030-int(missed_users):,} users have at least one hit and {20150-int(missed_answers):,}/20,150 true pairs are found somewhere. This union can contain up to 25 recommendations per user; it is **not** a deployable Top-5 hybrid or a hybrid MAP result.",
              "The same pairwise and exclusive-hit analyses for the 1,150 users are saved separately by cohort in reference_analysis/*.csv.",
              "", "## 4. Shared threshold × history-window study", "",
              "All thresholds affect training only. Each qualifying airing contributes one count at its declared threshold. Lower thresholds add partial airings with equal count contribution rather than assigning fractional confidence per event.",
              "", "| Window | Dates, local half-open | Interpretation |", "|---|---|---|",
              "| full10 | Mar 9 – May 18 | All weeks 11–20 |",
              "| early4 | Mar 9 – Apr 6 | Older weeks 11–14 |",
              "| recent4 | Apr 20 – May 18 | Recent weeks 17–20 |",
              "", "Older/recent windows have the same four-calendar-week width. Raw viewing intervals are clipped and rejoined at their exact boundaries, retaining full airing duration denominators. Filtering by filename, airing start or an aggregated first/last timestamp alone was not used."]
    for cohort in ["all_primary", "template_primary"]:
        lines += ["", f"### {cohort}: MAP@5", ""]
        lines += method_table(comparison.loc[comparison.cohort == cohort], "setting")
    lines += ["", "### What the threshold effect means", "",
              "| Full-history threshold | Qualifying airings | Positive user/programme pairs | Cold primary users | True slots now in own history |", "|---|---:|---:|---:|---:|"]
    for t in [80, 50, 20]:
        r = train_stats.loc[train_stats.id == f"full10_t{t}"].iloc[0]
        lines.append(f"| {t}% | {r.positive_airings:,} | {r.positive_user_programme_pairs:,} | {r.cold_primary_users} | {r.true_slots_supported_by_this_history:,} |")
    lines += ["", "- Full-history 50% improves both MF and PPR; 20% is not better than 50%. CBF and rules instead prefer the strict 80% input in this study. There is no universally best threshold across the four methods.",
              "- The 50% signal adds useful partial-history evidence. Under the ORIGINAL fixed familiarity labels, PPR new-type hits rise 176 -> 379: partial-exposure hits 73 -> 298, while no-recorded-exposure hits fall 103 -> 81. This is mainly recovery from previously observed partial interests, not discovery of wholly unknown programmes.",
              "- MF new-type hits rise 348 -> 561, with partial-exposure hits 186 -> 405. Its familiar hits also rise 7,924 -> 7,994. Denominators/types have not been changed to manufacture this gain.",
              "- At 20%, the positive-pair matrix is much broader (352,915 vs 114,851), and partial events count like full watches. That can dilute content profiles and broaden weak rule associations. Weekly rules grow from 16,126 to 84,436, but distinct recommended IDs fall 49 -> 24 and MAP worsens. This is evidence about these inputs, not proof that every partial view is a dislike.",
              "- Only 122 of the 861,447 full-history 20%-qualified events have under 60 watched seconds. The effect should not be simplistically attributed entirely to tiny channel-surfing fragments; fractional coverage and changed association structure matter.",
              "- Some original cold users become warm at softer thresholds, but remain in their original diagnostic bins. Setting-specific cold-user counts are also reported; nobody is dropped.",
              "", "### What the window effect means", "",
              "At 80%, recent4 beats early4 for MF/PPR, but neither beats full10. Recent4 has 133,800 qualifying events vs early4's 125,294, 1,578 vs 1,137 supported items, and 138 vs 189 cold primary users. Equal calendar width does not equal identical sample volume/catalogue coverage, so recency is not isolated from those changes.",
              "Full history retains useful information. Truncating to recent four weeks increases cold users and removes globally useful programme support. CBF also retains a fixed pre-cutoff metadata corpus; only its viewing profile changes.",
              "", "### Why popularity scores sometimes repeat exactly", "",
              "Global count magnitudes change, but Top-5 ranking metrics change only when the recommended IDs/order change. Many settings retain exactly the same ordered five IDs. Recent4/80 swaps SpongeBob and Fakty at ranks 2/3, reducing MAP without changing the five-item set. Full10/20 swaps the last two IDs. See popularity_top5_stability.csv; counts/rankings were independently reconstructed, not cached accidentally.",
              "", "## Interpretation before hybrids", "",
              "- Reference PPR/MF are strongest for recurring favourites and richer histories; popularity/rules contribute more new-to-user answers and can help different missed users or items.",
              "- For subsequent MF/PPR experiments, full ten weeks with 50% training qualification is a supported candidate input. It is not a universal improvement for CBF/rules; strict/full comparisons remain preserved.",
              "- At full10/50, MF has slightly higher all-primary MAP (0.36592473 vs PPR 0.36497436), while PPR leads on the template subset (0.40020000 vs MF 0.39746957). Do not turn this small ordering difference into a universal new method ranking.",
              "- Shared inputs were tested with frozen original method hyperparameters. The study is conditional on those settings, one temporal hold-out and the existing unknown fifth-place tie policy. No hybrid was trained or scored.",
              "", "## Verification and reproduction", "",
              f"Independent verification passed **{len(verification['checks'])} checks across {len(verification['verified_runs'])} runs**: fixed source fingerprints, reference familiar/new classes and overlap arithmetic, all threshold aggregates, exact sparse counts/IDs, candidate/popularity reconstruction, cold fallbacks, original-prediction reproduction and exact AP/MAP. Window clipping was independently rejoined from original raw view fragments for boundary/DST/example users.",
              "Three targeted unit checks cover AP partitioning, user-vs-answer complementarity and exact threshold/boundary denominator arithmetic. Each new MF/PPR fit also performs its objective/stationary-mass assertions; algorithm algebra was independently verified in prior stages.",
              "", "```bash", "python3 -m unittest discover -s scripts -p 'test_training_study.py'",
              "python3 scripts/analyze_method_segments.py", "python3 scripts/training_study.py",
              "python3 scripts/verify_training_study.py", "python3 scripts/summarize_training_study.py", "```", "",
              "Use --setting recent4_t50 to rerun one setting. Window caches are fingerprinted; original truth/cohorts/candidates/content artifacts are read-only and their hashes checked throughout. Original reports/all_methods results are not overwritten.",
              "All detailed reference/subgroup/overlap tables, 45 sets of predictions/per-user scores, scenario counts, frozen plan, models and conditional paired-user intervals are saved. Intervals use 2,000 paired resamples and do not account for input/model selection or temporal/label uncertainty. Student personal verification remains unclaimed.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    key = pd.DataFrame(intervals)
    print(key.loc[(key.setting_a == "full10_t50") & (key.setting_b == "full10_t80")].to_string(index=False))
    print(key.loc[(key.method_a == "implicit_mf") & (key.method_b == "ppr")].to_string(index=False))
    print(f"Wrote {OUT / 'README.md'}")


if __name__ == "__main__":
    main()
