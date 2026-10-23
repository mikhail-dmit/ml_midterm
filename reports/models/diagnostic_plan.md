# Diagnostic experiments — specified after the initial six runs

## What the initial results actually show

- Popularity MAP@5 is 0.27939123 (all primary) / 0.30530725 (template subset).
- Binary-target implicit ALS f=16, confidence scale=1, regularization=1 reaches
  0.27097767 overall at epoch 15. Its Precision@5 is slightly higher than
  popularity (0.36203474 vs 0.35766749), while MAP is lower: list ordering matters.
- Raising confidence scale to 10 lowers best overall MAP to 0.22296278. Increasing
  factors to 32 at that confidence further lowers it to 0.21019603. Training
  objectives decrease monotonically, so this is not evidence of a broken solver.
- At confidence 1, positive-pair score median is 0.2902; at confidence 10 it is
  0.6247. All observed positives still target the same value 1. More confidence
  does not directly ask for frequent programmes to rank above occasional ones.
- The heavy user's true favourite programmes have 83–164 training watches, but
  binary MF's selected list instead includes programmes with 3–13 training
  watches. Four of those are watched in validation at least once, yet none are
  in that user's true frequency Top-5. This is a concrete target/ranking mismatch.
- PPR with raw distinct-user co-view edges and log-count restart reaches overall
  MAP 0.35775352 at alpha=.50, 0.33516543 at .85, and 0.29378329 at .95.
- As alpha rises .50 -> .95, mean stationary mass on own history falls
  0.5706 -> 0.1737, mean Top-5 overlap with popularity rises 2.3248 -> 3.1806,
  and unique recommended programmes fall 535 -> 121. Weighted graph degree and
  training popularity have Spearman correlation 0.9699. Long diffusion washes
  out user-specific restart and promotes hubs in this measured graph.

## Three controlled follow-ups

1. **MF log-count target:** keep the best initial f=16 / confidence=1 / reg=1
   setup, but replace the binary target with log(1+qualified airing count).
   Confidence remains 1+log(1+count). This is still implicit-feedback matrix
   factorization over counts, allowed by the exam, but it is a documented variant
   of the original Hu–Koren–Volinsky binary preference objective. Hypothesis:
   explicitly preserving frequency magnitude repairs the heavy-user ranking
   mismatch. It is not a new heuristic or a star-rating model.
2. **PPR count restart:** keep the raw graph and alpha=.50, changing only restart
   weighting from log(1+count) to count. Hypothesis: log compression discards useful
   relative-frequency information when the target is the five most frequent
   programmes. Count weighting could improve recurrent-favourite ranking.
3. **Cosine-normalized co-view graph:** keep alpha=.50 and log-count restart,
   changing only A_ij from distinct co-view user count to
   n_ij/sqrt(n_i*n_j). Hypothesis: reduced hub dominance changes relevance and
   catalogue breadth. This can hurt if broad popularity is genuinely predictive;
   normalization is not assumed to be an automatic improvement.

Selection remains highest MAP@5 on all 4,030 primary users, with earliest best
checkpoint within MF. The 1,150 template users are reporting only. No additional
settings are planned merely to chase small metric changes on this same hold-out.
