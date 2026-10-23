# Submission 004: standalone implicit-count MF

**Scored: public 0.42643, private 0.40943.** The user supplied the result and
`submissions/Score for sub4.png`; the exact-CSV record is in `kaggle_result.json`
and the central `submissions/results.json` ledger.

## Recorded ranking and hypothesis

| Submission | Method | Local MAP all | Local MAP template | Kaggle public | Kaggle private |
|---|---|---:|---:|---:|---:|
| 001 | RRF MF/PPR/rules | 0.37356245 | 0.40764638 | 0.43347 | 0.41452 |
| 002 | RRF with rules/popularity split | 0.37284202 | 0.40792464 | 0.43359 | 0.41489 |
| 003 | PPR20 -> MF | 0.36888503 | 0.40055652 | 0.43042 | 0.41260 |
| 004 | Standalone MF | 0.36592473 | 0.39746957 | 0.42643 | 0.40943 |

003 is below both RRF uploads on public and private scores, as both local cohorts predicted. Relative to 002 it loses 0.00317 public and 0.00229 private; 002 remains best by the exam's public-score criterion. Across the three scored uploads, the returned ordering is 002 > 001 > 003. The template subset matches this ordering; primary validation reverses the close 001/002 pair.
Both local cohorts predict 004 below 001/002 and below 003. Comparing 004 with the RRF uploads tests the benefit of fusion; comparing it with 003 tests whether PPR's Top-20 shortlist helps the same MF model after the longer-history refit. The current observations support those specific comparisons, not a general validation-superiority claim.

The returned result confirms those specific ordering predictions on both score
splits: **002 > 001 > 003 > 004**. Relative to MF alone, 002 gains **0.00716 public /
0.00546 private**, and 003 gains **0.00399 public / 0.00317 private**. The next
upload, 005, isolates the rules contribution by ablating it from 001.

## Exact fixed strategy

004 is byte-identical to the standalone MF component already fitted for 001–003. No model is retrained or retuned. Training is all weeks 11–30, with >=50% qualifying watches, 16 factors, log(1+count) reconstruction target, confidence 1+log(1+count), regularisation 1, fifteen epochs and seed 20261023.
Eligible positive MF scores are sorted descending, with numeric programme ID for ties. Scores are clipped below at zero as in the validated model. Missing positive slots and the four actual cold users use the same training-popularity fallback. Repeats remain allowed, and availability is the same 6,632 programme IDs. Neither PPR nor rules constrain or contribute to this upload.

## Actual changes versus the scored uploads

| Reference | Changed ordered lists | Changed sets | Order only | Unchanged | Mean shared Top-5 |
|---|---:|---:|---:|---:|---:|
| submission_001 | 1,083 | 728 | 355 | 177 | 4.3103/5 |
| submission_002 | 1,089 | 734 | 355 | 171 | 4.2984/5 |
| submission_003 | 310 | 310 | 0 | 950 | 4.6571/5 |

The changes are not known relevance gains/losses: Kaggle's per-user truth is unavailable. All three earlier CSVs and screenshot evidence are retained with exact hashes.

## Verification and reproduction

**51 independent checks passed:** immutable inputs/code and scored-file evidence; template schema/order and exact user strings; five unique nonzero eligible IDs; byte identity with the saved MF component; all warm scores independently rebuilt from fitted factors; every final rank; cold fallback; per-user changes; and exact-rational local MAP on both frozen cohorts.

SHA-256:

```text
e22c0cb142ffae7daa38c4464bf3d6374c99775878ea14642517e3fa1e5092b4
```

```bash
python3 scripts/prepare_submission_004.py
python3 scripts/verify_submission_004.py
```

Configuration, summary, model/input hashes, the preparation-time score snapshot, comparison tables and verification are saved here. The snapshot precedes this upload's returned score. 005 is now prepared: the exact rules ablation from 001, with MF/PPR weights unchanged.
