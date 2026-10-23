# One further validation-only refinement around submission 006

**Primary-validation selection: `h8_rules01875_pop00625`.** Only the existing MF, PPR, association rules and popularity components are used.

## Recorded baseline and selection discipline

006 returned **public 0.43662 / private 0.42340**, supported by the user's screenshot and exact-CSV hash. It exceeds 002 by **0.00303 public / 0.00851 private**, becoming best on both returned scores. That motivates another experiment, but does not enter the selector's criterion.
The complete thirteen-new-configuration grid was declared before scoring. The runner loads no Kaggle score ledger or test-submission CSV. It ranks previously unsubmitted configurations by the original 4,030-user primary MAP@5; template metrics and paired intervals are descriptive. No grid expansion occurred after seeing results.
All original >=80% labels, 4,030/1,150 users, 6,384 candidates, repeats, AP denominator and method hyperparameters stay fixed. The eight-week baseline reproduces all previous 006 validation recommendations exactly.

## What was tested

- Common collaborative half-lives 6/12/16 weeks versus the fixed 8-week control.
- MF-only and PPR-only recency, and crossed 4/8-week memories, reusing previously fitted components where possible.
- Eight-week decay for strict-80% antecedent query counts, with the same mined weekly rules matrix.
- Eight-week decay for popularity votes only, retaining the original unweighted tie-break, positive-signal backfill and common cold fallback.
- Two modest MF/PPR weight shifts and a rules/popularity auxiliary-budget shift, using the unchanged eight-week models.

## All results

| Configuration | Primary MAP@5 | Template MAP@5 | Primary delta vs 006 |
|---|---:|---:|---:|
| control_006 | 0.37601075 | 0.41099420 | +0.00000000 |
| cf_h6 | 0.37620926 | 0.41210145 | +0.00019851 |
| cf_h12 | 0.37463772 | 0.40809275 | -0.00137304 |
| cf_h16 | 0.37444830 | 0.40857391 | -0.00156245 |
| mf_h8_ppr_raw | 0.37431100 | 0.40940870 | -0.00169975 |
| mf_raw_ppr_h8 | 0.37548718 | 0.40991594 | -0.00052357 |
| mf_h4_ppr_h8 | 0.37647146 | 0.41063768 | +0.00046071 |
| mf_h8_ppr_h4 | 0.37590902 | 0.41036522 | -0.00010174 |
| h8_rules_query | 0.37636063 | 0.41117101 | +0.00034988 |
| h8_pop_vote | 0.37601075 | 0.41099420 | +0.00000000 |
| h8_rules_and_pop | 0.37636063 | 0.41117101 | +0.00034988 |
| h8_mf0625_ppr0375 | 0.37394045 | 0.40634493 | -0.00207031 |
| h8_mf0375_ppr0625 | 0.37473118 | 0.40937971 | -0.00127957 |
| **h8_rules01875_pop00625** | 0.37652771 | 0.41177101 | +0.00051696 |

The highest primary score comes from a small auxiliary-budget reallocation, not a new recency model. Six weeks has the highest template-subset MAP, but it is not selected because the declared rule uses primary MAP. Weighted popularity changes no predictions at depth five here: its first five vote IDs/order remain unchanged. Combining it with rule-query decay therefore duplicates rule-query-only predictions. Previous-upload duplicates are excluded from eligibility.

## Exact selected change and why it may help

| Component / parameter | 006 | 007 |
|---|---:|---:|
| MF weight | 0.5 | 0.5 |
| PPR weight | 0.5 | 0.5 |
| Rules weight | 0.125 | 0.1875 |
| Popularity weight | 0.125 | 0.0625 |
| MF/PPR half-life | 8 weeks | 8 weeks |
| Component depth / RRF offset | 5 / 0 | 5 / 0 |

Total auxiliary weight stays .25. Personalized rules use each user's history, whereas popularity offers the same global list to warm users. Giving the conditional association signal more influence can improve ordering where generic popularity and personalized evidence disagree. This is an input/rank-fusion change within existing methods, not a new recommender.
The selection is supported only by a modest observed MAP increase. It is a ranking-quality trade-off, not better discovery or coverage: the selected primary lists have six more familiar true hits but nine fewer new-to-user hits (three fewer total). Correct-hit positions nevertheless yield higher AP.

### Fixed truth decomposition

| Strategy | Familiar hits | New hits | Familiar AP credit | New AP credit |
|---|---:|---:|---:|---:|
| control_006 | 8,197 | 577 | 0.35696857 | 0.01904218 |
| h8_rules01875_pop00625 | 8,203 | 568 | 0.35761952 | 0.01890819 |

### Paired conditional evidence

| Cohort | Mean MAP difference vs 006 | Conditional 95% interval | Better / worse / tied users |
|---|---:|---|---|
| all_primary | +0.00051696 | [-0.000056, +0.001112] | 128 / 88 / 3,814 |
| template_primary | +0.00077681 | [-0.000359, +0.001911] | 44 / 21 / 1,085 |

Both intervals include zero. The small gain does not establish a clear improvement, and these 2,000 paired-user resamples do not account for selecting among thirteen settings, earlier tuning, unknown fifth-place tie policy or temporal drift. This is the same repeatedly used temporal hold-out. The upload is a cautious validation-chosen attempt; no actual 007 Kaggle gain is claimed.

### Original strict distinct-history bins

| History | Users | 006 | Selected |
|---|---:|---:|---:|
| 0 (cold) | 59 | 0.190904 | 0.190904 |
| 1-5 | 224 | 0.184807 | 0.185387 |
| 6-20 | 1,512 | 0.326400 | 0.326338 |
| 21-50 | 1,836 | 0.428497 | 0.429639 |
| 51+ | 399 | 0.457210 | 0.457084 |

The effect is not uniform across users/history strata. All familiarity and history definitions stay fixed; actual cold fallbacks remain identical. Full novelty, volume, activity and last-activity tables are retained.

## Verification and reproduction

Two targeted tests and **408 independent checks** passed across the fixed local grid. Checks include all new/cached collaborative half-life arithmetic and MF/PPR equations, mixed model indices, strict-80% rule-query weights and matrix products, vote-only popularity, preserved unweighted tie/cold policy, full-pool component orders, exact rational fusion/AP/MAP, control reproduction and primary-only selection.

```bash
python3 -m unittest discover -s scripts -p 'test_recency_extension.py'
python3 scripts/run_recency_extension.py
python3 scripts/verify_recency_extension.py
python3 scripts/prepare_submission_007.py
python3 scripts/verify_submission_007.py
python3 scripts/summarize_recency_extension.py
```

All plans, source/code hashes, weaker trials, per-user predictions/scores and model/query/vote artifacts remain saved. No new baseline or method outside the previously implemented four methods is introduced. The student's personal verification is not claimed.
