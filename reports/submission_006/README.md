# Submission 006: locally selected eight-week recency recipe

**Scored: public 0.43662, private 0.42340.** The user's result and screenshot reference are saved in kaggle_result.json and submissions/results.json.

## Why this configuration

Primary local validation selects `recency_h8` from a fixed eleven-new-configuration study, with 001/002 controls. All settings are in reports/refinement/README.md. Local MAP is **0.37601075 all / 0.41099420 template**, versus **0.37284202 / 0.40792464** for 002. The selector did not load the Kaggle score ledger or test-submission CSVs.

Exact selected configuration:

```json
{
  "id": "recency_h8",
  "half_life_weeks": 8,
  "depth": 5,
  "offset": 0,
  "weights": {
    "implicit_mf": 0.5,
    "ppr": 0.5,
    "association_rules": 0.125,
    "popularity": 0.125
  }
}
```

## All-history inference

Training observations remain all weeks 11–30, ending exclusively 2020-07-27 Europe/Kyiv. Keep the same qualification thresholds and hyperparameters. Apply the selected relative-age weighting with that final cutoff, refit MF with fifteen fixed epochs, and compute PPR restarts from the newly weighted counts. Reuse the original raw co-view graph because pair support is unchanged. Weekly rules and their query scores, popularity and the RRF weighting/tie policies remain those of 002.
The final refit uses **938,133** >=50% qualifying airings, rescaling raw decay weights by **2.13216916** so the weighted total remains **938,133**. An airing observed eight weeks ago has half the raw weight of one just observed. Every original positive pair and all twenty weeks remain represented.
The source test schedule contributes only the existing candidate availability. No hidden viewing or validation target labels enter final fitting. The original 002 CSV is reproduced from baseline models before the new refit. Candidate eligibility, exact 1,260 template users/order and the four actual cold users stay unchanged.

## Completed uploads

| Submission | Public | Private |
|---|---:|---:|
| submission_001 | 0.43347 | 0.41452 |
| submission_002 | 0.43359 | 0.41489 |
| submission_003 | 0.43042 | 0.41260 |
| submission_004 | 0.42643 | 0.40943 |
| submission_005 | 0.43163 | 0.41039 |
| submission_006 | 0.43662 | 0.42340 |

Rules help in the direct 001-versus-005 ablation: +0.00184 public / +0.00413 private. Among those five uploads, public ordering is 002 > 001 > 005 > 003 > 004; private ordering swaps 003 and 005. The evidence therefore supports the specific rule/fusion comparisons, not universal ranking transfer. **submission_006 is now the best recorded public-score upload (0.43662).**

## Recommendation changes

| Reference | Changed lists | Changed item sets | Order only | Unchanged users | Mean shared Top-5 |
|---|---:|---:|---:|---:|---:|
| submission_001 | 1,084 | 785 | 299 | 176 | 4.2254/5 |
| submission_002 | 1,059 | 767 | 292 | 201 | 4.2579/5 |
| submission_003 | 1,183 | 959 | 224 | 77 | 3.9302/5 |
| submission_004 | 1,184 | 967 | 217 | 76 | 3.9246/5 |
| submission_005 | 1,126 | 883 | 243 | 134 | 4.0984/5 |

These changes are not known gains/losses in relevance; actual per-user Kaggle targets are unavailable. Recency is supported by local means, not guaranteed to improve the returned score.

## Verified format and models

**93 independent checks passed** in addition to 161 local checks and three unit tests. They cover exact two-column template schema/order and 1,260 user strings, five distinct nonzero eligible IDs, all-history recency event/count/factor arithmetic, PPR fixed points, unchanged rules/popularity/cold handling, each component Top-20, every final RRF rank and changes versus all five scored CSVs.

SHA-256:

```text
5d7ae1263308477f941d350ca214708f2cf7bdd8f06b8f28d4b31de24c299758
```

```bash
python3 scripts/prepare_submission_006.py
python3 scripts/verify_submission_006.py
python3 scripts/summarize_refinement.py
```

See selection_frozen_before_refit.json, config.json, summary.json, verification.json, frozen_inputs.json, results_at_preparation.json, recommendations.csv and changes_vs_*.csv. Complete new model/weight artifacts are under artifacts/submission_006/. Earlier CSVs and their screenshots remain unchanged. No 007 file is generated.
