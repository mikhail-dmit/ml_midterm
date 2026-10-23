# Compact report tables

Within the fixed 4,030-user primary validation cohort, select the maximum and minimum nonzero original >=80%-qualified training-airing counts. Break ties by the ascending decimal user-ID string. The unique heavy maximum is 1,845 watches; eighteen light users tie at one watch. These reproduce the previously selected examples, without inspecting predictions or AP for selection. They illustrate boundary cases rather than a representative performance sample.

Training: weeks 11–20, [2020-03-09, 2020-05-18). Validation: weeks 21–30, [2020-05-18, 2020-07-27), Europe/Kyiv. These are cached out-of-sample predictions from the validation-trained version of final 007; all model histories stop before validation. The uploaded 007 uses the same recipe refitted on weeks 11–30 for the later test period.

Use the shared programme legend below for each ID's full title/category. Hit marks are based on ID membership in the entire true Top-5.

✓ = member of the user's true five-ID target set; ○ = qualifying validation watch outside that set; ~ = observed partial overlap only, no >=80% qualifying watch; — = no recorded programme overlap. A hit is membership anywhere in the true set, not equality with the actual programme on the same displayed row.

## Heavy viewer — 13866173795451203812

Training: 1,845 >=80% watches / 408 programmes; 2,607 >=50% watches / 609 programmes. Validation: 477 qualifying watches / 210 programmes.

**Actual Top-5:** 2400480 × 35; 240081 × 34; 2400508 × 25; 12001682 × 22; 20088 × 15.

| Prediction rank | Popularity | CBF | Association rules | MF (8-week recency) | PPR (8-week recency) | Final 007 hybrid |
|---|---|---|---|---|---|---|
| 1 | ✓ 2400480 | ✓ 2400480 | ✓ 2400480 | ✓ 2400480 | ✓ 2400480 | ✓ 2400480 |
| 2 | ✓ 240081 | ✓ 240081 | ✓ 240081 | ✓ 12001682 | ✓ 240081 | ✓ 240081 |
| 3 | ✓ 12001682 | ○ 2400467 | ✓ 2400508 | ✓ 2400508 | ✓ 2400508 | ✓ 2400508 |
| 4 | ✓ 20088 | ○ 5900347 | ○ 2400467 | ✓ 240081 | ○ 2400467 | ✓ 12001682 |
| 5 | ✓ 2400508 | ✓ 2400508 | ✓ 20088 | ○ 12002955 | ✓ 20088 | ○ 2400467 |

**AP@5:** Popularity 1.0000; CBF 0.5200; Association rules 0.7600; MF (8-week recency) 0.8000; PPR (8-week recency) 0.7600; Final 007 hybrid 0.8000.

Popularity recovers all five favourites (AP=1.00). CBF over-concentrates on news (3/5), while rules/PPR recover four favourites but omit SpongeBob. MF recovers the cartoon but promotes the historical Peppa preference, which falls to six validation watches. The hybrid combines the main news favourites with SpongeBob (4/5, AP=0.80). Its last-slot Vikna prediction is watched 15 times, exactly tied with the included Breakfast target; that single set miss depends on the documented numeric-ID tie-break. This is a useful boundary case where the cohort-best hybrid does not beat popularity.

**Qualification:** Breakfast (ID 20088) and Vikna (ID 2400467) each have 15 qualifying validation watches. The frozen local numeric-ID tie-break includes Breakfast and excludes Vikna. Vikna is therefore a metric miss, despite equal observed frequency; it is not evidence that the viewer disliked or did not watch it. Peppa and Dengi were also watched, but fall outside the true Top-5.

## Light viewer — 1026253314001693311

Training: 1 >=80% watches / 1 programmes; 14 >=50% watches / 5 programmes. Validation: 8 qualifying watches / 5 programmes.

**Actual Top-5:** 2400508 × 3; 2400480 × 2; 240081 × 1; 400357 × 1; 10002514 × 1.

| Prediction rank | Popularity | CBF | Association rules | MF (8-week recency) | PPR (8-week recency) | Final 007 hybrid |
|---|---|---|---|---|---|---|
| 1 | ✓ 2400480 | — 200402 | ✓ 2400480 | ~ 2400467 | ✓ 400357 | ✓ 400357 |
| 2 | ✓ 240081 | ~ 400426 | ~ 20088 | ✓ 400357 | ✓ 2400508 | ~ 2400467 |
| 3 | — 12001682 | — 6600490 | ✓ 240081 | ✓ 2400508 | ~ 2400467 | ✓ 2400508 |
| 4 | ~ 20088 | ~ 400335 | ✓ 2400508 | ~ 400361 | — 200402 | ✓ 2400480 |
| 5 | ✓ 2400508 | — 500314 | ~ 200344 | — 10003159 | ✓ 2400480 | ~ 400361 |

**AP@5:** Popularity 0.5200; CBF 0.0000; Association rules 0.4833; MF (8-week recency) 0.2333; PPR (8-week recency) 0.5200; Final 007 hybrid 0.4833.

With only one strict training watch, CBF stays in entertainment and gets no Top-5 hit. Popularity and rules recover three news targets. The softer collaborative history retains nine partial Bachelor watches, helping MF (2/5) and PPR (3/5); PPR and popularity have equal AP=0.52 but different hit sets. The final hybrid gets Bachelor, Segodnya and TSN (3/5, AP=0.4833), yet reinforces the shared partial-only Vikna error and retains an MF-only MasterChef candidate instead of the true Fakty target. Kitchen is missed by every method. This illustrates sparse qualifying history and the limits of fusion, not a universal preference for popularity.

**Qualification:** MasterChef ties Dom na zavist vsem at RRF utility 0.125; the fixed training-popularity tie-break selects MasterChef. Light is defined by strict qualifying counts, not total logged activity: this user has many short overlaps. The example demonstrates threshold sensitivity and sparse-history uncertainty rather than proving that global popularity is always preferable.

## Shared programme legend

Representative pre-cutoff labels, keyed by programme ID; episode titles can vary in validation.

| Show ID | Title | Category |
|---|---|---|
| 20088 | 'Завтрак с 1+1'. Информационно-развлекательная программа. | Развлечения |
| 200344 | 'ЧистоNews'. | Развлечения |
| 200402 | Дом на зависть всем. | Развлечения |
| 240081 | Факты. День. | Инфо |
| 400335 | 'Хата на тата', 6 сезон, 5 эп. | Развлечения |
| 400357 | 'Холостяк', 10 сезон, 11 эп. | Развлечения |
| 400361 | 'МастерШеф. Профессионалы', 2 сезон, 12 эп. | Познавательное |
| 400426 | 'Меняю жену'. | Развлечения |
| 500314 | 'Вечерний Ургант'. Настя Ивлеева, Максим Фадеев, Валерия и Иосиф Пригожин. | Развлечения |
| 2400467 | 'Викна-Новости'. | Инфо |
| 2400480 | ТСН. Неделя. | Инфо |
| 2400508 | Сегодня. Итоги с Олегом Панютой. | Инфо |
| 5900347 | 'Деньги'. | Инфо |
| 6600490 | 'Смотреть всем!'. | Развлечения |
| 10002514 | Т/с 'Кухня'. | Сериалы |
| 10003159 | Т/с 'Ничто не случается дважды', 8 с. | Сериалы |
| 12001682 | М/с 'Губка Боб Квадратные Штаны', 92 с. 'Губка Боб Атлантические Штаны'. | Детям |
| 12002955 | М/с 'Свинка Пеппа', 58 с. | Детям |

All complete actual-watch frequencies and latest watched episode labels are in validation_watches.csv. The heavy user's fifth-place tie is described above; it is retained, not silently resolved in the model's favour.
