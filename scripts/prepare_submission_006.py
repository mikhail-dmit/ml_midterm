#!/usr/bin/env python3
"""Apply the frozen local-validation winner to all past weeks 11-30."""

import json
from pathlib import Path

import pandas as pd

from evaluate_rankings import read_rankings
from refinement_models import fit_recency, fuse_bundle, load_base, phase_paths
from run_model_experiments import digest, dump
from run_refinement_study import save_components

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_006"
ART = ROOT / "artifacts/submission_006"
SUBMISSION = ROOT / "submissions/submission_006.csv"


def main():
    selection_path = ROOT / "reports/refinement/selection.json"
    verification_path = ROOT / "reports/refinement/verification.json"
    selected = json.loads(selection_path.read_text())
    verified = json.loads(verification_path.read_text())
    if verified["status"] != "passed" or selected["public_private_scores_used_by_selector"] is not False:
        raise AssertionError("Local selection must pass verification and ignore leaderboard scores")
    if any(digest(ROOT / p) != h for p, h in verified["verified_outputs_sha256"].items()):
        raise AssertionError("Verified local outputs changed")
    plan_path = Path(__file__).parent / "refinement_plan.json"
    plan = json.loads(plan_path.read_text())
    config = selected["selected_config"]
    if config not in plan["runs"]:
        raise AssertionError("Selected configuration was not declared")
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    dump(OUT / "selection_frozen_before_refit.json", selected)
    dump(OUT / "plan.json", plan)
    ledger = json.loads((ROOT / "submissions/results.json").read_text())
    dump(OUT / "results_at_preparation.json", ledger)
    paths = phase_paths("final")
    paths.update(plan=plan_path, selection=selection_path, local_verification=verification_path,
                 template=ROOT / "sweettv-tv-program-recommender/submission.csv", score_snapshot=OUT / "results_at_preparation.json",
                 original_training_manifest=ROOT / "reports/final_11_30/summary.json",
                 original_training_verification=ROOT / "reports/final_11_30/verification.json",
                 original_events_manifest=ROOT / "artifacts/final_11_30/events_manifest.json",
                 test_candidates=ROOT / "reports/final_11_30/test_candidates.csv")
    for record in ledger["results"]:
        paths[f"scored_{record['submission_id']}"] = ROOT / record["csv_path"]
    before = {name: digest(path) for name, path in paths.items()}
    for record in ledger["results"]:
        if before[f"scored_{record['submission_id']}"] != record["csv_sha256"]:
            raise AssertionError("Previously scored CSV changed")
    original = json.loads(paths["original_training_manifest"].read_text())
    if any(digest(Path(__file__).parent / name) != h for name, h in original["code_hashes"].items()):
        raise AssertionError("Original model inference code changed")
    base = load_base("final")[0]
    base.prepare_queues(depth=20)
    control002 = next(c for c in plan["controls"] if c["id"] == "control_002")
    if fuse_bundle(base, control002) != read_rankings(paths["scored_submission_002"]):
        raise AssertionError("Original fitted inputs no longer reproduce scored 002")
    del base
    half_life = config["half_life_weeks"]
    bundle = load_base("final")[0] if half_life is None else fit_recency("final", half_life, ART, plan["seed"])
    bundle.prepare_queues(depth=20)
    save_components(bundle, ART)
    predictions = fuse_bundle(bundle, config)
    template = pd.read_csv(paths["template"], dtype=str, keep_default_na=False)
    users = template.user_id.tolist()
    if bundle.users != users or template.columns.tolist() != ["user_id", "tv_show_id"] or len(set(users)) != len(users) or len(users) != 1260:
        raise AssertionError("Template/order mismatch")
    output = pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predictions[u])) for u in users]})
    output.to_csv(SUBMISSION, index=False)
    if any(digest(SUBMISSION) == record["csv_sha256"] for record in ledger["results"]):
        raise AssertionError("New configuration duplicates an already scored CSV")
    trace = []
    for row, user in enumerate(users):
        for rank, item in enumerate(predictions[user], 1):
            record = {"user_id": user, "rank": rank, "tv_show_id": item, "cold": user not in bundle.warm,
                      "familiar_training_80pct": item in bundle.seen.get(user, set())}
            for method in config["weights"]:
                ids = bundle.queues[row][method]["global"][:config["depth"]]
                record[f"{method}_rank"] = ids.index(item)+1 if item in ids else 0
                record[f"{method}_score"] = bundle.score(method, row, item)
            trace.append(record)
    pd.DataFrame(trace).to_csv(OUT / "recommendations.csv", index=False)
    contrasts = []
    for result in ledger["results"]:
        name = result["submission_id"]
        previous = read_rankings(ROOT / result["csv_path"])
        rows = []
        for user in users:
            a, b = previous[user], predictions[user]
            rows.append({"user_id": user, "previous_ids": " ".join(map(str, a)), "new_ids": " ".join(map(str, b)),
                         "changed_order": a != b, "changed_set": set(a) != set(b), "shared_top5": len(set(a)&set(b)),
                         "entered_ids": " ".join(map(str, sorted(set(b)-set(a)))), "removed_ids": " ".join(map(str, sorted(set(a)-set(b))))})
        frame = pd.DataFrame(rows)
        frame.to_csv(OUT / f"changes_vs_{name}.csv", index=False)
        contrasts.append({"reference": name, "changed_ordered_users": int(frame.changed_order.sum()), "changed_set_users": int(frame.changed_set.sum()),
                          "order_only_users": int((frame.changed_order & ~frame.changed_set).sum()), "unchanged_users": int((~frame.changed_order).sum()),
                          "mean_shared_top5": float(frame.shared_top5.mean()), "entered_user_item_pairs": int(sum(5-n for n in frame.shared_top5))})
    dump(OUT / "config.json", config)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    dump(OUT / "summary.json", {"submission_id": "submission_006", "selected_id": config["id"], "selected_config": config,
         "submission_path": str(SUBMISSION.relative_to(ROOT)), "submission_sha256": digest(SUBMISSION),
         "selection_rule": selected["selection_rule"], "validation_primary": selected["primary_MAP"], "validation_template": selected["template_MAP"],
         "training": "Same all-weeks 11-30 observations; frozen local-selected recency weighting applied to MF and PPR restarts only",
         "training_cutoff_local_exclusive": "2020-07-27", "template_users": len(users), "candidates": len(bundle.pool),
         "cold_users": sum(u not in bundle.warm for u in users), "comparisons": contrasts,
         "public_private_scores_used_for_selection": False, "kaggle_status": "Prepared; awaiting user upload and returned score", "created_csvs": [str(SUBMISSION.relative_to(ROOT))],
         "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["prepare_submission_006.py", "refinement_models.py", "hybrid_models.py", "recommender_bundle.py", "collaborative_models.py"]}})
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Frozen sources or previously scored CSVs changed")
    print(f"Prepared {SUBMISSION}, selected locally: {config['id']}")
    print(f"SHA-256: {digest(SUBMISSION)}")
    print(pd.DataFrame(contrasts).to_string(index=False))


if __name__ == "__main__":
    main()
