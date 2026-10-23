#!/usr/bin/env python3
"""Prepare only 004: the existing all-history standalone MF component."""

import json
from pathlib import Path

import pandas as pd

from evaluate_rankings import read_rankings
from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_004"
ART = ROOT / "artifacts/final_11_30"
SUBMISSION = ROOT / "submissions/submission_004.csv"


def main():
    plan_path = ROOT / "scripts/kaggle_comparison_plan.json"
    plan = json.loads(plan_path.read_text())
    candidate = next(r for r in plan["submissions"] if r["id"] == "submission_004")
    config = candidate["strategy"]
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((ROOT / "submissions/results.json").read_text())
    dump(OUT / "results_at_preparation.json", ledger)
    paths = {"plan": plan_path, "score_snapshot": OUT / "results_at_preparation.json",
             "template": ROOT / "sweettv-tv-program-recommender/submission.csv",
             "component_mf": ROOT / "reports/final_11_30/component_implicit_mf.csv",
             "training_manifest": ROOT / "reports/final_11_30/summary.json",
             "training_verification": ROOT / "reports/final_11_30/verification.json",
             "scores": ART / "scores.npz", "model_users": ART / "users.json", "factors": ART / "factors.npz",
             "training_indices": ART / "indices_50.json", "training_counts": ART / "training_counts_50.parquet",
             "popularity": ART / "candidate_scores.csv", "cold_users": ART / "cold_users.json", "history": ART / "history.json",
             "candidates": ROOT / "reports/final_11_30/test_candidates.csv",
             "validation_comparison": ROOT / candidate["validation_comparison"],
             "validation_config": ROOT / "reports/semantic_hybrids/runs/implicit_mf/config.json"}
    for result in ledger["results"]:
        paths[f"scored_{result['submission_id']}"] = ROOT / result["csv_path"]
    before = {name: digest(path) for name, path in paths.items()}
    if json.loads(paths["validation_config"].read_text()) != config:
        raise AssertionError("004 differs from the declared standalone MF")
    training = json.loads(paths["training_manifest"].read_text())
    if json.loads(paths["training_verification"].read_text())["status"] != "passed":
        raise AssertionError("Original full-history fit not verified")
    if any(digest(Path(__file__).parent / f) != h for f, h in training["code_hashes"].items()):
        raise AssertionError("Fitted-model code changed")
    for result in ledger["results"]:
        if before[f"scored_{result['submission_id']}"] != result["csv_sha256"]:
            raise AssertionError("A scored submission changed")
    local = pd.read_csv(paths["validation_comparison"])
    local = local.loc[local.run_id == config["id"]].set_index("cohort")
    for cohort, expected in [("all_primary", candidate["validation_primary"]), ("template_primary", candidate["validation_template"])]:
        if abs(local.loc[cohort, "map_at_5"]-expected) > 1e-12:
            raise AssertionError("Local MF score differs from the declared plan")
    template = pd.read_csv(paths["template"], dtype=str, keep_default_na=False)
    component = pd.read_csv(paths["component_mf"], dtype=str, keep_default_na=False)
    users = template.user_id.tolist()
    if template.columns.tolist() != ["user_id", "tv_show_id"] or len(users) != len(set(users)) or len(users) != 1260:
        raise AssertionError("Unexpected template")
    if component.columns.tolist() != template.columns.tolist() or component.user_id.tolist() != users:
        raise AssertionError("Component schema/order differs from template")
    predictions = read_rankings(paths["component_mf"])
    pool = set(pd.read_csv(paths["candidates"]).tv_show_id.astype(int))
    pop_rows = pd.read_csv(paths["popularity"]).sort_values("rank")
    pop = pop_rows.tv_show_id.astype(int).tolist()
    cold = set(json.loads(paths["cold_users"].read_text()))
    if any(len(ids) != 5 or len(set(ids)) != 5 or not set(ids) <= pool for ids in predictions.values()):
        raise AssertionError("Invalid MF predictions")
    if any(predictions[u] != pop[:5] for u in cold):
        raise AssertionError("Cold fallback changed")
    component.to_csv(SUBMISSION, index=False)
    if digest(SUBMISSION) != before["component_mf"]:
        raise AssertionError("Standalone upload must be byte-identical to the saved MF component")
    contrasts = []
    for result in ledger["results"]:
        name = result["submission_id"]
        old = read_rankings(ROOT / result["csv_path"])
        rows = []
        for user in users:
            a, b = old[user], predictions[user]
            rows.append({"user_id": user, "previous_ids": " ".join(map(str, a)), "new_ids": " ".join(map(str, b)),
                         "changed_order": a != b, "changed_set": set(a) != set(b), "shared_top5": len(set(a)&set(b)),
                         "entered_ids": " ".join(map(str, sorted(set(b)-set(a)))), "removed_ids": " ".join(map(str, sorted(set(a)-set(b))))})
        frame = pd.DataFrame(rows)
        frame.to_csv(OUT / f"changes_vs_{name}.csv", index=False)
        contrasts.append({"reference": name, "changed_ordered_users": int(frame.changed_order.sum()), "changed_set_users": int(frame.changed_set.sum()),
                          "order_only_users": int((frame.changed_order & ~frame.changed_set).sum()), "unchanged_users": int((~frame.changed_order).sum()),
                          "mean_shared_top5": float(frame.shared_top5.mean()), "entered_user_item_pairs": int(sum(5-n for n in frame.shared_top5))})
    dump(OUT / "config.json", config)
    dump(OUT / "plan.json", plan)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    summary = {"submission_id": "submission_004", "selected_id": config["id"], "selected_config": config,
               "submission_path": str(SUBMISSION.relative_to(ROOT)), "submission_sha256": digest(SUBMISSION),
               "training": "Reuse the identical weeks 11-30 MF fit; no refitting, new seed or parameter changes",
               "validation_source": {"comparison": candidate["validation_comparison"], "run_id": config["id"], "all_primary": candidate["validation_primary"], "template_primary": candidate["validation_template"]},
               "template_users": len(users), "candidates": len(pool), "cold_users": len(cold), "comparisons": contrasts,
               "source_component_sha256": before["component_mf"], "kaggle_status": "Prepared; awaiting user upload and returned scores",
               "created_csvs": [str(SUBMISSION.relative_to(ROOT))], "code_hashes": {"prepare_submission_004.py": digest(Path(__file__))}}
    dump(OUT / "summary.json", summary)
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Inputs or scored submissions changed")
    print(f"Prepared {SUBMISSION}: standalone MF, byte-identical to the existing verified component.")
    print(f"SHA-256: {summary['submission_sha256']}")
    print(pd.DataFrame(contrasts).to_string(index=False))


if __name__ == "__main__":
    main()
