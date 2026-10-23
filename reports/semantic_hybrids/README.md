# Method-role hybrids versus the fixed RRF control

**Selected overall: RRF control: MF + PPR + rules. Best semantic hybrid: PPR Top-20 -> MF reranking.**

## Frozen experiment

Eleven configurations were declared before scoring: five familiar/new quotas; popularity switching to MF, PPR or a role-based warm branch; two collaborative candidate/reranker directions; and a rules-generated new-candidate shortlist reranked by popularity. The existing RRF is a fixed control, alongside the individual methods.
The exact original >=80% validation Top-5 labels, 4,030-user primary cohort, 1,150-user template subset, 6,384 eligible IDs, repeats, and denominator five are retained. Restored MF/PPR 50% and weekly-rule 80% models reproduce every original component Top-5 exactly. The RRF control reproduces every previous recommendation exactly.

### Meaning of the role rules

- Familiar: the user had >=1 original >=80% qualifying training watch. New: no such qualifying watch; partial-only prior exposure remains new. Neither definition uses validation answers.
- History size: all distinct >=80%-qualified training programmes, including IDs unavailable later. Popularity switching applies at <=5; there is no oracle routing by future truth composition.
- Fixed quotas place familiar slots first and new slots last. Positive component scores are sorted within roles; zero-signal slots use the shared 50%-training popularity backfill. If one role lacks enough eligible items, its unused slots are borrowed by the other role.
- Filtering into roles occurs over the complete eligible component order before keeping the first 20 candidates. The role queues are not restricted to each component's original Top-5.
- Two-stage strategies retrieve 20 IDs, then order them by the other method's raw score. Ties preserve generator order. Different methods' raw scores are never added.
- Every actual cold user receives identical popularity fallback. The original 59-user cold diagnostic bin is kept fixed; 16 are warm under 50%, leaving 43 actual cold users.

## Full comparison

| Strategy | MAP@5 all | MAP@5 template | Delta vs RRF: all |
|---|---:|---:|---:|
| MF 50% | 0.36592473 | 0.39746957 | -0.00763772 |
| PPR 50% | 0.36497436 | 0.40020000 | -0.00858809 |
| Weekly rules 80% | 0.31417783 | 0.33657681 | -0.05938462 |
| Popularity 50% | 0.27939123 | 0.30530725 | -0.09417122 |
| **RRF control: MF + PPR + rules** | 0.37356245 | 0.40764638 | +0.00000000 |
| 4 PPR familiar + 1 rules new | 0.35217866 | 0.38275072 | -0.02138379 |
| 3 PPR familiar + 2 rules new | 0.32332506 | 0.34808986 | -0.05023739 |
| 4 PPR familiar + 1 popular new | 0.34923325 | 0.38094493 | -0.02432920 |
| 3 PPR familiar + 2 popular new | 0.32050868 | 0.34716232 | -0.05305376 |
| 4 MF familiar + 1 rules new | 0.35286270 | 0.38192754 | -0.02069975 |
| Popularity if history <=5, else PPR | 0.36463772 | 0.40178261 | -0.00892473 |
| Popularity if history <=5, else MF | 0.36551944 | 0.39936522 | -0.00804301 |
| Popularity if history <=5, else 4 PPR + 1 rules | 0.35209512 | 0.38389275 | -0.02146733 |
| PPR Top-20 -> MF reranking | 0.36888503 | 0.40055652 | -0.00467742 |
| MF Top-20 -> PPR reranking | 0.36496195 | 0.39888986 | -0.00860050 |
| 4 PPR familiar + 1 new from rules Top-20 reranked by popularity | 0.34932258 | 0.38108406 | -0.02423987 |

All configurations are retained. Selection uses primary MAP only and includes the controls, so a semantic hybrid is not forced to win.

## Why the fixed-slot intuition did not improve MAP

The diagnostic identifies different average strengths, but a global role budget ignores each user's relative candidate quality. Making room for a weak new prediction can displace a correct recurring favourite. Strict familiarity also separates partial prior interests that the softer collaborative models can already use.

| Strategy | Familiar hits | New hits | Familiar recall | New recall | Familiar AP credit | New AP credit |
|---|---:|---:|---:|---:|---:|---:|
| RRF control: MF + PPR + rules | 8,150 | 596 | 71.98% | 6.75% | 0.354176 | 0.019386 |
| 4 PPR familiar + 1 rules new | 7,550 | 701 | 66.68% | 7.94% | 0.333230 | 0.018949 |
| 3 PPR familiar + 2 rules new | 6,436 | 1,034 | 56.84% | 11.71% | 0.293937 | 0.029388 |
| PPR Top-20 -> MF reranking | 8,134 | 499 | 71.84% | 5.65% | 0.352504 | 0.016381 |

The 4+1 rules allocation has +105 new-type hits but -600 familiar hits relative to RRF. The increased new recall does not compensate for lost familiar relevance and ranking quality. Even its new-type AP contribution is lower because hits generally occupy later positions and depend on earlier hit precision. AP-credit partitions preserve the original metric exactly.

## Switching and reranking

Popularity remains useful for some sparse users, but the strict-history <=5 switch does not improve primary MAP over its softer-input standalone counterpart. The earlier reference diagnostic used strict-input models; it does not guarantee a beneficial gate after those models change to 50%-qualified inputs. The template subgroup's improvement does not override primary selection.
The best semantic method, PPR Top-20 -> MF reranking, reaches 0.36888503. Candidate generation changes MF's eligible shortlist and improves over unrestricted MF, but remains below the 0.37356245 RRF control. MF/PPR ranked lists plus the rules contribution preserve more useful information than these particular hard constraints.

### History breakdown: primary cohort

| Strict distinct history | Users | Popularity | MF | PPR | RRF | PPR20 -> MF | Switch to MF |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 (cold) | 59 | 0.201864 | 0.181243 | 0.192599 | 0.189887 | 0.183107 | 0.201864 |
| 1-5 | 224 | 0.160164 | 0.172887 | 0.168661 | 0.189539 | 0.179092 | 0.160164 |
| 6-20 | 1,512 | 0.237123 | 0.317008 | 0.312619 | 0.323671 | 0.320432 | 0.317008 |
| 21-50 | 1,836 | 0.314178 | 0.418215 | 0.418758 | 0.425557 | 0.420574 | 0.418215 |
| 51+ | 399 | 0.357895 | 0.446358 | 0.451587 | 0.453843 | 0.448672 | 0.446358 |

Best semantic minus RRF: -0.00467742; conditional paired 95% interval [-0.007047, -0.002255]. Intervals use 2,000 user resamples, seed 20261023; they are conditional diagnostics, not corrected for selection on the repeatedly used temporal hold-out or unknown truth tie policy.

## Examples and verification

runs/NAME/recommendations.csv records each item's strict familiarity, routing/role, history count, all four source scores, title/category and true-hit status. recommendation_examples.csv retains the earlier light/heavy users across all tested strategies, with ordered IDs and matches.
Five targeted unit tests and 119 independent checks passed. Verification rebuilds full eligible orders from saved scores, applies masks before truncation, reconstructs every slot/switch/rerank/RRF prediction, and checks exact-rational AP/MAP, fixed users, fallback and feature provenance. The student's own verification remains pending.

## Reproduce

```bash
python3 -m unittest discover -s scripts -p 'test_semantic_hybrids.py'
python3 scripts/run_semantic_hybrids.py
python3 scripts/verify_semantic_hybrids.py
python3 scripts/make_first_submission.py
python3 scripts/verify_first_submission.py
python3 scripts/summarize_semantic_hybrids.py
```

Source plans, input/code SHA-256s, component scores, predictions, per-user metrics, all-segment tables and paired comparisons are retained. The earlier MF binary-target diagnosis remains in reports/models/README.md and reports/all_methods/report_notes.md.
