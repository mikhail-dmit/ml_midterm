# Submission 007: more rules and less popularity in the 006 fusion

**Final user-selected submission: public 0.43707, private 0.42472. Experiments are closed.** Result/screenshot evidence is in kaggle_result.json and submissions/results.json.

Selected by primary local validation: `h8_rules01875_pop00625`. The full thirteen-candidate study and uncertainty are in reports/recency_extension/README.md. No Kaggle score enters the selection rule.

## What changes

The exact same all-weeks 11–30 eight-week MF/PPR models, unweighted weekly-rule scores and unweighted popularity lists from 006 are reused. Every numerical component score, item index and Top-20 list is independently confirmed identical. No component is retrained for this weight-only winner.
Only RRF weights change: MF/PPR stay .5/.5, rules increase .125 -> .1875, popularity decreases .125 -> .0625. Total auxiliary weight stays .25, component depth stays five and offset stays zero. Missing component IDs contribute zero, mathematical ties use original training popularity, and all four actual cold users retain their exact common fallback.

## Local evidence

| Strategy | Primary MAP@5 | Template MAP@5 |
|---|---:|---:|
| 006 | 0.37601075 | 0.41099420 |
| 007 candidate | 0.37652771 | 0.41177101 |

Expected mechanism: rules provide history-conditioned associations, so reallocating part of the generic-popularity budget can rank correct familiar preferences earlier. Local primary AP improves for 128 users and worsens for 88; 3,814 tie. Total true hits slightly decrease, so the measured gain is rank quality rather than discovery/coverage. Both paired conditional intervals include zero, and no Kaggle improvement is guaranteed.

## Scored uploads

| Submission | Public | Private |
|---|---:|---:|
| submission_001 | 0.43347 | 0.41452 |
| submission_002 | 0.43359 | 0.41489 |
| submission_003 | 0.43042 | 0.41260 |
| submission_004 | 0.42643 | 0.40943 |
| submission_005 | 0.43163 | 0.41039 |
| submission_006 | 0.43662 | 0.42340 |
| submission_007 | 0.43707 | 0.42472 |

007 improves over 006 by **0.00045 public / 0.00132 private**. The user designated 007 as final best and stopped experiments. The final file/configuration are frozen in submissions/final_selection.json; report examples are in reports/final_examples/.

## Actual recommendation changes

| Reference | Changed lists | Changed sets | Order only | Unchanged | Mean shared Top-5 |
|---|---:|---:|---:|---:|---:|
| submission_001 | 1,070 | 763 | 307 | 190 | 4.2524/5 |
| submission_002 | 1,068 | 783 | 285 | 192 | 4.2310/5 |
| submission_003 | 1,180 | 957 | 223 | 80 | 3.9333/5 |
| submission_004 | 1,177 | 964 | 213 | 83 | 3.9421/5 |
| submission_005 | 1,115 | 870 | 245 | 145 | 4.1111/5 |
| submission_006 | 198 | 103 | 95 | 1,062 | 4.9183/5 |

No hidden per-user Kaggle targets are available: these are list changes, not known relevance gains/losses. All six earlier CSVs/screenshots remain intact.

## Verified format and inference

**146 final independent checks passed**, in addition to 408 local checks and two unit tests. They verify exact template schema/order and 1,260 user strings, five unique nonzero eligible IDs each, full-history source model/recency equations, unchanged 006 components and cold policy, exact RRF ranks and per-user comparison tables.

SHA-256:

```text
8d3bc085cb0a830cbab5c68789470c608fd34bb840dffbe75e4dd43833f87d8c
```

```bash
python3 scripts/prepare_submission_007.py
python3 scripts/verify_submission_007.py
python3 scripts/summarize_recency_extension.py
```

Configuration, frozen local selection, model/input hashes, score-feedback snapshot, recommendation traces and checks are retained here. Model arrays and component lists are in artifacts/submission_007/. No 008 CSV is generated.
