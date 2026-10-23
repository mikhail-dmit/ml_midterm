# Four informative follow-up submissions

Anchor: **submission_001**, RRF MF/PPR/rules, returned **public 0.43347** and
**private 0.41452**. Both were supplied by the user and match the inspected local
screenshot, `Score for sub1.png`. The exact CSV/hash and evidence are recorded in
`results.json` and `results.csv`.

**Progress:** 002 returned **public 0.43359 / private 0.41489**, confirmed by the
user and `Score for sub2.png`: +0.00012 public and +0.00037 private versus 001.
This pair agrees with the template-subset ordering and reverses the primary
ordering; its small difference does not establish a generally better validation
cohort. The user reports an allowance of **up to 100 submissions**. The original
comparison sequence is retained, with room for focused follow-ups later.

003 returned **public 0.43042 / private 0.41260**, confirmed by the user and
`Score for sub3.png`. Its disadvantage to both RRF variants matches both local
cohorts. 004 then returned **public 0.42643 / private 0.40943**, matching both
local cohorts' prediction that standalone MF trails the hybrids. The observed
ordering is now **002 > 001 > 003 > 004** on public and private scores. 002 remains
best, exceeding MF alone by +0.00716 public and +0.00546 private. 005 then returned
**public 0.43163 / private 0.41039**. Rules improve the direct 001-versus-005
comparison by +0.00184 public and +0.00413 private. Public ordering is now
**002 > 001 > 005 > 003 > 004**; private ordering swaps **003 and 005**. All five
planned uploads are recorded; 002 remains best on both scores.

| Upload | Strategy | Local MAP: all | Local MAP: template | What we learn |
|---|---|---:|---:|---|
| 002 — scored | RRF MF .5 / PPR .5 / rules .125 / popularity .125; offset 0 | 0.372842 | 0.407925 | Small observed improvement over 001 on both returned scores. |
| 003 — scored | PPR Top-20 candidates, reranked by MF | 0.368885 | 0.400557 | Below both RRF variants on both returned scores, matching validation. |
| 004 — scored | Standalone MF, 50% training qualification | 0.365925 | 0.397470 | Lowest on both returned scores; the tested fusion and PPR-candidate strategies outperform the same standalone MF. |
| 005 — scored | RRF MF .5 / PPR .5, offset 0; no rules | 0.370615 | 0.405823 | Below 001 on both scores: rules help in this exact ablation. Its ordering versus 003 differs between public/private. |

Use identical weeks 11–30 model fits, eligible candidates, template users/order,
tie-break and cold fallback for all four. Reuse the existing fitted components;
changing the ranking strategy should be the comparison, not new random fits or
different interaction definitions. All settings have already been evaluated
locally. These tests balance plausible improvements with interpretable evidence.

**Local ordering hypotheses:**

- Primary cohort: **001 > 002 > 005 > 003 > 004**.
- Template subset: **002 > 001 > 005 > 003 > 004**.

Compare returned score differences and ordering, rather than expecting absolute
local and Kaggle values to match. The cohorts, forecast period and final training
window differ. Four observed strategies support the tested RRF/reranking/MF
distinctions, while the close 001/002 pair reverses primary validation's order.
These observations do not establish general ranking transfer. Very small score differences are descriptive; aggregate
Kaggle scores do not give us per-user paired uncertainty.

Record both returned scores, and use **public score** for submission decisions
as specified by the exam. The inspected private scores are secondary reported
outcomes, not an untouched independent evaluation for later feedback-driven
choices. The remaining upload order can be reviewed after each response.
All five original uploads are scored. The next preparation is the separately
declared refinement for **006**, selected on primary local validation only.

Machine-readable original settings: `scripts/kaggle_comparison_plan.json`.
Current status and the user-reported allowance: `progress.json`.

## Submission 006: local refinement after the original plan

The three idea families were tested in a fixed eleven-new-configuration grid
with 001/002 controls: five auxiliary-budget/split variants, four deeper-list
variants, and two gradual-recency half-lives. The selector loaded no leaderboard
score ledger. Eight-week recency won primary local MAP: **0.37601075**, with
**0.41099420** on the template subset, versus 002's **0.37284202 / 0.40792464**.
The selected recipe was frozen and applied to all weeks 11–30; 006 returned
**public 0.43662 / private 0.42340**, exceeding 002 by **0.00303 / 0.00851** and
becoming the best recorded upload on both scores. See `reports/refinement/README.md` and
`reports/submission_006/README.md`. All trials, including weaker results, remain
saved. This repeatedly used hold-out and its conditional intervals do not
guarantee an improvement on Kaggle.

## Submission 007: one further locally selected refinement

A fixed thirteen-candidate study tested model-specific half-lives, strict rule
query decay, vote-only popularity decay and modest RRF budget changes around
006. Primary local MAP selected a weight-only change: keep both eight-week
MF/PPR models and all other component scores fixed, increase the rules weight
from .125 to .1875 and reduce popularity from .125 to .0625. MF/PPR weights stay
.5/.5. Local MAP is **0.37652771 all / 0.41177101 template**; both conditional
paired intervals include zero. The selector loaded no Kaggle score ledger.
007 returned **public 0.43707 / private 0.42472**, improving over 006 by
**0.00045 / 0.00132**. The user designated 007 as final and stopped experiments.
The final file/configuration is frozen in `submissions/final_selection.json`.
Full evidence is in `reports/recency_extension/` and `reports/submission_007/`;
report-ready heavy/light validation examples are in `reports/final_examples/`.
