# Popularity baseline and MAP@5

## Shared evaluation protocol

- Training: weeks 11–20. Validation: weeks 21–30; original five-ID local truth is unchanged under both repeat policies.
- Candidate pool: **6,384 nonzero programme IDs** with positive-duration airings overlapping validation. Selection uses schedule availability, not validation viewing.
- Popularity: sum of qualifying training airing counts over **all 4,737 training users**. Total qualifying training watches: **316,413**.
- Repeats excluded means masking only programmes with a qualifying training watch for that user. Partial-only viewing is not called watched.
- Missing items get popularity zero; count ties are broken by numeric ID. Cold users receive the common popularity fallback.
- Exactly five distinct predictions per user. No ground-truth pruning, denominator changes, warm-user filtering or silent exclusions.

## Formula

AP@5 = sum over ranks 1..5 of [precision@rank × first-relevant-hit indicator] / min(5, number of distinct true IDs). MAP@5 is the unweighted mean across the explicit cohort. Here each user's truth has five IDs, so the AP denominator is always five.
Prediction duplicates cannot earn credit twice; strict CSV evaluation rejects duplicate or short lists. Truth order is not a graded relevance level.

## Results

| Cohort | Users | Repeat policy | MAP@5 | Precision@5 | Hit rate@5 |
|---|---:|---|---:|---:|---:|
| all_primary | 4,030 | allow_repeats | 0.27939123 | 0.35766749 | 0.87444169 |
| template_primary | 1,150 | allow_repeats | 0.30530725 | 0.38730435 | 0.90956522 |
| all_primary | 4,030 | exclude_repeats | 0.04931266 | 0.07454094 | 0.30000000 |
| template_primary | 1,150 | exclude_repeats | 0.04693043 | 0.06886957 | 0.28000000 |

Recall@5 equals Precision@5 here because both the predicted and true lists have five distinct IDs.

## Why repeat filtering changes the task

| Cohort | True IDs previously watched in training | Share | No-repeat oracle MAP@5 ceiling | Users with all five true IDs masked |
|---|---:|---:|---:|---:|
| all_primary | 11,323 / 20,150 | 56.19% | 0.43806452 | 674 |
| template_primary | 3,561 / 5,750 | 61.93% | 0.38069565 | 243 |

The ceiling is a diagnostic bound, not a trained method: rank every still-eligible true ID first. With five original truth IDs it is the retained true count / 5, averaged over users.

## Decision

Use the schedule-availability pool and **allow repeats** for the shared protocol. This task predicts future favourite programmes, not exclusively discovery of programmes absent from recorded training history. The no-repeat run remains a documented policy comparison.

## Reproducing and inspecting

```bash
python3 -m unittest discover -s scripts -p 'test_ranking.py'
python3 scripts/evaluate_popularity.py
python3 scripts/verify_popularity.py
```

`validation_candidates.csv` fixes the shared pool/ranking; `predictions_*.csv` contain predictions for all 4030 primary users; `cohort_template_primary.csv` identifies the 1150-user subset. See metrics.csv, per_user_metrics.csv and example_rank_contributions.csv for traceable results.
The teacher's two AP@5 examples are unit-tested (11/12 and 8/15). No Kaggle submission or remote-score verification was performed by this local evaluation.
Local label uncertainty remains: the organiser's fifth-place frequency tie-break is unspecified. This evaluation retains the already documented local labels.
