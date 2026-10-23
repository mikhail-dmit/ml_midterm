#!/usr/bin/env python3
"""Verify standalone MF independently from saved factors and frozen local scores."""

import csv
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_004"


def rank_independently(users, scores, items, popularity, cold):
    eligible = set(popularity)
    result = {}
    for row, user in enumerate(users):
        if user in cold:
            result[user] = popularity[:5]
            continue
        positive = [(int(item), float(scores[row, n])) for n, item in enumerate(items) if int(item) in eligible and scores[row, n] > 0]
        positive.sort(key=lambda pair: (-pair[1], pair[0]))
        prefix = [item for item, value in positive]
        used = set(prefix)
        result[user] = (prefix+[item for item in popularity if item not in used])[:5]
    return result


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
    config = json.loads((OUT / "config.json").read_text())
    plan = json.loads(paths["plan"].read_text())
    candidate = next(r for r in plan["submissions"] if r["id"] == "submission_004")
    check("declared standalone MF configuration", config == summary["selected_config"] == candidate["strategy"] == json.loads(paths["validation_config"].read_text()) == {"id": "implicit_mf", "type": "single", "method": "implicit_mf"})
    check("preparation code fingerprint", all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    training = json.loads(paths["training_manifest"].read_text())
    check("fitted model code unchanged", all(sha256(ROOT / "scripts" / f) == h for f, h in training["code_hashes"].items()))
    ledger = json.loads(paths["score_snapshot"].read_text())
    records = {r["submission_id"]: r for r in ledger["results"]}
    for name, values in [("submission_001", (.43347, .41452)), ("submission_002", (.43359, .41489)), ("submission_003", (.43042, .41260))]:
        record = records[name]
        check(f"reported score and exact uploaded bytes: {name}", (record["public_score"], record["private_score"]) == values and sha256(ROOT / record["csv_path"]) == record["csv_sha256"])
        check(f"score screenshot retained: {name}", sha256(ROOT / record["screenshot_path"]) == record["screenshot_sha256"])
    submission = ROOT / summary["submission_path"]
    with submission.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.reader(stream))
    users = [r["user_id"] for r in read_csv(paths["template"])]
    check("exact two-column template schema and no index", raw[0] == ["user_id", "tv_show_id"] and all(len(r) == 2 for r in raw[1:]))
    check("1260 exact decimal user IDs in original order", len(raw)-1 == len(users) == len(set(users)) == 1260 and [r[0] for r in raw[1:]] == users and all(str(int(u)) == u for u in users))
    check("five distinct canonical positive integer IDs per cell", all(len(r[1].split()) == len(set(r[1].split())) == 5 and r[1] == " ".join(r[1].split()) and all(i.isdecimal() and int(i) > 0 and str(int(i)) == i for i in r[1].split()) for r in raw[1:]))
    check("standalone upload exactly equals the saved MF component bytes", sha256(submission) == sha256(paths["component_mf"]) == summary["submission_sha256"] == summary["source_component_sha256"])
    predictions = rankings(submission)
    pool = {int(r["tv_show_id"]) for r in read_csv(paths["candidates"])}
    pop = [int(r["tv_show_id"]) for r in read_csv(paths["popularity"])]
    check("same 6632 eligible candidates and all outputs eligible", len(pop) == len(pool) == 6632 and set(pop) == pool and all(set(ids) <= pool for ids in predictions.values()))
    cold = set(json.loads(paths["cold_users"].read_text()))
    check("same four cold users and exact popularity fallback", len(cold) == 4 and all(predictions[u] == pop[:5] for u in cold))
    check("score rows match exact template order", json.loads(paths["model_users"].read_text()) == users)
    archive = np.load(paths["scores"], allow_pickle=False)
    mf = archive["scores_implicit_mf"]
    items = archive["items_implicit_mf"].astype(int).tolist()
    check("all-history MF scores finite and nonnegative", mf.shape == (len(users), len(items)) and np.isfinite(mf).all() and (mf >= 0).all())
    indices = json.loads(paths["training_indices"].read_text())
    check("item indices match fitted factors", items == indices["items"])
    factors = np.load(paths["factors"], allow_pickle=False)
    ui = {u: n for n, u in enumerate(indices["users"])}
    warm_rows = [n for n, u in enumerate(users) if u in ui]
    factor_scores = np.maximum(factors["user_factors"][[ui[users[n]] for n in warm_rows]] @ factors["item_factors"].T, 0)
    check("all warm scores rebuilt from the same fitted factors", np.allclose(mf[warm_rows], factor_scores, rtol=1e-12, atol=1e-12))
    check("cold factor absence and zero MF signal", cold == {u for u in users if u not in ui} and all(not mf[n].any() for n, u in enumerate(users) if u in cold))
    rebuilt = rank_independently(users, mf, items, pop, cold)
    check("every submitted rank independently reconstructed over the full eligible pool", predictions == rebuilt)
    comparisons = {r["reference"]: r for r in summary["comparisons"]}
    for name in ["submission_001", "submission_002", "submission_003"]:
        previous = rankings(paths[f"scored_{name}"])
        changes = read_csv(OUT / f"changes_vs_{name}.csv")
        check(f"change table exact user coverage: {name}", len(changes) == len(users) and [r["user_id"] for r in changes] == users)
        for record in changes:
            user = record["user_id"]
            a, b = previous[user], predictions[user]
            assert record["previous_ids"] == " ".join(map(str, a)) and record["new_ids"] == " ".join(map(str, b))
            assert (record["changed_order"] == "True") == (a != b) and (record["changed_set"] == "True") == (set(a) != set(b))
            assert int(record["shared_top5"]) == len(set(a)&set(b)) and record["entered_ids"] == " ".join(map(str, sorted(set(b)-set(a)))) and record["removed_ids"] == " ".join(map(str, sorted(set(a)-set(b))))
        changed = sum(previous[u] != predictions[u] for u in users)
        changed_set = sum(set(previous[u]) != set(predictions[u]) for u in users)
        check(f"all changes and summary counters: {name}", comparisons[name]["changed_ordered_users"] == changed and comparisons[name]["changed_set_users"] == changed_set and comparisons[name]["order_only_users"] == changed-changed_set and comparisons[name]["unchanged_users"] == len(users)-changed and comparisons[name]["entered_user_item_pairs"] == sum(len(set(predictions[u])-set(previous[u])) for u in users))
    local_dir = ROOT / "artifacts/semantic_hybrids"
    local_archive = np.load(local_dir / "scores.npz", allow_pickle=False)
    local_users = json.loads((local_dir / "users.json").read_text())
    local_cold = set(json.loads((local_dir / "cold_users.json").read_text()))
    local_pop = [int(r["tv_show_id"]) for r in read_csv(ROOT / "reports/training_study/full10_t50/candidate_scores.csv")]
    local = rank_independently(local_users, local_archive["scores_implicit_mf"], local_archive["items_implicit_mf"], local_pop, local_cold)
    saved_local = rankings(ROOT / "reports/semantic_hybrids/runs/implicit_mf/predictions.csv")
    check("exact standalone MF validation predictions reproduced", local == saved_local)
    truth = rankings(ROOT / "reports/interactions/validation_ground_truth.csv")
    for cohort, filename, count in [("all_primary", "cohort_primary.csv", 4030), ("template_primary", "cohort_template_primary.csv", 1150)]:
        ids = [r["user_id"] for r in read_csv(ROOT / "reports/popularity" / filename)]
        mean = sum((exact_ap(set(truth[u]), local[u])[0] for u in ids), Fraction(0))/len(ids)
        check(f"exact local MAP and frozen cohort: {cohort}", len(ids) == count and close(mean, summary["validation_source"][cohort]) and close(mean, candidate["validation_primary" if cohort == "all_primary" else "validation_template"]))
    check("005 remains planned only", not (ROOT / "submissions/submission_005.csv").exists())
    report = {"status": "passed", "submission_path": summary["submission_path"], "submission_sha256": sha256(submission), "checks": checks,
              "verifier_sha256": sha256(Path(__file__)), "kaggle_score": None, "meaning": "Assistant numerical verification; 004 awaits user upload"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    lines = ["# Submission 004: standalone implicit-count MF", "", "**Upload `submissions/submission_004.csv`. Its returned score is pending.**", "",
             "## Recorded ranking and hypothesis", "",
             "| Submission | Method | Local MAP all | Local MAP template | Kaggle public | Kaggle private |", "|---|---|---:|---:|---:|---:|",
             "| 001 | RRF MF/PPR/rules | 0.37356245 | 0.40764638 | 0.43347 | 0.41452 |",
             "| 002 | RRF with rules/popularity split | 0.37284202 | 0.40792464 | 0.43359 | 0.41489 |",
             "| 003 | PPR20 -> MF | 0.36888503 | 0.40055652 | 0.43042 | 0.41260 |",
             "| 004 | Standalone MF | 0.36592473 | 0.39746957 | pending | pending |", "",
             "003 is below both RRF uploads on public and private scores, as both local cohorts predicted. Relative to 002 it loses 0.00317 public and 0.00229 private; 002 remains best by the exam's public-score criterion. Across the three scored uploads, the returned ordering is 002 > 001 > 003. The template subset matches this ordering; primary validation reverses the close 001/002 pair.",
             "Both local cohorts predict 004 below 001/002 and below 003. Comparing 004 with the RRF uploads tests the benefit of fusion; comparing it with 003 tests whether PPR's Top-20 shortlist helps the same MF model after the longer-history refit. The current observations support those specific comparisons, not a general validation-superiority claim.",
             "", "## Exact fixed strategy", "",
             "004 is byte-identical to the standalone MF component already fitted for 001–003. No model is retrained or retuned. Training is all weeks 11–30, with >=50% qualifying watches, 16 factors, log(1+count) reconstruction target, confidence 1+log(1+count), regularisation 1, fifteen epochs and seed 20261023.",
             "Eligible positive MF scores are sorted descending, with numeric programme ID for ties. Scores are clipped below at zero as in the validated model. Missing positive slots and the four actual cold users use the same training-popularity fallback. Repeats remain allowed, and availability is the same 6,632 programme IDs. Neither PPR nor rules constrain or contribute to this upload.",
             "", "## Actual changes versus the scored uploads", "",
             "| Reference | Changed ordered lists | Changed sets | Order only | Unchanged | Mean shared Top-5 |", "|---|---:|---:|---:|---:|---:|"]
    for name, record in comparisons.items():
        lines.append(f"| {name} | {record['changed_ordered_users']:,} | {record['changed_set_users']:,} | {record['order_only_users']:,} | {record['unchanged_users']:,} | {record['mean_shared_top5']:.4f}/5 |")
    lines += ["", "The changes are not known relevance gains/losses: Kaggle's per-user truth is unavailable. All three earlier CSVs and screenshot evidence are retained with exact hashes.",
              "", "## Verification and reproduction", "",
              f"**{len(checks)} independent checks passed:** immutable inputs/code and scored-file evidence; template schema/order and exact user strings; five unique nonzero eligible IDs; byte identity with the saved MF component; all warm scores independently rebuilt from fitted factors; every final rank; cold fallback; per-user changes; and exact-rational local MAP on both frozen cohorts.",
              "", "SHA-256:", "", "```text", summary["submission_sha256"], "```", "",
              "```bash", "python3 scripts/prepare_submission_004.py", "python3 scripts/verify_submission_004.py", "```", "",
              "Configuration, summary, model/input hashes, the preparation-time score snapshot, comparison tables and verification are saved here. Next planned comparison is 005: the exact rules ablation from 001, with MF/PPR weights unchanged. Only 004 is prepared in this stage.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Passed {len(checks)} checks. READY: {submission}")
    print(f"SHA-256: {sha256(submission)}")


if __name__ == "__main__":
    main()
