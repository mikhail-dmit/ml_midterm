# SWEET.TV — full data audit

Generated: 2026-10-23T05:33:44.368797+00:00

## Scope and definitions

All five supplied CSVs were read. Original files were not modified. IDs were parsed losslessly as unsigned 64-bit integers and exported as strings where needed.
Input is chunked; compact typed frames are retained for global checks. This runtime/memory is not comparable with a CSV-only counting pass.
Times are naive as supplied; timezone is unspecified. ISO weeks use start timestamps. Intervals are half-open [start, end).
Raw-log history/overlap is not an 80%-qualified programme interaction. No recommender or target generator is fitted by this audit.

## Files

| File | Rows | Columns | Decimal MB | Exact duplicate extra rows |
|---|---:|---:|---:|---:|
| dataset11-30.csv | 5,821,987 | 5 | 396.217 | 17 |
| export_arh_11-20-final.csv | 1,074,235 | 13 | 153.323 | 0 |
| export_arh_21-30-final.csv | 1,074,394 | 13 | 154.367 | 0 |
| export_arh_31-42-final.csv | 1,295,378 | 13 | 185.953 | 0 |
| submission.csv | 1,260 | 2 | 0.038 | 0 |

## Comparison with exam_quiz_AVITO.md

| Claim | Brief | Observed | Match |
|---|---:|---:|:---:|
| dataset11-30.csv data rows (header excluded) | 5821987 | 5821987 | yes |
| export_arh_11-20-final.csv data rows (header excluded) | 1074235 | 1074235 | yes |
| export_arh_21-30-final.csv data rows (header excluded) | 1074394 | 1074394 | yes |
| export_arh_31-42-final.csv data rows (header excluded) | 1295378 | 1295378 | yes |
| submission.csv data rows (header excluded) | 1260 | 1260 | yes |
| four data files: total rows | 9265994 | 9265994 | yes |
| export_arh_11-20-final.csv distinct programmes, nonzero | 5848 | 5847 | **NO** |
| export_arh_11-20-final.csv channels | 400 | 400 | yes |
| export_arh_11-20-final.csv nonblank categories | 9 | 9 | yes |
| export_arh_21-30-final.csv distinct programmes, nonzero | 6364 | 6363 | **NO** |
| export_arh_21-30-final.csv channels | 403 | 403 | yes |
| export_arh_21-30-final.csv nonblank categories | 9 | 9 | yes |
| export_arh_31-42-final.csv distinct programmes, nonzero | 6637 | 6636 | **NO** |
| export_arh_31-42-final.csv channels | 404 | 404 | yes |
| export_arh_31-42-final.csv nonblank categories | 9 | 9 | yes |
| first schedule labelled rows | 115613 | 115613 | yes |
| first schedule zero-id rows | 958622 | 958622 | yes |
| viewing duration median seconds | 396.0 | 396.0 | yes |
| viewing duration maximum seconds | 342145.0 | 342145.0 | yes |
| viewing duration equals stop-start: mismatches | 0 | 117 | **NO** |

File sizes in the brief are approximate; both decimal MB and MiB are recorded in JSON. The 131 MB archive is not present, so its size cannot be checked.
The brief's reading benchmark uses different work; the audit reports its own runtime and RSS, without claiming to reproduce 4.6 s / 12.6 MB.

## Dates and ISO weeks

| File | First start | Last start | Last stop/end | ISO weeks |
|---|---|---|---|---|
| dataset11-30.csv | 2020-03-09T00:00:02 | 2020-07-26T23:58:42 | 2020-07-26T23:59:58 | 2020-W11, 2020-W12, 2020-W13, 2020-W14, 2020-W15, 2020-W16, 2020-W17, 2020-W18, 2020-W19, 2020-W20, 2020-W21, 2020-W22, 2020-W23, 2020-W24, 2020-W25, 2020-W26, 2020-W27, 2020-W28, 2020-W29, 2020-W30 |
| export_arh_11-20-final.csv | 2020-03-08T23:00:00 | 2020-05-18T11:45:00 | 2020-05-18T12:00:00 | 2020-W10, 2020-W11, 2020-W12, 2020-W13, 2020-W14, 2020-W15, 2020-W16, 2020-W17, 2020-W18, 2020-W19, 2020-W20, 2020-W21 |
| export_arh_21-30-final.csv | 2020-05-18T00:00:00 | 2020-07-27T11:55:00 | 2020-07-27T12:00:00 | 2020-W21, 2020-W22, 2020-W23, 2020-W24, 2020-W25, 2020-W26, 2020-W27, 2020-W28, 2020-W29, 2020-W30, 2020-W31 |
| export_arh_31-42-final.csv | 2020-07-27T00:00:00 | 2020-10-19T11:55:00 | 2020-10-19T12:00:00 | 2020-W31, 2020-W32, 2020-W33, 2020-W34, 2020-W35, 2020-W36, 2020-W37, 2020-W38, 2020-W39, 2020-W40, 2020-W41, 2020-W42, 2020-W43 |

## Viewing log

```json
{
  "rows": 5821987,
  "column_count": 5,
  "size_bytes": 396216555,
  "size_MB_decimal": 396.216555,
  "size_MiB": 377.86155223846436,
  "invalid_parsed": {
    "user_id": 0,
    "vsetv_id": 0,
    "start_time": 0,
    "stop_time": 0,
    "duraton": 0
  },
  "invalid_examples": {},
  "compact_frame_memory_bytes": 244523586,
  "max_end": "2020-07-26T23:59:58",
  "distinct_users": 4914,
  "distinct_channels": 202,
  "user_id_min": "2244466330591177",
  "user_id_max": "18443832178892490378",
  "rows_user_id_above_int64": 2918899,
  "distinct_users_above_int64": 2483,
  "rows_user_id_above_exact_float64_integer_range": 5820193,
  "zero_user_rows": 0,
  "zero_channel_rows": 0,
  "duration_seconds": {
    "count": 5821987,
    "mean": 1480.4593730628392,
    "p00": 61.0,
    "p01": 62.0,
    "p10": 80.0,
    "p25": 133.0,
    "p50": 396.0,
    "p75": 1452.0,
    "p90": 3911.0,
    "p95": 6344.0,
    "p99": 14079.139999999665,
    "p100": 342145.0
  },
  "nonpositive_duration_rows": 0,
  "noninteger_duration_rows": 0,
  "stop_before_start_rows": 0,
  "zero_length_intervals": 0,
  "duration_mismatch_rows": 117,
  "duration_mismatch_examples": [
    {
      "user_id": "12466582247545246052",
      "vsetv_id": "1521",
      "start_time": "2020-03-28T22:47:45.000",
      "stop_time": "2020-03-30T09:02:48.000",
      "duraton": 119703
    },
    {
      "user_id": "10059425067810734795",
      "vsetv_id": "7",
      "start_time": "2020-03-28T22:56:59.000",
      "stop_time": "2020-03-29T04:11:55.000",
      "duraton": 15296
    },
    {
      "user_id": "12246241194532024321",
      "vsetv_id": "921",
      "start_time": "2020-03-29T00:15:15.000",
      "stop_time": "2020-03-29T04:05:32.000",
      "duraton": 10217
    },
    {
      "user_id": "6266399139997320035",
      "vsetv_id": "1521",
      "start_time": "2020-03-29T00:27:30.000",
      "stop_time": "2020-03-29T04:06:25.000",
      "duraton": 9535
    },
    {
      "user_id": "5842699175950256892",
      "vsetv_id": "3",
      "start_time": "2020-03-29T00:46:06.000",
      "stop_time": "2020-03-29T04:35:40.000",
      "duraton": 10174
    },
    {
      "user_id": "4051396765385629500",
      "vsetv_id": "1276",
      "start_time": "2020-03-29T00:50:30.000",
      "stop_time": "2020-03-29T04:29:39.000",
      "duraton": 9549
    },
    {
      "user_id": "13403292334828865123",
      "vsetv_id": "5",
      "start_time": "2020-03-29T01:00:23.000",
      "stop_time": "2020-03-29T04:02:23.000",
      "duraton": 7320
    },
    {
      "user_id": "14761563450803362415",
      "vsetv_id": "921",
      "start_time": "2020-03-29T01:00:52.000",
      "stop_time": "2020-03-29T04:23:46.000",
      "duraton": 8574
    }
  ],
  "naive_elapsed_minus_recorded_duration_seconds": {
    "3600.0": 117
  },
  "duration_mismatch_start_dates": {
    "2020-03-29": 115,
    "2020-03-28": 2
  },
  "duration_mismatch_stop_dates": {
    "2020-03-29": 116,
    "2020-03-30": 1
  },
  "duration_over_24h_rows": 52,
  "cross_midnight_rows": 119856,
  "cross_validation_cutoff_rows": 1007,
  "cross_test_cutoff_rows": 0,
  "stop_after_test_cutoff_rows": 0,
  "raw_rows_per_user": {
    "count": 4914,
    "mean": 1184.7755392755394,
    "p00": 1.0,
    "p01": 29.0,
    "p10": 223.3,
    "p25": 476.0,
    "p50": 874.0,
    "p75": 1547.0,
    "p90": 2429.7,
    "p95": 3170.699999999999,
    "p99": 5348.309999999999,
    "p100": 38114.0
  },
  "intervals_unique_sessions_same_user_channel": {
    "valid_positive_rows": 5821970,
    "groups": 291943,
    "rows_overlapping_any_prior_interval": 96555,
    "groups_with_overlap": 12115,
    "touching_prior_union_end": 283642,
    "gaps_after_prior_union_end": 5149830,
    "gap_seconds": {
      "count": 5149830,
      "mean": 299331.4420081828,
      "p00": 1.0,
      "p01": 2.0,
      "p10": 203.0,
      "p25": 3739.0,
      "p50": 58987.0,
      "p75": 202019.0,
      "p90": 639887.1000000006,
      "p95": 1297736.6499999994,
      "p99": 4994332.069999996,
      "p100": 12066569.0
    },
    "distinct_gap_lengths": 977115,
    "gap_seconds_frequency_top15": {
      "1.0": 37812,
      "2.0": 23758,
      "3.0": 21243,
      "4.0": 17217,
      "5.0": 15199,
      "6.0": 12323,
      "7.0": 10482,
      "8.0": 9182,
      "9.0": 8182,
      "10.0": 7541,
      "11.0": 6646,
      "15.0": 6137,
      "12.0": 6127,
      "14.0": 5789,
      "13.0": 5637
    },
    "overlap_with_prior_union_seconds": {
      "count": 96555,
      "mean": 1203.6279115530008,
      "p00": 1.0,
      "p01": 10.0,
      "p10": 72.0,
      "p25": 126.0,
      "p50": 420.0,
      "p75": 1319.0,
      "p90": 3184.0,
      "p95": 5186.0,
      "p99": 10455.920000000013,
      "p100": 41522.0
    }
  },
  "intervals_unique_sessions_same_user_any_channel": {
    "valid_positive_rows": 5821970,
    "groups": 4914,
    "rows_overlapping_any_prior_interval": 694713,
    "groups_with_overlap": 3239,
    "touching_prior_union_end": 953454,
    "gaps_after_prior_union_end": 4168889,
    "gap_seconds": {
      "count": 4168889,
      "mean": 11792.090979635102,
      "p00": 1.0,
      "p01": 1.0,
      "p10": 5.0,
      "p25": 18.0,
      "p50": 84.0,
      "p75": 2854.0,
      "p90": 31224.0,
      "p95": 53983.0,
      "p99": 135973.1200000001,
      "p100": 11060770.0
    },
    "distinct_gap_lengths": 144275,
    "gap_seconds_frequency_top15": {
      "1.0": 116377,
      "3.0": 92256,
      "2.0": 89358,
      "4.0": 82722,
      "5.0": 76507,
      "6.0": 68003,
      "7.0": 61465,
      "8.0": 57206,
      "9.0": 52508,
      "10.0": 49337,
      "11.0": 45771,
      "12.0": 43077,
      "13.0": 40667,
      "14.0": 39111,
      "15.0": 37821
    },
    "overlap_with_prior_union_seconds": {
      "count": 694713,
      "mean": 1075.322419473941,
      "p00": 1.0,
      "p01": 14.0,
      "p10": 71.0,
      "p25": 113.0,
      "p50": 311.0,
      "p75": 1022.0,
      "p90": 2768.0,
      "p95": 5007.0,
      "p99": 10570.880000000005,
      "p100": 52596.0
    }
  }
}
```

## Schedule diagnostics

### export_arh_11-20-final.csv

```json
{
  "rows": 1074235,
  "column_count": 13,
  "size_bytes": 153322643,
  "size_MB_decimal": 153.322643,
  "size_MiB": 146.2198667526245,
  "invalid_parsed": {
    "channel_id": 0,
    "tv_show_id": 0,
    "start_time": 0,
    "duration": 0
  },
  "invalid_examples": {},
  "compact_frame_memory_bytes": 85872683,
  "max_end": "2020-05-18T12:00:00",
  "distinct_programmes_including_zero": 5848,
  "distinct_programmes_nonzero": 5847,
  "distinct_channels": 400,
  "zero_channel_rows": 0,
  "labelled_rows": 115613,
  "zero_id_rows": 958622,
  "labelled_row_fraction": 0.10762356467625799,
  "labelled_summed_duration_fraction": 0.1596634144965732,
  "duration_seconds": {
    "count": 1074235,
    "mean": 2229.9894901953485,
    "p00": 0.0,
    "p01": 60.0,
    "p10": 300.0,
    "p25": 600.0,
    "p50": 1500.0,
    "p75": 3000.0,
    "p90": 5400.0,
    "p95": 6900.0,
    "p99": 12600.0,
    "p100": 86400.0
  },
  "labelled_duration_seconds": {
    "count": 115613,
    "mean": 3308.2693122745713,
    "p00": 60.0,
    "p01": 240.0,
    "p10": 600.0,
    "p25": 1200.0,
    "p50": 2700.0,
    "p75": 5400.0,
    "p90": 7200.0,
    "p95": 8400.0,
    "p99": 13800.0,
    "p100": 32700.0
  },
  "nonpositive_duration_rows": 1,
  "nonpositive_duration_examples": [
    {
      "channel_id": "644",
      "tv_show_id": "0",
      "start_time": "2020-03-29T04:00:00.000",
      "duration": 0,
      "channel_title": "Da Vinci Learning Europe",
      "tv_show_title": "Заражено! Жизнь с паразитами.",
      "tv_show_category": "Познавательное",
      "tv_show_genre_1": "познание",
      "tv_show_genre_2": "",
      "tv_show_genre_3": "",
      "year_of_production": "",
      "director": "",
      "actors": "",
      "end_time": "2020-03-29T04:00:00.000"
    }
  ],
  "noninteger_duration_rows": 0,
  "duration_over_24h_rows": 0,
  "categories_all_rows": {
    "Другое": 484058,
    "Познавательное": 221981,
    "Детям": 104593,
    "Сериалы": 72031,
    "Спорт": 62197,
    "Инфо": 50585,
    "Фильмы": 41579,
    "Музыка": 29200,
    "Развлечения": 8011
  },
  "categories_labelled_rows": {
    "Детям": 47862,
    "Сериалы": 31153,
    "Фильмы": 21895,
    "Развлечения": 6887,
    "Инфо": 4487,
    "Познавательное": 2792,
    "Другое": 527,
    "Спорт": 10
  },
  "labelled_metadata_blank_fraction": {
    "tv_show_title": 0.0,
    "tv_show_category": 0.0,
    "tv_show_genre_1": 0.04649131153071021,
    "tv_show_genre_2": 0.40725523946269016,
    "tv_show_genre_3": 0.8254867532197936,
    "year_of_production": 0.007594301678876943,
    "director": 0.1334452007992181,
    "actors": 0.13181043654260335
  },
  "extra_rows_same_airing_identity": 0,
  "same_channel_start_groups_with_multiple_programme_ids": 0,
  "duplicate_identity_groups_with_metadata_disagreement": 0,
  "intervals_raw": {
    "valid_positive_rows": 1074234,
    "groups": 400,
    "rows_overlapping_any_prior_interval": 2,
    "groups_with_overlap": 2,
    "touching_prior_union_end": 1073436,
    "gaps_after_prior_union_end": 396,
    "gap_seconds": {
      "count": 396,
      "mean": 6638.636363636364,
      "p00": 900.0,
      "p01": 3600.0,
      "p10": 3600.0,
      "p25": 3600.0,
      "p50": 3600.0,
      "p75": 3600.0,
      "p90": 3600.0,
      "p95": 3600.0,
      "p99": 3600.0,
      "p100": 1209600.0
    },
    "distinct_gap_lengths": 3,
    "gap_seconds_frequency_top15": {
      "3600.0": 394,
      "900.0": 1,
      "1209600.0": 1
    },
    "overlap_with_prior_union_seconds": {
      "count": 2,
      "mean": 2100.0,
      "p00": 1800.0,
      "p01": 1806.0,
      "p10": 1860.0,
      "p25": 1950.0,
      "p50": 2100.0,
      "p75": 2250.0,
      "p90": 2340.0,
      "p95": 2370.0,
      "p99": 2394.0,
      "p100": 2400.0
    }
  },
  "intervals_unique_airings": {
    "valid_positive_rows": 1074234,
    "groups": 400,
    "rows_overlapping_any_prior_interval": 2,
    "groups_with_overlap": 2,
    "touching_prior_union_end": 1073436,
    "gaps_after_prior_union_end": 396,
    "gap_seconds": {
      "count": 396,
      "mean": 6638.636363636364,
      "p00": 900.0,
      "p01": 3600.0,
      "p10": 3600.0,
      "p25": 3600.0,
      "p50": 3600.0,
      "p75": 3600.0,
      "p90": 3600.0,
      "p95": 3600.0,
      "p99": 3600.0,
      "p100": 1209600.0
    },
    "distinct_gap_lengths": 3,
    "gap_seconds_frequency_top15": {
      "3600.0": 394,
      "900.0": 1,
      "1209600.0": 1
    },
    "overlap_with_prior_union_seconds": {
      "count": 2,
      "mean": 2100.0,
      "p00": 1800.0,
      "p01": 1806.0,
      "p10": 1860.0,
      "p25": 1950.0,
      "p50": 2100.0,
      "p75": 2250.0,
      "p90": 2340.0,
      "p95": 2370.0,
      "p99": 2394.0,
      "p100": 2400.0
    }
  },
  "production_year": {
    "nonblank_rows": 114735,
    "range_or_open_range_rows": 53616,
    "nonstandard_rows": 17,
    "nonstandard_examples": [
      "2006 - ???"
    ]
  }
}
```

### export_arh_21-30-final.csv

```json
{
  "rows": 1074394,
  "column_count": 13,
  "size_bytes": 154366907,
  "size_MB_decimal": 154.366907,
  "size_MiB": 147.21575450897217,
  "invalid_parsed": {
    "channel_id": 0,
    "tv_show_id": 0,
    "start_time": 0,
    "duration": 0
  },
  "invalid_examples": {},
  "compact_frame_memory_bytes": 87074664,
  "max_end": "2020-07-27T12:00:00",
  "distinct_programmes_including_zero": 6364,
  "distinct_programmes_nonzero": 6363,
  "distinct_channels": 403,
  "zero_channel_rows": 0,
  "labelled_rows": 121505,
  "zero_id_rows": 952889,
  "labelled_row_fraction": 0.11309165911202036,
  "labelled_summed_duration_fraction": 0.16899980564172434,
  "duration_seconds": {
    "count": 1074394,
    "mean": 2261.3061874880163,
    "p00": 60.0,
    "p01": 120.0,
    "p10": 300.0,
    "p25": 600.0,
    "p50": 1500.0,
    "p75": 3000.0,
    "p90": 5400.0,
    "p95": 7200.0,
    "p99": 13200.0,
    "p100": 86400.0
  },
  "labelled_duration_seconds": {
    "count": 121505,
    "mean": 3379.2085922390024,
    "p00": 60.0,
    "p01": 240.0,
    "p10": 600.0,
    "p25": 1200.0,
    "p50": 2700.0,
    "p75": 5400.0,
    "p90": 7200.0,
    "p95": 8400.0,
    "p99": 13500.0,
    "p100": 30900.0
  },
  "nonpositive_duration_rows": 0,
  "nonpositive_duration_examples": [],
  "noninteger_duration_rows": 0,
  "duration_over_24h_rows": 0,
  "categories_all_rows": {
    "Другое": 480431,
    "Познавательное": 225108,
    "Детям": 104913,
    "Сериалы": 72081,
    "Спорт": 60163,
    "Инфо": 51039,
    "Фильмы": 44024,
    "Музыка": 28843,
    "Развлечения": 7792
  },
  "categories_labelled_rows": {
    "Детям": 46585,
    "Сериалы": 33288,
    "Фильмы": 25829,
    "Развлечения": 6603,
    "Инфо": 4485,
    "Познавательное": 4212,
    "Другое": 497,
    "Спорт": 6
  },
  "labelled_metadata_blank_fraction": {
    "tv_show_title": 0.0,
    "tv_show_category": 0.0,
    "tv_show_genre_1": 0.044541376898070036,
    "tv_show_genre_2": 0.4006172585490309,
    "tv_show_genre_3": 0.8047323155425703,
    "year_of_production": 0.01228756018270853,
    "director": 0.1366034319575326,
    "actors": 0.1312291675239702
  },
  "extra_rows_same_airing_identity": 0,
  "same_channel_start_groups_with_multiple_programme_ids": 0,
  "duplicate_identity_groups_with_metadata_disagreement": 0,
  "intervals_raw": {
    "valid_positive_rows": 1074394,
    "groups": 403,
    "rows_overlapping_any_prior_interval": 2,
    "groups_with_overlap": 2,
    "touching_prior_union_end": 1073986,
    "gaps_after_prior_union_end": 3,
    "gap_seconds": {
      "count": 3,
      "mean": 1008200.0,
      "p00": 600.0,
      "p01": 12684.0,
      "p10": 121440.0,
      "p25": 302700.0,
      "p50": 604800.0,
      "p75": 1512000.0,
      "p90": 2056320.0,
      "p95": 2237760.0,
      "p99": 2382912.0,
      "p100": 2419200.0
    },
    "distinct_gap_lengths": 3,
    "gap_seconds_frequency_top15": {
      "600.0": 1,
      "604800.0": 1,
      "2419200.0": 1
    },
    "overlap_with_prior_union_seconds": {
      "count": 2,
      "mean": 18000.0,
      "p00": 18000.0,
      "p01": 18000.0,
      "p10": 18000.0,
      "p25": 18000.0,
      "p50": 18000.0,
      "p75": 18000.0,
      "p90": 18000.0,
      "p95": 18000.0,
      "p99": 18000.0,
      "p100": 18000.0
    }
  },
  "intervals_unique_airings": {
    "valid_positive_rows": 1074394,
    "groups": 403,
    "rows_overlapping_any_prior_interval": 2,
    "groups_with_overlap": 2,
    "touching_prior_union_end": 1073986,
    "gaps_after_prior_union_end": 3,
    "gap_seconds": {
      "count": 3,
      "mean": 1008200.0,
      "p00": 600.0,
      "p01": 12684.0,
      "p10": 121440.0,
      "p25": 302700.0,
      "p50": 604800.0,
      "p75": 1512000.0,
      "p90": 2056320.0,
      "p95": 2237760.0,
      "p99": 2382912.0,
      "p100": 2419200.0
    },
    "distinct_gap_lengths": 3,
    "gap_seconds_frequency_top15": {
      "600.0": 1,
      "604800.0": 1,
      "2419200.0": 1
    },
    "overlap_with_prior_union_seconds": {
      "count": 2,
      "mean": 18000.0,
      "p00": 18000.0,
      "p01": 18000.0,
      "p10": 18000.0,
      "p25": 18000.0,
      "p50": 18000.0,
      "p75": 18000.0,
      "p90": 18000.0,
      "p95": 18000.0,
      "p99": 18000.0,
      "p100": 18000.0
    }
  },
  "production_year": {
    "nonblank_rows": 120012,
    "range_or_open_range_rows": 51935,
    "nonstandard_rows": 12,
    "nonstandard_examples": [
      "2006 - ???"
    ]
  }
}
```

### export_arh_31-42-final.csv

```json
{
  "rows": 1295378,
  "column_count": 13,
  "size_bytes": 185952991,
  "size_MB_decimal": 185.952991,
  "size_MiB": 177.33859157562256,
  "invalid_parsed": {
    "channel_id": 0,
    "tv_show_id": 0,
    "start_time": 0,
    "duration": 0
  },
  "invalid_examples": {},
  "compact_frame_memory_bytes": 100617824,
  "max_end": "2020-10-19T12:00:00",
  "distinct_programmes_including_zero": 6637,
  "distinct_programmes_nonzero": 6636,
  "distinct_channels": 404,
  "zero_channel_rows": 0,
  "labelled_rows": 144774,
  "zero_id_rows": 1150604,
  "labelled_row_fraction": 0.11176197218109309,
  "labelled_summed_duration_fraction": 0.16672061292721319,
  "duration_seconds": {
    "count": 1295378,
    "mean": 2263.1395469121753,
    "p00": 60.0,
    "p01": 120.0,
    "p10": 300.0,
    "p25": 600.0,
    "p50": 1500.0,
    "p75": 3000.0,
    "p90": 5400.0,
    "p95": 7200.0,
    "p99": 13500.0,
    "p100": 43200.0
  },
  "labelled_duration_seconds": {
    "count": 144774,
    "mean": 3376.032160470803,
    "p00": 60.0,
    "p01": 240.0,
    "p10": 600.0,
    "p25": 1200.0,
    "p50": 2700.0,
    "p75": 5400.0,
    "p90": 7200.0,
    "p95": 8400.0,
    "p99": 13500.0,
    "p100": 31200.0
  },
  "nonpositive_duration_rows": 0,
  "nonpositive_duration_examples": [],
  "noninteger_duration_rows": 0,
  "duration_over_24h_rows": 0,
  "categories_all_rows": {
    "Другое": 572099,
    "Познавательное": 273595,
    "Детям": 130440,
    "Сериалы": 86663,
    "Спорт": 72002,
    "Инфо": 62860,
    "Фильмы": 53708,
    "Музыка": 34441,
    "Развлечения": 9570
  },
  "categories_labelled_rows": {
    "Детям": 55130,
    "Сериалы": 40590,
    "Фильмы": 30420,
    "Развлечения": 8214,
    "Инфо": 5503,
    "Познавательное": 4367,
    "Другое": 548,
    "Спорт": 2
  },
  "labelled_metadata_blank_fraction": {
    "tv_show_title": 0.0,
    "tv_show_category": 0.0,
    "tv_show_genre_1": 0.03933717380192576,
    "tv_show_genre_2": 0.3930954453147665,
    "tv_show_genre_3": 0.8013662674237086,
    "year_of_production": 0.00761186400873085,
    "director": 0.1352798154364734,
    "actors": 0.13065191263624684
  },
  "extra_rows_same_airing_identity": 0,
  "same_channel_start_groups_with_multiple_programme_ids": 0,
  "duplicate_identity_groups_with_metadata_disagreement": 0,
  "intervals_raw": {
    "valid_positive_rows": 1295378,
    "groups": 404,
    "rows_overlapping_any_prior_interval": 8,
    "groups_with_overlap": 8,
    "touching_prior_union_end": 1294962,
    "gaps_after_prior_union_end": 4,
    "gap_seconds": {
      "count": 4,
      "mean": 2400.0,
      "p00": 300.0,
      "p01": 327.0,
      "p10": 570.0,
      "p25": 975.0,
      "p50": 2550.0,
      "p75": 3975.0,
      "p90": 4110.0,
      "p95": 4155.0,
      "p99": 4191.0,
      "p100": 4200.0
    },
    "distinct_gap_lengths": 4,
    "gap_seconds_frequency_top15": {
      "4200.0": 1,
      "300.0": 1,
      "3900.0": 1,
      "1200.0": 1
    },
    "overlap_with_prior_union_seconds": {
      "count": 8,
      "mean": 2002.5,
      "p00": 120.0,
      "p01": 132.6,
      "p10": 246.0,
      "p25": 525.0,
      "p50": 2100.0,
      "p75": 3600.0,
      "p90": 3600.0,
      "p95": 3600.0,
      "p99": 3600.0,
      "p100": 3600.0
    }
  },
  "intervals_unique_airings": {
    "valid_positive_rows": 1295378,
    "groups": 404,
    "rows_overlapping_any_prior_interval": 8,
    "groups_with_overlap": 8,
    "touching_prior_union_end": 1294962,
    "gaps_after_prior_union_end": 4,
    "gap_seconds": {
      "count": 4,
      "mean": 2400.0,
      "p00": 300.0,
      "p01": 327.0,
      "p10": 570.0,
      "p25": 975.0,
      "p50": 2550.0,
      "p75": 3975.0,
      "p90": 4110.0,
      "p95": 4155.0,
      "p99": 4191.0,
      "p100": 4200.0
    },
    "distinct_gap_lengths": 4,
    "gap_seconds_frequency_top15": {
      "4200.0": 1,
      "300.0": 1,
      "3900.0": 1,
      "1200.0": 1
    },
    "overlap_with_prior_union_seconds": {
      "count": 8,
      "mean": 2002.5,
      "p00": 120.0,
      "p01": 132.6,
      "p10": 246.0,
      "p25": 525.0,
      "p50": 2100.0,
      "p75": 3600.0,
      "p90": 3600.0,
      "p95": 3600.0,
      "p99": 3600.0,
      "p100": 3600.0
    }
  },
  "production_year": {
    "nonblank_rows": 143672,
    "range_or_open_range_rows": 64162,
    "nonstandard_rows": 6,
    "nonstandard_examples": [
      "2006 - ???"
    ]
  }
}
```

## Cross-file coverage and cold-start accounting

```json
{
  "raw_log_distinct_users": 4914,
  "raw_log_distinct_channels": 202,
  "template_users_in_raw_log": 1260,
  "template_users_absent_raw_log": 0,
  "template_users_absent_raw_log_ids": [],
  "template_users_with_raw_history_weeks11_20": 1256,
  "template_users_with_raw_history_weeks21_30": 1246,
  "raw_log_users_outside_template": 3654,
  "raw_users_weeks11_20": 4876,
  "raw_users_weeks21_30": 4820,
  "raw_users_first_seen_weeks21_30": 38,
  "channel_coverage": {
    "export_arh_11-20-final.csv": {
      "log_channels_absent_schedule_count": 9,
      "schedule_channels_absent_log_count": 207,
      "log_channels_absent_schedule": [
        149,
        763,
        911,
        1174,
        1508,
        1509,
        1510,
        1528,
        1531
      ],
      "schedule_channels_absent_log": [
        8,
        9,
        10,
        11,
        13,
        14,
        15,
        17,
        21,
        22,
        30,
        31,
        32,
        33,
        34,
        38,
        45,
        48,
        49,
        56,
        68,
        82,
        89,
        90,
        91,
        99,
        123,
        124,
        142,
        146,
        176,
        177,
        213,
        214,
        216,
        235,
        237,
        238,
        241,
        242,
        243,
        244,
        246,
        255,
        260,
        263,
        270,
        272,
        278,
        284,
        286,
        288,
        292,
        293,
        301,
        302,
        303,
        305,
        308,
        309,
        310,
        311,
        312,
        316,
        327,
        328,
        329,
        331,
        334,
        341,
        350,
        355,
        381,
        383,
        384,
        390,
        394,
        413,
        414,
        415,
        432,
        433,
        439,
        443,
        454,
        459,
        476,
        484,
        487,
        491,
        507,
        534,
        590,
        591,
        599,
        601,
        602,
        603,
        604,
        605,
        608,
        627,
        637,
        639,
        643,
        648,
        649,
        651,
        653,
        656,
        667,
        669,
        681,
        682,
        687,
        688,
        689,
        691,
        693,
        694,
        703,
        707,
        711,
        712,
        719,
        724,
        732,
        747,
        752,
        753,
        757,
        770,
        774,
        781,
        783,
        798,
        800,
        804,
        808,
        812,
        825,
        829,
        832,
        838,
        839,
        841,
        842,
        845,
        858,
        867,
        871,
        880,
        889,
        900,
        901,
        902,
        905,
        910,
        917,
        924,
        934,
        938,
        946,
        952,
        961,
        962,
        963,
        993,
        994,
        995,
        996,
        998,
        999,
        1014,
        1022,
        1026,
        1037,
        1040,
        1045,
        1058,
        1060,
        1061,
        1062,
        1075,
        1077,
        1102,
        1117,
        1121,
        1138,
        1149,
        1150,
        1151,
        1175,
        1177,
        1178,
        1188,
        1208,
        1209,
        1214,
        1215,
        1216,
        1223,
        1227,
        1238,
        1299,
        1310,
        1377
      ]
    },
    "export_arh_21-30-final.csv": {
      "log_channels_absent_schedule_count": 6,
      "schedule_channels_absent_log_count": 207,
      "log_channels_absent_schedule": [
        149,
        823,
        1174,
        1508,
        1509,
        1510
      ],
      "schedule_channels_absent_log": [
        8,
        9,
        10,
        11,
        13,
        14,
        15,
        17,
        21,
        22,
        30,
        31,
        32,
        33,
        34,
        38,
        45,
        48,
        49,
        56,
        68,
        82,
        89,
        90,
        91,
        99,
        123,
        124,
        142,
        146,
        176,
        177,
        213,
        214,
        216,
        235,
        237,
        238,
        241,
        242,
        243,
        244,
        246,
        255,
        260,
        263,
        270,
        272,
        278,
        284,
        286,
        288,
        292,
        293,
        301,
        302,
        303,
        305,
        308,
        309,
        310,
        311,
        312,
        316,
        327,
        328,
        329,
        331,
        334,
        341,
        350,
        355,
        381,
        383,
        384,
        390,
        394,
        413,
        414,
        415,
        432,
        433,
        439,
        443,
        454,
        459,
        476,
        484,
        487,
        491,
        507,
        534,
        590,
        591,
        599,
        601,
        602,
        603,
        604,
        605,
        608,
        627,
        637,
        639,
        643,
        648,
        649,
        651,
        653,
        656,
        667,
        669,
        681,
        682,
        687,
        688,
        689,
        691,
        693,
        694,
        703,
        707,
        711,
        712,
        719,
        724,
        732,
        747,
        752,
        753,
        757,
        770,
        774,
        781,
        783,
        798,
        800,
        804,
        808,
        812,
        825,
        829,
        832,
        838,
        839,
        841,
        842,
        845,
        858,
        867,
        871,
        880,
        889,
        900,
        901,
        902,
        905,
        910,
        917,
        924,
        934,
        938,
        946,
        952,
        961,
        962,
        963,
        993,
        994,
        995,
        996,
        998,
        999,
        1014,
        1022,
        1026,
        1037,
        1040,
        1045,
        1058,
        1060,
        1061,
        1062,
        1075,
        1077,
        1102,
        1117,
        1121,
        1138,
        1149,
        1150,
        1151,
        1175,
        1177,
        1178,
        1188,
        1208,
        1209,
        1214,
        1215,
        1216,
        1223,
        1227,
        1238,
        1299,
        1310,
        1377
      ]
    },
    "export_arh_31-42-final.csv": {
      "log_channels_absent_schedule_count": 6,
      "schedule_channels_absent_log_count": 208,
      "log_channels_absent_schedule": [
        149,
        823,
        1174,
        1508,
        1509,
        1510
      ],
      "schedule_channels_absent_log": [
        8,
        9,
        10,
        11,
        13,
        14,
        15,
        17,
        21,
        22,
        30,
        31,
        32,
        33,
        34,
        38,
        45,
        48,
        49,
        56,
        68,
        82,
        89,
        90,
        91,
        99,
        123,
        124,
        142,
        146,
        176,
        177,
        213,
        214,
        216,
        235,
        237,
        238,
        241,
        242,
        243,
        244,
        246,
        255,
        260,
        263,
        270,
        272,
        278,
        284,
        286,
        288,
        292,
        293,
        301,
        302,
        303,
        305,
        308,
        309,
        310,
        311,
        312,
        316,
        327,
        328,
        329,
        331,
        334,
        341,
        350,
        355,
        381,
        383,
        384,
        390,
        394,
        413,
        414,
        415,
        432,
        433,
        439,
        443,
        454,
        459,
        476,
        484,
        487,
        491,
        507,
        534,
        590,
        591,
        599,
        601,
        602,
        603,
        604,
        605,
        608,
        627,
        637,
        639,
        643,
        648,
        649,
        651,
        653,
        656,
        667,
        669,
        681,
        682,
        687,
        688,
        689,
        691,
        693,
        694,
        703,
        707,
        711,
        712,
        719,
        724,
        732,
        747,
        752,
        753,
        757,
        770,
        774,
        781,
        783,
        798,
        800,
        804,
        808,
        812,
        825,
        829,
        832,
        838,
        839,
        841,
        842,
        845,
        858,
        867,
        871,
        880,
        889,
        900,
        901,
        902,
        905,
        910,
        917,
        924,
        934,
        938,
        946,
        952,
        961,
        962,
        963,
        993,
        994,
        995,
        996,
        998,
        999,
        1014,
        1022,
        1026,
        1037,
        1040,
        1045,
        1058,
        1060,
        1061,
        1062,
        1075,
        1077,
        1102,
        1117,
        1121,
        1138,
        1149,
        1150,
        1151,
        1175,
        1177,
        1178,
        1188,
        1208,
        1209,
        1214,
        1215,
        1216,
        1223,
        1227,
        1238,
        1299,
        1310,
        1377,
        1541
      ]
    }
  },
  "channel_coverage_corresponding_windows": {
    "export_arh_11-20-final.csv": {
      "raw_rows_starting_in_corresponding_window": 3945173,
      "raw_rows_on_channels_absent_this_schedule": 113854,
      "users_on_these_channels": 4471,
      "missing_channels_row_counts": {
        "1174": 55429,
        "1528": 37476,
        "1510": 6615,
        "1509": 6052,
        "1508": 5172,
        "911": 1485,
        "149": 892,
        "763": 733
      }
    },
    "export_arh_21-30-final.csv": {
      "raw_rows_starting_in_corresponding_window": 1876814,
      "raw_rows_on_channels_absent_this_schedule": 40549,
      "users_on_these_channels": 3450,
      "missing_channels_row_counts": {
        "1174": 31454,
        "1510": 2742,
        "1509": 2494,
        "1508": 2319,
        "823": 1130,
        "149": 410
      }
    }
  },
  "adjacent_schedule_file_duplicates": {
    "export_arh_11-20-final.csv + export_arh_21-30-final.csv": {
      "shared_airing_identities": 0,
      "identical_content_rows": 0,
      "shared_identity_with_different_metadata": 0,
      "shared_labelled_airings": 0,
      "min_shared_start": null,
      "max_shared_start": null
    },
    "export_arh_21-30-final.csv + export_arh_31-42-final.csv": {
      "shared_airing_identities": 0,
      "identical_content_rows": 0,
      "shared_identity_with_different_metadata": 0,
      "shared_labelled_airings": 0,
      "min_shared_start": null,
      "max_shared_start": null
    }
  },
  "combined_schedule_intervals": {
    "valid_positive_rows": 3444006,
    "groups": 405,
    "rows_overlapping_any_prior_interval": 13,
    "groups_with_overlap": 13,
    "touching_prior_union_end": 3443184,
    "gaps_after_prior_union_end": 404,
    "gap_seconds": {
      "count": 404,
      "mean": 14022.029702970298,
      "p00": 300.0,
      "p01": 1854.0000000000005,
      "p10": 3600.0,
      "p25": 3600.0,
      "p50": 3600.0,
      "p75": 3600.0,
      "p90": 3600.0,
      "p95": 3600.0,
      "p99": 3890.999999999991,
      "p100": 2419200.0
    },
    "distinct_gap_lengths": 11,
    "gap_seconds_frequency_top15": {
      "3600.0": 394,
      "900.0": 1,
      "4200.0": 1,
      "600.0": 1,
      "604800.0": 1,
      "1209600.0": 1,
      "2419200.0": 1,
      "300.0": 1,
      "3900.0": 1,
      "1200.0": 1,
      "1800.0": 1
    },
    "overlap_with_prior_union_seconds": {
      "count": 13,
      "mean": 4509.2307692307695,
      "p00": 120.0,
      "p01": 141.6,
      "p10": 360.00000000000006,
      "p25": 1500.0,
      "p50": 2400.0,
      "p75": 3600.0,
      "p90": 15120.000000000011,
      "p95": 18000.0,
      "p99": 18000.0,
      "p100": 18000.0
    }
  },
  "strict_time_window_catalogues": {
    "weeks11_20": {
      "programmes_with_any_airing_overlap": 5842
    },
    "weeks21_30": {
      "programmes_with_any_airing_overlap": 6384
    },
    "weeks31_42": {
      "programmes_with_any_airing_overlap": 6649
    }
  },
  "programme_catalogue": {
    "historical_union": 8234,
    "future": 6636,
    "shared_history_future": 5199,
    "future_not_in_historical_schedule": 1437,
    "historical_not_in_future_schedule": 3035,
    "weeks21_30_not_in_weeks11_20": 2387,
    "all_three_union": 9671
  },
  "schedule_boundary_crossings": {
    "export_arh_11-20-final.csv": {
      "2020-05-18T00:00:00": 248,
      "2020-07-27T00:00:00": 0,
      "2020-10-19T00:00:00": 0
    },
    "export_arh_21-30-final.csv": {
      "2020-05-18T00:00:00": 0,
      "2020-07-27T00:00:00": 260,
      "2020-10-19T00:00:00": 0
    },
    "export_arh_31-42-final.csv": {
      "2020-05-18T00:00:00": 0,
      "2020-07-27T00:00:00": 0,
      "2020-10-19T00:00:00": 250
    }
  }
}
```

## Historical schedule / raw viewing overlap

```json
{
  "any_schedule": {
    "valid_view_rows": 5821987,
    "rows_with_any_overlap": 5408598,
    "rows_fully_covered": 5408388,
    "rows_partially_covered": 210,
    "rows_without_overlap": 413389,
    "view_row_seconds_covered": 8107716484,
    "view_row_seconds_total": 8619636424,
    "fraction_view_row_seconds_covered": 0.9406100310014653,
    "users_with_any_overlap": 4912,
    "definition": "sum over raw viewing rows; overlapping user sessions are not deduplicated here"
  },
  "labelled_schedule": {
    "valid_view_rows": 5821987,
    "rows_with_any_overlap": 2964346,
    "rows_fully_covered": 2555628,
    "rows_partially_covered": 408718,
    "rows_without_overlap": 2857641,
    "view_row_seconds_covered": 4575253209,
    "view_row_seconds_total": 8619636424,
    "fraction_view_row_seconds_covered": 0.5307942219303982,
    "users_with_any_overlap": 4895,
    "definition": "sum over raw viewing rows; overlapping user sessions are not deduplicated here",
    "by_window": {
      "weeks11_20": {
        "rows_starting_in_window_with_any_labelled_overlap": 1897800,
        "users_with_any_labelled_overlap": 4841,
        "template_users_with_any_labelled_overlap": 1250,
        "caveat": "Sessions are grouped by start; boundary-crossing overlaps are not clipped here. No 80% threshold applied."
      },
      "weeks21_30": {
        "rows_starting_in_window_with_any_labelled_overlap": 1066546,
        "users_with_any_labelled_overlap": 4806,
        "template_users_with_any_labelled_overlap": 1246,
        "caveat": "Sessions are grouped by start; boundary-crossing overlaps are not clipped here. No 80% threshold applied."
      }
    }
  }
}
```

## Programme metadata consistency

```json
{
  "training_schedules": {
    "tv_show_title": {
      "ids_with_multiple_nonblank_values": 3498,
      "maximum_nonblank_values_per_id": 887
    },
    "tv_show_category": {
      "ids_with_multiple_nonblank_values": 0,
      "maximum_nonblank_values_per_id": 1
    },
    "tv_show_genre_1": {
      "ids_with_multiple_nonblank_values": 46,
      "maximum_nonblank_values_per_id": 2
    },
    "tv_show_genre_2": {
      "ids_with_multiple_nonblank_values": 42,
      "maximum_nonblank_values_per_id": 2
    },
    "tv_show_genre_3": {
      "ids_with_multiple_nonblank_values": 7,
      "maximum_nonblank_values_per_id": 2
    },
    "year_of_production": {
      "ids_with_multiple_nonblank_values": 5,
      "maximum_nonblank_values_per_id": 2
    },
    "director": {
      "ids_with_multiple_nonblank_values": 22,
      "maximum_nonblank_values_per_id": 2
    },
    "actors": {
      "ids_with_multiple_nonblank_values": 105,
      "maximum_nonblank_values_per_id": 3
    },
    "channel_title": {
      "ids_with_multiple_nonblank_values": 6,
      "maximum_nonblank_values_per_id": 2
    }
  },
  "all_schedules": {
    "tv_show_title": {
      "ids_with_multiple_nonblank_values": 4351,
      "maximum_nonblank_values_per_id": 1209
    },
    "tv_show_category": {
      "ids_with_multiple_nonblank_values": 0,
      "maximum_nonblank_values_per_id": 1
    },
    "tv_show_genre_1": {
      "ids_with_multiple_nonblank_values": 80,
      "maximum_nonblank_values_per_id": 3
    },
    "tv_show_genre_2": {
      "ids_with_multiple_nonblank_values": 80,
      "maximum_nonblank_values_per_id": 2
    },
    "tv_show_genre_3": {
      "ids_with_multiple_nonblank_values": 16,
      "maximum_nonblank_values_per_id": 2
    },
    "year_of_production": {
      "ids_with_multiple_nonblank_values": 11,
      "maximum_nonblank_values_per_id": 2
    },
    "director": {
      "ids_with_multiple_nonblank_values": 48,
      "maximum_nonblank_values_per_id": 2
    },
    "actors": {
      "ids_with_multiple_nonblank_values": 174,
      "maximum_nonblank_values_per_id": 3
    },
    "channel_title": {
      "ids_with_multiple_nonblank_values": 9,
      "maximum_nonblank_values_per_id": 2
    }
  }
}
```

## Submission template

```json
{
  "distinct_users": 1260,
  "duplicate_user_rows": 0,
  "all_user_ids_decimal_uint64": true,
  "all_rows_have_five_tokens": true,
  "all_prediction_cells_are_zero_placeholders": true,
  "user_ids_sorted_numeric": false
}
```

## Verification and run environment

```json
{
  "python": "3.12.2 | packaged by conda-forge | (main, Feb 16 2024, 20:54:21) [Clang 16.0.6 ]",
  "pandas": "2.2.2",
  "numpy": "1.26.4",
  "platform": "macOS-15.7.3-arm64-arm-64bit",
  "machine": "arm64",
  "chunk_size": 250000,
  "elapsed_seconds": 70.94754712500003,
  "peak_rss_MiB": 3449.03125,
  "self_checks": {
    "passed": true,
    "checks": [
      "nested/touching interval union",
      "coverage vs enumeration oracle",
      "uint64 exact round trip and invalid IDs",
      "explicit day-first dates",
      "prior-maximum overlap detection"
    ]
  },
  "accounting_assertions_passed": true,
  "personal_student_verification": "Not performed or claimed by this automated audit"
}
```

## Interpretation cautions

- `tv_show_id = 0` is not a recommendable item. Row coverage is not airtime coverage; summed-duration coverage is separately reported and can itself be affected by overlapping schedule records.
- Schedule metadata statistics that include weeks 31–42 are data-quality diagnostics, not training features. Training-only metadata variants are separately exported.
- The interval overlap counts count rows intersecting a prior union, not all overlapping pairs. Identical-airing and unique-airing statistics are separate.
- Blank cells, whitespace-only cells, literal zeros and null-like text are distinct. A zero-filled numeric field is not automatically missing.
- Catalogue presence is not observed viewing support. A future programme appearing in an old schedule can still have zero training interactions.
- See columns.csv for every column's missingness and cardinality; daily_counts.csv and weekly_counts.csv for complete temporal counts; and example/metadata CSVs for inspectable records.
- All automated checks here were executed by the assistant. The student's personal verification remains to be performed and is not claimed.
