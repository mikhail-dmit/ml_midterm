# Submission 002: split the auxiliary RRF weight between rules and popularity

**Scored: public 0.43359, private 0.41489.** The user supplied the result and
`submissions/Score for sub2.png`; the record is in `kaggle_result.json` and the
central `submissions/results.json` ledger.

## Hypothesis and fixed comparison

Submission 001 returned public **0.43347**, private **0.41452**, recorded against its exact CSV SHA-256 with the user's screenshot. One submission alone does not establish validation rank transfer.
002 keeps the identical weeks 11–30 MF/PPR50 and weekly-rule80 fits and source Top-5s. It changes RRF weights from MF=.5/PPR=.5/rules=.25 to MF=.5/PPR=.5/rules=.125/popularity=.125; offset remains zero. Total auxiliary weight stays .25. The full popularity Top-5 contributes to fusion, with the same popularity tie-break and actual-cold fallback as before.

| Strategy | Primary validation MAP@5 | Template validation MAP@5 |
|---|---:|---:|
| 001 | 0.37356245 | 0.40764638 |
| 002 | 0.37284202 | 0.40792464 |

Primary validation slightly favours 001; template validation slightly favours 002. This is a close challenger for score improvement and a direct test of which local ordering transfers. Candidate weights were chosen from the existing validation runs rather than fitted to hidden user labels. Track both returned scores; use public for submission decisions per the exam.

The observed change is **+0.00012 public / +0.00037 private** versus 001. This
pair matches the template-subset ordering and reverses the primary ordering;
the small observed difference is not a general validation-superiority claim.

## Actual change in the upload

- **323/1,260** users have a changed ordered Top-5; **144** change the set of IDs and **179** change order only.
- **937** users are unchanged; mean list overlap is **4.8857/5**.
- **144** user–programme pairs enter and the same number leave. These are recommendation changes, not known relevance gains; Kaggle per-user truth is unavailable.
- All **four actual cold users** retain the identical popularity Top-5.

## Verification and evidence

**48 independent checks passed:** exact template header/order and user strings, five unique nonzero eligible IDs, immutable scored anchor and model inputs, reconstruction of all component Top-5s from full-history scores, exact-rational fusion for both CSVs, per-user changes, and exact reconstruction of the prior local validation result.

SHA-256:

```text
cbf6a25c207876cce727b6b325c8793fca6ff04b7c6d0ec1aab8c2983c51439c
```

See summary.json, config.json, frozen_inputs.json, verification.json, recommendations.csv and changes_vs_001.csv. The original four-upload sequence is in scripts/kaggle_comparison_plan.json; current progress is in submissions/next_four_plan.md and submissions/progress.json. This report's verification describes the preparation-time input snapshot, before subsequent score feedback.

```bash
python3 scripts/prepare_submission_002.py
python3 scripts/verify_submission_002.py
```
