# First Kaggle submission: frozen winner refitted on weeks 11–30

**Upload: `submissions/submission_001.csv`**

Selected strategy: `rrf_mf_ppr_rules_k0`. The semantic-hybrid study did not beat the fixed RRF control. Its earlier local MAP@5 is 0.37356245 on 4,030 users and 0.40764638 on the template validation subset; these are not Kaggle scores or scores of the all-history refit.

## Frozen training and inference

- Training observations: [2020-03-09, 2020-07-27), Europe/Kyiv. Former validation-period behaviour is now past training data, after freezing the strategy and all parameters. The validation Top-5 target CSV is not used in refitting.
- MF: 50% watch qualification, 16 factors, log(1+count) target and confidence increment, regularisation 1, 15 epochs, seed 20261023.
- PPR: the same 50% counts, raw distinct-user co-view graph, log-count restart, link probability .5.
- Rules: 80% qualification, user/ISO-week baskets, joint count >=5, confidence >=.1, lift >1, log-count query weights.
- RRF: each component's available Top-5, weights MF=.5/PPR=.5/rules=.25, offset 0; absent item contributes zero. Ties and all cold/insufficient-signal backfills use 50%-training popularity.
- Availability: [2020-07-27, 2020-10-19). The test schedule contributes programme ID/channel/time/duration only, never future viewing or descriptive training features.

## Full-window interaction reconstruction

Raw views were deduplicated, unioned per user/channel, clipped to the complete twenty-week training window and rejoined to historical airings. Full airing durations remain the denominators. A watch spanning the former May18 split is evaluated once, using its combined observed fragments.

| Qualification | Separate-fold qualified events | Full-window qualified events | Boundary difference |
|---|---:|---:|---:|
| 50% | 938,008 | 938,133 | +125 |
| 80% | 611,457 | 611,757 | +300 |

The independent verifier reconciles every fresh full-window user/airing overlap with the sum of the earlier disjoint folds' raw overlap seconds, then reconstructs counts after applying thresholds. It does not concatenate the old qualified-watch flags.

## Fitted data and submission

- MF/PPR training matrix: **4,871 users × 4,071 items**, 367,883 positive pairs, 938,133 qualifying airing watches.
- Weekly rule model: **66,155 baskets**, **34,444 retained rules**.
- Submission: **1,260 users × five distinct nonzero IDs**, **6,632 eligible programmes**, **4 actual cold users** receiving identical popularity fallback.
- The source test-schedule file has 6,636 nonzero IDs, but 4 have no positive-duration airing overlapping weeks 31–42. Availability is reconstructed by time, not file membership alone; excluded IDs are saved in verification.json.
- 3,667 available IDs have no learned MF/PPR training representation. They remain eligible with zero collaborative score; this hybrid does not solve globally unsupported catalogue cold start.
- Component fitting plus component scoring: 9.10 seconds; full generation including raw join, saving models and predictions: 31.60 seconds in the recorded environment.

## Independent verification

**39 checks passed**: immutable inputs and strategy/code fingerprints; template header, count, exact uint64-safe user strings and row order; five distinct canonical nonzero IDs; test-period availability; all twenty-week event/count reconstruction; MF factor scores and fixed epochs; raw co-view graph and PPR stationarity; rule/query algebra; every component Top-5; and every final RRF rank with exact rational arithmetic.

SHA-256:

```text
138b69c4dbb2d1aa97df390e5fc6e311eaa3838109c85d132d94a9aba5e56313
```

The original template and validation artifacts remain intact. The user reported returned Kaggle public **0.43347** and private **0.41452** for this exact CSV. The record and screenshot reference are in submissions/results.json and kaggle_result.json. Scores are user-supplied, not fetched through the API. The assistant's checks do not claim the student's personal verification.

## Reproduction and evidence

```bash
python3 scripts/make_first_submission.py
python3 scripts/verify_first_submission.py
python3 scripts/summarize_semantic_hybrids.py
```

See summary.json, frozen_inputs.json, selected_strategy.json, verification.json, component_*.csv, recommendations.csv and test_candidates.csv here. Complete event/count matrices, model factors, transitions, rules, baskets and scores are under artifacts/final_11_30/. Model selection is documented in reports/semantic_hybrids/README.md.
