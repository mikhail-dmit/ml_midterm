# Predictions directly beside actual validation favourites

Training: weeks 11–20, [2020-03-09, 2020-05-18). Validation: weeks 21–30, [2020-05-18, 2020-07-27), Europe/Kyiv. These are cached out-of-sample predictions from the validation-trained version of final 007; all model histories stop before validation. The uploaded 007 uses the same recipe refitted on weeks 11–30 for the later test period.

Prediction titles/categories are representative pre-cutoff catalogue labels. A programme ID can cover changing episodes/titles, so a SpongeBob episode title in a recommendation need not equal the later episode title. The actual column uses the latest genuinely qualified validation airing's title/category. All frequency counts aggregate by programme ID. Only labelled, nonzero-ID airtime is evaluated.

✓ = member of the user's true five-ID target set; ○ = qualifying validation watch outside that set; ~ = observed partial overlap only, no >=80% qualifying watch; — = no recorded programme overlap. A hit is membership anywhere in the true set, not equality with the actual programme on the same displayed row.

## Heavy viewer — 13866173795451203812

Training: 1,845 >=80% watches / 408 programmes; 2,607 >=50% watches / 609 programmes. Validation: 477 qualifying watches / 210 programmes.

### Popularity — AP@5=1.0000

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 35 | 2400480 — ТСН. [Инфо] | 35 |
| 2 | 240081 — Факты. День. [Инфо] | ✓ | 34 | 240081 — Факты. День. [Инфо] | 34 |
| 3 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] | ✓ | 22 | 2400508 — Сегодня. [Инфо] | 25 |
| 4 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ✓ | 15 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 192 с. 'Пикник для всей компании / Свистать всех наверх!'. [Детям] | 22 |
| 5 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 25 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | 15 |

5/5 hits, AP@5=1.0000. All five global favourites are also this viewer's local true Top-5; their internal frequency order is irrelevant when every recommendation is relevant.

### CBF — AP@5=0.5200

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 35 | 2400480 — ТСН. [Инфо] | 35 |
| 2 | 240081 — Факты. День. [Инфо] | ✓ | 34 | 240081 — Факты. День. [Инфо] | 34 |
| 3 | 2400467 — 'Викна-Новости'. [Инфо] | ○ | 15 | 2400508 — Сегодня. [Инфо] | 25 |
| 4 | 5900347 — 'Деньги'. [Инфо] | ○ | 1 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 192 с. 'Пикник для всей компании / Свистать всех наверх!'. [Детям] | 22 |
| 5 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 25 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | 15 |

3/5 hits, AP@5=0.5200. The count-weighted content profile returns five news programmes, recovering TSN, Fakty and Segodnya but missing the cartoon and breakfast show. Dengi has only one qualifying validation watch; semantic similarity does not identify the user's frequency favourites precisely.

### Association rules — AP@5=0.7600

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 35 | 2400480 — ТСН. [Инфо] | 35 |
| 2 | 240081 — Факты. День. [Инфо] | ✓ | 34 | 240081 — Факты. День. [Инфо] | 34 |
| 3 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 25 | 2400508 — Сегодня. [Инфо] | 25 |
| 4 | 2400467 — 'Викна-Новости'. [Инфо] | ○ | 15 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 192 с. 'Пикник для всей компании / Свистать всех наверх!'. [Детям] | 22 |
| 5 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ✓ | 15 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | 15 |

4/5 hits, AP@5=0.7600. Weekly co-view links recover the news/breakfast cluster but allocate two slots to the programmes tied at 15 watches and omit SpongeBob, which has 22. The saved antecedent contributions show the matched rules supporting these scores.

### MF (8-week recency) — AP@5=0.8000

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 35 | 2400480 — ТСН. [Инфо] | 35 |
| 2 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] | ✓ | 22 | 240081 — Факты. День. [Инфо] | 34 |
| 3 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 25 | 2400508 — Сегодня. [Инфо] | 25 |
| 4 | 240081 — Факты. День. [Инфо] | ✓ | 34 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 192 с. 'Пикник для всей компании / Свистать всех наверх!'. [Детям] | 22 |
| 5 | 12002955 — М/с 'Свинка Пеппа', 58 с. [Детям] | ○ | 6 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | 15 |

4/5 hits, AP@5=0.8000. MF retains the major news programmes and SpongeBob, but promotes Peppa Pig instead of Breakfast. Peppa had 93 strict training watches but only six qualifying validation watches, consistent with a historical favourite becoming less prominent.

### PPR (8-week recency) — AP@5=0.7600

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 35 | 2400480 — ТСН. [Инфо] | 35 |
| 2 | 240081 — Факты. День. [Инфо] | ✓ | 34 | 240081 — Факты. День. [Инфо] | 34 |
| 3 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 25 | 2400508 — Сегодня. [Инфо] | 25 |
| 4 | 2400467 — 'Викна-Новости'. [Инфо] | ○ | 15 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 192 с. 'Пикник для всей компании / Свистать всех наверх!'. [Детям] | 22 |
| 5 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ✓ | 15 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | 15 |

4/5 hits, AP@5=0.7600. The personalized co-view graph returns the same news/breakfast IDs as rules here. It misses the 22-watch SpongeBob target while retaining Vikna, whose 15 watches tie the fifth-place threshold.

### Final 007 hybrid — AP@5=0.8000

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 35 | 2400480 — ТСН. [Инфо] | 35 |
| 2 | 240081 — Факты. День. [Инфо] | ✓ | 34 | 240081 — Факты. День. [Инфо] | 34 |
| 3 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 25 | 2400508 — Сегодня. [Инфо] | 25 |
| 4 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] | ✓ | 22 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 192 с. 'Пикник для всей компании / Свистать всех наверх!'. [Детям] | 22 |
| 5 | 2400467 — 'Викна-Новости'. [Инфо] | ○ | 15 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | 15 |

4/5 hits, AP@5=0.8000. MF/popularity support brings SpongeBob into the list, while PPR/rules agreement retains Vikna in the last slot. This replaces the MF-only Peppa recommendation. Its single set miss is sensitive to the fifth-place tie described below.

## Light viewer — 1026253314001693311

Training: 1 >=80% watches / 1 programmes; 14 >=50% watches / 5 programmes. Validation: 8 qualifying watches / 5 programmes.

### Popularity — AP@5=0.5200

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 2 | 2400508 — Сегодня. [Инфо] | 3 |
| 2 | 240081 — Факты. День. [Инфо] | ✓ | 1 | 2400480 — ТСН. [Инфо] | 2 |
| 3 | 12001682 — М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. [Детям] | — | 0 | 240081 — Факты. [Инфо] | 1 |
| 4 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ~ | 0 | 400357 — 'Холостяк', 10 сезон, 13 эп. Пост-шоу, 1 ч. [Развлечения] | 1 |
| 5 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 3 | 10002514 — Т/с 'Кухня', 1 сезон, 5-8 с. [Сериалы] | 1 |

3/5 hits, AP@5=0.5200. Global news favourites recover Segodnya, TSN and Fakty even with little strict personal history. SpongeBob has no observed validation overlap; Breakfast has only partial overlap and no qualifying watch.

### CBF — AP@5=0.0000

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 200402 — Дом на зависть всем. [Развлечения] | — | 0 | 2400508 — Сегодня. [Инфо] | 3 |
| 2 | 400426 — 'Меняю жену'. [Развлечения] | ~ | 0 | 2400480 — ТСН. [Инфо] | 2 |
| 3 | 6600490 — 'Смотреть всем!'. [Развлечения] | — | 0 | 240081 — Факты. [Инфо] | 1 |
| 4 | 400335 — 'Хата на тата', 6 сезон, 5 эп. [Развлечения] | ~ | 0 | 400357 — 'Холостяк', 10 сезон, 13 эп. Пост-шоу, 1 ч. [Развлечения] | 1 |
| 5 | 500314 — 'Вечерний Ургант'. Настя Ивлеева, Максим Фадеев, Валерия и Иосиф Пригожин. [Развлечения] | — | 0 | 10002514 — Т/с 'Кухня', 1 сезон, 5-8 с. [Сериалы] | 1 |

0/5 hits, AP@5=0.0000. Its strict-count profile is anchored entirely to Dom na zavist vsem, so all five outputs are entertainment. None enters the qualifying validation Top-5; Menyayu zhenu and Khata na tata do have partial overlaps, so these are not claims of no viewing or dislike.

### Association rules — AP@5=0.4833

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 2 | 2400508 — Сегодня. [Инфо] | 3 |
| 2 | 20088 — 'Завтрак с 1+1'. Информационно-развлекательная программа. [Развлечения] | ~ | 0 | 2400480 — ТСН. [Инфо] | 2 |
| 3 | 240081 — Факты. День. [Инфо] | ✓ | 1 | 240081 — Факты. [Инфо] | 1 |
| 4 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 3 | 400357 — 'Холостяк', 10 сезон, 13 эп. Пост-шоу, 1 ч. [Развлечения] | 1 |
| 5 | 200344 — 'ЧистоNews'. [Развлечения] | ~ | 0 | 10002514 — Т/с 'Кухня', 1 сезон, 5-8 с. [Сериалы] | 1 |

3/5 hits, AP@5=0.4833. Rules transfer from the one strict antecedent to three correct news targets. For example, Dom na zavist vsem -> TSN has training weekly-basket confidence 0.673. Breakfast and ChistoNews still receive slots without qualifying validation watches.

### MF (8-week recency) — AP@5=0.2333

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 2400467 — 'Викна-Новости'. [Инфо] | ~ | 0 | 2400508 — Сегодня. [Инфо] | 3 |
| 2 | 400357 — 'Холостяк', 10 сезон, 11 эп. [Развлечения] | ✓ | 1 | 2400480 — ТСН. [Инфо] | 2 |
| 3 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 3 | 240081 — Факты. [Инфо] | 1 |
| 4 | 400361 — 'МастерШеф. Профессионалы', 2 сезон, 12 эп. [Познавательное] | ~ | 0 | 400357 — 'Холостяк', 10 сезон, 13 эп. Пост-шоу, 1 ч. [Развлечения] | 1 |
| 5 | 10003159 — Т/с 'Ничто не случается дважды', 8 с. [Сериалы] | — | 0 | 10002514 — Т/с 'Кухня', 1 сезон, 5-8 с. [Сериалы] | 1 |

2/5 hits, AP@5=0.2333. Softer training preserves nine 50%-qualified Bachelor airings, and MF correctly recommends The Bachelor and Segodnya. It ranks Vikna first even though validation has only partial overlaps, and its MasterChef/series candidates do not become true Top-5 programmes.

### PPR (8-week recency) — AP@5=0.5200

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 400357 — 'Холостяк', 10 сезон, 11 эп. [Развлечения] | ✓ | 1 | 2400508 — Сегодня. [Инфо] | 3 |
| 2 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 3 | 2400480 — ТСН. [Инфо] | 2 |
| 3 | 2400467 — 'Викна-Новости'. [Инфо] | ~ | 0 | 240081 — Факты. [Инфо] | 1 |
| 4 | 200402 — Дом на зависть всем. [Развлечения] | — | 0 | 400357 — 'Холостяк', 10 сезон, 13 эп. Пост-шоу, 1 ч. [Развлечения] | 1 |
| 5 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 2 | 10002514 — Т/с 'Кухня', 1 сезон, 5-8 с. [Сериалы] | 1 |

3/5 hits, AP@5=0.5200. The Bachelor receives 44.2% of the training restart mass and is correctly ranked first; Segodnya and TSN also hit. Vikna and the old strict favourite Dom na zavist vsem consume two slots without a qualifying validation watch. This hit set differs from popularity despite identical AP.

### Final 007 hybrid — AP@5=0.4833

| Pred. rank | Prediction: ID — title [category] | Hit | Predicted ID's val. watches | Actual favourite at frequency rank r: ID — title [category] | Actual watches |
|---|---|---|---|---|---|
| 1 | 400357 — 'Холостяк', 10 сезон, 11 эп. [Развлечения] | ✓ | 1 | 2400508 — Сегодня. [Инфо] | 3 |
| 2 | 2400467 — 'Викна-Новости'. [Инфо] | ~ | 0 | 2400480 — ТСН. [Инфо] | 2 |
| 3 | 2400508 — Сегодня. Итоги с Олегом Панютой. [Инфо] | ✓ | 3 | 240081 — Факты. [Инфо] | 1 |
| 4 | 2400480 — ТСН. Неделя. [Инфо] | ✓ | 2 | 400357 — 'Холостяк', 10 сезон, 13 эп. Пост-шоу, 1 ч. [Развлечения] | 1 |
| 5 | 400361 — 'МастерШеф. Профессионалы', 2 сезон, 12 эп. [Познавательное] | ~ | 0 | 10002514 — Т/с 'Кухня', 1 сезон, 5-8 с. [Сериалы] | 1 |

3/5 hits, AP@5=0.4833. It combines Bachelor, Segodnya and TSN, but MF/PPR agreement reinforces the partial-only Vikna prediction. The MF-only MasterChef rank-four vote contributes 0.125, exceeding Fakty's combined rules/popularity contribution 0.09375, so the true Fakty target is missed.
