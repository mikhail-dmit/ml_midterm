# Original manual log-to-schedule example: independent raw-source recheck

User **127680364314713816**. Read the original log and both raw historical schedules with the standard library; no interaction-core join, saved watch flag or cached matched-schedule file is used for these calculations.

Rule: same channel, positive half-open time intersection; union overlapping/touching raw fragments per user/channel, clip observed time to validation, and divide by the **full scheduled duration**. Supplied times are interpreted as Europe/Kyiv; schedule end is start plus elapsed seconds.

## Programme 700389: Кто сверху?, 7 сезон, 3 эп.

Raw schedule: `export_arh_21-30-final.csv`, CSV record **7021**, channel **7**.
Airing: **2020-07-16T19:00:00+03:00 → 2020-07-16T21:00:00+03:00**, duration **7200 seconds**.

| Non-overlapping clipped union piece | Explicit seconds calculation | Seconds |
|---|---|---:|
| 2020-07-16T19:07:28+03:00 → 2020-07-16T21:00:00+03:00 | 1×3600 + 52×60 + 32 | 6752 |

Union watched time = 6752 = **6752 seconds**.
Coverage = 6752 / 7200 = **211/225 = 0.937777777778**.
Exact 80% test: 5×6752 = **33760** ≥ 4×7200 = **28800**.
Decision: **watched / counts once**.

## Programme 90076035: Х/ф 'Эффект колибри'.

Raw schedule: `export_arh_21-30-final.csv`, CSV record **29434**, channel **23**.
Airing: **2020-07-21T15:25:00+03:00 → 2020-07-21T17:20:00+03:00**, duration **6900 seconds**.

| Non-overlapping clipped union piece | Explicit seconds calculation | Seconds |
|---|---|---:|
| 2020-07-21T15:38:05+03:00 → 2020-07-21T16:50:21+03:00 | 1×3600 + 12×60 + 16 | 4336 |
| 2020-07-21T17:04:14+03:00 → 2020-07-21T17:18:10+03:00 | 0×3600 + 13×60 + 56 | 836 |

Union watched time = 4336 + 836 = **5172 seconds**.
Coverage = 5172 / 6900 = **431/575 = 0.749565217391**.
Exact 80% test: 5×5172 = **25860** < 4×6900 = **27600**.
Decision: **not watched / does not count**.

## Programme counts and boundary tie

The independent full-validation rejoin recovers **six qualifying programmes**, with one qualifying airing each. Sorting frequency descending and numeric ID ascending reproduces **700389 2400480 6700482 12001682 12002355**. All six tie at the Top-5 boundary; this is the documented local tie convention, not proof of the organiser's hidden tie rule.

| Rank | Programme ID | Qualifying airings | In local Top-5? |
|---:|---:|---:|---|
| 1 | 700389 | 1 | yes |
| 2 | 2400480 | 1 | yes |
| 3 | 6700482 | 1 | yes |
| 4 | 12001682 | 1 | yes |
| 5 | 12002355 | 1 | yes |
| 6 | 12002809 | 1 | no |

## Source evidence

- manual_join_raw_views.csv: all 783 original rows for this user, with source CSV records.
- manual_join_raw_fragments.csv: original matching rows and their clipped intersections for the two worked airings.
- manual_join_union_intervals.csv: the union pieces used in the arithmetic.
- manual_join_independent_airings.csv: independently reconstructed positive validation intersections for the manual and AP users.
- manual_join_programme_counts.csv: complete manual-user qualified counts and local Top-5 flags.

Both the positive 6,752/7,200 case and the negative (4,336+836)/6,900 case exactly match the original interactions example. These are assistant-executed raw-source checks; student personal verification remains pending.
