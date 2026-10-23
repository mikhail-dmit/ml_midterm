# Short comments for the report

Within the fixed 4,030-user primary validation cohort, select the maximum and minimum nonzero original >=80%-qualified training-airing counts. Break ties by the ascending decimal user-ID string. The unique heavy maximum is 1,845 watches; eighteen light users tie at one watch. These reproduce the previously selected examples, without inspecting predictions or AP for selection. They illustrate boundary cases rather than a representative performance sample.

MF/PPR below are the final hybrid's eight-week-recency components, not the earlier undecayed reference runs. CBF uses the selected strict-history title/metadata TF-IDF profile; rules remain strict weekly rules; popularity remains unweighted 50%-history popularity. All use the same train/validation dates and fixed truth.

## Heavy viewer — 13866173795451203812

Maximum original >=80% training-airing count within the fixed primary validation cohort: 1,845 watches across 408 programmes. This is the unique maximum. The same earlier example is retained, independently of predictions or AP.

Popularity recovers all five favourites (AP=1.00). CBF over-concentrates on news (3/5), while rules/PPR recover four favourites but omit SpongeBob. MF recovers the cartoon but promotes the historical Peppa preference, which falls to six validation watches. The hybrid combines the main news favourites with SpongeBob (4/5, AP=0.80). Its last-slot Vikna prediction is watched 15 times, exactly tied with the included Breakfast target; that single set miss depends on the documented numeric-ID tie-break. This is a useful boundary case where the cohort-best hybrid does not beat popularity.

**Interpretation limit:** Breakfast (ID 20088) and Vikna (ID 2400467) each have 15 qualifying validation watches. The frozen local numeric-ID tie-break includes Breakfast and excludes Vikna. Vikna is therefore a metric miss, despite equal observed frequency; it is not evidence that the viewer disliked or did not watch it. Peppa and Dengi were also watched, but fall outside the true Top-5.

## Light viewer — 1026253314001693311

Minimum nonzero original >=80% training-airing count within the fixed primary validation cohort: one watch of one programme. Eighteen users tie at one; ascending decimal user-ID string selects this user. At >=50% this viewer has 14 qualifying airings across five programmes, so the viewer is warm and has useful partial evidence.

With only one strict training watch, CBF stays in entertainment and gets no Top-5 hit. Popularity and rules recover three news targets. The softer collaborative history retains nine partial Bachelor watches, helping MF (2/5) and PPR (3/5); PPR and popularity have equal AP=0.52 but different hit sets. The final hybrid gets Bachelor, Segodnya and TSN (3/5, AP=0.4833), yet reinforces the shared partial-only Vikna error and retains an MF-only MasterChef candidate instead of the true Fakty target. Kitchen is missed by every method. This illustrates sparse qualifying history and the limits of fusion, not a universal preference for popularity.

**Interpretation limit:** MasterChef ties Dom na zavist vsem at RRF utility 0.125; the fixed training-popularity tie-break selects MasterChef. Light is defined by strict qualifying counts, not total logged activity: this user has many short overlaps. The example demonstrates threshold sensitivity and sparse-history uncertainty rather than proving that global popularity is always preferable.

## Overall conclusion for these examples

The final hybrid is selected for cohort performance and the designated Kaggle result, yet it does not beat popularity on these two retained training-selected examples. The cases show recurring-favourite recovery, the value of partial history, metric boundary ties, and shared-error reinforcement in fusion. They are explanations, not a two-user evaluation of general superiority.
