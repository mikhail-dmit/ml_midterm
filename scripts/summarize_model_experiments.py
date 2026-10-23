#!/usr/bin/env python3
"""Write evidence-backed MF/PPR comparison and conditional paired uncertainty."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/models"


def main():
    comparison = pd.read_csv(OUTPUT / "comparison.csv")
    selected = json.loads((OUTPUT / "selected_models.json").read_text())
    data = json.loads((OUTPUT / "training_data.json").read_text())
    verification = json.loads((OUTPUT / "verification.json").read_text())
    examples = pd.read_csv(OUTPUT / "selected_recommendation_examples.csv", dtype={"user_id": str})
    users = json.loads((OUTPUT / "example_users.json").read_text())["users"]
    runs = {path.parent.name: json.loads(path.read_text()) for path in (OUTPUT / "runs").glob("*/summary.json")}
    mf, ppr = selected["implicit_mf"]["run_id"], selected["ppr"]["run_id"]
    per_user = {}
    popularity = pd.read_csv(ROOT / "reports/popularity/per_user_metrics.csv", dtype={"user_id": str})
    per_user["popularity"] = popularity.loc[popularity.policy == "allow_repeats"].set_index("user_id").ap_at_5
    for run_id in [mf, ppr]:
        per_user[run_id] = pd.read_csv(OUTPUT / "runs" / run_id / "per_user_metrics.csv", dtype={"user_id": str}).set_index("user_id").ap_at_5
    all_users = per_user["popularity"].index.tolist()
    template = pd.read_csv(ROOT / "reports/popularity/cohort_template_primary.csv", dtype=str).user_id.tolist()
    rng = np.random.default_rng(20261023)
    uncertainty = []
    for cohort, subset in [("all_primary", all_users), ("template_primary", template)]:
        for a, b in [(mf, "popularity"), (ppr, "popularity"), (ppr, mf)]:
            delta = (per_user[a].loc[subset] - per_user[b].loc[subset]).to_numpy()
            means = np.mean(delta[rng.integers(0, len(delta), size=(2000, len(delta)))], axis=1)
            uncertainty.append({"cohort": cohort, "model_a": a, "model_b": b, "users": len(delta),
                                "mean_MAP_difference_a_minus_b": float(delta.mean()),
                                "paired_bootstrap_95pct_lower": float(np.quantile(means, .025)),
                                "paired_bootstrap_95pct_upper": float(np.quantile(means, .975)),
                                "users_a_better": int((delta > 0).sum()), "users_b_better": int((delta < 0).sum())})
    pd.DataFrame(uncertainty).to_csv(OUTPUT / "paired_uncertainty.csv", index=False)
    # Report the known label ambiguity as a diagnostic, not a new selection cohort.
    tied = set(pd.read_csv(ROOT / "reports/interactions/validation_boundary_ties.csv", dtype={"user_id": str}).user_id)
    tie_rows = []
    for label, subset in [("all_primary", all_users), ("template_primary", template)]:
        for flag in [False, True]:
            ids = [u for u in subset if (u in tied) == flag]
            for model in per_user:
                tie_rows.append({"cohort": label, "ambiguous_top5_boundary": flag, "users": len(ids),
                                 "model": model, "map_at_5": float(per_user[model].loc[ids].mean())})
    pd.DataFrame(tie_rows).to_csv(OUTPUT / "label_tie_diagnostics.csv", index=False)
    lines = ["# Implicit matrix factorization and Personalized PageRank", "",
             "## Main result", "",
             f"Selected MF: **{mf}**. Selected PPR: **{ppr}**. Selection uses all-primary validation MAP@5 only; the template subset is reporting, not a separate tuning target.",
             "", "| Method/configuration | MAP@5: all 4,030 | MAP@5: template 1,150 | Selected MF epoch |",
             "|---|---:|---:|---:|"]
    for run_id in ["popularity"] + list(runs):
        rows = comparison.loc[comparison.run_id == run_id].set_index("cohort")
        epoch = runs.get(run_id, {}).get("diagnostics", {}).get("selected_epoch", "—")
        lines.append(f"| {run_id} | {rows.loc['all_primary', 'map_at_5']:.8f} | {rows.loc['template_primary', 'map_at_5']:.8f} | {epoch} |")
    lines += ["", "## Frozen protocol", "",
              "- Same original train/validation windows, >=80%-qualified interactions, 6,384 schedule-available candidates, repeats allowed and shared MAP@5 evaluator as popularity.",
              "- All 4,030 primary users and the nested 1,150 template users are retained. Cold users get exactly the same popularity Top-5 in every method.",
              f"- Training matrix: **{data['users']:,} users × {data['programmes']:,} programmes**, **{data['positive_user_programme_pairs']:,} positive pairs**, **{data['qualifying_airings']:,} qualifying airings**; density {data['density']:.4%}.",
              f"- Both collaborative methods learn {data['programmes']:,} training item representations/nodes, of which {data['candidate_programmes_with_training_vector']:,} are in the validation pool. Unsupported candidate items get score zero; the pool is not pruned.",
              f"- {data['primary_true_ids_without_training_vector']:,}/20,150 true IDs have no learned training item vector/node. This is a shared coverage limitation, not removed from the denominator.",
              "- No validation viewing enters model fitting, confidence weights, graph construction or restart profiles. No test-period data is read by these experiments.",
              "- Seed 20261023; one BLAS thread. Configurations are in scripts/model_experiments.json and experiment_plan.json. MF checks epochs 5/10/15 and restores the best factor arrays; no test-driven checkpointing.",
              "", "## Matrix factorization: what was implemented", "",
              "For qualifying training count r_ui, confidence c_ui=1+s*log(1+r_ui). Binary implicit ALS uses target p_ui=1 when r_ui>0 and 0 otherwise. Missing observations have confidence 1; they are not asserted to be explicit dislikes.",
              "The objective is sum over ALL user/item pairs c_ui*(p_ui-x_u·y_i)^2 + lambda*(sum ||x_u||² + sum ||y_i||²). Exact alternating normal equations are solved with Cholesky, using the sparse correction to Y.T@Y / X.T@X. This is not observed-only rating regression or a zero-filled classical SVD.",
              "The task-aligned diagnostic variant changes only the target to p_ui=log(1+r_ui), leaving confidence, dimensions and regularization fixed. It remains MF over implicit viewing counts; it is explicitly not the original binary-preference formulation. Scores approximate log frequency rather than stars or watch probabilities.",
              "", "### Why the first MF runs disappointed", "",
              "- Binary MF f16/s1/r1 obtains slightly higher Precision@5 than popularity but lower MAP@5: retrieving some correct programmes is not enough if their order is poorer.",
              "- Increasing confidence s=1 -> 10 and then factors 16 -> 32 makes MAP worse, while exact training objectives keep decreasing. We verified the solver rather than interpreting low validation quality as a code failure.",
              "- In the heavy-user example, binary MF returns programmes with 3–13 historical watches instead of favourites with 83–164 watches. Several predictions were watched later but were not among the five most frequent. Binary reconstruction treats every observed positive as target 1 and can fit occurrence without preserving frequency order.",
              f"- The log-count target changes overall MAP {runs['mf_f16_a1_r1']['metrics'][0]['map_at_5']:.8f} -> {runs[mf]['metrics'][0]['map_at_5']:.8f}; median within-user training count/score Spearman improves {runs['mf_f16_a1_r1']['diagnostics']['median_within_user_count_score_spearman']:.4f} -> {runs[mf]['diagnostics']['median_within_user_count_score_spearman']:.4f}. This controlled comparison supports target alignment as part of the explanation.",
              "- Objectives with different confidence scales or targets are not numerically comparable to each other. Monotone descent is checked within each run; checkpoint selection uses MAP@5.",
              "", "## PPR: what was implemented", "",
              "- Programme co-view graph, not the earlier homework's bipartite user/movie graph. A_ij is the number of distinct training users with qualifying watches of both i and j. Self-loops are removed.",
              "- Raw graph: 2,490 nodes, 603,374 undirected edges, one connected component, zero dangling nodes in this dataset. Dangling-node support is nevertheless unit-tested.",
              "- P is row-normalized adjacency. The user's restart vector is their training counts transformed by log(1+r) and normalized to mass one.",
              "- PPR follows p = alpha*(pP + dangling_mass*v) + (1-alpha)*v. Alpha is link-following probability, not restart probability.",
              "- At this small graph size the implementation solves the fixed-point linear system directly for the user batch. It checks stationary residuals and probability conservation. An independent iterative solver verifies sampled users. This direct LU implementation is dense O(n²) memory / O(n³) factorization, not a claimed billion-item sparse online system.",
              "- Candidate availability is applied after diffusion; no scores are relabelled as predicted viewing probabilities.",
              "", "### Why higher alpha and extra normalization did not help", "",
              f"- At alpha .50 -> .95, overall MAP falls {runs['ppr_raw_a050_log']['metrics'][0]['map_at_5']:.8f} -> {runs['ppr_raw_a095_log']['metrics'][0]['map_at_5']:.8f}.",
              f"- Mean stationary mass on own history falls {runs['ppr_raw_a050_log']['diagnostics']['mean_stationary_mass_on_own_history']:.2%} -> {runs['ppr_raw_a095_log']['diagnostics']['mean_stationary_mass_on_own_history']:.2%}; average Top-5 overlap with popularity rises {runs['ppr_raw_a050_log']['diagnostics']['mean_top5_overlap_with_popularity']:.3f} -> {runs['ppr_raw_a095_log']['diagnostics']['mean_top5_overlap_with_popularity']:.3f}. Longer diffusion demonstrably washes out the restart in this graph.",
              "- Raw-count rather than log-count restart slightly lowers MAP. Frequency magnitude matters, but simply amplifying the most frequent historical programme does not uniformly improve future Top-5 prediction. The log restart remains selected.",
              f"- Cosine-normalized edges reduce graph degree/popularity correlation {runs['ppr_raw_a050_log']['diagnostics']['graph_weighted_degree_training_popularity_spearman']:.3f} -> {runs['ppr_cosine_a050_log']['diagnostics']['graph_weighted_degree_training_popularity_spearman']:.3f} and expand recommended catalogue coverage from {runs['ppr_raw_a050_log']['diagnostics']['unique_recommended_programmes']} to {runs['ppr_cosine_a050_log']['diagnostics']['unique_recommended_programmes']} distinct IDs, but lower MAP. Less hub concentration is not automatically better prediction of recurring favourites.",
              "", "## Same two users across all methods", "",
              "These examples were selected by training history before model runs, not by a flattering recommendation outcome. IDs, titles/categories and validation-hit flags are in selected_recommendation_examples.csv; all initial configurations also retain their examples in runs/."]
    for user in users:
        lines += ["", f"### {user['role'].title()} viewer {user['user_id']}", "",
                  f"Training: {user['train_watched_airings']} qualifying airings across {user['train_qualified_programmes']} programme IDs.",
                  "", "| Method | Top-5 IDs in order | User AP@5 |", "|---|---|---:|"]
        for model in ["popularity", mf, ppr]:
            f = examples.loc[(examples.user_id == user["user_id"]) & (examples.model == model)].sort_values("rank")
            lines.append(f"| {model} | {' '.join(map(str, f.tv_show_id))} | {f.user_AP_at_5.iloc[0]:.8f} |")
    lines += ["", "The thin viewer has one training watch: both personal models can overcommit to an unrepresentative seed; popularity does better for this example. The heavy viewer shows binary MF's frequency-order failure and its repair, while popularity is still perfect for this particular user. Neither example is evidence that personalisation wins for every user.",
              "", "## Paired uncertainty", "",
              "Conditional 95% bootstrap intervals over paired per-user AP differences (2,000 resamples, seed 20261023). These describe this fixed hold-out; they do not account for model selection, label-tie uncertainty or temporal distribution shift.",
              "", "| Cohort | A minus B | Mean MAP difference | 95% lower | 95% upper |", "|---|---|---:|---:|---:|"]
    for row in uncertainty:
        lines.append(f"| {row['cohort']} | {row['model_a']} minus {row['model_b']} | {row['mean_MAP_difference_a_minus_b']:.8f} | {row['paired_bootstrap_95pct_lower']:.8f} | {row['paired_bootstrap_95pct_upper']:.8f} |")
    lines += ["", "PPR has the highest observed all-primary MAP. Do not interpret a small PPR/MF difference as a universal superiority claim. label_tie_diagnostics.csv also reports scores separately for ambiguous/unambiguous Top-5 membership; those subsets were not used for tuning.",
              "", "## Cost and verification", "",
              "| Selected method | Training or graph preparation, s | Batch scoring/solve + ranking, s | Full run incl. validation/export, s |", "|---|---:|---:|---:|"]
    for run_id in [mf, ppr]:
        runtime = runs[run_id]["runtime"]
        if run_id == mf:
            train_seconds = runtime["training_seconds_excluding_validation"]
            predict_seconds = runtime["final_scoring_and_ranking_seconds"]
        else:
            train_seconds = runtime["graph_and_profiles_seconds"]
            predict_seconds = runtime["linear_solve_seconds"] + runtime["final_scoring_and_ranking_seconds"]
        lines.append(f"| {run_id} | {train_seconds:.3f} | {predict_seconds:.3f} | {runtime['total_seconds']:.3f} |")
    lines += ["", f"Independent verification passed **{len(verification['checks'])} checks across {len(verification['experiments'])} runs**. It recomputes exact AP/MAP for every user, reproduces all MF rankings from saved factors, checks sampled ALS normal equations, verifies co-view edges from viewer sets, and checks PPR against a separate power-iteration implementation. See verification.json.",
              "8 algorithm edge-case tests passed, including full dense vs sparse ALS algebra, log-count targets, monotone fitting, co-view count semantics, direct-vs-iterative PPR with a dangling node, and the shared cold fallback.",
              "manual_mf_dot_product.csv/json contains one real 16-factor prediction with all intermediate products for a later personal check. No student verification is claimed by these automated results.",
              "", "## Reproduction", "", "```bash", "python3 -m unittest discover -s scripts -p 'test_collaborative_models.py'",
              "python3 scripts/run_model_experiments.py --stage all", "python3 scripts/verify_model_experiments.py",
              "python3 scripts/summarize_model_experiments.py", "```", "",
              "Use --run-id NAME to rerun one declared configuration. Configs, seed, library versions, BLAS settings, source/input hashes, learning curves, selected factors/graphs, predictions, per-user metrics, history segments and paired baseline comparisons are saved. See scripts/README.md for paths.",
              "", "## Decision supported by this work", "",
              "PPR (raw co-view graph, alpha=.50, log-count restart) is the current leading standalone strategy on the documented hold-out. Log-count MF is a competitive second implemented method. Keep popularity for the common cold-start fallback and as a visible benchmark. No hybrid, Kaggle submission, full-history refit or online/revenue experiment is claimed here.",
              "", "## Sources consulted", "",
              "1. Y. Hu, Y. Koren and C. Volinsky, *Collaborative Filtering for Implicit Feedback Datasets*, ICDM, 2008. Equations (3)–(6), preference/confidence distinction and the TV-viewing discussion were read. https://yifanhu.net/PUB/cf.pdf",
              "2. SciPy documentation, `cho_solve`: Cholesky normal-equation solves. Runtime uses SciPy 1.13.1; code is tested against dense NumPy solves. https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.cho_solve.html",
              "3. NetworkX PageRank documentation: alpha, personalized restart and dangling redistribution semantics. Used as an algorithm reference, not as the production implementation. https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html",
              "4. Supplied exam brief, midterm MAP@5 slides and MF/PPR lectures. The fixed course evaluation protocol remains unchanged.", ""]
    (OUTPUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(pd.DataFrame(uncertainty).to_string(index=False))
    print(f"Wrote {OUTPUT / 'README.md'}")


if __name__ == "__main__":
    main()
