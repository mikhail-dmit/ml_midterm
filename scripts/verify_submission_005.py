#!/usr/bin/env python3
"""Independently verify the exact MF/PPR-only RRF rules ablation."""

import csv
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256
from verify_submission_002 import exact_fusion

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_005"


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    manifest = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in manifest["paths"].items()}
    for name, path in paths.items():
        check(f"immutable preparation input: {name}", sha256(path) == manifest["sha256"][name])
    summary = json.loads((OUT / "summary.json").read_text())
    plan = json.loads(paths["plan"].read_text())
    candidate = next(r for r in plan["submissions"] if r["id"] == "submission_005")
    config = json.loads((OUT / "config.json").read_text())
    check("exact predeclared MF/PPR-only RRF", config == summary["selected_config"] == candidate["strategy"] == json.loads(paths["validation_config"].read_text()) == {"id": "rrf_mf_ppr_k0", "type": "rrf", "offset": 0, "weights": {"implicit_mf": .5, "ppr": .5}})
    training = json.loads(paths["training_manifest"].read_text())
    old_config = training["selected_config"]
    check("remove only rules from scored 001", old_config["type"] == "rrf" and old_config["offset"] == config["offset"] == 0 and old_config["weights"] == {"implicit_mf": .5, "ppr": .5, "association_rules": .25})
    check("preparation/fusion code fingerprints", all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    check("original fitted-model code unchanged", all(sha256(ROOT / "scripts" / f) == h for f, h in training["code_hashes"].items()))
    snapshot = json.loads(paths["score_snapshot"].read_text())
    results = {r["submission_id"]: r for r in snapshot["results"]}
    expected_scores = {"submission_001": (.43347, .41452), "submission_002": (.43359, .41489),
                       "submission_003": (.43042, .41260), "submission_004": (.42643, .40943)}
    for name, values in expected_scores.items():
        record = results[name]
        check(f"reported scores match exact uploaded CSV: {name}", (record["public_score"], record["private_score"]) == values and sha256(ROOT / record["csv_path"]) == record["csv_sha256"])
        check(f"score screenshot retained: {name}", sha256(ROOT / record["screenshot_path"]) == record["screenshot_sha256"])
    submission = ROOT / summary["submission_path"]
    with submission.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.reader(stream))
    users = [r["user_id"] for r in read_csv(paths["template"])]
    check("exact two-column template schema with no index", raw[0] == ["user_id", "tv_show_id"] and all(len(r) == 2 for r in raw[1:]))
    check("1260 exact decimal user IDs in template order", len(raw)-1 == len(users) == len(set(users)) == 1260 and [r[0] for r in raw[1:]] == users and all(str(int(u)) == u for u in users))
    check("five unique canonical positive integer IDs per cell", all(len(r[1].split()) == len(set(r[1].split())) == 5 and r[1] == " ".join(r[1].split()) and all(i.isdecimal() and int(i) > 0 and str(int(i)) == i for i in r[1].split()) for r in raw[1:]))
    check("CSV bytes match saved generation hash", sha256(submission) == summary["submission_sha256"])
    predictions = rankings(submission)
    pop = [int(r["tv_show_id"]) for r in read_csv(paths["popularity"])]
    pop_rank = {item: n for n, item in enumerate(pop)}
    pool = {int(r["tv_show_id"]) for r in read_csv(paths["candidates"])}
    check("same 6632 eligible candidates and all outputs eligible", len(pop) == len(pool) == 6632 and set(pop) == pool and all(set(ids) <= pool for ids in predictions.values()))
    cold = set(json.loads(paths["cold_users"].read_text()))
    check("same four cold users and exact common fallback", len(cold) == 4 and all(predictions[u] == pop[:5] for u in cold))
    check("score matrix rows match exact template order", json.loads(paths["model_users"].read_text()) == users)
    model = np.load(paths["scores"], allow_pickle=False)
    components = {m: rankings(paths[f"component_{m}"]) for m in ["implicit_mf", "ppr", "association_rules"]}
    for method, output in components.items():
        check(f"component cohort and valid eligible Top-5: {method}", set(output) == set(users) and all(len(ids) == len(set(ids)) == 5 and set(ids) <= pool for ids in output.values()))
        values, items = model[f"scores_{method}"], model[f"items_{method}"].astype(int).tolist()
        for row, user in enumerate(users):
            positive = [(item, float(values[row, n])) for n, item in enumerate(items) if item in pool and values[row, n] > 0]
            positive.sort(key=lambda pair: (-pair[1], pair[0]))
            prefix = [item for item, score in positive]
            seen = set(prefix)
            ordered = prefix+[item for item in pop if item not in seen]
            assert output[user] == (pop[:5] if user in cold else ordered[:5])
        check(f"component Top-5 reconstructed from identical full-history scores: {method}", True)
    previous = {name: rankings(paths[f"scored_{name}"]) for name in expected_scores}
    check("unchanged components reproduce all scored 001 ranks", all(previous["submission_001"][u] == exact_fusion(components, u, old_config, pop_rank) for u in users))
    check("every 005 rank independently reconstructed using exact fractions", all(predictions[u] == exact_fusion(components, u, config, pop_rank) for u in users))
    check("005 recommendations use only the MF/PPR Top-5 union", all(set(predictions[u]) <= set(components["implicit_mf"][u]) | set(components["ppr"][u]) for u in users))
    history = json.loads(paths["history"].read_text())
    trace = read_csv(OUT / "recommendations.csv")
    check("submitted rank and training-familiarity trace", len(trace) == 5*len(users) and all(predictions[r["user_id"]][int(r["rank"])-1] == int(r["tv_show_id"]) and (r["familiar_training_80pct"] == "True") == (int(r["tv_show_id"]) in history[r["user_id"]]) for r in trace))
    contrasts = {r["reference"]: r for r in summary["comparisons"]}
    for name, output in previous.items():
        rows = read_csv(OUT / f"changes_vs_{name}.csv")
        check(f"change-table exact user coverage: {name}", len(rows) == len(users) and [r["user_id"] for r in rows] == users)
        for record in rows:
            user = record["user_id"]
            a, b = output[user], predictions[user]
            assert record["previous_ids"] == " ".join(map(str, a)) and record["new_ids"] == " ".join(map(str, b))
            assert (record["changed_order"] == "True") == (a != b) and (record["changed_set"] == "True") == (set(a) != set(b))
            assert int(record["shared_top5"]) == len(set(a)&set(b)) and record["entered_ids"] == " ".join(map(str, sorted(set(b)-set(a)))) and record["removed_ids"] == " ".join(map(str, sorted(set(a)-set(b))))
        changed = sum(output[u] != predictions[u] for u in users)
        changed_set = sum(set(output[u]) != set(predictions[u]) for u in users)
        check(f"all list changes and aggregate counters: {name}", contrasts[name]["changed_ordered_users"] == changed and contrasts[name]["changed_set_users"] == changed_set and contrasts[name]["order_only_users"] == changed-changed_set and contrasts[name]["unchanged_users"] == len(users)-changed and contrasts[name]["entered_user_item_pairs"] == sum(len(set(predictions[u])-set(output[u])) for u in users))
    local_components = {m: rankings(ROOT / "reports/training_study/full10_t50/runs" / m / "predictions.csv") for m in config["weights"]}
    local_pop = [int(r["tv_show_id"]) for r in read_csv(ROOT / "reports/training_study/full10_t50/candidate_scores.csv")]
    local_pop_rank = {item: n for n, item in enumerate(local_pop)}
    local_saved = rankings(ROOT / "reports/hybrids/runs/rrf_mf_ppr_k0/predictions.csv")
    truth = rankings(ROOT / "reports/interactions/validation_ground_truth.csv")
    check("exact predeclared local MF/PPR RRF rankings reproduced", set(local_saved) == set(truth) and all(local_saved[u] == exact_fusion(local_components, u, config, local_pop_rank) for u in truth))
    for cohort, filename, count in [("all_primary", "cohort_primary.csv", 4030), ("template_primary", "cohort_template_primary.csv", 1150)]:
        ids = [r["user_id"] for r in read_csv(ROOT / "reports/popularity" / filename)]
        mean = sum((exact_ap(set(truth[u]), local_saved[u])[0] for u in ids), Fraction(0))/len(ids)
        check(f"exact local MAP with frozen population: {cohort}", len(ids) == count and close(mean, summary["validation_source"][cohort]) and close(mean, candidate["validation_primary" if cohort == "all_primary" else "validation_template"]))
    report = {"status": "passed", "submission_path": summary["submission_path"], "submission_sha256": sha256(submission), "checks": checks,
              "verifier_sha256": sha256(Path(__file__)), "kaggle_score": None, "meaning": "Assistant numerical verification; 005 awaits user upload"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    lines = ["# Submission 005: exact rules ablation from 001", "", "**Upload `submissions/submission_005.csv`. Returned scores are pending.**", "",
             "## Recorded results and hypothesis", "",
             "| Submission | Method | Local MAP all | Local MAP template | Kaggle public | Kaggle private |", "|---|---|---:|---:|---:|---:|",
             "| 001 | MF/PPR/rules RRF | 0.37356245 | 0.40764638 | 0.43347 | 0.41452 |",
             "| 002 | MF/PPR/rules/popularity RRF | 0.37284202 | 0.40792464 | 0.43359 | 0.41489 |",
             "| 003 | PPR20 -> MF | 0.36888503 | 0.40055652 | 0.43042 | 0.41260 |",
             "| 004 | Standalone MF | 0.36592473 | 0.39746957 | 0.42643 | 0.40943 |",
             "| 005 | MF/PPR RRF, no rules | 0.37061538 | 0.40582319 | pending | pending |", "",
             "004 is the lowest scored method so far on both returned scores. The best RRF (002) improves over standalone MF by **0.00716 public / 0.00546 private**; PPR candidate generation in 003 improves over 004 by **0.00399 / 0.00317**. These specific local distinctions transfer to Kaggle. Current ordering is **002 > 001 > 003 > 004** on public and private scores; the close 001/002 pair still reverses primary validation's ordering.",
             "005 isolates the weekly-rules contribution by comparing directly to 001. Both local cohorts predict **001 > 005 > 003 > 004**; template validation additionally predicts **002 > 001**, while primary validation reverses that pair. The local 001-minus-005 MAP differences are +0.00294706 all / +0.00182319 template. The actual Kaggle effect of removing rules remains unknown until this upload is scored.",
             "", "## Exact controlled change", "",
             "Reuse the same weeks 11–30 MF/PPR50 fitted models and each component's available Top-5. RRF uses `0.5 / rank_MF + 0.5 / rank_PPR`, with an absent item contributing zero and offset zero. Compared with 001, remove only the .25/rank_rules term. No popularity voting term is added. Popularity remains the identical tie-break and common fallback for four actual cold users; repeats and all 6,632 eligible candidates remain unchanged.",
             "The 001 CSV is reproduced exactly from the reused components before generation. Neither models nor parameters are refitted/retuned. Rules ranks are retained in the trace for explanation only; they do not contribute to the 005 scores or shortlist.",
             "", "## Changes versus prior uploads", "",
             "| Reference | Changed lists | Changed item sets | Order only | Unchanged users | Mean shared Top-5 |", "|---|---:|---:|---:|---:|---:|"]
    for name, record in contrasts.items():
        lines.append(f"| {name} | {record['changed_ordered_users']:,} | {record['changed_set_users']:,} | {record['order_only_users']:,} | {record['unchanged_users']:,} | {record['mean_shared_top5']:.4f}/5 |")
    lines += ["", "These are recommendation changes, not known relevance gains/losses: no per-user Kaggle truth is available. All four scored CSVs and screenshots are retained with exact hashes.",
              "", "## Verification and reproduction", "",
              f"**{len(checks)} independent checks passed:** immutable inputs/code and all recorded score evidence; exact template order/header and user IDs; five distinct nonzero eligible IDs; same cold fallback; component Top-5 reconstruction from saved full-history scores; exact-rational fusion for both 001 and 005; every list change; and exact local AP/MAP on the frozen cohorts.",
              "", "SHA-256:", "", "```text", summary["submission_sha256"], "```", "",
              "```bash", "python3 scripts/prepare_submission_005.py", "python3 scripts/verify_submission_005.py", "```", "",
              "See config.json, summary.json, frozen_inputs.json, results_at_preparation.json, recommendations.csv, changes_vs_*.csv and verification.json. Only 005 is prepared in this stage; later ideas in submissions/progress.json remain suggestions pending local validation and user direction.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Passed {len(checks)} checks. READY: {submission}")
    print(f"SHA-256: {sha256(submission)}")


if __name__ == "__main__":
    main()
