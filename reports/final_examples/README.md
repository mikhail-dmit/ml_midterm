# Final report examples: one heavy and one light validation viewer

Final strategy: **submission 007**, user-reported Kaggle **public 0.43707 / private 0.42472**, linked to its CSV hash and screenshot. **Experiments are closed by user instruction.**

## Start here

- **examples.html**: full ID/title/category tables for all six methods, with actual watches next to the predictions; browser-friendly for copying or printing.
- **compact_tables.md**: rank-by-method ID tables, shared title/category legend and short comments for a compact PDF layout.
- **side_by_side.md / side_by_side.csv**: each method's five predictions directly beside the user's actual five favourites.
- **short_comments.md / comments.json**: concise report prose and fuller per-method explanations.
- **validation_watches.csv**: every qualified validation programme (210 heavy, 5 light), not just the five targets. Raw partial overlaps and source records are retained separately.

## Choice of viewers

Within the fixed 4,030-user primary validation cohort, select the maximum and minimum nonzero original >=80%-qualified training-airing counts. Break ties by the ascending decimal user-ID string. The unique heavy maximum is 1,845 watches; eighteen light users tie at one watch. These reproduce the previously selected examples, without inspecting predictions or AP for selection. They illustrate boundary cases rather than a representative performance sample.

Training: weeks 11–20, [2020-03-09, 2020-05-18). Validation: weeks 21–30, [2020-05-18, 2020-07-27), Europe/Kyiv. These are cached out-of-sample predictions from the validation-trained version of final 007; all model histories stop before validation. The uploaded 007 uses the same recipe refitted on weeks 11–30 for the later test period.

Prediction titles/categories are representative pre-cutoff catalogue labels. A programme ID can cover changing episodes/titles, so a SpongeBob episode title in a recommendation need not equal the later episode title. The actual column uses the latest genuinely qualified validation airing's title/category. All frequency counts aggregate by programme ID. Only labelled, nonzero-ID airtime is evaluated.

## Hit legend

✓ = member of the user's true five-ID target set; ○ = qualifying validation watch outside that set; ~ = observed partial overlap only, no >=80% qualifying watch; — = no recorded programme overlap. A hit is membership anywhere in the true set, not equality with the actual programme on the same displayed row.

## Local example metrics

| Method | Heavy hits | Heavy AP@5 | Light hits | Light AP@5 |
|---|---|---|---|---|
| Popularity | 5/5 | 1.0000 | 3/5 | 0.5200 |
| CBF | 3/5 | 0.5200 | 0/5 | 0.0000 |
| Association rules | 4/5 | 0.7600 | 3/5 | 0.4833 |
| MF (8-week recency) | 4/5 | 0.8000 | 2/5 | 0.2333 |
| PPR (8-week recency) | 4/5 | 0.7600 | 3/5 | 0.5200 |
| Final 007 hybrid | 4/5 | 0.8000 | 3/5 | 0.4833 |

## Heavy viewer — 13866173795451203812

Maximum original >=80% training-airing count within the fixed primary validation cohort: 1,845 watches across 408 programmes. This is the unique maximum. The same earlier example is retained, independently of predictions or AP.

Training: 1,845 >=80% watches / 408 programmes; 2,607 >=50% watches / 609 programmes. Validation: 477 qualifying watches / 210 programmes.

### What the user actually watched: true Top-5

| Actual rank | Show ID | Latest watched title | Category | >=80% airings |
|---|---|---|---|---|
| 1 | 2400480 | ТСН. | Инфо | 35 |
| 2 | 240081 | Факты. День. | Инфо | 34 |
| 3 | 2400508 | Сегодня. | Инфо | 25 |
| 4 | 12001682 | М/с 'Губка Боб Квадратные Штаны', 192 с. 'Пикник для всей компании / Свистать всех наверх!'. | Детям | 22 |
| 5 | 20088 | 'Завтрак с 1+1'. Информационно-развлекательная программа. | Развлечения | 15 |

### All six methods, in prediction order

| Rank | Popularity | CBF | Association rules | MF (8-week recency) | PPR (8-week recency) | Final 007 hybrid |
|---|---|---|---|---|---|---|
| 1 | ✓ 2400480 — ТСН. Неделя. [Инфо] | ✓ 2400480 — ТСН. Неделя. [Инфо] | ✓ 2400480 — ТСН. Неделя. [Инфо] | ✓ 2400480 — ТСН. Неделя. [Инфо] | ✓ 2400480 — ТСН. Неделя. [Инфо] | ✓ 2400480 — ТСН. Неделя. [Инфо] |
| 2 | ✓ 240081 — Факты. День. [Инфо] | ✓ 240081 — Факты. День. [Инфо] | ✓ 240081 — Факты. День. [Инфо] | ✓ 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] | ✓ 240081 — Факты. День. [Инфо] | ✓ 240081 — Факты. День. [Инфо] |
| 3 | ✓ 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] | ○ 2400467 — 'Викна-Новости'. [Инфо] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] |
| 4 | ✓ 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ○ 5900347 — 'Деньги'. [Инфо] | ○ 2400467 — 'Викна-Новости'. [Инфо] | ✓ 240081 — Факты. День. [Инфо] | ○ 2400467 — 'Викна-Новости'. [Инфо] | ✓ 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] |
| 5 | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ○ 12002955 — М/с 'Свинка Пеппа', 58 с. [Детям] | ✓ 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ○ 2400467 — 'Викна-Новости'. [Инфо] |

### Short interpretation

Popularity recovers all five favourites (AP=1.00). CBF over-concentrates on news (3/5), while rules/PPR recover four favourites but omit SpongeBob. MF recovers the cartoon but promotes the historical Peppa preference, which falls to six validation watches. The hybrid combines the main news favourites with SpongeBob (4/5, AP=0.80). Its last-slot Vikna prediction is watched 15 times, exactly tied with the included Breakfast target; that single set miss depends on the documented numeric-ID tie-break. This is a useful boundary case where the cohort-best hybrid does not beat popularity.

### Per-method comments

- **Popularity:** 5/5 hits, AP@5=1.0000. All five global favourites are also this viewer's local true Top-5; their internal frequency order is irrelevant when every recommendation is relevant.
- **CBF:** 3/5 hits, AP@5=0.5200. The count-weighted content profile returns five news programmes, recovering TSN, Fakty and Segodnya but missing the cartoon and breakfast show. Dengi has only one qualifying validation watch; semantic similarity does not identify the user's frequency favourites precisely.
- **Association rules:** 4/5 hits, AP@5=0.7600. Weekly co-view links recover the news/breakfast cluster but allocate two slots to the programmes tied at 15 watches and omit SpongeBob, which has 22. The saved antecedent contributions show the matched rules supporting these scores.
- **MF (8-week recency):** 4/5 hits, AP@5=0.8000. MF retains the major news programmes and SpongeBob, but promotes Peppa Pig instead of Breakfast. Peppa had 93 strict training watches but only six qualifying validation watches, consistent with a historical favourite becoming less prominent.
- **PPR (8-week recency):** 4/5 hits, AP@5=0.7600. The personalized co-view graph returns the same news/breakfast IDs as rules here. It misses the 22-watch SpongeBob target while retaining Vikna, whose 15 watches tie the fifth-place threshold.
- **Final 007 hybrid:** 4/5 hits, AP@5=0.8000. MF/popularity support brings SpongeBob into the list, while PPR/rules agreement retains Vikna in the last slot. This replaces the MF-only Peppa recommendation. Its single set miss is sensitive to the fifth-place tie described below.

**Important interpretation:** Breakfast (ID 20088) and Vikna (ID 2400467) each have 15 qualifying validation watches. The frozen local numeric-ID tie-break includes Breakfast and excludes Vikna. Vikna is therefore a metric miss, despite equal observed frequency; it is not evidence that the viewer disliked or did not watch it. Peppa and Dengi were also watched, but fall outside the true Top-5.


## Light viewer — 1026253314001693311

Minimum nonzero original >=80% training-airing count within the fixed primary validation cohort: one watch of one programme. Eighteen users tie at one; ascending decimal user-ID string selects this user. At >=50% this viewer has 14 qualifying airings across five programmes, so the viewer is warm and has useful partial evidence.

Training: 1 >=80% watches / 1 programmes; 14 >=50% watches / 5 programmes. Validation: 8 qualifying watches / 5 programmes.

### What the user actually watched: true Top-5

| Actual rank | Show ID | Latest watched title | Category | >=80% airings |
|---|---|---|---|---|
| 1 | 2400508 | Сегодня. | Инфо | 3 |
| 2 | 2400480 | ТСН. | Инфо | 2 |
| 3 | 240081 | Факты. | Инфо | 1 |
| 4 | 400357 | 'Холостяк', 10 сезон, 13 эп. Пост-шоу, 1 ч. | Развлечения | 1 |
| 5 | 10002514 | Т/с 'Кухня', 1 сезон, 5-8 с. | Сериалы | 1 |

### All six methods, in prediction order

| Rank | Popularity | CBF | Association rules | MF (8-week recency) | PPR (8-week recency) | Final 007 hybrid |
|---|---|---|---|---|---|---|
| 1 | ✓ 2400480 — ТСН. Неделя. [Инфо] | — 200402 — Дом на зависть всем. [Развлечения] | ✓ 2400480 — ТСН. Неделя. [Инфо] | ~ 2400467 — 'Викна-Новости'. [Инфо] | ✓ 400357 — 'Холостяк', 10 сезон, 11 эп. [Развлечения] | ✓ 400357 — 'Холостяк', 10 сезон, 11 эп. [Развлечения] |
| 2 | ✓ 240081 — Факты. День. [Инфо] | ~ 400426 — 'Меняю жену'. [Развлечения] | ~ 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ✓ 400357 — 'Холостяк', 10 сезон, 11 эп. [Развлечения] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ~ 2400467 — 'Викна-Новости'. [Инфо] |
| 3 | — 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] | — 6600490 — 'Смотреть всем!'. [Развлечения] | ✓ 240081 — Факты. День. [Инфо] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ~ 2400467 — 'Викна-Новости'. [Инфо] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] |
| 4 | ~ 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ~ 400335 — 'Хата на тата', 6 сезон, 5 эп. [Развлечения] | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ~ 400361 — 'МастерШеф. Профессионалы', 2 сезон, 12 эп. [Познавательное] | — 200402 — Дом на зависть всем. [Развлечения] | ✓ 2400480 — ТСН. Неделя. [Инфо] |
| 5 | ✓ 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | — 500314 — 'Вечерний Ургант'. Настя Ивлеева, Максим Фадеев, Валерия и Иосиф Пригожин. [Развлечения] | ~ 200344 — 'ЧистоNews'. [Развлечения] | — 10003159 — Т/с 'Ничто не случается дважды', 8 с. [Сериалы] | ✓ 2400480 — ТСН. Неделя. [Инфо] | ~ 400361 — 'МастерШеф. Профессионалы', 2 сезон, 12 эп. [Познавательное] |

### Short interpretation

With only one strict training watch, CBF stays in entertainment and gets no Top-5 hit. Popularity and rules recover three news targets. The softer collaborative history retains nine partial Bachelor watches, helping MF (2/5) and PPR (3/5); PPR and popularity have equal AP=0.52 but different hit sets. The final hybrid gets Bachelor, Segodnya and TSN (3/5, AP=0.4833), yet reinforces the shared partial-only Vikna error and retains an MF-only MasterChef candidate instead of the true Fakty target. Kitchen is missed by every method. This illustrates sparse qualifying history and the limits of fusion, not a universal preference for popularity.

### Per-method comments

- **Popularity:** 3/5 hits, AP@5=0.5200. Global news favourites recover Segodnya, TSN and Fakty even with little strict personal history. SpongeBob has no observed validation overlap; Breakfast has only partial overlap and no qualifying watch.
- **CBF:** 0/5 hits, AP@5=0.0000. Its strict-count profile is anchored entirely to Dom na zavist vsem, so all five outputs are entertainment. None enters the qualifying validation Top-5; Menyayu zhenu and Khata na tata do have partial overlaps, so these are not claims of no viewing or dislike.
- **Association rules:** 3/5 hits, AP@5=0.4833. Rules transfer from the one strict antecedent to three correct news targets. For example, Dom na zavist vsem -> TSN has training weekly-basket confidence 0.673. Breakfast and ChistoNews still receive slots without qualifying validation watches.
- **MF (8-week recency):** 2/5 hits, AP@5=0.2333. Softer training preserves nine 50%-qualified Bachelor airings, and MF correctly recommends The Bachelor and Segodnya. It ranks Vikna first even though validation has only partial overlaps, and its MasterChef/series candidates do not become true Top-5 programmes.
- **PPR (8-week recency):** 3/5 hits, AP@5=0.5200. The Bachelor receives 44.2% of the training restart mass and is correctly ranked first; Segodnya and TSN also hit. Vikna and the old strict favourite Dom na zavist vsem consume two slots without a qualifying validation watch. This hit set differs from popularity despite identical AP.
- **Final 007 hybrid:** 3/5 hits, AP@5=0.4833. It combines Bachelor, Segodnya and TSN, but MF/PPR agreement reinforces the partial-only Vikna prediction. The MF-only MasterChef rank-four vote contributes 0.125, exceeding Fakty's combined rules/popularity contribution 0.09375, so the true Fakty target is missed.

**Important interpretation:** MasterChef ties Dom na zavist vsem at RRF utility 0.125; the fixed training-popularity tie-break selects MasterChef. Light is defined by strict qualifying counts, not total logged activity: this user has many short overlaps. The example demonstrates threshold sensitivity and sparse-history uncertainty rather than proving that global popularity is always preferable.

## Method versions and reproducibility

See method_definitions.csv for exact prediction paths and thresholds. MF/PPR are the final hybrid's eight-week-recency validation components. CBF uses strict-80% history and frozen pre-cutoff title/metadata TF-IDF; weekly rules use strict history; popularity uses unweighted 50%-qualified counts. The same two viewers are used for all six methods.

**71 independent checks passed**, including an independent standard-library raw-log/schedule interval rejoin for both viewers: 41,234 raw view rows and 7,635 positive train/validation user-airing overlaps. Counts, truth, boundary ties, all sixty predictions/hits/AP values, labels and source contributions were checked. This is assistant-executed verification; student personal review remains pending.

```bash
python3 scripts/build_final_examples.py
python3 scripts/verify_final_examples.py
python3 scripts/render_final_examples.py
```

Evidence: frozen_inputs.json, selection.json, selected_users.csv, training_profiles.csv, validation_qualified_airings.csv, validation_programme_overlaps.csv, raw_selected_views.csv, independent_raw_airing_matches.csv, cbf_feature_contributions.csv, association_rule_contributions.csv, hybrid_score_contributions.csv and verification.json. No fitting or further model experiment is performed by these scripts.
