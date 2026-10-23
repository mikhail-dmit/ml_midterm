# SWEET.TV data audit

Run from the project directory:

```bash
python3 scripts/audit_data.py
```

Or from any directory (defaults are resolved relative to this script):

```bash
python3 /absolute/path/to/scripts/audit_data.py --data-dir /path/to/data --output-dir /path/to/results
```

Dependencies are listed in `requirements.txt`. The original run uses Python 3.12.2,
pandas 2.2.2 and NumPy 1.26.4. No data files are modified.

Outputs go to `reports/data_audit/`:

- `audit.md`: readable findings, definitions, and comparison with the exam brief.
- `audit_details.md`: expanded per-file diagnostics.
- `audit.json`: complete machine-readable results, input SHA-256s, environment,
  runtime, and memory information.
- `columns.csv`, `daily_counts.csv`, `weekly_counts.csv`: raw-column and temporal profiles.
- `schedule_metadata_variants.csv`: all nonzero programme IDs with conflicting
  nonblank metadata, with example values and training-only flags.
- `schedule_interval_examples.csv`, `view_interval_examples.csv`: bounded samples
  of interval problems; exact totals are in JSON/Markdown.
- `test_users.csv`: per-template-user **raw-log** coverage; this is not yet
  programme-interaction or 80%-watch coverage.
- `view_duration_mismatches.csv`: every row whose recorded duration disagrees
  with the naive timestamp difference.

Input is read in chunks (`--chunk-size`, default 250,000). Compact typed frames
are retained for exact distinct counts, sorting, and interval diagnostics. This
is a full audit, not a constant-memory CSV row count or a model-training pipeline.
Peak RSS includes those retained frames. Exact full-row duplicates are screened
with pandas hashes and then verified by comparing the actual raw tuples in a
second pass; hash collisions alone never count as duplicates.

Temporal checks use explicit formats, naive timestamps as supplied (no timezone
is asserted), and half-open intervals `[start, stop)`. The proposed validation
cutoff is 2020-05-18 00:00:00, and the test cutoff is 2020-07-27 00:00:00.
These boundaries are checked against the files, not inferred from row position.

The audit checks schedule overlaps both on raw rows and after dropping duplicate
airing identities `(channel, start, end, programme id)`. Conflicting schedule rows
remain visible. Viewing overlaps are checked after removing identical parsed
sessions and separately for the same user/channel and for the user across all
channels. Coverage is measured with interval unions so overlapping schedule rows
cannot inflate it.

Built-in verification is run before the full audit. Run it independently with:

```bash
python3 scripts/audit_data.py --self-check-only
```

The verification uses small cases with nested/touching intervals, overlapping
schedule coverage, an exact large user-ID round trip, and explicit date parsing.
These are assistant-executed checks; they do not constitute the student's
personal verification for the exam.

After the full audit, independently verify key counts using the standard library:

```bash
python3 scripts/verify_audit.py
```

This recounts all five CSVs without importing pandas or the audit implementation,
checks input SHA-256s, rows, columns, IDs, zero counts, log date endpoints, exact
median/maximum duration and duration inconsistencies. It writes
`reports/data_audit/verification.json` and checks a DST hypothesis for the duration
mismatches without altering timestamps or asserting a source timezone.

Modelling scope agreed with the student: **popularity is the only baseline**;
any implemented recommendation models will come from the teacher's four-method
list. This script fits no recommender and constructs no target labels.

## User–programme interactions and local validation labels

```bash
python3 -m unittest discover -s scripts -p 'test_interactions.py'
python3 scripts/build_interactions.py
python3 scripts/verify_interactions.py
```

The builder uses Europe/Kyiv local timestamps converted to UTC. This is a stated
assumption supported by **all** recorded log durations and removal of the 394
one-hour schedule gaps. `inspect_time_alignment.py` reproduces that diagnostic
without building interactions. Nonexistent/ambiguous timestamps cause an error;
they are never silently shifted.

Schedule end is **localized start + duration in elapsed seconds**, not naive
local start plus duration. The train window is [2020-03-09, 2020-05-18), validation
is [2020-05-18, 2020-07-27), in the declared local timezone.

A user watched an airing if the union of same-channel watched fragments inside
that window covers >=80% of the **full** scheduled duration. One qualifying
airing adds one frequency count. The validation Top-5 uses those counts,
descending, with ascending numeric programme ID for ties. Kaggle documents the
80%/frequency procedure but not its fragment aggregation or tie-break; these
outputs are a documented local reconstruction, not guaranteed identical to its
private generator.

### Outputs

`artifacts/interactions/` (Parquet, Zstandard compression):

- `airings.parquet`: labelled positive-duration airings from both historical
  schedule files, including original source filename/CSV-record references.
- `airing_interactions.parquet`: one row per split/user/airing with union watched
  seconds, full duration, coverage, watched flag and clipped observation bounds.
- `user_programme_interactions.parquet`: one row per split/user/programme,
  including overlap-airing count, qualifying-airing count (`watched_airings`),
  total observed seconds and qualified seconds. **Filter `watched_airings > 0`
  for the strict implicit-feedback interaction matrix.** Partial overlaps remain
  available for diagnostics; they are not automatically positive labels.

User IDs are stored as decimal strings. Time columns `start`, `end`,
`first_overlap`, `last_overlap`, and `last_qualified_overlap` are UTC epoch seconds.
One user's total time across different airings may exceed an individual show's
duration; the <=duration constraint applies to each user–airing record.

`reports/interactions/`:

- `README.md`, `summary.json`: protocol, counts, checks and environment.
- `validation_top5.csv`: long-format ranked local truth for every user with
  positives, with counts and a title from that user's most recent qualifying
  airing. This metadata is an explanatory lookup, not a model feature.
- `validation_ground_truth.csv`: strictly five distinct IDs for every user with
  >=5 qualified validation programmes; these are targets, not predictions.
- `validation_ground_truth_partial.csv`: 1–4 true IDs for the broader cohort.
- `validation_users.csv`: all raw users, eligibility, cold-start and template flags.
- `validation_boundary_ties.csv`: ambiguous fifth-place frequency ties and all
  IDs competing for the remaining slots. Useful for reporting label uncertainty.
- `manual_example/README.md` and CSVs: worked positive/negative airing decisions,
  all the example user's raw log rows, matching schedule source references,
  all airing-level overlaps and programme counts.
- `verification.json`: full artifact checks and independent raw-CSV rejoin for
  deterministic sampled users, including boundary/cold-start examples.

The builder accepts `--data-dir`, `--artifact-dir`, `--report-dir`, and
`--chunk-size`. The verifier accepts matching directory arguments. Only the log,
two historical schedule files and user template are read; no test viewing or
test-period content metadata is used.

## MAP@5 evaluator and popularity baseline

```bash
python3 -m unittest discover -s scripts -p 'test_ranking.py'
python3 scripts/evaluate_popularity.py
python3 scripts/verify_popularity.py
```

The evaluator uses the teacher slide's formula: sum precision at each first
relevant hit, divide by `min(5, number of distinct true IDs)`, then macro-average
over the explicit cohort. Our primary truth has five IDs per user, so the
denominator is always five. Duplicate predictions never earn repeated credit;
strict CSV evaluation requires exactly five distinct nonzero IDs. Missing users
and empty truth are errors in cohort evaluation, not silently dropped cases.

The sole baseline ranks by the **total qualifying training airing count** per
programme, summing over all 4,737 users with training positives. It is fitted
once, not refitted to the 1,150-user reporting subset. Candidate eligibility uses
the schedule: nonzero IDs with positive-duration airings overlapping validation.
All 6,384 available programmes remain candidates, including zero-training-score
items. Popularity ties use ascending numeric ID.

Both repeat policies are evaluated against the **same original five-ID truth**:

- allow repeats: no watched-item mask;
- exclude repeats: remove IDs with >=1 qualifying training watch for that user.

Partial-only training overlaps do not trigger the watched mask. Cold users have
an empty watched set and receive the same popularity list under either policy.
Filtering never causes truth pruning, denominator reduction or user exclusion.

`reports/popularity/` contains:

- `README.md`, `protocol.json`, `summary.json`: definitions, decisions and results.
- `metrics.csv`: both policies for 4,030 primary users and the nested 1,150-user
  template subset; MAP@5, P@5, Recall@5, hit rate and repeat-mask diagnostics.
- `validation_candidates.csv`: the shared pool, training scores, rank and
  explanatory pre-cutoff titles/categories; this fixes candidates for later methods.
- `training_popularity.csv`: counts before availability filtering.
- `predictions_allow_repeats.csv`, `predictions_exclude_repeats.csv`: validation
  predictions in Kaggle-style CSV format, **not test submissions**.
- `cohort_primary.csv`, `cohort_template_primary.csv`: exact reporting populations.
- `per_user_metrics.csv`, `example_rank_contributions.csv`: inspectable user scores.
- `verification.json`: independent training-count/prediction reconstruction and
  exact-rational AP/MAP checks for all evaluated users.

The metric is reusable for any later method's predictions:

```bash
python3 scripts/evaluate_rankings.py --truth reports/interactions/validation_ground_truth.csv --predictions reports/popularity/predictions_allow_repeats.csv
python3 scripts/evaluate_rankings.py --truth reports/interactions/validation_ground_truth.csv --predictions reports/popularity/predictions_allow_repeats.csv --users reports/popularity/cohort_template_primary.csv
```

User IDs stay strings; programme IDs are parsed as exact integers. MAP checks
relevant-ID membership and prediction order, not the order of true IDs. These are
local scores, not returned Kaggle public scores. Local fifth-place tie uncertainty
remains as documented by the interaction builder.

## Implicit matrix factorization and programme-co-view Personalized PageRank

```bash
python3 -m unittest discover -s scripts -p 'test_collaborative_models.py'
python3 scripts/run_model_experiments.py --stage all
python3 scripts/verify_model_experiments.py
python3 scripts/summarize_model_experiments.py
```

`model_experiments.json` declares the small initial grid and three diagnostic
follow-ups. All runs use the existing evaluator, unchanged labels/cohorts,
6,384-item pool, repeats allowed, and the same popularity fallback for cold users.
The 4,030-user MAP@5 selects models/checkpoints; the 1,150-user subset is reporting
only. `--run-id NAME` reruns one declared configuration; `--threads` controls BLAS
threads (default 1).

- `collaborative_models.py`: exact weighted implicit ALS normal equations and
  programme-co-view PPR. Original MF target is binary occurrence, confidence
  `1 + scale*log1p(count)`. The diagnostic MF variant explicitly targets
  `log1p(count)` instead, because the competition asks for frequency favourites.
  This is MF over implicit counts, not star-rating regression.
- PPR edges count distinct training users co-viewing two programmes, with no
  self-loops. Restart uses the target user's training history. Both raw and
  cosine-normalized edges are tested. Direct LU gives the stationary solution
  at this small graph size; fixed-point/mass checks and independent power
  iteration verify it. This implementation has dense quadratic memory and cubic
  factorization cost and is not represented as a sparse production-scale solver.
- Candidate programmes without a learned vector/node get score zero and remain
  in the pool. Cold users receive the already fixed global popularity Top-5.

Outputs:

- `reports/models/README.md`: complete comparison, equations, diagnosis, examples,
  costs, limitations and references consulted.
- `reports/models/comparison.csv`, `selected_models.json`: all configurations and
  selected standalone model for each method.
- `reports/models/diagnostic_plan.md`: measured initial failure evidence and
  follow-up hypotheses recorded before running the follow-ups.
- `reports/models/runs/NAME/`: config, predictions, recommendation scores/metadata,
  per-user metrics, training-history segments, paired popularity comparison,
  summary and (for MF) learning curves/checkpoint scores.
- `artifacts/models/NAME/`: MF factor arrays or PPR adjacency/transitions and item
  maps. The shared training matrix and exact original-ID maps are also saved.
- `reports/models/example_users.json`, `selected_recommendation_examples.csv`:
  same training-selected light/heavy viewers for popularity, MF and PPR.
- `reports/models/paired_uncertainty.csv`: conditional paired-user bootstrap
  intervals; does not account for model selection or temporal/label uncertainty.
- `reports/models/label_tie_diagnostics.csv`: scores on ambiguous/unambiguous
  Top-5 boundary cases, for diagnosis only, not a new tuning cohort.
- `reports/models/verification.json`, `manual_mf_dot_product.csv/json`:
  independent numerical evidence and a real factor dot product to check later.

All automated verification is assistant-executed. Student personal verification
is not claimed. No final refit, hybrid or Kaggle test submission is performed by
these scripts.

## Content-based filtering and association rules

```bash
python3 -m unittest discover -s scripts -p 'test_content_rules.py'
python3 scripts/run_content_rules.py --stage all
python3 scripts/verify_content_rules.py
python3 scripts/summarize_content_rules.py
```

Settings and diagnostic follow-ups are declared in `content_rule_experiments.json`.
`--stage initial`, `--stage diagnostic` or `--run-id NAME` can run a smaller subset.

Content features come from the supplied schedule category, genres, production
start decade, directors, actors and (in the diagnostic variant) title words.
Attributes as well as vocabulary/IDF are **frozen before the validation cutoff**;
future candidate metadata is not used for features. This conservative policy is
documented in `reports/content_rules/metadata_provenance.json`. Family-normalized
item vectors and count/log-count user profiles produce cosine rankings. No
programme-ID feature or popularity score fusion is introduced.

Rules are exact frequent singleton/pair itemsets yielding directional A->B
rules, with support-count/confidence thresholds, lift>1 and no self-rules.
Baskets are either nonempty whole-user training histories or nonempty user/week
histories. The latter's support is a count of user-weeks, not distinct people;
distinct joint-user counts are also exported. History-weighted confidence/lift
sums rank candidates, including previously watched consequent programmes.

The same full pool, cohorts, true labels, repeat policy and metric apply. Positive
model scores rank first; insufficient-signal slots use the common popularity
backfill. Every existing warm MF/PPR Top-5 score is positive, so their predictions
are unchanged under this convention. All cold users receive identical output.

Outputs:

- `reports/content_rules/README.md`: all settings, diagnoses, counts, examples,
  verification and reproduction instructions.
- `reports/content_rules/diagnostic_plan.md`: measured initial failures and
  hypotheses recorded before follow-ups.
- `reports/content_rules/runs/NAME/`: predictions, scores, per-user metrics,
  history segments, identical-content groups or top rules, and complete example
  feature/rule score contributions.
- `artifacts/content_rules/`: frozen metadata, item vectors, profiles, vocabulary,
  IDF, baskets, directional rule weights and full rule statistics.
- `reports/content_rules/verification.json`: raw-schedule reconstruction,
  independent profile/rule/ranking reconstruction and exact AP/MAP checks.
- `reports/all_methods/README.md`, `selected_comparison.csv`,
  `all_configurations.csv`: all four methods against popularity, both cohorts.
- `reports/all_methods/recommendation_examples.csv`: the same training-selected
  light/heavy viewers with IDs, titles/categories and actual validation matches.
- `reports/all_methods/report_notes.md`: preserves the MF diagnosis requested by
  the student, plus PPR/CBF/rule findings for the later exam PDF.

The original MF/PPR experiment records and diagnoses remain intact. No final PDF,
hybrid, full-history refit, test predictions or student-personal verification is
claimed by this stage.

## Method strengths, complementarity and shared training-input study

```bash
python3 -m unittest discover -s scripts -p 'test_training_study.py'
python3 scripts/analyze_method_segments.py
python3 scripts/training_study.py
python3 scripts/verify_training_study.py
python3 scripts/summarize_training_study.py
```

The reference analysis decomposes true programmes into familiar (original >=80%
training watch) vs new-to-user, distinguishing partial prior exposure and no
recorded programme overlap. Original AP credit is partitioned by hit type without
changing precision terms or the five-ID denominator. History bins use distinct
programmes, airing volume, active weeks and last activity, all from training only.
Overlap is measured separately for hit users, correct user/programme pairs and
recommended lists. These are diagnostics before hybrids, not a target-aware
switching or union recommender.

`training_study_plan.json` fixes the factorial experiment: training coverage
80/50/20% × full ten / older four / recent four weeks × popularity and four
selected methods (45 runs). Method hyperparameters are frozen; there is no
per-setting retuning. **Validation remains the original >=80% Top-5**, with the
original 4,030 / 1,150 cohorts, 6,384 candidates, repeats and evaluator. Metadata
vectors and IDF also remain frozen; windows change viewing behaviour, not the
known pre-cutoff item catalogue.

Early/recent views are clipped and rejoined at exact boundaries, preserving full
airing denominators. Each setting fits the same input's global popularity as
reference and common fallback; newly cold users stay in evaluation. Familiarity
and history diagnostics remain fixed to original strict/full history, so segment
names do not change to make a new setting look better.

Outputs:

- `reports/training_study/README.md`, `comparison.csv`: interpretation and all
  45 runs on both cohorts, with same-setting popularity and original-model deltas.
- `reference_analysis/`: true-answer attributes, fixed user features, novelty
  recalls/AP-credit decomposition, history metrics, pairwise/exclusive hits and
  overlap distributions for the original selected methods.
- `SETTING/runs/METHOD/`: predictions, per-user metrics, same examples, fixed
  novelty/history breakdowns, learning/ranking summaries and source fingerprints.
- `SETTING/training_summary.json`, `training_data_comparison.csv`: event/pair/item
  coverage, true-history support and newly cold-user accounting.
- `novelty_all_settings.csv`, `history_all_settings.csv`, `paired_input_effects.csv`:
  changes by original segments and conditional paired-user uncertainty.
- `popularity_top5_stability.csv`: verifies identical scores when count magnitudes
  change but the five IDs/order remain unchanged.
- `artifacts/training_study/`: fingerprinted exact-window event caches, scenario
  count matrices and indices, saved MF factors/PPR transitions/CBF profiles/rules.
- `verification.json`: independent input/label/cohort/candidate/count/fallback and
  exact AP/MAP checks, including raw-view boundary/DST rejoin examples.

Use `python3 scripts/training_study.py --setting recent4_t50` for one setting.
Original interaction labels and original selected-model reports remain intact.
No hybrid or final refit/submission is generated by this study.

## Compact hybrid experiment

After the diagnostic stage, run the declared thirteen-configuration study:

```bash
python3 -m unittest discover -s scripts -p 'test_hybrids.py'
python3 scripts/run_hybrid_experiments.py
python3 scripts/verify_hybrid_experiments.py
python3 scripts/summarize_hybrid_experiments.py
```

`hybrid_plan.json` records the component sources, weights, rank offsets, sparse
history boundary and selection metric before scoring. MF/PPR use full-history
50%-training inputs; CBF/weekly rules retain full-history 80% inputs. The existing
component models are reused. The original strict validation labels, 4,030/1,150
cohorts, 6,384 eligible IDs, repeats and MAP@5 evaluator stay fixed.

`hybrid_models.py` implements weighted reciprocal-rank fusion of the saved
component Top-5 lists, plus training-only sparse-history switching. Absent IDs
have zero fusion contribution; exact rational keys resolve mathematical ties
before the shared training-popularity tie-break. Lower-ranked component items
are outside this experiment's retrieval depth. All actual 50%-history cold users
retain the same popularity fallback. Inference accepts no labels or per-user AP.

Outputs under `reports/hybrids/`:

- `README.md`, `comparison.csv`, `selection.json`: all five components and
  thirteen hybrids, both cohorts; selection uses primary-cohort MAP only.
- `plan.json`, `frozen_inputs.json`, `environment.json`, `runtime.csv`: search,
  input/code provenance and cost evidence.
- `runs/NAME/`: exact predictions, component-rank explanations, per-user metrics,
  configs, fixed history/novelty diagnostics and the same example viewers.
- `selected_paired_comparisons.csv`, `selected_hit_changes.csv`,
  `selected_gain_loss_summary.csv`: conditional paired uncertainty and actual
  additions/losses versus the strong components.
- `recommendation_examples.csv`: the earlier light/heavy viewers, with all five
  current components and the selected hybrid, ordered IDs, titles and categories.
- `verification.json`: independent training-count, rank, exact AP/MAP, fallback,
  segment, explanation and paired-result reconstruction.

The selected hybrid is a local validation choice. Conditional paired-user
intervals do not correct for selecting methods/inputs/hybrid weights on the same
hold-out. Full-history refitting, a test submission and student-personal
verification have not been performed by this stage.

## Method-role hybrids and first all-history submission

```bash
python3 -m unittest discover -s scripts -p 'test_semantic_hybrids.py'
python3 scripts/run_semantic_hybrids.py
python3 scripts/verify_semantic_hybrids.py
python3 scripts/make_first_submission.py
python3 scripts/verify_first_submission.py
python3 scripts/summarize_semantic_hybrids.py
```

`semantic_hybrid_plan.json` declares eleven method-role alternatives before
scoring, with the unchanged selected RRF as a control: familiar/new fixed slots,
popularity switching for <=5-programme histories, PPR/MF candidate generation
followed by the other model's reranking, and a rules-generated new shortlist
reranked by popularity. Familiarity and switching use strict >=80% training
history; queues are filtered over the full eligible order before taking twenty
candidates. Fixed quotas borrow unused slots if a role is exhausted. No future
target composition or per-user validation AP enters inference.

`recommender_bundle.py` restores the existing validation models, reproduces
their exact Top-5 and exposes full scores for role filtering/reranking.
`semantic_hybrids.py` contains the shared inference-only rules. All primary
labels/users/candidates, repeats and metric denominators are unchanged. Selection
includes singles and the RRF control and uses primary-cohort MAP, not the nested
template-subset score. All declared configurations and segment results remain
under `reports/semantic_hybrids/`.

After freezing that selection, `make_first_submission.py` refits on **all past
weeks 11–30**, as requested. It rejoins deduplicated raw view unions across the
former split boundary, rather than concatenating separately thresholded folds.
MF/PPR retain 50% training qualification; rules retain 80%. Fifteen MF epochs and
all other selected parameters stay fixed. Former validation-period observations
are training data in this final refit; the validation target CSV is not used by
the fitting script. Test-period schedule input is limited to programme
ID/channel/start/duration for availability, with no test behaviour.

The output **`submissions/submission_001.csv`** keeps the original template's
header, 1,260 exact string IDs and row order, with five distinct nonzero eligible
programme IDs per cell. The independent verifier reconstructs full-window counts,
model scores, availability and final ranks, and checks the submission SHA-256.
Full model artifacts are in `artifacts/final_11_30/`; reproducibility, frozen
selection, component lists, recommendations and verification evidence are in
`reports/final_11_30/`. Upload is manual; an actual Kaggle score is recorded only
after the user supplies the returned result.

## Kaggle score ledger and submission 002

Actual returned scores are recorded separately from local validation:

```bash
python3 scripts/record_kaggle_result.py --submission submissions/submission_001.csv --public-score 0.43347 --private-score 0.41452 --screenshot "submissions/Score for sub1.png"
```

This hashes the exact generated CSV and screenshot, checks the saved generation
manifest, and writes `submissions/results.json`, `results.csv` and a result copy
alongside the generation report. It records user-supplied values and does not
retrieve scores through an API. The final report summarizer reads this ledger,
so regenerating its documentation retains the reported result.

The proposed four-upload sequence is in `submissions/next_four_plan.md` and
`kaggle_comparison_plan.json`. **Only submission 002 is generated now:**

```bash
python3 scripts/prepare_submission_002.py
python3 scripts/verify_submission_002.py
```

002 reuses the identical fitted models and verified component lists from 001.
It splits the .25 auxiliary RRF weight into .125 rules + .125 popularity, with
MF/PPR=.5/.5 and offset zero unchanged. The generator first reproduces the
scored 001 CSV exactly, then saves `submissions/submission_002.csv` and per-user
changes. The independent verifier reconstructs the components from saved model
scores, both fusion rankings with exact rational arithmetic, the template
format/candidate checks and the already evaluated local validation counterpart.
Results and provenance are under `reports/submission_002/`.

## Submission 003: PPR candidates reranked by MF

Record the second returned result, then prepare the next planned semantic hybrid:

```bash
python3 scripts/record_kaggle_result.py --submission submissions/submission_002.csv --public-score 0.43359 --private-score 0.41489 --screenshot "submissions/Score for sub2.png"
python3 scripts/prepare_submission_003.py
python3 scripts/verify_submission_003.py
```

003 uses the already fitted weeks 11–30 MF/PPR50 scores. It generates the first
twenty eligible positive PPR candidates (then popularity backfill), sorts that
shortlist by MF score, retains generator order for MF ties, and returns five IDs.
All actual cold users keep the identical popularity fallback. The existing
`Bundle` and semantic-hybrid inference functions are reused without changing
model parameters or fitting anything new.

`reports/submission_003/` saves the exact configuration, twenty candidates and
their scores per user, final recommendations, comparisons to 001/002, CSV hash,
and independent verification. The verifier independently reconstructs final
candidate generation/reranking and the earlier validation predictions/MAP.
Score feedback is copied into `results_at_preparation.json`, allowing the active
ledger to receive later results without changing this input snapshot.

The original four-comparison plan remains intact. Current status, the user's
reported 100-submission allowance, and later ideas to validate first are saved
in `submissions/progress.json`. 004 and 005 remain plans at this stage.

## Submission 004: standalone MF

```bash
python3 scripts/record_kaggle_result.py --submission submissions/submission_003.csv --public-score 0.43042 --private-score 0.41260 --screenshot "submissions/Score for sub3.png"
python3 scripts/prepare_submission_004.py
python3 scripts/verify_submission_004.py
```

004 is byte-identical to `reports/final_11_30/component_implicit_mf.csv`, the MF
component already fitted on all weeks 11–30. No model is retrained. The 50%
qualification, fixed 16-factor/log-count/15-epoch MF, candidate pool, repeats and
common cold fallback stay unchanged. This compares unrestricted standalone MF
with the RRF uploads and with 003's PPR-restricted MF candidate ranking.

`reports/submission_004/` saves its configuration, exact CSV hash, input hashes,
preparation-time score snapshot and per-user changes versus all three scored
uploads. The independent verifier reconstructs all warm MF scores from the fitted
factors, every eligible Top-5 and the earlier local predictions/exact MAP. The
next planned upload is 005, the original RRF's rules ablation.

## Submission 005: exact rules ablation

```bash
python3 scripts/record_kaggle_result.py --submission submissions/submission_004.csv --public-score 0.42643 --private-score 0.40943 --screenshot "submissions/Score for sub4.png"
python3 scripts/prepare_submission_005.py
python3 scripts/verify_submission_005.py
```

005 reuses the unchanged weeks 11–30 MF/PPR components and existing RRF helper.
It removes only the .25 rules contribution from 001, retaining MF/PPR weights
.5/.5, offset zero, component retrieval depth five, candidate eligibility,
repeats, popularity tie-break and cold fallback. Popularity is not a voting
component in this upload. 001 is reconstructed exactly before 005 is written.

`reports/submission_005/` saves component-rank explanations, changes versus all
four scored uploads, the score-feedback snapshot, frozen configuration/model
inputs and independent verification. The verifier rebuilds source component
Top-5s from saved scores, both the 001/005 rankings with exact fractions, and the
previous local 005 predictions/exact MAP on both cohorts. Later experiments in
`submissions/progress.json` remain suggestions pending local validation.

## Local refinement and submission 006

```bash
python3 scripts/record_kaggle_result.py --submission submissions/submission_005.csv --public-score 0.43163 --private-score 0.41039 --screenshot "submissions/Score for sub5.png"
python3 -m unittest discover -s scripts -p 'test_refinement.py'
python3 scripts/run_refinement_study.py
python3 scripts/verify_refinement_study.py
python3 scripts/prepare_submission_006.py
python3 scripts/verify_submission_006.py
python3 scripts/summarize_refinement.py
```

`refinement_plan.json` declares eleven new local configurations and two fixed
001/002 controls before scoring: auxiliary-weight splits/budgets, deeper RRF
lists, and 4/8-week collaborative recency weighting. Original labels, cohorts,
candidates, repeats and method hyperparameters remain fixed. The validation
runner never loads the Kaggle score ledger or test-submission CSVs. Selection
uses all-primary MAP among genuinely new configurations; template metrics and
paired intervals are diagnostics only. All trials are retained.

For recency, each 50%-qualified airing is weighted by
`2 ** (-age_weeks / half_life)`, age measured to the applicable training cutoff
using its last observed overlap. One training-only scalar preserves total
qualifying-airing mass. MF targets/confidences and PPR restarts consume these
weighted counts; raw co-view graph support, rules, popularity and cold handling
stay unchanged. Final fitting uses the same formula on all weeks 11–30, with
cutoff July27; the selected configuration is frozen beforehand. No hard history
truncation or additional checkpoint selection is performed.

`reports/refinement/` contains all results, exact controls, primary-only
selection, fixed novelty/history metrics and paired conditional intervals.
`artifacts/refinement/validation/` retains base/h4/h8 scores, model factors and
event/count weight evidence. The verifier independently reconstructs recency
weights, MF scores, PPR stationarity, full-pool component ranks, exact fusion and
MAP, and the selection rule. Intervals do not correct for repeated hold-out use
or choosing among the eleven new settings.

`submissions/submission_006.csv` and `reports/submission_006/` hold the selected
all-history upload and its full provenance, old-score snapshot, recommendation
changes and independent format/model/ranking verification. New model artifacts
are in `artifacts/submission_006/`; previous fitted models, CSVs and screenshots
remain intact. The actual Kaggle result for 006 is pending.

## Model-specific recency extension and submission 007

```bash
python3 scripts/record_kaggle_result.py --submission submissions/submission_006.csv --public-score 0.43662 --private-score 0.42340 --screenshot "submissions/Score for sub6.png"
python3 -m unittest discover -s scripts -p 'test_recency_extension.py'
python3 scripts/run_recency_extension.py
python3 scripts/verify_recency_extension.py
python3 scripts/prepare_submission_007.py
python3 scripts/verify_submission_007.py
python3 scripts/summarize_recency_extension.py
```

`recency_extension_plan.json` fixes thirteen new configurations before scoring:
common/model-specific memories; eight-week strict-80% rule antecedent query
counts with the original mined matrix; recency popularity votes with original
unweighted tie/backfill/cold policy; and small RRF weight changes. The exact
006 validation predictions are reproduced as the control. All labels, users,
candidates, methods and learning hyperparameters remain fixed. Selection uses
only primary local MAP among unsubmitted rankings; the runner loads no Kaggle
score ledger or test-upload CSV and retains all trial results.

The winning setting changes only the auxiliary RRF allocation: MF/PPR stay
.5/.5, rules increase .125 -> .1875 and popularity decreases .125 -> .0625.
The all-history 006 numerical model scores, item indices and every component
Top-20 are confirmed identical; no model is retrained for this winner. The
small local MAP gain has paired intervals spanning zero and is not a clear
generalisation improvement.

`reports/recency_extension/` and `artifacts/recency_extension/validation/` retain
the full grid, component mixes, source models, new CF fits/query counts/vote
evidence and independent checks. `submissions/submission_007.csv` and
`reports/submission_007/` hold the frozen winner, old-score snapshot, per-user
changes, source hashes, traces and final independent verification. Model arrays
and lists are under `artifacts/submission_007/`. The earlier files remain intact;
006 is recorded as best and no 008 CSV is generated.

## Final selection and report-ready validation examples

The user designated 007 as final (**public 0.43707 / private 0.42472**) and closed
experiments. The exact CSV hash and model/validation configuration are frozen in
`submissions/final_selection.json`; progress records closure explicitly.

```bash
python3 scripts/record_kaggle_result.py --submission submissions/submission_007.csv --public-score 0.43707 --private-score 0.42472 --screenshot "submissions/Score for sub7.png"
python3 scripts/build_final_examples.py
python3 scripts/verify_final_examples.py
python3 scripts/render_final_examples.py
```

These scripts fit or tune no models. Within the fixed 4,030-user validation
cohort, they retain the earlier training-selected users: the unique largest
strict-80% training-airing count and smallest nonzero count, with decimal user-ID
string tie-break. The examples use the pre-May18 validation-trained 007 recipe,
not its all-history test-fit scores. MF/PPR are its eight-week-recency components;
CBF uses the selected strict-history metadata/title profile, rules remain strict
weekly confidence rules, and popularity uses unweighted 50% history.

`reports/final_examples/` contains a full HTML two-column comparison with actual
validation watches, full/compact Markdown, literal side-by-side CSV/Markdown,
short/per-method comments, all qualified watch counts and partial-only statuses.
Programme IDs, representative pre-cutoff titles and categories are retained;
actual latest watched episode labels are saved separately. All sixty hits/AP
values use membership anywhere in the fixed true Top-5, not same-row equality.

The independent verifier rejoins original raw view fragments and both historical
schedule CSVs for these two viewers, reconstructing train/validation unions,
strict/soft counts, recency weights and exact truth/tie handling. It also checks
labels against raw schedule evidence, CBF feature/query and rule contributions,
RRF ranks, per-user AP and the final freeze. The heavy fifth-place tie and the
light viewer's partial history are explained explicitly. These assistant checks
do not claim the student's personal verification.

## Final raw-data reproducibility replay and hand checks

```bash
python3 scripts/run_final_check.py
python3 scripts/hand_final_checks.py
```

All output is isolated under **`reports/final_check/`**. Each invocation allocates
a new numbered rebuild folder, preserving earlier runs and every original
artifact. The first run is `rebuild_001/`. It executes the raw audit and original
interaction builder with explicit new output directories, then fits all six
selected validation strategies and the frozen final 007 recipe from those new
tables. MF factors, raw co-view graph, weekly rule mining, CBF metadata vectors /
profiles, recency counts and full-window joins are rebuilt. Selected parameters,
seed and fifteen MF epochs stay fixed.

`final_check_sandbox.py` records file access and denies old derived paths under
the original `artifacts/`, `reports/` and `submissions/` during compute stages.
Only frozen configuration copies, raw input CSVs and the new run's artifacts
feed model fitting. References are read afterwards for reconciliation. All forty
logical stage comparisons and the final byte-for-byte CSV comparison pass.
The original and fresh CSV have SHA-256
`8d3bc085cb0a830cbab5c68789470c608fd34bb840dffbe75e4dd43833f87d8c`.

The independent hand-check script writes `hand_ap.md` and `hand_join.md` with
rank-by-rank exact fractions, source log/schedule records, clipped fragments,
union intervals and programme counts. It reconstructs the manual example from
the raw CSVs using the standard library rather than the interaction join helper.
The AP example gives `(1 + 2/3 + 3/4)/5 = 29/60`; the two watched decisions reproduce
`6752/7200` (qualifies) and `(4336+836)/6900` (does not). The combined evidence is
in `verification.json`, `rebuild_result.json` and `stage_reconciliation.csv`;
commands, environment, logs and access manifests are retained inside the fresh
run. The check reads the latest run status and stops if it is not successful.
This is assistant-executed reproduction/arithmetic evidence, with no new tuning,
upload or claim that student personal checks have been performed.
