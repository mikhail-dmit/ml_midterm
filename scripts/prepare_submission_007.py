#!/usr/bin/env python3
"""Prepare one upload from the frozen primary-validation extension winner."""

import json
from pathlib import Path

import pandas as pd

from evaluate_rankings import read_rankings
from prepare_submission_002 import fuse
from recency_extension import SPEC_KEYS, compose_bundle
from refinement_models import fuse_bundle, phase_paths
from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_007"
ART = ROOT / "artifacts/submission_007"
SUBMISSION = ROOT / "submissions/submission_007.csv"


def main():
    selection_path = ROOT / "reports/recency_extension/selection.json"
    verification_path = ROOT / "reports/recency_extension/verification.json"
    selected = json.loads(selection_path.read_text())
    verified = json.loads(verification_path.read_text())
    if verified["status"] != "passed" or selected["public_private_scores_used_by_selector"] is not False:
        raise AssertionError("Need a verified primary-only local selection")
    if any(digest(ROOT / path) != h for path, h in verified["verified_outputs_sha256"].items()):
        raise AssertionError("Verified local outputs changed")
    plan_path = ROOT / "scripts/recency_extension_plan.json"
    plan = json.loads(plan_path.read_text())
    config = selected["selected_config"]
    if config not in plan["runs"]:
        raise AssertionError("Selected configuration was not predeclared")
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    dump(OUT / "selection_frozen_before_inference.json", selected)
    dump(OUT / "plan.json", plan)
    ledger = json.loads((ROOT / "submissions/results.json").read_text())
    dump(OUT / "results_at_preparation.json", ledger)
    paths = phase_paths("final")
    paths.update(plan=plan_path, selection=selection_path, local_verification=verification_path,
                 template=ROOT / "sweettv-tv-program-recommender/submission.csv", score_snapshot=OUT / "results_at_preparation.json",
                 test_candidates=ROOT / "reports/final_11_30/test_candidates.csv",
                 control_scores=ROOT / "artifacts/submission_006/scores.npz", control_config=ROOT / "reports/submission_006/config.json")
    for method in ["implicit_mf", "ppr", "association_rules", "popularity"]:
        paths[f"control_{method}"] = ROOT / "artifacts/submission_006" / f"component_{method}_top20.csv"
    for record in ledger["results"]:
        paths[f"scored_{record['submission_id']}"] = ROOT / record["csv_path"]
    before = {name: digest(path) for name, path in paths.items()}
    for record in ledger["results"]:
        if before[f"scored_{record['submission_id']}"] != record["csv_sha256"]:
            raise AssertionError("A scored CSV changed")
    bundle = compose_bundle("final", config, ART, ART / "cf_cache", plan["seed"])
    prior006 = read_rankings(paths["scored_submission_006"])
    control_components = {m: read_rankings(paths[f"control_{m}"]) for m in ["implicit_mf", "ppr", "association_rules", "popularity"]}
    for user in bundle.users:
        lists = {m: source[user][:5] for m, source in control_components.items()}
        if fuse(lists, plan["control"], bundle.popularity) != prior006[user]:
            raise AssertionError("006 sources do not reproduce the scored control")
    predictions = fuse_bundle(bundle, config)
    template = pd.read_csv(paths["template"], dtype=str, keep_default_na=False)
    users = template.user_id.tolist()
    if bundle.users != users or template.columns.tolist() != ["user_id", "tv_show_id"] or len(users) != len(set(users)) or len(users) != 1260:
        raise AssertionError("Template mismatch")
    if {k: config[k] for k in SPEC_KEYS} == {k: plan["control"][k] for k in SPEC_KEYS}:
        for method, previous in control_components.items():
            if {u: bundle.queues[n][method]["global"] for n, u in enumerate(users)} != previous:
                raise AssertionError("Weight-only change altered a component")
    pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predictions[u])) for u in users]}).to_csv(SUBMISSION, index=False)
    if any(digest(SUBMISSION) == record["csv_sha256"] for record in ledger["results"]):
        raise AssertionError("Candidate duplicates a previously scored file")
    traces = []
    for row, user in enumerate(users):
        for rank, item in enumerate(predictions[user], 1):
            record = {"user_id": user, "rank": rank, "tv_show_id": item, "cold": user not in bundle.warm,
                      "familiar_training_80pct": item in bundle.seen.get(user, set())}
            for method in config["weights"]:
                ids = bundle.queues[row][method]["global"][:config["depth"]]
                record[f"{method}_rank"] = ids.index(item)+1 if item in ids else 0
                record[f"{method}_score"] = bundle.score(method, row, item)
            traces.append(record)
    pd.DataFrame(traces).to_csv(OUT / "recommendations.csv", index=False)
    contrasts = []
    for result in ledger["results"]:
        name = result["submission_id"]
        previous = read_rankings(ROOT / result["csv_path"])
        records = []
        for user in users:
            a, b = previous[user], predictions[user]
            records.append({"user_id": user, "previous_ids": " ".join(map(str, a)), "new_ids": " ".join(map(str, b)),
                            "changed_order": a != b, "changed_set": set(a) != set(b), "shared_top5": len(set(a)&set(b)),
                            "entered_ids": " ".join(map(str, sorted(set(b)-set(a)))), "removed_ids": " ".join(map(str, sorted(set(a)-set(b))))})
        frame = pd.DataFrame(records)
        frame.to_csv(OUT / f"changes_vs_{name}.csv", index=False)
        contrasts.append({"reference": name, "changed_ordered_users": int(frame.changed_order.sum()), "changed_set_users": int(frame.changed_set.sum()),
                          "order_only_users": int((frame.changed_order & ~frame.changed_set).sum()), "unchanged_users": int((~frame.changed_order).sum()),
                          "mean_shared_top5": float(frame.shared_top5.mean()), "entered_user_item_pairs": int(sum(5-n for n in frame.shared_top5))})
    dump(OUT / "config.json", config)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    dump(OUT / "summary.json", {"submission_id": "submission_007", "selected_id": config["id"], "selected_config": config,
         "submission_path": str(SUBMISSION.relative_to(ROOT)), "submission_sha256": digest(SUBMISSION),
         "selection_rule": selected["selection_rule"], "validation_primary": selected["primary_MAP"], "validation_template": selected["template_MAP"],
         "training": "All weeks 11-30, unchanged parameters; selected component specification applied using the original cutoffs",
         "weight_only_change_from_006": {k: config[k] for k in SPEC_KEYS} == {k: plan["control"][k] for k in SPEC_KEYS},
         "template_users": len(users), "candidates": len(bundle.pool), "cold_users": sum(u not in bundle.warm for u in users),
         "comparisons": contrasts, "public_private_scores_used_for_selection": False, "kaggle_status": "Prepared; returned score pending user upload",
         "created_csvs": [str(SUBMISSION.relative_to(ROOT))], "code_hashes": {f: digest(ROOT / "scripts" / f) for f in ["prepare_submission_007.py", "recency_extension.py", "refinement_models.py", "hybrid_models.py", "recommender_bundle.py"]}})
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Frozen input or scored file changed")
    print(f"Prepared {SUBMISSION}: {config['id']}, selected by local primary MAP only.")
    print(f"SHA-256: {digest(SUBMISSION)}")
    print(pd.DataFrame(contrasts).to_string(index=False))


if __name__ == "__main__":
    main()
