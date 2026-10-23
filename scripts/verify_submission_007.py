#!/usr/bin/env python3
"""Independently verify the frozen existing-method extension and upload 007."""

import csv
import json
from pathlib import Path

import numpy as np

from verify_hybrid_experiments import rankings, read_csv, sha256
from verify_recency_extension import SPEC_KEYS, verify_extension_bundle
from verify_refinement_study import exact_depth_fusion, verify_recency

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_007"
ART = ROOT / "artifacts/submission_007"


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    frozen = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in frozen["paths"].items()}
    for name, path in paths.items():
        check(f"unchanged source: {name}", sha256(path) == frozen["sha256"][name])
    summary = json.loads((OUT / "summary.json").read_text())
    selection = json.loads(paths["selection"].read_text())
    local_check = json.loads(paths["local_verification"].read_text())
    config = summary["selected_config"]
    check("verified primary-only selection frozen before inference", local_check["status"] == "passed" and selection == json.loads((OUT / "selection_frozen_before_inference.json").read_text()) and config == selection["selected_config"] == json.loads((OUT / "config.json").read_text()) and selection["public_private_scores_used_by_selector"] is False and summary["public_private_scores_used_for_selection"] is False)
    for path, value in local_check["verified_outputs_sha256"].items():
        check(f"locally verified output retained: {path}", sha256(ROOT / path) == value)
    plan = json.loads(paths["plan"].read_text())
    check("configuration belongs to predeclared existing-method grid", config in plan["runs"] and set(config["weights"]) <= {"implicit_mf", "ppr", "association_rules", "popularity"})
    check("final inference code fingerprints", all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    records = {r["submission_id"]: r for r in json.loads(paths["score_snapshot"].read_text())["results"]}
    expected = {"submission_001": (.43347, .41452), "submission_002": (.43359, .41489), "submission_003": (.43042, .41260),
                "submission_004": (.42643, .40943), "submission_005": (.43163, .41039), "submission_006": (.43662, .42340)}
    for name, scores in expected.items():
        record = records[name]
        check(f"exact recorded score and earlier CSV: {name}", (record["public_score"], record["private_score"]) == scores and sha256(ROOT / record["csv_path"]) == record["csv_sha256"])
        check(f"score screenshot retained: {name}", sha256(ROOT / record["screenshot_path"]) == record["screenshot_sha256"])
    submitted = ROOT / summary["submission_path"]
    with submitted.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.reader(stream))
    users = [r["user_id"] for r in read_csv(paths["template"])]
    check("exact two-column template schema without index", raw[0] == ["user_id", "tv_show_id"] and all(len(r) == 2 for r in raw[1:]))
    check("1260 exact decimal user strings in original order", len(raw)-1 == len(users) == len(set(users)) == 1260 and [r[0] for r in raw[1:]] == users and all(str(int(u)) == u for u in users))
    check("five unique canonical nonzero integer IDs per user", all(len(r[1].split()) == len(set(r[1].split())) == 5 and r[1] == " ".join(r[1].split()) and all(i.isdecimal() and int(i) > 0 and str(int(i)) == i for i in r[1].split()) for r in raw[1:]))
    check("new CSV identity and no duplicate upload", sha256(submitted) == summary["submission_sha256"] and all(sha256(submitted) != r["csv_sha256"] for r in records.values()))
    info = json.loads((ART / "extension.json").read_text())
    for folder in {ROOT / info["mf_source"], ROOT / info["ppr_source"]}:
        if (folder / "recency.json").exists():
            verify_recency(folder, paths, "final", check)
    ordered_users, pop, cold, components = verify_extension_bundle(ART, paths, "final", check)
    check("exact declared component specification", info["component_spec"] == {k: config[k] for k in SPEC_KEYS})
    check("same template, 6632 available IDs and four actual cold users", ordered_users == users and len(pop) == 6632 and set(pop) == {int(r["tv_show_id"]) for r in read_csv(paths["test_candidates"])} and len(cold) == 4)
    predictions = rankings(submitted)
    pop_rank = {item: n for n, item in enumerate(pop)}
    check("all final ranks reconstructed with exact rational fusion", all(predictions[u] == exact_depth_fusion(components, u, config, pop_rank) for u in users))
    check("eligible outputs and exact shared cold fallback", all(set(ids) <= set(pop) for ids in predictions.values()) and all(predictions[u] == pop[:5] for u in cold))
    baseline_components = {m: rankings(paths[f"control_{m}"]) for m in config["weights"]}
    old006 = rankings(paths["scored_submission_006"])
    check("006 sources still reproduce every scored control rank", all(old006[u] == exact_depth_fusion(baseline_components, u, plan["control"], pop_rank) for u in users))
    if summary["weight_only_change_from_006"]:
        check("same component recipe as 006", {k: config[k] for k in SPEC_KEYS} == {k: plan["control"][k] for k in SPEC_KEYS})
        current, original = np.load(ART / "scores.npz", allow_pickle=False), np.load(paths["control_scores"], allow_pickle=False)
        check("every MF/PPR/rule score and item index identical to 006", current.files == original.files and all(np.array_equal(current[name], original[name]) for name in current.files))
        check("all component Top-20 lists identical to 006", all(components[m] == baseline_components[m] for m in components))
        check("only rules/popularity budget changed, total auxiliary weight fixed", config["weights"]["implicit_mf"] == config["weights"]["ppr"] == .5 and config["weights"]["association_rules"] == .1875 and config["weights"]["popularity"] == .0625 and config["offset"] == plan["control"]["offset"] == 0 and config["depth"] == plan["control"]["depth"] == 5)
    contrasts = {r["reference"]: r for r in summary["comparisons"]}
    for name, record in records.items():
        previous = rankings(ROOT / record["csv_path"])
        rows = read_csv(OUT / f"changes_vs_{name}.csv")
        check(f"exact change-table cohort/order: {name}", len(rows) == len(users) and [r["user_id"] for r in rows] == users)
        for row in rows:
            user = row["user_id"]
            a, b = previous[user], predictions[user]
            assert row["previous_ids"] == " ".join(map(str, a)) and row["new_ids"] == " ".join(map(str, b))
            assert (row["changed_order"] == "True") == (a != b) and (row["changed_set"] == "True") == (set(a) != set(b))
            assert row["entered_ids"] == " ".join(map(str, sorted(set(b)-set(a)))) and row["removed_ids"] == " ".join(map(str, sorted(set(a)-set(b)))) and int(row["shared_top5"]) == len(set(a)&set(b))
        changed = sum(previous[u] != predictions[u] for u in users)
        changed_set = sum(set(previous[u]) != set(predictions[u]) for u in users)
        check(f"every comparison and aggregate count: {name}", contrasts[name]["changed_ordered_users"] == changed and contrasts[name]["changed_set_users"] == changed_set and contrasts[name]["order_only_users"] == changed-changed_set and contrasts[name]["unchanged_users"] == len(users)-changed and contrasts[name]["entered_user_item_pairs"] == sum(len(set(predictions[u])-set(previous[u])) for u in users))
    trace = read_csv(OUT / "recommendations.csv")
    check("recommendation traces match submitted and component ranks", len(trace) == 5*len(users) and all(predictions[r["user_id"]][int(r["rank"])-1] == int(r["tv_show_id"]) and all(int(r[f"{m}_rank"]) == (components[m][r["user_id"]][:config["depth"]].index(int(r["tv_show_id"]))+1 if int(r["tv_show_id"]) in components[m][r["user_id"]][:config["depth"]] else 0) for m in config["weights"]) for r in trace))
    report = {"status": "passed", "submission_path": summary["submission_path"], "submission_sha256": sha256(submitted), "checks": checks,
              "verifier_sha256": sha256(Path(__file__)), "kaggle_score": None, "meaning": "Assistant numerical verification; 007 returned score pending"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Passed {len(checks)} checks. READY: {submitted}")
    print(f"SHA-256: {sha256(submitted)}")


if __name__ == "__main__":
    main()
