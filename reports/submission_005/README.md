# Submission 005: exact rules ablation from 001

**Scored: public 0.43163, private 0.41039.** The user supplied the result and
`submissions/Score for sub5.png`; the exact-CSV record is in `kaggle_result.json`
and `submissions/results.json`.

## Recorded results and hypothesis

| Submission | Method | Local MAP all | Local MAP template | Kaggle public | Kaggle private |
|---|---|---:|---:|---:|---:|
| 001 | MF/PPR/rules RRF | 0.37356245 | 0.40764638 | 0.43347 | 0.41452 |
| 002 | MF/PPR/rules/popularity RRF | 0.37284202 | 0.40792464 | 0.43359 | 0.41489 |
| 003 | PPR20 -> MF | 0.36888503 | 0.40055652 | 0.43042 | 0.41260 |
| 004 | Standalone MF | 0.36592473 | 0.39746957 | 0.42643 | 0.40943 |
| 005 | MF/PPR RRF, no rules | 0.37061538 | 0.40582319 | 0.43163 | 0.41039 |

004 is the lowest scored method so far on both returned scores. The best RRF (002) improves over standalone MF by **0.00716 public / 0.00546 private**; PPR candidate generation in 003 improves over 004 by **0.00399 / 0.00317**. These specific local distinctions transfer to Kaggle. Current ordering is **002 > 001 > 003 > 004** on public and private scores; the close 001/002 pair still reverses primary validation's ordering.
005 isolates the weekly-rules contribution by comparing directly to 001. Both local cohorts predict **001 > 005 > 003 > 004**; template validation additionally predicts **002 > 001**, while primary validation reverses that pair. The local 001-minus-005 MAP differences are +0.00294706 all / +0.00182319 template. The actual Kaggle effect of removing rules remains unknown until this upload is scored.

The returned ablation confirms a rules gain for 001 over 005: **+0.00184 public /
+0.00413 private**. Public ordering now follows the template-subset ordering of
all five methods. Private ordering instead places 003 above 005, so ranking
transfer is not universal. The paragraph above records the pre-upload hypothesis;
this result is user-supplied feedback, separate from local model selection.

## Exact controlled change

Reuse the same weeks 11–30 MF/PPR50 fitted models and each component's available Top-5. RRF uses `0.5 / rank_MF + 0.5 / rank_PPR`, with an absent item contributing zero and offset zero. Compared with 001, remove only the .25/rank_rules term. No popularity voting term is added. Popularity remains the identical tie-break and common fallback for four actual cold users; repeats and all 6,632 eligible candidates remain unchanged.
The 001 CSV is reproduced exactly from the reused components before generation. Neither models nor parameters are refitted/retuned. Rules ranks are retained in the trace for explanation only; they do not contribute to the 005 scores or shortlist.

## Changes versus prior uploads

| Reference | Changed lists | Changed item sets | Order only | Unchanged users | Mean shared Top-5 |
|---|---:|---:|---:|---:|---:|
| submission_001 | 725 | 406 | 319 | 535 | 4.6635/5 |
| submission_002 | 690 | 410 | 280 | 570 | 4.6532/5 |
| submission_003 | 1,071 | 690 | 381 | 189 | 4.3294/5 |
| submission_004 | 1,073 | 674 | 399 | 187 | 4.4000/5 |

These are recommendation changes, not known relevance gains/losses: no per-user Kaggle truth is available. All four scored CSVs and screenshots are retained with exact hashes.

## Verification and reproduction

**60 independent checks passed:** immutable inputs/code and all recorded score evidence; exact template order/header and user IDs; five distinct nonzero eligible IDs; same cold fallback; component Top-5 reconstruction from saved full-history scores; exact-rational fusion for both 001 and 005; every list change; and exact local AP/MAP on the frozen cohorts.

SHA-256:

```text
8a688a1f5b149dcad51acbf651a69183f75eb15659c9c8d2d0873971e910656f
```

```bash
python3 scripts/prepare_submission_005.py
python3 scripts/verify_submission_005.py
```

See config.json, summary.json, frozen_inputs.json, results_at_preparation.json, recommendations.csv, changes_vs_*.csv and verification.json. The snapshot precedes this upload's returned score. The three follow-up idea families have since been tested locally for 006; current progress is in submissions/progress.json.
