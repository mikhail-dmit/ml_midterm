# Implicit matrix factorization and Personalized PageRank

## Main result

Selected MF: **mf_f16_logtarget_a1_r1**. Selected PPR: **ppr_raw_a050_log**. Selection uses all-primary validation MAP@5 only; the template subset is reporting, not a separate tuning target.

| Method/configuration | MAP@5: all 4,030 | MAP@5: template 1,150 | Selected MF epoch |
|---|---:|---:|---:|
| popularity | 0.27939123 | 0.30530725 | — |
| ppr_cosine_a050_log | 0.35213730 | 0.38730435 | — |
| mf_f16_logtarget_a1_r1 | 0.35298677 | 0.38568116 | 15 |
| mf_f16_a10_r1 | 0.22296278 | 0.23373913 | 5 |
| mf_f32_a10_r1 | 0.21019603 | 0.22009855 | 5 |
| ppr_raw_a085_log | 0.33516543 | 0.36413333 | — |
| ppr_raw_a050_count | 0.35489413 | 0.39053333 | — |
| mf_f16_a1_r1 | 0.27097767 | 0.28804928 | 15 |
| ppr_raw_a050_log | 0.35775352 | 0.39209275 | — |
| ppr_raw_a095_log | 0.29378329 | 0.31657681 | — |

## Frozen protocol

- Same original train/validation windows, >=80%-qualified interactions, 6,384 schedule-available candidates, repeats allowed and shared MAP@5 evaluator as popularity.
- All 4,030 primary users and the nested 1,150 template users are retained. Cold users get exactly the same popularity Top-5 in every method.
- Training matrix: **4,737 users × 2,490 programmes**, **114,851 positive pairs**, **316,413 qualifying airings**; density 0.9737%.
- Both collaborative methods learn 2,490 training item representations/nodes, of which 1,874 are in the validation pool. Unsupported candidate items get score zero; the pool is not pruned.
- 1,043/20,150 true IDs have no learned training item vector/node. This is a shared coverage limitation, not removed from the denominator.
- No validation viewing enters model fitting, confidence weights, graph construction or restart profiles. No test-period data is read by these experiments.
- Seed 20261023; one BLAS thread. Configurations are in scripts/model_experiments.json and experiment_plan.json. MF checks epochs 5/10/15 and restores the best factor arrays; no test-driven checkpointing.

## Matrix factorization: what was implemented

For qualifying training count r_ui, confidence c_ui=1+s*log(1+r_ui). Binary implicit ALS uses target p_ui=1 when r_ui>0 and 0 otherwise. Missing observations have confidence 1; they are not asserted to be explicit dislikes.
The objective is sum over ALL user/item pairs c_ui*(p_ui-x_u·y_i)^2 + lambda*(sum ||x_u||² + sum ||y_i||²). Exact alternating normal equations are solved with Cholesky, using the sparse correction to Y.T@Y / X.T@X. This is not observed-only rating regression or a zero-filled classical SVD.
The task-aligned diagnostic variant changes only the target to p_ui=log(1+r_ui), leaving confidence, dimensions and regularization fixed. It remains MF over implicit viewing counts; it is explicitly not the original binary-preference formulation. Scores approximate log frequency rather than stars or watch probabilities.

### Why the first MF runs disappointed

- Binary MF f16/s1/r1 obtains slightly higher Precision@5 than popularity but lower MAP@5: retrieving some correct programmes is not enough if their order is poorer.
- Increasing confidence s=1 -> 10 and then factors 16 -> 32 makes MAP worse, while exact training objectives keep decreasing. We verified the solver rather than interpreting low validation quality as a code failure.
- In the heavy-user example, binary MF returns programmes with 3–13 historical watches instead of favourites with 83–164 watches. Several predictions were watched later but were not among the five most frequent. Binary reconstruction treats every observed positive as target 1 and can fit occurrence without preserving frequency order.
- The log-count target changes overall MAP 0.27097767 -> 0.35298677; median within-user training count/score Spearman improves 0.6097 -> 0.6960. This controlled comparison supports target alignment as part of the explanation.
- Objectives with different confidence scales or targets are not numerically comparable to each other. Monotone descent is checked within each run; checkpoint selection uses MAP@5.

## PPR: what was implemented

- Programme co-view graph, not the earlier homework's bipartite user/movie graph. A_ij is the number of distinct training users with qualifying watches of both i and j. Self-loops are removed.
- Raw graph: 2,490 nodes, 603,374 undirected edges, one connected component, zero dangling nodes in this dataset. Dangling-node support is nevertheless unit-tested.
- P is row-normalized adjacency. The user's restart vector is their training counts transformed by log(1+r) and normalized to mass one.
- PPR follows p = alpha*(pP + dangling_mass*v) + (1-alpha)*v. Alpha is link-following probability, not restart probability.
- At this small graph size the implementation solves the fixed-point linear system directly for the user batch. It checks stationary residuals and probability conservation. An independent iterative solver verifies sampled users. This direct LU implementation is dense O(n²) memory / O(n³) factorization, not a claimed billion-item sparse online system.
- Candidate availability is applied after diffusion; no scores are relabelled as predicted viewing probabilities.

### Why higher alpha and extra normalization did not help

- At alpha .50 -> .95, overall MAP falls 0.35775352 -> 0.29378329.
- Mean stationary mass on own history falls 57.06% -> 17.37%; average Top-5 overlap with popularity rises 2.325 -> 3.181. Longer diffusion demonstrably washes out the restart in this graph.
- Raw-count rather than log-count restart slightly lowers MAP. Frequency magnitude matters, but simply amplifying the most frequent historical programme does not uniformly improve future Top-5 prediction. The log restart remains selected.
- Cosine-normalized edges reduce graph degree/popularity correlation 0.970 -> 0.864 and expand recommended catalogue coverage from 535 to 768 distinct IDs, but lower MAP. Less hub concentration is not automatically better prediction of recurring favourites.

## Same two users across all methods

These examples were selected by training history before model runs, not by a flattering recommendation outcome. IDs, titles/categories and validation-hit flags are in selected_recommendation_examples.csv; all initial configurations also retain their examples in runs/.

### Light viewer 1026253314001693311

Training: 1 qualifying airings across 1 programme IDs.

| Method | Top-5 IDs in order | User AP@5 |
|---|---|---:|
| popularity | 2400480 240081 12001682 20088 2400508 | 0.52000000 |
| mf_f16_logtarget_a1_r1 | 20088 700389 2400508 5900256 200469 | 0.06666667 |
| ppr_raw_a050_log | 200402 240081 2400480 2400467 2400508 | 0.35333333 |

### Heavy viewer 13866173795451203812

Training: 1845 qualifying airings across 408 programme IDs.

| Method | Top-5 IDs in order | User AP@5 |
|---|---|---:|
| popularity | 2400480 240081 12001682 20088 2400508 | 1.00000000 |
| mf_f16_logtarget_a1_r1 | 2400480 2400508 12002955 240081 12001682 | 0.71000000 |
| ppr_raw_a050_log | 2400480 240081 2400508 2400467 20088 | 0.76000000 |

The thin viewer has one training watch: both personal models can overcommit to an unrepresentative seed; popularity does better for this example. The heavy viewer shows binary MF's frequency-order failure and its repair, while popularity is still perfect for this particular user. Neither example is evidence that personalisation wins for every user.

## Paired uncertainty

Conditional 95% bootstrap intervals over paired per-user AP differences (2,000 resamples, seed 20261023). These describe this fixed hold-out; they do not account for model selection, label-tie uncertainty or temporal distribution shift.

| Cohort | A minus B | Mean MAP difference | 95% lower | 95% upper |
|---|---|---:|---:|---:|
| all_primary | mf_f16_logtarget_a1_r1 minus popularity | 0.07359553 | 0.06717184 | 0.08033431 |
| all_primary | ppr_raw_a050_log minus popularity | 0.07836228 | 0.07169566 | 0.08463364 |
| all_primary | ppr_raw_a050_log minus mf_f16_logtarget_a1_r1 | 0.00476675 | 0.00178139 | 0.00795703 |
| template_primary | mf_f16_logtarget_a1_r1 minus popularity | 0.08037391 | 0.06862877 | 0.09295891 |
| template_primary | ppr_raw_a050_log minus popularity | 0.08678551 | 0.07535913 | 0.09846188 |
| template_primary | ppr_raw_a050_log minus mf_f16_logtarget_a1_r1 | 0.00641159 | 0.00010543 | 0.01253384 |

PPR has the highest observed all-primary MAP. Do not interpret a small PPR/MF difference as a universal superiority claim. label_tie_diagnostics.csv also reports scores separately for ambiguous/unambiguous Top-5 membership; those subsets were not used for tuning.

## Cost and verification

| Selected method | Training or graph preparation, s | Batch scoring/solve + ranking, s | Full run incl. validation/export, s |
|---|---:|---:|---:|
| mf_f16_logtarget_a1_r1 | 1.133 | 1.043 | 6.592 |
| ppr_raw_a050_log | 0.035 | 2.976 | 3.662 |

Independent verification passed **95 checks across 9 runs**. It recomputes exact AP/MAP for every user, reproduces all MF rankings from saved factors, checks sampled ALS normal equations, verifies co-view edges from viewer sets, and checks PPR against a separate power-iteration implementation. See verification.json.
8 algorithm edge-case tests passed, including full dense vs sparse ALS algebra, log-count targets, monotone fitting, co-view count semantics, direct-vs-iterative PPR with a dangling node, and the shared cold fallback.
manual_mf_dot_product.csv/json contains one real 16-factor prediction with all intermediate products for a later personal check. No student verification is claimed by these automated results.

## Reproduction

```bash
python3 -m unittest discover -s scripts -p 'test_collaborative_models.py'
python3 scripts/run_model_experiments.py --stage all
python3 scripts/verify_model_experiments.py
python3 scripts/summarize_model_experiments.py
```

Use --run-id NAME to rerun one declared configuration. Configs, seed, library versions, BLAS settings, source/input hashes, learning curves, selected factors/graphs, predictions, per-user metrics, history segments and paired baseline comparisons are saved. See scripts/README.md for paths.

## Decision supported by this work

PPR (raw co-view graph, alpha=.50, log-count restart) is the current leading standalone strategy on the documented hold-out. Log-count MF is a competitive second implemented method. Keep popularity for the common cold-start fallback and as a visible benchmark. No hybrid, Kaggle submission, full-history refit or online/revenue experiment is claimed here.

## Sources consulted

1. Y. Hu, Y. Koren and C. Volinsky, *Collaborative Filtering for Implicit Feedback Datasets*, ICDM, 2008. Equations (3)–(6), preference/confidence distinction and the TV-viewing discussion were read. https://yifanhu.net/PUB/cf.pdf
2. SciPy documentation, `cho_solve`: Cholesky normal-equation solves. Runtime uses SciPy 1.13.1; code is tested against dense NumPy solves. https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.cho_solve.html
3. NetworkX PageRank documentation: alpha, personalized restart and dangling redistribution semantics. Used as an algorithm reference, not as the production implementation. https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html
4. Supplied exam brief, midterm MAP@5 slides and MF/PPR lectures. The fixed course evaluation protocol remains unchanged.
