# SWEET.TV user–programme interactions and local validation labels

## Definition

1. Interpret supplied timestamp strings as Europe/Kyiv local time, convert to UTC seconds. Schedule end is localized start plus supplied elapsed duration. This is an empirically supported assumption, not a declared organiser timezone.
2. Exclude programme ID 0 and nonpositive-duration airings. Read both historical schedule files; do not partition by filename. Preserve IDs exactly.
3. Remove identical log rows, union all overlapping/touching view intervals per user and channel, and clip observed viewing to each temporal window.
4. Join on the same channel and a strictly positive interval overlap. For each user and airing, add the non-overlapping watched fragments.
5. A watched airing has union watched seconds / full original airing duration >= 0.8. Implement the exact integer condition `5 * watched_seconds >= 4 * duration`. Never shrink the denominator at a split boundary.
6. Count qualifying airings per user and programme ID. Each airing contributes at most one count per user; fragments do not add extra counts. Distinct broadcasts/channels are distinct airings.
7. Validation Top-5: five distinct IDs with highest qualifying-airing counts in weeks 21–30; ties use ascending numeric ID.

Kaggle documents the 80% threshold and frequency Top-5. Fragment union, airing-event identity and tie-breaking are explicit reconstruction choices; the hidden generator's full code was not supplied. These are **local reference labels**, not access to Kaggle's hidden answers.

## Windows

| Split | Local start, inclusive | Local end, exclusive | User–airing overlaps | Qualified airings | Users with qualified watches | Programmes with qualified watches |
|---|---|---|---:|---:|---:|---:|
| train | 2020-03-09 00:00:00 | 2020-05-18 00:00:00 | 1,823,893 | 316,413 | 4,737 | 2,490 |
| validation | 2020-05-18 00:00:00 | 2020-07-27 00:00:00 | 1,191,015 | 295,044 | 4,643 | 2,852 |

## Sanity checks

- all watched times positive and no larger than full programme duration: **True**
- all coverage values in (0,1]: **True**
- one row per split/user/airing: **True**
- no ID zero in joined events: **True**
- train plus validation watched seconds do not exceed an airing duration: **True**
- no airing counted watched in both temporal splits: **True**
- programme counts reconcile to qualified airing counts: **True**
- primary ground truth always five distinct IDs: **True**
- raw user cohort accounting closes: **True**
- zero timezone elapsed-duration mismatches: **True**

## Cohort and labels

```json
{
  "raw_users": 4914,
  "users_no_validation_qualified_programmes": 271,
  "users_one_to_four_validation_qualified_programmes": 613,
  "primary_users_at_least_five": 4030,
  "primary_ground_truth_rows": 4030,
  "primary_cold_start_users": 59,
  "primary_test_template_users": 1150,
  "test_template_users_without_training_qualified_history": 18,
  "primary_users_with_fifth_sixth_count_tie": 2630,
  "validation_top5_unseen_in_training_items": 1283,
  "primary_validation_top5_unseen_in_training_items": 1043,
  "validation_qualified_programme_count_quantiles": {
    "0": 0.0,
    "0.25": 7.0,
    "0.5": 16.0,
    "0.75": 36.0,
    "0.9": 74.0,
    "0.99": 160.8699999999999,
    "1": 284.0
  },
  "tie_break": "Descending qualifying-airing count, then ascending numeric tv_show_id; organiser tie-break unspecified",
  "display_title": "Title/category of this user's most recent qualifying validation airing for that ID; explanatory lookup only",
  "primary_cohort": "All raw-log users with >=5 distinct qualified validation programmes; no warm-user filter",
  "broad_cohort": "All users with >=1 qualified validation programme, with up to five true IDs"
}
```

Primary ground truth includes every user with at least five qualified validation programmes, including training-cold users. Users with 1–4 positives are exported separately for a broader evaluation; users with zero positives are accounted for in validation_users.csv. Nothing is padded with invented true IDs.

**Label uncertainty:** 2,630 primary users have a frequency tie crossing the Top-5 boundary. See `validation_boundary_ties.csv`. Membership under Kaggle's undocumented tie-break can differ; do not describe these local labels as an exact reproduction of the hidden generator.

## Time interpretation evidence

```json
{
  "assumed_timezone": "Europe/Kyiv",
  "viewing_duration_mismatches": {
    "naive": 117,
    "timezone_elapsed": 0
  },
  "schedule_continuity": {
    "export_arh_11-20-final.csv": {
      "naive": {
        "gaps": 396,
        "overlaps": 2,
        "one_hour_gaps": 394
      },
      "timezone_elapsed": {
        "gaps": 2,
        "overlaps": 2,
        "one_hour_gaps": 0
      }
    },
    "export_arh_21-30-final.csv": {
      "naive": {
        "gaps": 3,
        "overlaps": 2,
        "one_hour_gaps": 0
      },
      "timezone_elapsed": {
        "gaps": 3,
        "overlaps": 2,
        "one_hour_gaps": 0
      }
    },
    "combined_historical_schedule": {
      "naive": {
        "gaps": 399,
        "overlaps": 5,
        "one_hour_gaps": 394
      },
      "timezone_elapsed": {
        "gaps": 5,
        "overlaps": 5,
        "one_hour_gaps": 0
      }
    }
  }
}
```

## Worked example

User **127680364314713816**. See [manual_example/README.md](manual_example/README.md) for arithmetic and source-record references.

## Reproduction

```bash
python3 -m unittest discover -s scripts -p 'test_interactions.py'
python3 scripts/build_interactions.py
python3 scripts/verify_interactions.py
```

Artifacts: airings.parquet, airing_interactions.parquet, user_programme_interactions.parquet under artifacts/interactions/.

Saved tables contain **3,014,908 user–airing rows**, **1,516,807 split/user/programme rows** including partial overlaps, and **255,337 positive split/user/programme rows** after filtering `watched_airings > 0`.
Reports: validation_top5.csv (long format; all users with positives), validation_ground_truth.csv (strictly five IDs), validation_ground_truth_partial.csv (1–4 IDs), validation_users.csv, summary.json, and the worked example.

No recommendation model or baseline was trained. Popularity remains the only planned baseline.
All automated verifications were performed by the assistant. Student personal verification is not claimed.
