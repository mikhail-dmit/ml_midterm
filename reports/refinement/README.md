# Local-validation refinement for submission 006

**Selected by primary local MAP only: `recency_h8`.** The eleven new configurations and two fixed controls were declared before scoring. All candidates are retained below; the grid was not extended after viewing results.

## What was fixed

Original strict >=80% validation Top-5 labels; 4,030 primary users; nested 1,150 template users; 6,384 eligible IDs; repeats allowed; standard MAP@5 denominator five. MF/PPR use 50%-qualified training history and the original hyperparameters; weekly rules remain the selected strict-80% model. Every actual cold user receives identical unweighted training popularity.
After seeing five aggregate Kaggle results, the user requested improvements around 002. That motivated the study, but the validation runner loads no score ledger or test-submission CSV. Selection uses primary MAP only; template scores and bootstrap intervals do not choose parameters. Controls reproduce 001/002 exactly on the earlier hold-out.

## Declared candidates

- Five changes to the rules/popularity split or total auxiliary budget, with MF/PPR fixed at .5/.5.
- Four deeper-list RRF configurations: depth 10/20 × offset 0/10, with the original 002 weights.
- Two gradual-recency configurations: 4- and 8-week half-life, keeping 002's weights/depth/offset and retaining all training history.

## All results

| Configuration | Primary MAP@5 | Template MAP@5 | Primary delta vs 002 |
|---|---:|---:|---:|
| control_001 | 0.37356245 | 0.40764638 | +0.00072043 |
| control_002 | 0.37284202 | 0.40792464 | +0.00000000 |
| split_rules00625_pop01875 | 0.37182465 | 0.40741159 | -0.00101737 |
| split_rules01875_pop00625 | 0.37348635 | 0.40795942 | +0.00064433 |
| aux0125_balanced | 0.37197105 | 0.40680870 | -0.00087097 |
| aux0375_balanced | 0.37164516 | 0.40606377 | -0.00119686 |
| rules025_pop0125 | 0.37289247 | 0.40650145 | +0.00005045 |
| depth10_k0 | 0.37323904 | 0.40583478 | +0.00039702 |
| depth20_k0 | 0.37341853 | 0.40676522 | +0.00057651 |
| depth10_k10 | 0.37097519 | 0.40204348 | -0.00186683 |
| depth20_k10 | 0.37197105 | 0.40327246 | -0.00087097 |
| recency_h4 | 0.37556824 | 0.40960580 | +0.00272622 |
| **recency_h8** | 0.37601075 | 0.41099420 | +0.00316873 |

The best weight-split change yields only a small primary gain over 002 and remains slightly below 001. Deeper lists with offset zero improve primary MAP modestly but reduce template MAP; offset ten is weaker here. Both gradual-recency recipes outperform these variants on the two reported cohorts. Eight weeks wins the declared primary criterion; the small 4-versus-8-week difference does not establish a precisely optimal half-life.

## Exact recency definition

For every >=50%-qualified training airing, raw weight is `2 ** (-age_weeks / half_life)`, where age is from the last observed overlap second to the current training cutoff. A single scale, computed using training events only, preserves their total mass: `scale = number_of_qualifying_airings / sum(raw_weights)`. Sum the scaled weights into user/programme counts.
The MF log-count target and confidence use these weighted counts. PPR restarts use normalized log(1+weighted_count). Every positive pair remains, so the distinct-user binary co-view graph is unchanged and reused. Rule mining/query scores, popularity votes, popularity tie-break, warm/cold status and strict-history diagnostic bins remain fixed.
This is the combined decay-plus-mass-preservation recipe. The normalisation keeps overall count scale comparable; the current study does not separately identify its effect from time decay. There is no hard history truncation or use of future observations.

## Paired evidence and limitations

| Cohort | Reference | Selected MAP difference | Conditional 95% interval | Better / worse / tied users |
|---|---|---:|---|---|
| all_primary | control_001 | +0.00244830 | [+0.000689, +0.004219] | 717 / 640 / 2,673 |
| all_primary | control_002 | +0.00316873 | [+0.001514, +0.004961] | 657 / 562 / 2,811 |
| template_primary | control_001 | +0.00334783 | [-0.000412, +0.007223] | 218 / 202 / 730 |
| template_primary | control_002 | +0.00306957 | [-0.000638, +0.006603] | 195 / 174 / 781 |

These 2,000 paired user resamples (seed 20261023) are conditional diagnostics, not adjusted for choosing among eleven new settings, earlier tuning, temporal drift or the unknown organiser tie policy. The same temporal hold-out has already been used repeatedly. Template-subset intervals include zero; its average gain is not a decisive independent confirmation. No actual 006 Kaggle improvement is claimed before the returned score.

## Familiar versus new targets

Original strict-history definitions and AP denominators remain fixed.

| Strategy | Familiar hits | New hits | Familiar recall | New recall | Familiar AP credit | New AP credit |
|---|---:|---:|---:|---:|---:|---:|
| control_002 | 8,146 | 592 | 71.94% | 6.71% | 0.353756 | 0.019086 |
| recency_h8 | 8,197 | 577 | 72.39% | 6.54% | 0.356969 | 0.019042 |

### Original strict distinct-history segments

| Segment | Users | 002 | Selected |
|---|---:|---:|---:|
| 0 (cold) | 59 | 0.189887 | 0.190904 |
| 1-5 | 224 | 0.188542 | 0.184807 |
| 6-20 | 1,512 | 0.322244 | 0.326400 |
| 21-50 | 1,836 | 0.425171 | 0.428497 |
| 51+ | 399 | 0.454311 | 0.457210 |

The selected recipe's average gain does not imply every user or sparse-history segment benefits. The fixed cold bin still includes sixteen users warmed by the softer training threshold; actual cold users retain identical fallback. All active-week, volume and last-activity tables are saved in history_metrics.csv.

## Verification and reproduction

Three targeted tests and **161 independent local checks** passed: immutable inputs, train-only event weights and globally preserved mass, original pair support/graph, MF factors and fixed epochs, PPR stationarity, unchanged rules/popularity/cold handling, every component order and fusion rank, exact AP/MAP, primary-only selection and reproducible paired intervals.

```bash
python3 -m unittest discover -s scripts -p 'test_refinement.py'
python3 scripts/run_refinement_study.py
python3 scripts/verify_refinement_study.py
python3 scripts/prepare_submission_006.py
python3 scripts/verify_submission_006.py
python3 scripts/summarize_refinement.py
```

Plans, source/code hashes, all configurations/predictions/per-user scores, fixed novelty/history metrics and weighted model artifacts are saved. No new grid was fitted to public/private score differences. The selected configuration was frozen before the all-weeks refit. The student's own numerical verification is not claimed.
