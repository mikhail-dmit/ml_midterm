#!/usr/bin/env python3
"""Prepare the planned rules ablation: unchanged MF/PPR Top-5 RRF only."""

import json
from pathlib import Path

import pandas as pd

from evaluate_rankings import read_rankings
from prepare_submission_002 import fuse
from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_005"
ART = ROOT / "artifacts/final_11_30"
SUBMISSION = ROOT / "submissions/submission_005.csv"


def main():
    plan_path = ROOT / "scripts/kaggle_comparison_plan.json"
    plan = json.loads(plan_path.read_text())
    candidate = next(r for r in plan["submissions"] if r["id"] == "submission_005")
    config = candidate["strategy"]
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = json.loads((ROOT / "submissions/results.json").read_text())
    dump(OUT / "results_at_preparation.json", ledger)
    paths = {"plan": plan_path, "score_snapshot": OUT / "results_at_preparation.json",
             "template": ROOT / "sweettv-tv-program-recommender/submission.csv",
             "training_manifest": ROOT / "reports/final_11_30/summary.json",
             "training_verification": ROOT / "reports/final_11_30/verification.json",
             "scores": ART / "scores.npz", "model_users": ART / "users.json",
             "popularity": ART / "candidate_scores.csv", "cold_users": ART / "cold_users.json", "history": ART / "history.json",
             "candidates": ROOT / "reports/final_11_30/test_candidates.csv",
             "validation_comparison": ROOT / candidate["validation_comparison"],
             "validation_config": ROOT / "reports/hybrids/runs" / config["id"] / "config.json"}
    for method in ["implicit_mf", "ppr", "association_rules"]:
        paths[f"component_{method}"] = ROOT / "reports/final_11_30" / f"component_{method}.csv"
    for result in ledger["results"]:
        paths[f"scored_{result['submission_id']}"] = ROOT / result["csv_path"]
    before = {name: digest(path) for name, path in paths.items()}
    if config != json.loads(paths["validation_config"].read_text()):
        raise AssertionError("005 differs from the previously validated rules ablation")
    training = json.loads(paths["training_manifest"].read_text())
    if json.loads(paths["training_verification"].read_text())["status"] != "passed":
        raise AssertionError("Original full-history fit not verified")
    if any(digest(Path(__file__).parent / f) != h for f, h in training["code_hashes"].items()):
        raise AssertionError("Original fitted-model code changed")
    for result in ledger["results"]:
        if before[f"scored_{result['submission_id']}"] != result["csv_sha256"]:
            raise AssertionError("A scored CSV changed")
    local = pd.read_csv(paths["validation_comparison"])
    local = local.loc[local.run_id == config["id"]].set_index("cohort")
    for cohort, expected in [("all_primary", candidate["validation_primary"]), ("template_primary", candidate["validation_template"])]:
        if abs(local.loc[cohort, "map_at_5"]-expected) > 1e-12:
            raise AssertionError("Declared local score changed")
    template = pd.read_csv(paths["template"], dtype=str, keep_default_na=False)
    users = template.user_id.tolist()
    if template.columns.tolist() != ["user_id", "tv_show_id"] or len(users) != len(set(users)) or len(users) != 1260:
        raise AssertionError("Unexpected template")
    pop = pd.read_csv(paths["popularity"]).sort_values("rank").tv_show_id.astype(int).tolist()
    pool = set(pop)
    if len(pop) != len(pool) or pool != set(pd.read_csv(paths["candidates"]).tv_show_id.astype(int)):
        raise AssertionError("Availability changed")
    components = {m: read_rankings(paths[f"component_{m}"]) for m in ["implicit_mf", "ppr", "association_rules"]}
    for method, output in components.items():
        if set(output) != set(users) or any(len(ids) != 5 or len(set(ids)) != 5 or not set(ids) <= pool for ids in output.values()):
            raise AssertionError(f"Invalid component {method}")
    anchor = read_rankings(paths["scored_submission_001"])
    cold = set(json.loads(paths["cold_users"].read_text()))
    history = json.loads(paths["history"].read_text())
    predictions, trace = {}, []
    for user in users:
        lists = {m: source[user] for m, source in components.items()}
        if fuse(lists, training["selected_config"], pop) != anchor[user]:
            raise AssertionError("Unchanged components do not reproduce scored 001")
        ids = fuse(lists, config, pop)
        if len(ids) != len(set(ids)) or len(ids) != 5 or not set(ids) <= pool or (user in cold and ids != pop[:5]):
            raise AssertionError("Invalid fusion or changed cold fallback")
        predictions[user] = ids
        for rank, item in enumerate(ids, 1):
            record = {"user_id": user, "rank": rank, "tv_show_id": item,
                      "familiar_training_80pct": item in set(history[user]), "cold": user in cold}
            record.update({f"{m}_rank": source.index(item)+1 if item in source else 0 for m, source in lists.items()})
            trace.append(record)
    pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predictions[u])) for u in users]}).to_csv(SUBMISSION, index=False)
    pd.DataFrame(trace).to_csv(OUT / "recommendations.csv", index=False)
    comparisons = []
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
        comparisons.append({"reference": name, "changed_ordered_users": int(frame.changed_order.sum()), "changed_set_users": int(frame.changed_set.sum()),
                            "order_only_users": int((frame.changed_order & ~frame.changed_set).sum()), "unchanged_users": int((~frame.changed_order).sum()),
                            "mean_shared_top5": float(frame.shared_top5.mean()), "entered_user_item_pairs": int(sum(5-n for n in frame.shared_top5))})
    dump(OUT / "config.json", config)
    dump(OUT / "plan.json", plan)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    summary = {"submission_id": "submission_005", "selected_id": config["id"], "selected_config": config,
               "submission_path": str(SUBMISSION.relative_to(ROOT)), "submission_sha256": digest(SUBMISSION),
               "training": "Reuse identical weeks 11-30 fits; remove only the .25 rules term from 001",
               "validation_source": {"comparison": candidate["validation_comparison"], "run_id": config["id"], "all_primary": candidate["validation_primary"], "template_primary": candidate["validation_template"]},
               "template_users": len(users), "candidates": len(pool), "cold_users": len(cold), "comparisons": comparisons,
               "ablation_reference": "submission_001", "kaggle_status": "Prepared; awaiting user upload and returned scores",
               "created_csvs": [str(SUBMISSION.relative_to(ROOT))],
               "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["prepare_submission_005.py", "prepare_submission_002.py", "hybrid_models.py"]}}
    dump(OUT / "summary.json", summary)
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Inputs or scored uploads changed")
    print(f"Prepared {SUBMISSION}: MF .5 / PPR .5, RRF offset 0; rules removed from 001.")
    print(f"SHA-256: {summary['submission_sha256']}")
    print(pd.DataFrame(comparisons).to_string(index=False))


if __name__ == "__main__":
    main()
