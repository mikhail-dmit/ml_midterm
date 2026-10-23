# SWEET.TV programme recommendation — LLM4Rec midterm

Predict five ranked programme IDs for each of 1,260 users in weeks 31–42 from
historical channel-view logs and broadcast schedules. Implemented methods are
content-based filtering (CBF), weekly association rules, implicit-count matrix
factorization (MF), personalized PageRank (PPR), and popularity as the sole
baseline.

**Final designated submission: [`submissions/submission_007.csv`](submissions/submission_007.csv).**
Returned Kaggle **public MAP@5: 0.43707**, **private: 0.42472**.
The competition leaderboard is frozen; these are returned scores, not standings.
Experiments are closed. The final file/recipe is frozen in
[`submissions/final_selection.json`](submissions/final_selection.json).

## Interaction and label rule

1. Parse timestamps as **Europe/Kyiv**, then perform interval arithmetic in UTC.
   Schedule end is localized start plus the supplied elapsed duration. This is a
   documented assumption supported by the log durations, not a declared
   organiser timezone.
2. Drop `tv_show_id=0` (unlabelled airtime) and nonpositive-duration airings.
   Match `vsetv_id` to `channel_id` and require positive half-open interval overlap.
3. Deduplicate log rows; union overlapping/touching fragments per user/channel.
   Clip observed viewing to the applicable time window before aggregation.
4. A qualifying airing covers **at least 80% of the full scheduled duration**:
   `5 * union_watched_seconds >= 4 * scheduled_duration`. Count each qualifying
   user/airing once, then count airings by programme ID. Boundary clipping never
   shrinks the denominator.
5. Local truth is each eligible user's five most frequent qualified programmes,
   ties resolved by ascending numeric ID. Organiser fragment/tie details are not
   fully documented, so these are reproducible local labels, not access to hidden
   Kaggle answers.

## Validation and final recipe

| Purpose | Local half-open time window |
|---|---|
| Training for hold-out comparisons | `[2020-03-09, 2020-05-18)` — weeks 11–20 |
| Validation | `[2020-05-18, 2020-07-27)` — weeks 21–30 |
| Frozen final refit | `[2020-03-09, 2020-07-27)` — all observed weeks 11–30 |
| Submission forecast/availability | `[2020-07-27, 2020-10-19)` — weeks 31–42 |

- Primary validation: **4,030 users with at least five qualified targets**;
  nested template subset: **1,150**, for reporting only. Primary MAP@5 selects
  configurations. Cold users and unsupported true IDs remain in the denominator.
- All methods share **6,384** locally eligible programme IDs; final availability
  has **6,632**. Eligibility is determined by airing overlap, not file membership
  alone. **Repeats are allowed.** Scores from unsupported representations are zero.
- Training inputs: **50%** qualification for MF/PPR/popularity, **80%** for
  CBF/rules. Validation truth always stays at 80%. The shared-input study is saved.
- All no-signal/cold cases use the same training-popularity fallback. The final
  upload has **four actual cold users**. IDs are preserved as strings/uint64, not
  float or signed-int64 user identifiers.

Final 007 uses **eight-week recency** for collaborative counts only:
`weight = 2 ** (-age_weeks / 8)`, measured to the current fitting cutoff from the
last observed overlap. A single training-only scalar preserves total qualifying
airing mass. Refit 16-factor log-count-target ALS (regularization 1, 15 epochs,
seed **20261023**) and use the weighted log-count PPR restart (raw co-view graph,
link probability **0.5**). Binary pair support stays unchanged. Weekly rules use
joint count ≥5, confidence ≥0.10, lift >1 and unweighted strict-history queries.
Popularity remains unweighted.

Weighted reciprocal-rank fusion uses the available **Top-5 from each component**:

```text
score = 0.5/rank_MF + 0.5/rank_PPR + 0.1875/rank_rules + 0.0625/rank_popularity
```

An absent item contributes zero; offset is zero. Exact rational tie handling
uses the original training-popularity order, then numeric ID. Return five unique
IDs. Frozen configs are in [`configs/`](configs/). No future viewing behaviour is
read; test-period schedule input is limited to ID/channel/time/duration availability.

## Reproduce from raw Kaggle CSVs on a clean clone

### 1. Data and environment

Download the data yourself after accepting the
[Kaggle competition rules](https://www.kaggle.com/competitions/sweettv-tv-program-recommender).
Extract these **five original files** into the ignored directory
`sweettv-tv-program-recommender/` at the repository root:

```text
sweettv-tv-program-recommender/
  dataset11-30.csv
  export_arh_11-20-final.csv
  export_arh_21-30-final.csv
  export_arh_31-42-final.csv
  submission.csv                 # original zero-filled template, not our output
```

The recorded environment is **Python 3.12.2**, macOS 15.7.3 ARM64, with one BLAS
thread during fitting. Direct and transitive runtime dependencies are pinned in
[`requirements.txt`](requirements.txt); `.python-version` records the interpreter.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Fresh reconstruction, selected models and final refit

```bash
python scripts/reproduce_submission_007.py
```

This is the **clean-clone entry point**. It requires no existing model or
interaction artifacts. It creates a fresh ignored `artifacts/reproduce_007_NNN/`
directory and performs:

1. Raw historical schedule/log parsing, elapsed-time checks and deduplication.
2. New train/validation interval unions, joins, programme counts and truth.
3. Fresh selected validation MF/PPR/CBF/rules/popularity models and final fusion.
4. A fresh full twenty-week join across the former validation boundary, followed
   by new final factors, co-view graph, weekly rules, scores and rank fusion.
5. Exact template-order/format output and **byte-for-byte comparison** with the
   tracked final CSV. The scored original is never overwritten.

Compute stages run under a file-access guard that prohibits old derived
artifacts, report caches and scored CSVs as fitting inputs. Old reference results
are unnecessary for this entry point. The final comparison uses only the tracked
CSV, and writes a small proof to `reports/repo_reproduction/summary.json`.

Expected SHA-256:

```text
8d3bc085cb0a830cbab5c68789470c608fd34bb840dffbe75e4dd43833f87d8c
```

The output path, timings, environment, input/config hashes and access logs are
printed/saved. Numerical-library differences across platforms can affect floating
point operations; the command explicitly fails if the final CSV differs.

The clean-clone entry point was tested locally in **85.3 s**, with a byte-identical
result and zero old-derived-artifact accesses. Its saved evidence is
[`reports/repo_reproduction/summary.json`](reports/repo_reproduction/summary.json).

### 3. Tests and the complete audit replay

```bash
python -m unittest discover -s scripts -p 'test_*.py'
```

The recorded run passes **62 tests**.

The earlier complete raw-audit + rebuild + comparison run took **164.9 s** in
the recorded environment: raw audit 70.5 s, interactions 25.7 s, model stage
64.6 s. The model stage includes both validation and all-history models; these
are not serving-latency measurements. See
[`reports/final_check/README.md`](reports/final_check/README.md).

For the original step-by-step experimental workflow, use
[`scripts/README.md`](scripts/README.md). It documents how to regenerate the
detailed artifacts and historical experiment tables omitted from Git. The
original `run_final_check.py` is a historical-cache reconciliation workflow;
use the clean-clone command above when those reference caches are absent.

## All seven returned Kaggle results

| CSV | Recipe | Public | Private | Designation |
|---|---|---:|---:|---|
| `submission_001.csv` | MF/PPR/rules RRF | 0.43347 | 0.41452 | |
| `submission_002.csv` | RRF rules/popularity split | 0.43359 | 0.41489 | |
| `submission_003.csv` | PPR Top-20 → MF reranking | 0.43042 | 0.41260 | |
| `submission_004.csv` | Standalone undecayed MF | 0.42643 | 0.40943 | |
| `submission_005.csv` | MF/PPR RRF without rules | 0.43163 | 0.41039 | |
| `submission_006.csv` | Eight-week collaborative recency + RRF | 0.43662 | 0.42340 | |
| **`submission_007.csv`** | **006 models, more rules/less popularity weight** | **0.43707** | **0.42472** | **FINAL** |

Exact CSV/screenshot hashes and user-reported provenance are in
[`submissions/results.json`](submissions/results.json) and
[`results.csv`](submissions/results.csv). All seven scored CSVs and supplied
screenshots are retained. Later research directions were informed by aggregate
Kaggle feedback; each configuration grid was selected by local primary MAP, not
by a score argument passed to the selector. Visible private scores are secondary
feedback, not a pristine independent evaluation.

## Main reports and evidence

| Report | Contents |
|---|---|
| [`reports/final_check/`](reports/final_check/) | Fresh raw-data replay, 40 exact intermediate matches, final CSV identity, AP@5 hand worksheet and raw-source interval check |
| [`reports/final_examples/`](reports/final_examples/) | Same heavy/light users, all six methods, hit-marked tables, titles/categories, actual validation watches and comments |
| [`reports/submission_007/`](reports/submission_007/) | Final config, scores, source hashes, differences and verification |
| [`reports/recency_extension/`](reports/recency_extension/) | Fixed validation grid for 007, all outcomes and conditional paired intervals |
| [`reports/refinement/`](reports/refinement/) | Local recency/depth/weight study leading to 006 |
| [`reports/training_study/`](reports/training_study/) | Shared coverage thresholds/history windows and method segments |
| [`reports/semantic_hybrids/`](reports/semantic_hybrids/) | Fixed-slot, switching and candidate/reranker alternatives |
| [`reports/models/`](reports/models/) | MF binary-target failure/repair and PPR diffusion diagnosis |
| [`reports/content_rules/`](reports/content_rules/) | CBF and association-rule experiments, including negative results |
| [`reports/data_audit/`](reports/data_audit/) | Raw-data accounting and row-share/timezone/ID checks |

Local final MAP@5 is **0.37652771** on 4,030 users and **0.41177101** on the
1,150-user subset. Predictions address recurring favourites, not measured
enjoyment or causal business uplift. Local ties/fragment/timezone choices are
documented; the same temporal hold-out was used repeatedly. The heavy/light
examples are not a representative estimate and do not make the hybrid win every
case. Prepared checks are assistant-executed evidence, not a claim of student
personal verification.

## Repository contents and size policy

Tracked: source/configs, pinned requirements, compact report summaries/tables,
all scored CSVs/screenshots and the designated final CSV. Raw Kaggle inputs,
model/interactions binaries, full scratch rebuilds, course materials, report
drafts, environments and OS caches remain local/ignored. Detailed run folders
retain only compact configuration/summary JSON; larger report tables are regenerated.

Git cannot express a size predicate in `.gitignore`: its generated block names
current files above **50,000,000 bytes**, plus report files above **1 MB**.
Directory/format rules cover normal future model/data outputs. Before a future
commit, stage intentionally selected files and run:

```bash
python scripts/check_repository_size.py
```

The checker reads **staged Git blob sizes** and rejects any file over 50 MB.
`.gitattributes` preserves exact submission CSV bytes across line-ending settings.
