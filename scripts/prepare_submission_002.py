#!/usr/bin/env python3
"""Prepare only 002: replace half of 001's rules weight with popularity."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from hybrid_models import reciprocal_rank_fusion
from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_002"
SUBMISSION = ROOT / "submissions/submission_002.csv"


def fuse(lists, config, popularity):
    pop_rank = {item: rank for rank, item in enumerate(popularity)}
    union = set(popularity[:5]).union(*(lists[m] for m in config["weights"]))
    return reciprocal_rank_fusion(lists, config["weights"], sorted(union, key=pop_rank.__getitem__), config["offset"])[0]


def main():
    plan_path = ROOT / "scripts/kaggle_comparison_plan.json"
    plan = json.loads(plan_path.read_text())
    candidate = next(r for r in plan["submissions"] if r["id"] == "submission_002")
    config = candidate["strategy"]
    paths = {"plan": plan_path, "ledger": ROOT / "submissions/results.json",
             "template": ROOT / "sweettv-tv-program-recommender/submission.csv",
             "anchor_csv": ROOT / "submissions/submission_001.csv",
             "training_manifest": ROOT / "reports/final_11_30/summary.json",
             "training_verification": ROOT / "reports/final_11_30/verification.json",
             "test_candidates": ROOT / "reports/final_11_30/test_candidates.csv",
             "popularity": ROOT / "artifacts/final_11_30/candidate_scores.csv",
             "cold_users": ROOT / "artifacts/final_11_30/cold_users.json",
             "history": ROOT / "artifacts/final_11_30/history.json",
             "model_scores": ROOT / "artifacts/final_11_30/scores.npz",
             "model_users": ROOT / "artifacts/final_11_30/users.json",
             "validation_comparison": ROOT / candidate["validation_comparison"],
             "validation_config": ROOT / "reports/hybrids/runs" / config["id"] / "config.json"}
    for method in config["weights"]:
        paths[f"component_{method}"] = ROOT / "reports/final_11_30" / f"component_{method}.csv"
    before = {key: digest(path) for key, path in paths.items()}
    if before["anchor_csv"] != plan["anchor"]["csv_sha256"]:
        raise AssertionError("Scored submission_001 has changed")
    training = json.loads(paths["training_manifest"].read_text())
    verified = json.loads(paths["training_verification"].read_text())
    if verified["status"] != "passed" or verified["submission_sha256"] != before["anchor_csv"] or training["submission_sha256"] != before["anchor_csv"]:
        raise AssertionError("First model verification does not match scored anchor")
    if json.loads(paths["validation_config"].read_text()) != config:
        raise AssertionError("002 config differs from the already validated configuration")
    local = pd.read_csv(paths["validation_comparison"])
    local = local.loc[local.run_id == config["id"]].set_index("cohort")
    for cohort, expected in [("all_primary", candidate["validation_primary"]), ("template_primary", candidate["validation_template"])]:
        if abs(local.loc[cohort, "map_at_5"]-expected) > 1e-12:
            raise AssertionError("Declared local score differs from saved comparison")
    template = pd.read_csv(paths["template"], dtype=str, keep_default_na=False)
    users = template.user_id.tolist()
    if template.columns.tolist() != ["user_id", "tv_show_id"] or len(users) != len(set(users)) or len(users) != 1260:
        raise AssertionError("Unexpected template")
    pop_rows = pd.read_csv(paths["popularity"]).sort_values("rank")
    popularity = pop_rows.tv_show_id.astype(int).tolist()
    pool = set(popularity)
    if len(popularity) != len(pool) or pool != set(pd.read_csv(paths["test_candidates"]).tv_show_id):
        raise AssertionError("Changed availability")
    components = {m: read_rankings(paths[f"component_{m}"]) for m in config["weights"]}
    for method, predictions in components.items():
        if set(predictions) != set(users) or any(len(ids) != 5 or len(set(ids)) != 5 or not set(ids) <= pool for ids in predictions.values()):
            raise AssertionError(f"Invalid component: {method}")
    anchor = read_rankings(paths["anchor_csv"])
    history = json.loads(paths["history"].read_text())
    cold = set(json.loads(paths["cold_users"].read_text()))
    predictions, changes, trace = {}, [], []
    for user in users:
        lists = {m: source[user] for m, source in components.items()}
        if fuse(lists, training["selected_config"], popularity) != anchor[user]:
            raise AssertionError("Existing components do not reproduce scored submission_001")
        ids = fuse(lists, config, popularity)
        if len(ids) != 5 or len(set(ids)) != 5 or not set(ids) <= pool or (user in cold and ids != popularity[:5]):
            raise AssertionError("Invalid 002 prediction or cold fallback")
        predictions[user] = ids
        entered, removed = set(ids)-set(anchor[user]), set(anchor[user])-set(ids)
        changes.append({"user_id": user, "anchor_ids": " ".join(map(str, anchor[user])), "new_ids": " ".join(map(str, ids)),
                        "changed_order": ids != anchor[user], "changed_set": set(ids) != set(anchor[user]), "shared_top5": len(set(ids)&set(anchor[user])),
                        "entered_ids": " ".join(map(str, sorted(entered))), "removed_ids": " ".join(map(str, sorted(removed))),
                        "new_items": len(entered), "changed_positions": sum(a != b for a, b in zip(ids, anchor[user])),
                        "anchor_familiar_slots": sum(i in set(history[user]) for i in anchor[user]), "new_familiar_slots": sum(i in set(history[user]) for i in ids)})
        for rank, item in enumerate(ids, 1):
            row = {"user_id": user, "rank": rank, "tv_show_id": item, "familiar_training_80pct": item in set(history[user]), "cold": user in cold}
            row.update({f"{m}_rank": source.index(item)+1 if item in source else 0 for m, source in lists.items()})
            trace.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    output = pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predictions[u])) for u in users]})
    output.to_csv(SUBMISSION, index=False)
    pd.DataFrame(trace).to_csv(OUT / "recommendations.csv", index=False)
    change_frame = pd.DataFrame(changes)
    change_frame.to_csv(OUT / "changes_vs_001.csv", index=False)
    dump(OUT / "config.json", config)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    dump(OUT / "plan.json", plan)
    summary = {"submission_id": "submission_002", "selected_id": config["id"], "selected_config": config,
               "submission_path": str(SUBMISSION.relative_to(ROOT)), "submission_sha256": digest(SUBMISSION),
               "anchor_path": plan["anchor"]["id"]+".csv", "anchor_sha256": before["anchor_csv"], "training": "Reuse identical verified weeks 11-30 fits; no training changes",
               "validation_source": {"comparison": candidate["validation_comparison"], "run_id": config["id"], "all_primary": candidate["validation_primary"], "template_primary": candidate["validation_template"]},
               "template_users": len(users), "candidates": len(pool), "cold_users": len(cold),
               "changed_ordered_users": int(change_frame.changed_order.sum()), "changed_set_users": int(change_frame.changed_set.sum()),
               "order_only_users": int((change_frame.changed_order & ~change_frame.changed_set).sum()), "unchanged_users": int((~change_frame.changed_order).sum()),
               "replaced_user_item_pairs": int(change_frame.new_items.sum()), "mean_shared_top5": float(change_frame.shared_top5.mean()),
               "changed_positions": int(change_frame.changed_positions.sum()), "difference_in_familiar_slots": int((change_frame.new_familiar_slots-change_frame.anchor_familiar_slots).sum()),
               "kaggle_status": "Prepared only; awaiting user upload and returned score", "created_csvs": [str(SUBMISSION.relative_to(ROOT))],
               "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["prepare_submission_002.py", "hybrid_models.py"]}}
    dump(OUT / "summary.json", summary)
    if before != {key: digest(path) for key, path in paths.items()}:
        raise AssertionError("Frozen inputs or anchor changed")
    print(f"Prepared only {SUBMISSION}: {len(users)} users, {summary['changed_ordered_users']} changed lists, {summary['changed_set_users']} changed sets.")
    print(f"SHA-256: {summary['submission_sha256']}")


if __name__ == "__main__":
    main()
