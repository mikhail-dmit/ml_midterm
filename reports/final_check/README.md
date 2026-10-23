# Final reproducibility and hand checks

**PASS: a fresh raw-CSV rebuild produces the exact original submission_007.csv.**

- Fresh output: `reports/final_check/rebuild_001/final/submission_007.csv`.
- Original: `submissions/submission_007.csv`.
- **Byte-identical: yes. Changed users: 0 / 1260.**
- All **40 logical intermediate comparisons match exactly**, including raw-derived interactions/labels, counts, MF factors, graph, rules, CBF vectors/profiles, model scores and validation rankings.
- Separate guarded processes deny reads of old artifacts/reports/submissions during fitting. The access logs show **zero forbidden old-derived accesses**. Old results are read only afterwards for comparison.
- Raw files, frozen configurations, compute code and the published CSV remain unchanged.

SHA-256 of both CSVs:

```text
8d3bc085cb0a830cbab5c68789470c608fd34bb840dffbe75e4dd43833f87d8c
```

## What was replayed

Raw data audit → fresh split interactions and labels → all six selected validation strategies (popularity, CBF, weekly rules, eight-week MF/PPR and final007 fusion) → fresh full weeks11–30 rejoin → new final007 factors, co-view graph, rule mining, scores and fusion. Parameters stay frozen; the historical search is not rerun. This is reproducibility verification, not a new experiment or submission.

## Hand checks

1. **[hand_ap.md](hand_ap.md):** validation user `1026253314001693311`; hit pattern yes/no/yes/yes/no. AP@5 = (1 + 2/3 + 3/4)/5 = **29/60 = 0.483333333333**. Raw-source truth and the scorer agree.
2. **[hand_join.md](hand_join.md):** original user `127680364314713816`. Programme700389: **6752/7200 = 0.937777777778**, qualifies. Programme90076035: **(4336+836)/6900 = 0.749565217391**, does not qualify. Raw record references, clipped fragments, union pieces and all six validation programme counts are saved.

## Reproduce / inspect

```bash
python3 scripts/run_final_check.py
python3 scripts/hand_final_checks.py
```

Each replay creates a new numbered rebuild folder and keeps earlier runs. `latest_run.json` identifies the run. `rebuild_result.json`, `stage_reconciliation.csv` and `verification.json` summarize outcomes. The rebuild folder contains `configuration.json`, `input_manifest.json`, `commands.json`, all fresh model/interactions artifacts and logs/access manifests. Commands and environment are saved there.
This run took 164.9s for audit/build/model/comparison stages; stage times: raw_audit 70.5s, interactions 25.7s, models 64.6s.

No differences were found to investigate. JSON report generation times and container metadata are not treated as model differences; model/interactions values and ordering are compared directly, and the final CSV is compared byte-for-byte. Local timezone/fragment-union and frequency-tie assumptions remain the documented reconstruction choices. All checks here were performed by the assistant; the student's personal checks are not claimed.
