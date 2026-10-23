# Manual verification example — user 127680364314713816

This example was computed by the assistant. It is prepared for the student to independently check later; personal verification is not claimed.

## 1. Reconstruct one watched/not-watched decision

Use `worked_raw_fragments.csv` and `worked_airings.csv`. Source CSV record numbers include the header as record 1. Times with offsets are Europe/Kyiv local time.

### Programme 700389: Кто сверху?, 7 сезон, 3 эп.

Schedule: `export_arh_21-30-final.csv`, CSV record **7021**.
Airing: 2020-07-16T19:00:00+03:00 → 2020-07-16T21:00:00+03:00; full duration **7200 seconds**.

| Non-overlapping watched union interval | Seconds |
|---|---:|
| 2020-07-16T19:07:28+03:00 → 2020-07-16T21:00:00+03:00 | 6752 |

Watched union time = **6752s**. Coverage = 6752 / 7200 = **0.937778**.
Exact comparison: 5 × 6752 ≥ 4 × 7200; watched = **True**.

### Programme 90076035: Х/ф 'Эффект колибри'.

Schedule: `export_arh_21-30-final.csv`, CSV record **29434**.
Airing: 2020-07-21T15:25:00+03:00 → 2020-07-21T17:20:00+03:00; full duration **6900 seconds**.

| Non-overlapping watched union interval | Seconds |
|---|---:|
| 2020-07-21T15:38:05+03:00 → 2020-07-21T16:50:21+03:00 | 4336 |
| 2020-07-21T17:04:14+03:00 → 2020-07-21T17:18:10+03:00 | 836 |

Watched union time = **5172s**. Coverage = 5172 / 6900 = **0.749565**.
Exact comparison: 5 × 5172 < 4 × 6900; watched = **False**.

## 2. Reproduce the validation Top-5

Filter `all_airing_interactions.csv` to validation and watched_80pct=True. Count rows per tv_show_id. Sort count descending, numeric ID ascending. Compare with `validation_programme_counts.csv` and the table below.

| Rank | Programme ID | Title | Category | Qualified airings |
|---:|---:|---|---|---:|
| 1 | 700389 | Кто сверху?, 7 сезон, 3 эп. | Развлечения | 1 |
| 2 | 2400480 | ТСН. | Инфо | 1 |
| 3 | 6700482 | 'Секретные материалы'. | Другое | 1 |
| 4 | 12001682 | М/с 'Губка Боб Квадратные Штаны'. | Детям | 1 |
| 5 | 12002355 | М/с 'Кунг-фу панда: Удивительные легенды'. | Детям | 1 |

There are **6 qualified programmes** for this user. IDs tied at the fifth-place frequency (1): **700389 2400480 6700482 12001682 12002355 12002809**.
The local labels resolve this with ascending numeric ID. Kaggle does not document its tie-break; the exact hidden choice among boundary-tied programmes is therefore unknown.
Displayed titles come from this user's most recent qualifying airing for each ID; episode titles can vary under one programme ID.

## 3. Trace back to the originals

`raw_views.csv` contains every original log record for this user, including duplicate markers. `matched_schedule_rows.csv` includes the original schedule filename/record, title, duration and raw start. All matches, including below-threshold cases, remain in `all_airing_interactions.csv`.
For full independence you can scan the original schedule for that user's channels/time intervals too; the exported matched schedule is an aid, not a substitute for checking missed matches.
