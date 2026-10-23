#!/usr/bin/env python3
"""Verify the locally frozen refinement and all-history submission 006."""

import csv
import json
from pathlib import Path

from verify_hybrid_experiments import rankings, read_csv, sha256
from verify_refinement_study import exact_depth_fusion, verify_component_orders, verify_recency

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_006"
ART = ROOT / "artifacts/submission_006"


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
    selected = json.loads(paths["selection"].read_text())
    config = summary["selected_config"]
    local_check = json.loads(paths["local_verification"].read_text())
    check("verified local selection frozen before refitting", local_check["status"] == "passed" and selected == json.loads((OUT / "selection_frozen_before_refit.json").read_text()) and config == selected["selected_config"] == json.loads((OUT / "config.json").read_text()) and selected["public_private_scores_used_by_selector"] is False and summary["public_private_scores_used_for_selection"] is False)
    for path, expected in local_check["verified_outputs_sha256"].items():
        check(f"locally verified output retained: {path}", sha256(ROOT / path) == expected)
    check("final configuration belongs to the declared local study", config in json.loads(paths["plan"].read_text())["runs"])
    check("final fit/inference code fingerprints", all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    records = {r["submission_id"]: r for r in json.loads(paths["score_snapshot"].read_text())["results"]}
    expected = {"submission_001": (.43347, .41452), "submission_002": (.43359, .41489), "submission_003": (.43042, .41260),
                "submission_004": (.42643, .40943), "submission_005": (.43163, .41039)}
    for name, scores in expected.items():
        record = records[name]
        check(f"exact earlier scored CSV and reported scores: {name}", (record["public_score"], record["private_score"]) == scores and sha256(ROOT / record["csv_path"]) == record["csv_sha256"])
        check(f"retained screenshot: {name}", sha256(ROOT / record["screenshot_path"]) == record["screenshot_sha256"])
    submission = ROOT / summary["submission_path"]
    with submission.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.reader(stream))
    users = [r["user_id"] for r in read_csv(paths["template"])]
    check("exact original two-column schema, no index", raw[0] == ["user_id", "tv_show_id"] and all(len(r) == 2 for r in raw[1:]))
    check("1260 exact original decimal user strings/order", len(raw)-1 == len(users) == len(set(users)) == 1260 and [r[0] for r in raw[1:]] == users and all(str(int(u)) == u for u in users))
    check("five distinct canonical positive integer programme IDs", all(len(r[1].split()) == len(set(r[1].split())) == 5 and r[1] == " ".join(r[1].split()) and all(i.isdecimal() and int(i) > 0 and str(int(i)) == i for i in r[1].split()) for r in raw[1:]))
    check("CSV identity and genuinely new upload", sha256(submission) == summary["submission_sha256"] and all(sha256(submission) != r["csv_sha256"] for r in records.values()))
    if config["half_life_weeks"] is not None:
        verify_recency(ART, paths, "final", check)
        check("same half-life and correct final cutoff", json.loads((ART / "recency.json").read_text())["half_life_weeks"] == config["half_life_weeks"] and summary["training_cutoff_local_exclusive"] == "2020-07-27")
    ordered_users, pop, cold, components = verify_component_orders(ART, check)
    check("same template/candidate availability/four cold users", users == ordered_users and len(pop) == 6632 and set(pop) == {int(r["tv_show_id"]) for r in read_csv(paths["test_candidates"])} and len(cold) == 4)
    check("original unweighted popularity preserved byte-for-byte", (ART / "candidate_scores.csv").read_bytes() == paths["popularity"].read_bytes())
    check("original strict training history unchanged", json.loads((ART / "history.json").read_text()) == json.loads((ROOT / "artifacts/final_11_30/history.json").read_text()))
    predicted = rankings(submission)
    pop_rank = {item: n for n, item in enumerate(pop)}
    check("all final RRF ranks independently reconstructed", all(predicted[u] == exact_depth_fusion(components, u, config, pop_rank) for u in users))
    check("all five IDs eligible and exact cold fallback", all(set(ids) <= set(pop) for ids in predicted.values()) and all(predicted[u] == pop[:5] for u in cold))
    contrasts = {r["reference"]: r for r in summary["comparisons"]}
    for name, result in records.items():
        previous = rankings(ROOT / result["csv_path"])
        rows = read_csv(OUT / f"changes_vs_{name}.csv")
        check(f"exact change-table user coverage: {name}", len(rows) == len(users) and [r["user_id"] for r in rows] == users)
        for row in rows:
            user = row["user_id"]
            a, b = previous[user], predicted[user]
            assert row["previous_ids"] == " ".join(map(str, a)) and row["new_ids"] == " ".join(map(str, b))
            assert (row["changed_order"] == "True") == (a != b) and (row["changed_set"] == "True") == (set(a) != set(b))
            assert row["entered_ids"] == " ".join(map(str, sorted(set(b)-set(a)))) and row["removed_ids"] == " ".join(map(str, sorted(set(a)-set(b)))) and int(row["shared_top5"]) == len(set(a)&set(b))
        changed = sum(previous[u] != predicted[u] for u in users)
        changed_set = sum(set(previous[u]) != set(predicted[u]) for u in users)
        check(f"every change and summary counter reconstructed: {name}", contrasts[name]["changed_ordered_users"] == changed and contrasts[name]["changed_set_users"] == changed_set and contrasts[name]["order_only_users"] == changed-changed_set and contrasts[name]["unchanged_users"] == len(users)-changed and contrasts[name]["entered_user_item_pairs"] == sum(len(set(predicted[u])-set(previous[u])) for u in users))
    trace = read_csv(OUT / "recommendations.csv")
    check("recommendation trace matches submitted ranks and source-component ranks", len(trace) == 5*len(users) and all(predicted[r["user_id"]][int(r["rank"])-1] == int(r["tv_show_id"]) and all(int(r[f"{m}_rank"]) == (components[m][r["user_id"]][:config["depth"]].index(int(r["tv_show_id"]))+1 if int(r["tv_show_id"]) in components[m][r["user_id"]][:config["depth"]] else 0) for m in config["weights"]) for r in trace))
    report = {"status": "passed", "submission_path": summary["submission_path"], "submission_sha256": sha256(submission), "checks": checks,
              "verifier_sha256": sha256(Path(__file__)), "kaggle_score": None, "meaning": "Assistant verification; 006 actual returned score pending"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(f"Passed {len(checks)} checks. READY: {submission}")
    print(f"SHA-256: {sha256(submission)}")


if __name__ == "__main__":
    main()
