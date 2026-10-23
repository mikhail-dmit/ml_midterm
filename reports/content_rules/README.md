# Content-based filtering and association rules

## Fixed protocol and result

Training weeks 11–20, validation weeks 21–30, original >=80%-watch labels, repeats allowed, all 6,384 schedule-available candidates, original MAP@5 evaluator. All-primary (4,030) selects settings; template-primary (1,150) is reporting only.

| Method | Selected run | MAP@5 all primary | MAP@5 template primary |
|---|---|---:|---:|
| Popularity | popularity | 0.27939123 | 0.30530725 |
| implicit_mf | mf_f16_logtarget_a1_r1 | 0.35298677 | 0.38568116 |
| ppr | ppr_raw_a050_log | 0.35775352 | 0.39209275 |
| content_based | cbf_title_tfidf_count | 0.24500165 | 0.26950145 |
| association_rules | ar_week_s5_conf | 0.31417783 | 0.33657681 |

PPR remains the highest observed standalone result. Weekly association rules beat popularity but remain below MF/PPR. The improved content method remains below popularity; that negative result is retained.

## All new experiments

| Configuration | MAP@5 all 4,030 | MAP@5 template 1,150 |
|---|---:|---:|
| cbf_genre_log | 0.08695203 | 0.09376522 |
| cbf_rich_log | 0.08166170 | 0.08644058 |
| cbf_rich_tfidf_log | 0.08551282 | 0.09045507 |
| ar_user_s5_conf | 0.25769148 | 0.27998551 |
| ar_user_s20_conf | 0.25549711 | 0.27737391 |
| ar_user_s5_lift | 0.03793879 | 0.03788986 |
| cbf_rich_tfidf_count | 0.16109512 | 0.17817971 |
| cbf_title_tfidf_count | 0.24500165 | 0.26950145 |
| ar_user_s5_conf_count | 0.23485939 | 0.25402319 |
| ar_week_s5_conf | 0.31417783 | 0.33657681 |

## Content method and leakage boundary

- The metadata snapshot contains 5,842 labelled programme IDs from 115,316 positive-duration airings starting before the validation cutoff. The second schedule contributes zero rows to feature fitting. Source hashes and cutoff timestamps are in metadata_provenance.json.
- This deliberately conservative policy freezes item attributes as well as vocabulary/IDF before validation. Of the fixed 6,384 candidates, 3,993 have frozen metadata. The others keep zero content score; none are removed from the pool. This is a coverage choice of this implementation, not an inherent inability of content methods to describe new items when their metadata is permitted.
- Category is the deterministic most frequent training value; genres, actors/directors, production-start decades and (when enabled) title words are unioned across training airings of the same ID. Missing fields add no artificial unknown token. Year ranges use their starting year.
- Binary multi-hot tokens are weighted with training-item smoothed IDF, `log((1+N)/(1+df))+1`, where configured. Each feature family is L2-normalized before applying the declared family weight; the concatenated item vector is normalized again.
- User profiles are weighted sums of watched-item content vectors, using log counts or counts, then L2-normalized. Scoring is cosine. No programme-ID feature, personal-frequency ranker or popularity score fusion is introduced.

### What was strange and what the checks established

1. Genre/category CBF reaches only MAP 0.08695203. It has 518 unique vectors for 5,842 IDs; 5,609 items share a vector with another ID and the largest group contains 460 programmes. Around 32 candidates tie at the fifth score on average. Generic genre matching cannot uniquely identify a user's favourite show.
2. Richer TF-IDF metadata removes most exact collisions (5,766 unique vectors), but MAP stays at 0.08551282. Higher Precision@5 without an MAP gain shows that representation uniqueness alone does not fix ranking of the exact favourite IDs.
3. Changing only profile weights from log counts to counts raises rich CBF MAP to 0.16109512. The heavy viewer's profile shifts from films to news. This supports the hypothesis that many occasional items were overwhelming a few recurring favourites after log compression.
4. Adding supplied past-schedule title-word features raises MAP to 0.24500165, with only 26 items remaining in nonunique vector groups. Numeric episode/season labels and boilerplate are stripped; tokens remain actual metadata, not item IDs. Titles help distinguish programmes sharing broad genres.
5. The selected content model is still below popularity. The light user has one entertainment-programme watch and gets an entertainment-only list, while later favourites include news. Metadata similarity cannot infer that change from a single seed. The heavy user gets the right broad category but still includes occasional news programmes outside their exact favourite Top-5.
6. Selected CBF recommends 2,785 slots with zero collaborative training support; 0 are actual Top-5 hits. Of 1,043 true slots without collaborative training support, only 272 have metadata in the frozen snapshot. This coverage limit must be separated from ranking quality; these counts do not establish a general failure of content-based item-cold-start handling. See content_new_item_diagnostics.json.

## Association-rule method

A basket is a set of distinct qualified programme IDs. Initial baskets are nonempty user histories; diagnostic baskets are nonempty user/ISO-week histories, assigned by the local week of the first in-window watched overlap. No validation event enters any basket.
The implementation exactly enumerates frequent singletons and pairs using a binary basket-item matrix. It mines singleton A->B rules (not an unrestricted full Apriori search), requiring A!=B, joint count >=5 or >=20, confidence >=0.10 and lift>1.
For N baskets: support=n_AB/N; confidence=n_AB/n_A; lift=(n_AB/n_A)/(n_B/N). Lift>1 is filtered using exact integer cross-products. Repeated watches never inflate a basket's item indicator.
Candidate score = sum over watched antecedents A of history_weight(u,A)*rule_weight(A->B). Rule weight is confidence or lift. Consequents already watched in training are allowed. Self-rules are excluded because A->A is tautological. Scores are not calibrated probabilities and are not causal effects.

### Why history/confidence, lift and weekly baskets differ

- Whole-history confidence rules get 0.25769148, below popularity, and concentrate recommendations on only 24 IDs. Many weakly related antecedents point to ubiquitous news, while ten weeks of viewing mix different interests and schedules.
- Raising the joint floor to 20 does not repair that: MAP is 0.25549711. This is evidence against treating support tuning alone as the solution.
- Changing only aggregation from confidence to lift collapses MAP to 0.03793879. Lift divides by consequent prevalence, strongly amplifying niche associations. One observed rule has n_A=6, n_B=11, n_AB=5, N=4,737: support=5/4737, confidence=5/6, lift=358.86. It addresses only six observed antecedent-user baskets; extreme enrichment is neither broad actionable reach nor proof of future favourite frequency.
- Raw-count antecedent weights also fail to help (MAP 0.23485939). Stronger historical frequency alone does not make a cross-programme conditional association a direct persistence model.
- Weekly baskets produce 37,403 baskets and 16,126 retained rules, improving MAP to 0.31417783. This is consistent with more local co-view context being useful, but basket definition also changes prevalence and support semantics; it is not proof that locality alone causes the improvement.
- The support floor is still five baskets, now user-weeks rather than users. Twelve weekly rules have fewer than five distinct joint users; their distinct-user counts remain exported rather than hidden behind repeated weeks.
- Weekly rules require three popularity-backfilled slots for one warm user, in addition to the shared 59 cold-user fallbacks. This cannot explain a cohort MAP improvement of about 0.0565: at most one user's AP changes from that extra backfill.

## Common fallback and tie policy

All methods retain exactly five unique candidates. Positive content/rule scores rank descending with numeric-ID ties; slots with no positive model signal are filled from the same training popularity order. Cold-user output is identical across all methods. Every previous warm MF/PPR Top-5 score is positive, so this backfill convention leaves all saved MF/PPR predictions unchanged. The verifier checks new fallback provenance explicitly.
Local true-ID tie uncertainty remains unchanged (2,630 of 4,030 primary users). No truth pruning or method-specific denominator is used.

## Same two users

| User role | Programme history | Popularity AP | MF AP | PPR AP | CBF AP | Rules AP |
|---|---|---:|---:|---:|---:|---:|
| light: 1026253314001693311 | 1 airings / 1 IDs | 0.52000000 | 0.06666667 | 0.35333333 | 0.00000000 | 0.48333333 |
| heavy: 13866173795451203812 | 1845 airings / 408 IDs | 1.00000000 | 0.71000000 | 0.76000000 | 0.52000000 | 0.76000000 |

The users were selected from training-history extremes before any model runs; they are not flattering examples selected after comparing algorithms. Full ordered IDs, titles, categories, history counts and actual validation matches are in reports/all_methods/recommendation_examples.csv.

## Verification, reproducibility and later report

Independent verification passed **120 checks across 10 runs**. It reconstructs all frozen documents from raw CSVs, item weights/IDF/profile algebra, user-week baskets, frequent-pair filters, rule metrics, full predictions, fallbacks and exact per-user AP/MAP. Eight unit tests cover hand cosine, IDF, family balancing, title parsing, directional confidence, self-rule removal and backfill.
Complete feature and matched-rule contributions are saved for the same example users. manual_rule_calculation.json contains one real rule with all counts for a later student calculation. These are assistant-executed checks; personal verification is not claimed.

```bash
python3 -m unittest discover -s scripts -p 'test_content_rules.py'
python3 scripts/run_content_rules.py --stage all
python3 scripts/verify_content_rules.py
python3 scripts/summarize_content_rules.py
```

The previous MF diagnosis is preserved in reports/models/README.md and diagnostic_plan.md. reports/all_methods/report_notes.md collects the four method-specific findings to use in the later PDF. No final exam PDF, test-period refit, hybrid, Kaggle submission or online-effect claim is generated here.

## Sources consulted

- Supplied content/association-rule lectures, exam brief and teacher feedback/answers, including the distinction between high lift and actionable reach.
- scikit-learn feature extraction documentation: multi-valued categorical encoding, smoothed IDF and cosine normalization. Used as formula reference; implementation uses NumPy/SciPy. https://scikit-learn.org/1.5/modules/feature_extraction.html#text-feature-extraction
- mlxtend association-rule documentation: support, confidence and lift definitions. Used as formula reference, not as the mining implementation. https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/
