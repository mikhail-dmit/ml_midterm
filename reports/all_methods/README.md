# Four-method SWEET.TV validation comparison

The complete CBF/rule diagnosis is in [../content_rules/README.md](../content_rules/README.md); MF/PPR analysis remains in [../models/README.md](../models/README.md).

| Method | Selected configuration | All-primary MAP@5 | Template-primary MAP@5 |
|---|---|---:|---:|
| popularity | popularity | 0.27939123 | 0.30530725 |
| implicit_mf | mf_f16_logtarget_a1_r1 | 0.35298677 | 0.38568116 |
| ppr | ppr_raw_a050_log | 0.35775352 | 0.39209275 |
| content_based | cbf_title_tfidf_count | 0.24500165 | 0.26950145 |
| association_rules | ar_week_s5_conf | 0.31417783 | 0.33657681 |

All use the same original 4,030 users, 1,150-user reporting subset, 6,384 candidates, repeats allowed, training-only history, ground truth, MAP@5 evaluator and cold popularity fallback. Full configurations are retained in all_configurations.csv; no weak run is hidden.

Selection is based only on all-primary MAP@5. Conditional paired-user intervals are in paired_comparisons.csv; they do not account for selection or unknown label tie-breaking.

PPR remains the leading observed standalone method; count-target MF is second, weekly association rules third, popularity fourth and metadata CBF fifth. This is a result for this temporal favourite-frequency task, not a universal algorithm ranking.

The same training-selected heavy/light user examples with all ordered IDs, titles/categories and validation matches are in recommendation_examples.csv.

MF/PPR verification: ../models/verification.json (95 checks over nine runs). CBF/rule verification: ../content_rules/verification.json (120 checks over ten runs).
