# Where each method works, and shared training-input experiments

## Scope and controls

This stage is diagnosis before hybrids. No fusion, switching recommender or target-aware per-user method selection was trained. The reference analysis uses the previously selected strict/full-history models.
The shared study changes only training behaviour: watched coverage threshold 80/50/20 percent × full ten / older four / recent four weeks. All five methods receive the same selected events in a setting. Validation stays the original >=80% Top-5, with the same 4,030 users, 1,150-user subset, 6,384 candidates, repeat policy and MAP@5 denominator.
Method hyperparameters are frozen at their previous selections: log-count MF f16/confidence1/reg1/15 epochs; raw PPR alpha=.50/log restart; rich+title TF-IDF CBF/count profile; weekly pair rules/joint>=5/confidence>=.10/lift>1/log query weights.
CBF item vectors/vocabulary/IDF remain fixed from all pre-May18 metadata. Window changes concern viewing behaviour, not erasing known catalogue attributes. Each setting fits its own training popularity, shared by all cold/insufficient-signal fallbacks. Original strict-history familiarity and user bins remain fixed across settings.

## 1. How many true answers are familiar versus new?

Familiar means a programme with >=1 original >=80% qualifying training watch in weeks 11–20. New means no such qualifying watch; it is not proof the person has never seen it or would enjoy discovering it.

| Cohort | Familiar true slots | New true slots | New but partial overlap before | New with no recorded programme overlap |
|---|---:|---:|---:|---:|
| all_primary | 11,323 (56.19%) | 8,827 (43.81%) | 3,441 (17.08%) | 5,386 (26.73%) |
| template_primary | 3,561 (61.93%) | 2,189 (38.07%) | 958 (16.66%) | 1,231 (21.41%) |

### Which types do methods retrieve?

These are micro recalls of each true-answer type, not separately renormalized MAP scores. Familiar and new AP-credit contributions are also saved; their sum exactly reproduces original MAP@5.

| Reference method | Familiar recall: all | New recall: all | Familiar recall: template | New recall: template |
|---|---:|---:|---:|---:|
| Popularity | 54.02% | 12.35% | 54.51% | 13.07% |
| MF | 69.98% | 3.94% | 69.39% | 3.52% |
| PPR | 73.05% | 1.99% | 72.45% | 1.55% |
| CBF | 47.68% | 2.79% | 47.43% | 2.97% |
| Rules | 59.46% | 11.73% | 58.94% | 11.56% |

PPR and MF excel at recurring favourites. Popularity and weekly rules recover substantially more new-to-user truth, despite lower overall MAP. CBF's unfamiliar outputs are not automatically relevant discoveries. In the strict reference runs all methods miss the 1,043 true slots with no global strict training support.

### User-level target composition (post-hoc only)

These groups use validation answers for explanation, not for training or a deployable switching rule.

| validation_composition | Users | Popularity | MF | PPR | CBF | Rules |
|---|---:|---:|---:|---:|---:|---:|
| all_five_new | 393 | 0.094733 | 0.038117 | 0.040628 | 0.032061 | 0.085386 |
| mixed | 2,963 | 0.275154 | 0.338364 | 0.341011 | 0.238740 | 0.303814 |
| all_five_familiar | 674 | 0.405692 | 0.600865 | 0.616266 | 0.396691 | 0.493145 |


## 2. Short versus long histories

Bins use only original training data; users never move bins when softer/recent inputs are tested. History size is shown by distinct programme count below. The files also cover qualifying-airing volume, active training weeks and age of last training activity.

### all_primary: MAP@5 by distinct-programme history

| segment | Users | Popularity | MF | PPR | CBF | Rules |
|---|---:|---:|---:|---:|---:|---:|
| 0 (cold) | 59 | 0.201864 | 0.201864 | 0.201864 | 0.201864 | 0.201864 |
| 1-5 | 224 | 0.160164 | 0.141935 | 0.155149 | 0.102396 | 0.157217 |
| 6-20 | 1,512 | 0.237123 | 0.300628 | 0.300018 | 0.217932 | 0.273267 |
| 21-50 | 1,836 | 0.314178 | 0.408640 | 0.413094 | 0.277901 | 0.354512 |
| 51+ | 399 | 0.357895 | 0.436140 | 0.458688 | 0.282632 | 0.388338 |

### template_primary: MAP@5 by distinct-programme history

| segment | Users | Popularity | MF | PPR | CBF | Rules |
|---|---:|---:|---:|---:|---:|---:|
| 0 (cold) | 10 | 0.180000 | 0.180000 | 0.180000 | 0.180000 | 0.180000 |
| 1-5 | 39 | 0.211709 | 0.134872 | 0.165556 | 0.113333 | 0.190427 |
| 6-20 | 373 | 0.246631 | 0.320518 | 0.319169 | 0.237659 | 0.281251 |
| 21-50 | 589 | 0.334601 | 0.433616 | 0.439898 | 0.293860 | 0.371647 |
| 51+ | 139 | 0.373909 | 0.442590 | 0.464029 | 0.301990 | 0.388705 |

All truly cold reference users get the same popularity fallback. For 1–5-programme histories, popularity is competitive or better than the personal models; the template subgroup has only 39 users, so this is a small-sample observation, not a validated switching rule. MF/PPR's gains are much clearer for richer and consistently active histories.
Popularity itself improves for richer-history users: cohort composition/target predictability changes too. These strata do not prove that increasing a person's history alone causes the observed gains.

## 3. Same users or different correct programmes?

Any-hit user overlap and correct (user,programme) pair overlap are distinct. Two methods can both hit a user while finding different favourites.

| Reference pair | Both hit users | A-only hit users | B-only hit users | A-only correct pairs | B-only correct pairs | Mean shared Top-5 IDs | AP Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| A=MF, B=PPR | 3,491 | 55 | 120 | 759 | 934 | 3.679 | 0.918 |
| A=PPR, B=Rules | 3,389 | 222 | 142 | 2,265 | 1,586 | 2.700 | 0.705 |
| A=Popularity, B=PPR | 3,353 | 171 | 258 | 1,561 | 2,801 | 2.325 | 0.599 |

MF/PPR any-hit user Jaccard is 0.952, but their correct-pair Jaccard is 0.816: complementarity is more about different answers/rankings for overlapping users than two disjoint audiences.

| Method | Users only this method hits | Correct pairs only this method finds |
|---|---:|---:|
| Popularity | 44 | 400 |
| MF | 22 | 408 |
| PPR | 25 | 442 |
| CBF | 6 | 189 |
| Rules | 11 | 240 |

Across the five separate lists, 3,832 users have at least one hit and 11,120/20,150 true pairs are found somewhere. This union can contain up to 25 recommendations per user; it is **not** a deployable Top-5 hybrid or a hybrid MAP result.
The same pairwise and exclusive-hit analyses for the 1,150 users are saved separately by cohort in reference_analysis/*.csv.

## 4. Shared threshold × history-window study

All thresholds affect training only. Each qualifying airing contributes one count at its declared threshold. Lower thresholds add partial airings with equal count contribution rather than assigning fractional confidence per event.

| Window | Dates, local half-open | Interpretation |
|---|---|---|
| full10 | Mar 9 – May 18 | All weeks 11–20 |
| early4 | Mar 9 – Apr 6 | Older weeks 11–14 |
| recent4 | Apr 20 – May 18 | Recent weeks 17–20 |

Older/recent windows have the same four-calendar-week width. Raw viewing intervals are clipped and rejoined at their exact boundaries, retaining full airing duration denominators. Filtering by filename, airing start or an aggregated first/last timestamp alone was not used.

### all_primary: MAP@5

| setting | Popularity | MF | PPR | CBF | Rules |
|---|---:|---:|---:|---:|---:|
| early4_t20 | 0.278754 | 0.322839 | 0.319495 | 0.213352 | 0.291525 |
| early4_t50 | 0.279391 | 0.315870 | 0.317366 | 0.226344 | 0.290807 |
| early4_t80 | 0.279391 | 0.300672 | 0.306459 | 0.222183 | 0.294962 |
| full10_t20 | 0.278754 | 0.363757 | 0.360674 | 0.215796 | 0.291246 |
| full10_t50 | 0.279391 | 0.365925 | 0.364974 | 0.236984 | 0.302012 |
| full10_t80 | 0.279391 | 0.352987 | 0.357754 | 0.245002 | 0.314178 |
| recent4_t20 | 0.279391 | 0.340976 | 0.335156 | 0.176639 | 0.280682 |
| recent4_t50 | 0.279391 | 0.336103 | 0.333391 | 0.202761 | 0.293883 |
| recent4_t80 | 0.261178 | 0.321006 | 0.323457 | 0.213057 | 0.296371 |

### template_primary: MAP@5

| setting | Popularity | MF | PPR | CBF | Rules |
|---|---:|---:|---:|---:|---:|
| early4_t20 | 0.304507 | 0.350423 | 0.350612 | 0.230939 | 0.316586 |
| early4_t50 | 0.305307 | 0.345548 | 0.346145 | 0.244357 | 0.316241 |
| early4_t80 | 0.305307 | 0.327812 | 0.330557 | 0.239545 | 0.320962 |
| full10_t20 | 0.304507 | 0.394699 | 0.391687 | 0.234994 | 0.315122 |
| full10_t50 | 0.305307 | 0.397470 | 0.400200 | 0.260301 | 0.326670 |
| full10_t80 | 0.305307 | 0.385681 | 0.392093 | 0.269501 | 0.336577 |
| recent4_t20 | 0.305307 | 0.371661 | 0.366542 | 0.196336 | 0.303954 |
| recent4_t50 | 0.305307 | 0.365432 | 0.368745 | 0.226962 | 0.316272 |
| recent4_t80 | 0.285220 | 0.351130 | 0.359264 | 0.240719 | 0.315258 |

### What the threshold effect means

| Full-history threshold | Qualifying airings | Positive user/programme pairs | Cold primary users | True slots now in own history |
|---|---:|---:|---:|---:|
| 80% | 316,413 | 114,851 | 59 | 11,323 |
| 50% | 515,512 | 199,036 | 43 | 12,573 |
| 20% | 861,447 | 352,915 | 33 | 13,590 |

- Full-history 50% improves both MF and PPR; 20% is not better than 50%. CBF and rules instead prefer the strict 80% input in this study. There is no universally best threshold across the four methods.
- The 50% signal adds useful partial-history evidence. Under the ORIGINAL fixed familiarity labels, PPR new-type hits rise 176 -> 379: partial-exposure hits 73 -> 298, while no-recorded-exposure hits fall 103 -> 81. This is mainly recovery from previously observed partial interests, not discovery of wholly unknown programmes.
- MF new-type hits rise 348 -> 561, with partial-exposure hits 186 -> 405. Its familiar hits also rise 7,924 -> 7,994. Denominators/types have not been changed to manufacture this gain.
- At 20%, the positive-pair matrix is much broader (352,915 vs 114,851), and partial events count like full watches. That can dilute content profiles and broaden weak rule associations. Weekly rules grow from 16,126 to 84,436, but distinct recommended IDs fall 49 -> 24 and MAP worsens. This is evidence about these inputs, not proof that every partial view is a dislike.
- Only 122 of the 861,447 full-history 20%-qualified events have under 60 watched seconds. The effect should not be simplistically attributed entirely to tiny channel-surfing fragments; fractional coverage and changed association structure matter.
- Some original cold users become warm at softer thresholds, but remain in their original diagnostic bins. Setting-specific cold-user counts are also reported; nobody is dropped.

### What the window effect means

At 80%, recent4 beats early4 for MF/PPR, but neither beats full10. Recent4 has 133,800 qualifying events vs early4's 125,294, 1,578 vs 1,137 supported items, and 138 vs 189 cold primary users. Equal calendar width does not equal identical sample volume/catalogue coverage, so recency is not isolated from those changes.
Full history retains useful information. Truncating to recent four weeks increases cold users and removes globally useful programme support. CBF also retains a fixed pre-cutoff metadata corpus; only its viewing profile changes.

### Why popularity scores sometimes repeat exactly

Global count magnitudes change, but Top-5 ranking metrics change only when the recommended IDs/order change. Many settings retain exactly the same ordered five IDs. Recent4/80 swaps SpongeBob and Fakty at ranks 2/3, reducing MAP without changing the five-item set. Full10/20 swaps the last two IDs. See popularity_top5_stability.csv; counts/rankings were independently reconstructed, not cached accidentally.

## Interpretation before hybrids

- Reference PPR/MF are strongest for recurring favourites and richer histories; popularity/rules contribute more new-to-user answers and can help different missed users or items.
- For subsequent MF/PPR experiments, full ten weeks with 50% training qualification is a supported candidate input. It is not a universal improvement for CBF/rules; strict/full comparisons remain preserved.
- At full10/50, MF has slightly higher all-primary MAP (0.36592473 vs PPR 0.36497436), while PPR leads on the template subset (0.40020000 vs MF 0.39746957). Do not turn this small ordering difference into a universal new method ranking.
- Shared inputs were tested with frozen original method hyperparameters. The study is conditional on those settings, one temporal hold-out and the existing unknown fifth-place tie policy. No hybrid was trained or scored.

## Verification and reproduction

Independent verification passed **328 checks across 45 runs**: fixed source fingerprints, reference familiar/new classes and overlap arithmetic, all threshold aggregates, exact sparse counts/IDs, candidate/popularity reconstruction, cold fallbacks, original-prediction reproduction and exact AP/MAP. Window clipping was independently rejoined from original raw view fragments for boundary/DST/example users.
Three targeted unit checks cover AP partitioning, user-vs-answer complementarity and exact threshold/boundary denominator arithmetic. Each new MF/PPR fit also performs its objective/stationary-mass assertions; algorithm algebra was independently verified in prior stages.

```bash
python3 -m unittest discover -s scripts -p 'test_training_study.py'
python3 scripts/analyze_method_segments.py
python3 scripts/training_study.py
python3 scripts/verify_training_study.py
python3 scripts/summarize_training_study.py
```

Use --setting recent4_t50 to rerun one setting. Window caches are fingerprinted; original truth/cohorts/candidates/content artifacts are read-only and their hashes checked throughout. Original reports/all_methods results are not overwritten.
All detailed reference/subgroup/overlap tables, 45 sets of predictions/per-user scores, scenario counts, frozen plan, models and conditional paired-user intervals are saved. Intervals use 2,000 paired resamples and do not account for input/model selection or temporal/label uncertainty. Student personal verification remains unclaimed.
