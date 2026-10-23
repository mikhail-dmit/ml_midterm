# Compact hybrid experiment: do complementary hits improve Top-5?

## Protocol and declared search

The source plan was saved before scoring thirteen hybrid configurations. This follows the shared training-input study; its selected components use full weeks 11–20: MF/PPR at 50% training coverage, weekly rules/CBF at 80%, and the common 50%-training popularity fallback. No component is refitted here.
Validation remains the original >=80% frequency Top-5, with all 4,030 primary users, the nested 1,150-user template subset, all 6,384 eligible programme IDs and repeats allowed. The primary cohort alone selects a configuration; the template subset is descriptive reporting.

### Rank fusion

For each candidate, `score = sum_m weight_m / (offset + rank_m)`. Component ranks are one-based. Each component supplies its saved Top-5; an absent item contributes zero. These utilities are not calibrated watch probabilities. The retrieval shortlist is the union of those lists, bounded by the unchanged candidate eligibility pool.
Offsets 0 and 10 contrast first-rank emphasis with stronger consensus emphasis on these short lists. Ties use the full 50%-training popularity order, then numeric ID; exact rational keys prevent rounding from breaking mathematical ties. Popularity supplies any missing slots. All 43 users without 50%-qualified training history retain exactly the same popularity Top-5 across every component and hybrid.
The configurations compare MF+PPR; adding a modest popularity or weekly-rule contribution; adding both; equal fusion of all five methods; and MF/popularity or PPR/popularity alone. The complete weights and offsets are in plan.json and each run's config.json.

### Training-only switching

Two additional configurations return popularity when a user has <=5 distinct programmes under the 50% training definition, otherwise MF or PPR. The threshold is a fixed coarse-history boundary motivated by the earlier diagnostic, not fitted per user. Validation answers, their familiar/new composition and per-user AP never enter inference.

## All results

| Strategy | MAP@5: all 4,030 | MAP@5: template 1,150 | Delta vs MF: all |
|---|---:|---:|---:|
| Popularity (50%) | 0.27939123 | 0.30530725 | -0.08653350 |
| MF (50%) | 0.36592473 | 0.39746957 | +0.00000000 |
| PPR (50%) | 0.36497436 | 0.40020000 | -0.00095037 |
| CBF (80%) | 0.24500165 | 0.26950145 | -0.12092308 |
| Weekly rules (80%) | 0.31417783 | 0.33657681 | -0.05174690 |
| rrf_mf_ppr_k0 | 0.37061538 | 0.40582319 | +0.00469065 |
| rrf_mf_ppr_k10 | 0.37093548 | 0.40620290 | +0.00501075 |
| rrf_mf_ppr_pop_k0 | 0.37057320 | 0.40648116 | +0.00464847 |
| rrf_mf_ppr_pop_k10 | 0.37197601 | 0.40715652 | +0.00605128 |
| **rrf_mf_ppr_rules_k0** | 0.37356245 | 0.40764638 | +0.00763772 |
| rrf_mf_ppr_rules_k10 | 0.37162779 | 0.40559130 | +0.00570306 |
| rrf_mf_ppr_rules_pop_k0 | 0.37284202 | 0.40792464 | +0.00691729 |
| rrf_mf_ppr_rules_pop_k10 | 0.37271050 | 0.40737391 | +0.00678577 |
| rrf_all_equal_k0 | 0.36478825 | 0.39808696 | -0.00113648 |
| rrf_mf_pop_k0 | 0.36469479 | 0.39754493 | -0.00122994 |
| rrf_ppr_pop_k0 | 0.36355418 | 0.39922319 | -0.00237055 |
| switch_mf_sparse5 | 0.36616294 | 0.39822899 | +0.00023821 |
| switch_ppr_sparse5 | 0.36502895 | 0.40084928 | -0.00089578 |

## Selected local strategy

**Primary-cohort selection: `rrf_mf_ppr_rules_k0`.** Best hybrid: `rrf_mf_ppr_rules_k0`. Its exact configuration is:

```json
{
  "id": "rrf_mf_ppr_rules_k0",
  "type": "rrf",
  "offset": 0,
  "weights": {
    "implicit_mf": 0.5,
    "ppr": 0.5,
    "association_rules": 0.25
  }
}
```

All candidate configurations, including failures, remain in comparison.csv; this stage does not extend the declared search after inspecting its scores.

| Reference component | Primary MAP difference | Conditional 95% interval | Users better / worse / tied |
|---|---:|---|---|
| Popularity (50%) | +0.09417122 | [+0.088236, +0.099900] | 2,426 / 910 / 694 |
| MF (50%) | +0.00763772 | [+0.005385, +0.009891] | 1,116 / 788 / 2,126 |
| PPR (50%) | +0.00858809 | [+0.006301, +0.010775] | 1,138 / 799 / 2,093 |
| CBF (80%) | +0.12856079 | [+0.123434, +0.133654] | 2,641 / 428 / 961 |
| Weekly rules (80%) | +0.05938462 | [+0.054442, +0.064358] | 2,146 / 958 / 926 |

Intervals use 2,000 paired user resamples with seed 20261023. They describe uncertainty conditional on this fitted-model/label/hold-out choice; they do not correct for the thirteen-way hybrid selection, earlier model/input selection, temporal drift or the unresolved organiser tie policy. They are not an untouched-test generalisation estimate.

### What changed in the actual answers?

| Reference | Correct pairs added | Correct pairs lost | Net correct pairs |
|---|---:|---:|---:|
| MF (50%) | 617 | 426 | +191 |
| PPR (50%) | 639 | 468 | +171 |

The saved selected_hit_changes.csv identifies the added/lost IDs and delta AP for every user. Some users lose relevance or rank quality even when the macro average improves.

## Familiar versus new-to-user

Definitions remain those from the original strict/full history, including in the softer-input components. These are micro recalls within each true-answer type; AP contributions retain the full original denominator.

| Strategy | Familiar recall: all | New recall: all | Familiar recall: template | New recall: template |
|---|---:|---:|---:|---:|
| Popularity (50%) | 54.02% | 12.35% | 54.51% | 13.07% |
| MF (50%) | 70.60% | 6.36% | 70.18% | 6.12% |
| PPR (50%) | 72.38% | 4.29% | 72.20% | 4.02% |
| Weekly rules (80%) | 59.46% | 11.73% | 58.94% | 11.56% |
| rrf_mf_ppr_rules_k0 | 71.98% | 6.75% | 71.81% | 6.44% |

New-to-user does not imply never seen or enjoyed. Partial prior exposure is separately recorded. The selected hybrid remains much stronger at repeated preferences than new-to-user truth; this is not an exploration or satisfaction experiment.

## Original history segments

### all_primary

| Original strict distinct history | Users | Popularity | MF 50% | PPR 50% | Selected hybrid |
|---|---:|---:|---:|---:|---:|
| 0 (cold) | 59 | 0.201864 | 0.181243 | 0.192599 | 0.189887 |
| 1-5 | 224 | 0.160164 | 0.172887 | 0.168661 | 0.189539 |
| 6-20 | 1,512 | 0.237123 | 0.317008 | 0.312619 | 0.323671 |
| 21-50 | 1,836 | 0.314178 | 0.418215 | 0.418758 | 0.425557 |
| 51+ | 399 | 0.357895 | 0.446358 | 0.451587 | 0.453843 |

### template_primary

| Original strict distinct history | Users | Popularity | MF 50% | PPR 50% | Selected hybrid |
|---|---:|---:|---:|---:|---:|
| 0 (cold) | 10 | 0.180000 | 0.180000 | 0.180000 | 0.180000 |
| 1-5 | 39 | 0.211709 | 0.155812 | 0.165043 | 0.185556 |
| 6-20 | 373 | 0.246631 | 0.339196 | 0.338025 | 0.347596 |
| 21-50 | 589 | 0.334601 | 0.442518 | 0.445444 | 0.452513 |
| 51+ | 139 | 0.373909 | 0.446403 | 0.457146 | 0.457362 |

The original cold bin contains 59 users; 16 acquire qualifying history at 50%, leaving 43 actual cold users. The fixed 59-user bin therefore can differ across strategies even though every actual cold fallback is identical. Both the fixed-history diagnostic and the actual 50% routing feature are saved.

## Evidence-backed interpretation

- Equal MF/PPR fusion already improves the primary MAP from 0.365925 to 0.370615. With the same offset and MF/PPR weights, adding weekly rules raises it to 0.373562. This is a realised Top-5 gain, beyond the earlier up-to-25-item union diagnostic.
- Weighted rules contribute differently from the collaborative pair. In this plan, making all five methods equally influential performs worse than the strongest standalone models on the primary cohort. This is evidence for the tested weighting, not proof that CBF can never help a hybrid.
- Adding popularity can increase any-hit coverage without maximising MAP: how correct IDs are ranked matters. The sparse-history switches offer only small macro gains over their respective standalone components.
- The selected hybrid improves the average, but popularity remains ahead in the original-cold primary bin and the small template 1–5-history bin. Gains are not uniform across users.
- The highest template-subset score is 0.40792464, from `rrf_mf_ppr_rules_pop_k0`; it does not replace the primary-cohort selection.
- Source models and earlier input choices were already selected on this same temporal hold-out. Lower-ranked candidates beyond component Top-5 are untested by this fusion study. The unknown fifth-place truth tie policy and sparse labelled-airtime coverage remain limitations.

## Examples and cost

recommendation_examples.csv keeps the same earlier light/heavy viewers and shows all five current components plus the selected hybrid, with ordered IDs, pre-cutoff schedule titles/categories and true-Top-5 matches. These are assistant-produced examples awaiting the student's own review.

| Example | User ID | Popularity AP | MF AP | PPR AP | CBF AP | Rules AP | Hybrid AP |
|---|---|---:|---:|---:|---:|---:|---:|
| light | 1026253314001693311 | 0.520000 | 0.233333 | 0.600000 | 0.000000 | 0.483333 | 0.483333 |
| heavy | 13866173795451203812 | 1.000000 | 0.800000 | 0.760000 | 0.520000 | 0.760000 | 0.800000 |

The light viewer illustrates a local loss versus PPR despite the macro gain; the heavy viewer still favours popularity. The examples were retained from the earlier training-based choice rather than picked to flatter the hybrid.
The selected fusion inference took 0.278 seconds for 4,030 users in this run. This excludes component fitting/inference and all evaluation/report writing. Environment and per-configuration times are saved; the hybrid adds the cost of retaining and operating its component models.

## Verification and reproduction

Five targeted unit tests passed. Independent verification passed 219 checks for all thirteen hybrids and five components: frozen inputs/provenance, 50% counts reconstructed from airing-level training evidence, common cold fallback, exact-rational ranks/AP/MAP, fixed segments/novelty, explanation ranks, per-user answer changes, and reproducible paired intervals.

```bash
python3 -m unittest discover -s scripts -p 'test_hybrids.py'
python3 scripts/run_hybrid_experiments.py
python3 scripts/verify_hybrid_experiments.py
python3 scripts/summarize_hybrid_experiments.py
```

The source plan, component paths, input SHA-256s, code fingerprints, environment, every prediction and per-user score are saved. selection.json records a local-validation strategy selection. Final refitting, Kaggle scoring and the student's personal verification are later steps.
