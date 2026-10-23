# SWEET.TV data audit — findings

Generated: 2026-10-23T05:33:44.368797+00:00

All five original CSVs were read in full; they were not modified. This is a data-quality audit, not model fitting or 80%-watch label generation.

## 1. File counts and comparison with the task

| File | Data rows | Columns | Size, decimal MB | Exact duplicate extra rows |
|---|---:|---:|---:|---:|
| dataset11-30.csv | 5,821,987 | 5 | 396.217 | 17 |
| export_arh_11-20-final.csv | 1,074,235 | 13 | 153.323 | 0 |
| export_arh_21-30-final.csv | 1,074,394 | 13 | 154.367 | 0 |
| export_arh_31-42-final.csv | 1,295,378 | 13 | 185.953 | 0 |
| submission.csv | 1,260 | 2 | 0.038 | 0 |

All row counts, schemas, channel counts, nine-category counts, first-schedule zero/nonzero counts, and the log duration median/maximum agree with the task.
The four main files contain exactly 9,265,994 rows, excluding headers. The five files total 889,897,444 bytes (848.67 MiB). No archive is present to verify its stated size.

**Discrepancies / clarifications:**

- export_arh_11-20-final.csv distinct programmes, nonzero: brief **5848**, observed **5847**.
- export_arh_21-30-final.csv distinct programmes, nonzero: brief **6364**, observed **6363**.
- export_arh_31-42-final.csv distinct programmes, nonzero: brief **6637**, observed **6636**.
- viewing duration equals stop-start: mismatches: brief **0**, observed **117**.
- The programme-count differences are explained exactly by including ID `0`; the task's counts are distinct raw IDs, not valid recommendable items.
- The task's 10.8% is a **row fraction**, not a measured fraction of airtime or user viewing time.

## 2. Dates, weeks and temporal boundaries

Naive timestamps as supplied; the source timezone is not specified. Date formats are explicitly parsed, never auto-inferred.

| File | Earliest start | Latest start | Latest end |
|---|---|---|---|
| dataset11-30.csv | 2020-03-09T00:00:02 | 2020-07-26T23:58:42 | 2020-07-26T23:59:58 |
| export_arh_11-20-final.csv | 2020-03-08T23:00:00 | 2020-05-18T11:45:00 | 2020-05-18T12:00:00 |
| export_arh_21-30-final.csv | 2020-05-18T00:00:00 | 2020-07-27T11:55:00 | 2020-07-27T12:00:00 |
| export_arh_31-42-final.csv | 2020-07-27T00:00:00 | 2020-10-19T11:55:00 | 2020-10-19T12:00:00 |

- Viewing starts occupy ISO weeks 11–30 only; there is no viewing behaviour in weeks 31–42.
- The schedule filenames are not exact timestamp partitions. The first includes week-10 spill-in and week-21 spill-out; the second includes week-31 spill-out; the third includes week-43 spill-out.
- **1,007 viewing sessions cross 2020-05-18 00:00**, so splitting only on start time can leak or lose viewing seconds. Clip/split at the cutoff before constructing interactions.
- Adjacent schedule calendar ranges overlap, but no repeated airing identities were found across adjacent files. Use channel/time boundaries rather than filename alone.

| Adjacent files | Shared airing identities | Identical content rows | Labelled shared airings |
|---|---:|---:|---:|
| export_arh_11-20-final.csv + export_arh_21-30-final.csv | 0 | 0 | 0 |
| export_arh_21-30-final.csv + export_arh_31-42-final.csv | 0 | 0 | 0 |

Complete per-day and ISO-week counts are in `daily_counts.csv` and `weekly_counts.csv`. Counts use start timestamps.

## 3. Viewing log and IDs

- **4,914 users**, **202 channels** in the raw log.
- All user/channel IDs and timestamps parse; no missing core values, nonpositive view durations or reversed intervals were found.
- **2,483 user IDs exceed signed int64**; 5,820,193 rows have IDs above the contiguous exact-integer range of float64. Preserve strings/uint64 and map to separate model indices.
- Duration: minimum 61s; median **396s**; mean 1480.5s; maximum **342145s**. 52 timestamp intervals exceed 24h.
- **117 rows disagree between `duraton` and naive stop-minus-start**. All discrepancies are exported, with offset counts and dates in JSON. A clock-change hypothesis must be distinguished from a confirmed source timezone.
- **17 exact duplicate extra rows** were verified against raw tuples, not inferred solely from hashes.
- After identical parsed sessions are removed, **96,555 sessions overlap a prior same-user/same-channel interval**.
- Across all channels, **694,713 sessions overlap a prior interval for the same user**. This can reflect multiple devices, household accounts or logging behaviour; this audit does not identify the cause.
- Overlap counts count affected rows, not all overlapping pairs. Within an airing, sum interval-union coverage rather than raw segment durations.

## 4. Schedule coverage and metadata

| Schedule | Nonzero IDs | Channels | Labelled rows | Labelled row share | Share of summed scheduled seconds |
|---|---:|---:|---:|---:|---:|
| export_arh_11-20-final.csv | 5,847 | 400 | 115,613 | 10.76% | 15.97% |
| export_arh_21-30-final.csv | 6,363 | 403 | 121,505 | 11.31% | 16.90% |
| export_arh_31-42-final.csv | 6,636 | 404 | 144,774 | 11.18% | 16.67% |

Summed scheduled seconds are not union airtime; overlapping schedule records can affect that denominator.

**Missing metadata among labelled rows** (row-weighted, not unique-item-weighted):

| Field | Weeks 11–20 | Weeks 21–30 | Weeks 31–42 |
|---|---:|---:|---:|
| tv_show_title | 0.00% | 0.00% | 0.00% |
| tv_show_category | 0.00% | 0.00% | 0.00% |
| tv_show_genre_1 | 4.65% | 4.45% | 3.93% |
| tv_show_genre_2 | 40.73% | 40.06% | 39.31% |
| tv_show_genre_3 | 82.55% | 80.47% | 80.14% |
| year_of_production | 0.76% | 1.23% | 0.76% |
| director | 13.34% | 13.66% | 13.53% |
| actors | 13.18% | 13.12% | 13.07% |

- Titles and categories are complete for labelled rows; secondary genres, directors and actors have missing values.
- No exact duplicate rows or duplicate airing identities occur **within** individual schedule files.
- Nonpositive durations by schedule: export_arh_11-20-final.csv: 1, export_arh_21-30-final.csv: 0, export_arh_31-42-final.csv: 0. Inspect/drop zero-duration airings before percentage division.
- Overlapping schedule rows by file (positive intervals): 2, 2, 8. Examples and gaps are exported.
- Production years include closed/open ranges and `2006 - ???`; do not blindly cast the whole field to an integer.
- Many IDs have multiple titles (including episode/season variants). Categories are consistent per nonzero ID, but some genres/cast/director values vary.

| Metadata field | Historical IDs with multiple nonblank values | All-schedule IDs with multiple nonblank values |
|---|---:|---:|
| tv_show_title | 3,498 | 4,351 |
| tv_show_category | 0 | 0 |
| tv_show_genre_1 | 46 | 80 |
| tv_show_genre_2 | 42 | 80 |
| tv_show_genre_3 | 7 | 16 |
| year_of_production | 5 | 11 |
| director | 22 | 48 |
| actors | 105 | 174 |

Historical means the first two schedule files, not the fitting-only side of a future validation split. These are diagnostic counts, not fitted content features.

## 5. Users, catalogue changes and join coverage

- All **1,260/1,260 template users** have some raw historical viewing; 1,256 appear before the proposed validation cutoff.
- Raw history does not guarantee labelled programme interactions or 80%-qualified watches. Per-template-user raw counts/labelled-overlap counts are in `test_users.csv`.
- Historical schedule union: **8,234** nonzero IDs. Future file: **6,636**; **5,199** are shared and **1,437** are absent from both historical files.
- These catalogue counts use complete files, including boundary spillovers; strict timestamp-window counts are separately recorded in JSON.

**Raw viewing overlap against the union of the historical schedule files:**

| Schedule scope | Viewing rows with any overlap | Viewing rows with no overlap | Share of raw view-row seconds covered | Users with overlap |
|---|---:|---:|---:|---:|
| any_schedule | 5,408,598 | 413,389 | 94.06% | 4,912 |
| labelled_schedule | 2,964,346 | 2,857,641 | 53.08% | 4,895 |

These are overlaps of any positive length, not watched labels. The denominator sums raw viewing rows, so concurrent/duplicate sessions are counted per row. Schedule coverage itself uses interval unions.
Some viewed channels are absent from the schedules. Per-window affected row/user counts and channel IDs are in JSON; do not assume every view can be matched.

## 6. Submission template

- 1,260 rows, two columns `user_id,tv_show_id`, unique users, five zero placeholders per prediction cell.
- Preserve its user IDs/order; only replace predictions when producing a submission.

## 7. Verification and rerunning

```bash
python3 scripts/audit_data.py --self-check-only
python3 scripts/audit_data.py
python3 scripts/verify_audit.py
```

Full audit time: **70.9s**; peak RSS **3449.0 MiB**.
Python/pandas/NumPy versions, source-file SHA-256s, built-in verification and accounting checks are recorded in `audit.json`.
The separate verifier recounts raw CSV data with the Python standard library, including the median and duration inconsistencies. It writes `verification.json` after a successful run.
All checks so far are assistant-executed. Student personal verification has not been performed or claimed.

See `audit_details.md` for expanded diagnostics and `audit.json` for complete machine-readable results.
