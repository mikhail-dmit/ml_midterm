# Submission 003: PPR Top-20 candidates reranked by MF

**Scored: public 0.43042, private 0.41260.** The user supplied the result and
`submissions/Score for sub3.png`; the exact-CSV record is in `kaggle_result.json`
and the central `submissions/results.json` ledger.

## Recorded results and question

| Submission | Local MAP all | Local MAP template | Kaggle public | Kaggle private |
|---|---:|---:|---:|---:|
| 001: RRF MF/PPR/rules | 0.37356245 | 0.40764638 | 0.43347 | 0.41452 |
| 002: RRF with rules/popularity split | 0.37284202 | 0.40792464 | 0.43359 | 0.41489 |
| 003: PPR20 -> MF | 0.36888503 | 0.40055652 | 0.43042 | 0.41260 |

002 exceeds 001 by **0.00012 public** and **0.00037 private**. This observed pair agrees with the template-subset ordering and reverses the primary-cohort ordering. The difference is small; it does not establish that one validation cohort is generally superior.
003 is the strongest previously tested semantic hybrid. Both local cohorts predict it below 001 and 002. This upload tests whether that larger RRF-versus-reranking distinction transfers after all-history refitting. Public score remains the exam selection metric; inspected private scores are recorded as secondary feedback.

The returned result is below both RRF uploads, matching that hypothesis on
public and private scores. Relative to 002 the differences are **-0.00317 public**
and **-0.00229 private**. The current observed ordering is **002 > 001 > 003**.

## Exact inference

1. Reuse identical weeks 11–30 MF/PPR models trained on 50%-qualified counts; no model is retrained and no parameters are retuned.
2. Rank all eligible positive PPR scores, breaking score ties by numeric programme ID, then backfill from the same training-popularity order if necessary.
3. Keep the first 20 eligible PPR candidates, then sort only those by MF score descending. MF-score ties retain generator order; scores from different methods are not added.
4. Return five unique IDs. All four actual cold users receive exactly the previous popularity fallback.

The saved rerank_candidates.csv shows all twenty IDs, PPR ranks, MF/PPR scores and selected flags. recommendations.csv gives the submitted ranks and training-only features. No hidden future viewing or per-user Kaggle labels are available.

## Difference from the scored uploads

| Reference | Changed ordered lists | Changed item sets | Order only | Unchanged users | Mean shared Top-5 |
|---|---:|---:|---:|---:|---:|
| submission_001 | 1,079 | 734 | 345 | 181 | 4.2683/5 |
| submission_002 | 1,084 | 743 | 341 | 176 | 4.2690/5 |

These are recommendation changes, not known gains or losses in relevance. Both previously uploaded CSVs remain byte-identical to their recorded hashes.

## Verification and reproduction

**48 independent checks passed:** immutable fitted inputs and code; exact template header/user strings/order; five unique nonzero eligible IDs; all full-history candidate generation and stable MF reranking; cold fallback; every saved candidate and change; and reconstruction of the exact earlier validation predictions and rational MAP on both cohorts.

SHA-256:

```text
aa81d12d12e4d640ed07404d269593d51883182e01bdcc8454e5d35d8417fc02
```

```bash
python3 scripts/prepare_submission_003.py
python3 scripts/verify_submission_003.py
```

The appendable score ledger is snapshotted in results_at_preparation.json for reproducibility; that snapshot precedes this upload's returned score. Configuration, summary, model/input hashes and validation evidence are retained here. 004 (standalone MF) is now prepared; 005 (the rules ablation) remains planned. The user-reported allowance is up to 100 submissions; additional ideas are recorded in submissions/progress.json for later local validation.
