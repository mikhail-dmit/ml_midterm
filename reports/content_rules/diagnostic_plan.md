# Diagnostic follow-ups after the first six CBF/rule experiments

The MF target-alignment diagnosis remains preserved in
`reports/models/diagnostic_plan.md` and `reports/models/README.md`; it is intended
for the later exam report, not replaced by this document.

## Initial measured evidence

- Popularity MAP@5 is 0.27939123 overall / 0.30530725 on the template subset;
  selected MF and PPR are 0.35298677 / 0.35775352 overall.
- Category/genre CBF gets 0.08695203 overall. There are only 518 distinct vectors
  for 5,842 metadata programmes; 5,609 items belong to nonunique vector groups,
  the largest containing 460 IDs. Roughly 32 available candidates tie at each
  warm user's fifth-place score on average. Numeric-ID tie-breaking cannot
  resolve preference between content-identical programmes.
- Rich TF-IDF CBF has 5,766 distinct vectors and only 138 items in nonunique
  groups, but still gets MAP 0.08551282. Its Precision@5 rises to 0.14014888,
  above genre-only 0.11379653, without an MAP gain. Removing exact ties alone
  therefore does not solve the relevance/order problem.
- The heavy viewer's genre profile recommends films they mostly did not watch,
  rather than their frequent news/cartoon favourites. Log-count averaging gives
  many occasional film IDs considerable combined mass relative to a few repeat
  favourites. The broad centroid reflects aggregate content, not item frequency.
- Confidence-weighted user-history rules get 0.25769148 overall; stronger
  minimum joint support (5 -> 20) gets 0.25549711. Both are below popularity.
  Recommendations are concentrated on 24 IDs, with popularity Top-5 overlap 3.10
  for the support-5 run: many different antecedents point to the same common news.
- Changing only rule aggregation weights from confidence to lift collapses MAP
  to 0.03793879, reducing mean recommendation training-popularity from about
  18,989 to 1,459. The highest-lift rule has antecedent count 6, consequent count
  11, joint count 5, N=4,737: support=5/4737, confidence=5/6,
  lift=(5/6)/(11/4737)=358.86. It can trigger in only six observed user baskets.
  Large enrichment is not the same as broad reach or future favourite likelihood.

## Controlled changes (specified before running them)

1. **Rich CBF count profile:** keep the rich TF-IDF item vectors and family
   weights, changing only user-history weighting from log1p(count) to count.
   Hypothesis: preserve relative repeat frequency instead of letting many
   one-off items dominate an averaged profile.
2. **Title-feature CBF:** from that count-profile setting, add a title-word TF-IDF
   block (weight 1). Titles are supplied schedule metadata, frozen before the
   cutoff. Numeric episode/season labels and boilerplate are stripped; no item-ID
   feature is added. Hypothesis: title content distinguishes specific recurring
   programmes that share generic category/genre/cast attributes.
3. **Count-weighted association antecedents:** keep the support-5/confidence/lift>1
   user-history rules, changing only antecedent query weights to raw counts.
   Hypothesis: stronger recurring triggers improve favourite prediction. This
   does not add self-rules or blend in a personal-frequency heuristic.
4. **Weekly baskets:** retain confidence scoring, log history weights and the
   support-count floor, but mine from each nonempty user/ISO-week basket rather
   than one whole-history basket. Hypothesis: temporally local co-view signal is
   more informative than mixing ten weeks of heterogeneous viewing. Support now
   means user-week baskets, not independent users; distinct joint-user counts
   are separately reported so repeated weeks cannot masquerade as broad reach.

The same 4,030 users select configurations; the 1,150-user cohort is reporting
only. No more settings are planned solely to make a weak method beat the baseline.
