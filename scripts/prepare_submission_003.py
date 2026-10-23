#!/usr/bin/env python3
"""Prepare only 003: existing PPR Top-20 candidates reranked by existing MF."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from recommender_bundle import Bundle
from run_model_experiments import digest, dump
from run_semantic_hybrids import predict_all

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_003"
ART = ROOT / "artifacts/final_11_30"
SUBMISSION = ROOT / "submissions/submission_003.csv"


def main():
    plan_path = ROOT / "scripts/kaggle_comparison_plan.json"
    plan = json.loads(plan_path.read_text())
    candidate = next(r for r in plan["submissions"] if r["id"] == "submission_003")
    config = candidate["strategy"]
    OUT.mkdir(parents=True, exist_ok=True)
    # Score feedback is appendable. Snapshot it here so later reported results
    # cannot invalidate this generation's immutable model/input evidence.
    ledger = json.loads((ROOT / "submissions/results.json").read_text())
    dump(OUT / "results_at_preparation.json", ledger)
    paths = {"plan": plan_path, "score_snapshot": OUT / "results_at_preparation.json",
             "template": ROOT / "sweettv-tv-program-recommender/submission.csv",
             "training_manifest": ROOT / "reports/final_11_30/summary.json",
             "training_verification": ROOT / "reports/final_11_30/verification.json",
             "scores": ART / "scores.npz", "model_users": ART / "users.json",
             "training_counts_50": ART / "training_counts_50.parquet", "training_counts_80": ART / "training_counts_80.parquet",
             "popularity": ART / "candidate_scores.csv", "cold_users": ART / "cold_users.json", "history": ART / "history.json",
             "candidates": ROOT / "reports/final_11_30/test_candidates.csv",
             "previous_001": ROOT / "submissions/submission_001.csv", "previous_002": ROOT / "submissions/submission_002.csv",
             "validation_comparison": ROOT / candidate["validation_comparison"],
             "validation_config": ROOT / "reports/semantic_hybrids/runs" / config["id"] / "config.json"}
    for method in ["implicit_mf", "ppr", "association_rules", "popularity"]:
        paths[f"component_{method}"] = ROOT / "reports/final_11_30" / f"component_{method}.csv"
    before = {name: digest(path) for name, path in paths.items()}
    for result in ledger["results"]:
        if result["submission_id"] in {"submission_001", "submission_002"}:
            if digest(ROOT / result["csv_path"]) != result["csv_sha256"]:
                raise AssertionError("A scored CSV has changed")
    training = json.loads(paths["training_manifest"].read_text())
    if json.loads(paths["training_verification"].read_text())["status"] != "passed":
        raise AssertionError("Original full-history models were not verified")
    if any(digest(Path(__file__).parent / f) != h for f, h in training["code_hashes"].items()):
        raise AssertionError("Fitted-model inference code changed")
    if json.loads(paths["validation_config"].read_text()) != config:
        raise AssertionError("003 does not match the already validated strategy")
    local = pd.read_csv(paths["validation_comparison"])
    local = local.loc[local.run_id == config["id"]].set_index("cohort")
    for cohort, expected in [("all_primary", candidate["validation_primary"]), ("template_primary", candidate["validation_template"])]:
        if abs(local.loc[cohort, "map_at_5"]-expected) > 1e-12:
            raise AssertionError("Declared validation result changed")
    template = pd.read_csv(paths["template"], dtype=str, keep_default_na=False)
    users = template.user_id.tolist()
    if template.columns.tolist() != ["user_id", "tv_show_id"] or len(users) != 1260 or len(set(users)) != 1260:
        raise AssertionError("Unexpected template")
    if users != json.loads(paths["model_users"].read_text()):
        raise AssertionError("Model score rows differ from template order")
    pool = pd.read_csv(paths["candidates"]).tv_show_id.astype(int).tolist()
    saved = np.load(paths["scores"], allow_pickle=False)
    methods = ["implicit_mf", "ppr", "association_rules"]
    values = {m: saved[f"scores_{m}"] for m in methods}
    items = {m: saved[f"items_{m}"].astype(int).tolist() for m in methods}
    bundle = Bundle(users, pool, pd.read_parquet(paths["training_counts_50"]), pd.read_parquet(paths["training_counts_80"]), values, items)
    bundle.prepare_queues(depth=config["depth"])
    recorded_pop = pd.read_csv(paths["popularity"]).sort_values("rank").tv_show_id.astype(int).tolist()
    if recorded_pop != bundle.popularity:
        raise AssertionError("Shared training-popularity order changed")
    for method in methods+["popularity"]:
        recreated = {u: bundle.queues[row][method]["global"][:5] for row, u in enumerate(users)}
        if recreated != read_rankings(paths[f"component_{method}"]):
            raise AssertionError(f"Reused component differs: {method}")
    predictions, trace = predict_all(bundle, config)
    output = pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predictions[u])) for u in users]})
    output.to_csv(SUBMISSION, index=False)
    trace.to_csv(OUT / "recommendations.csv", index=False)
    candidates = []
    for row, user in enumerate(users):
        for rank, item in enumerate(bundle.queues[row]["ppr"]["global"][:config["depth"]], 1):
            candidates.append({"user_id": user, "ppr_generator_rank": rank, "tv_show_id": item,
                               "ppr_score": bundle.score("ppr", row, item), "mf_score": bundle.score("implicit_mf", row, item),
                               "selected": item in predictions[user], "cold": user not in bundle.warm})
    pd.DataFrame(candidates).to_csv(OUT / "rerank_candidates.csv", index=False)
    contrasts = []
    for previous_id, source in [("submission_001", paths["previous_001"]), ("submission_002", paths["previous_002"])]:
        old = read_rankings(source)
        changes = []
        for user in users:
            a, b = old[user], predictions[user]
            changes.append({"user_id": user, "previous_ids": " ".join(map(str, a)), "new_ids": " ".join(map(str, b)),
                            "changed_order": a != b, "changed_set": set(a) != set(b), "shared_top5": len(set(a)&set(b)),
                            "entered_ids": " ".join(map(str, sorted(set(b)-set(a)))), "removed_ids": " ".join(map(str, sorted(set(a)-set(b))))})
        frame = pd.DataFrame(changes)
        frame.to_csv(OUT / f"changes_vs_{previous_id}.csv", index=False)
        contrasts.append({"reference": previous_id, "changed_ordered_users": int(frame.changed_order.sum()), "changed_set_users": int(frame.changed_set.sum()),
                          "order_only_users": int((frame.changed_order & ~frame.changed_set).sum()), "unchanged_users": int((~frame.changed_order).sum()),
                          "mean_shared_top5": float(frame.shared_top5.mean()), "entered_user_item_pairs": int(sum(5-n for n in frame.shared_top5))})
    dump(OUT / "config.json", config)
    dump(OUT / "plan.json", plan)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    summary = {"submission_id": "submission_003", "selected_id": config["id"], "selected_config": config,
               "submission_path": str(SUBMISSION.relative_to(ROOT)), "submission_sha256": digest(SUBMISSION),
               "training": "Reuse identical verified weeks 11-30 fits; no refitting or parameter change",
               "validation_source": {"comparison": candidate["validation_comparison"], "run_id": config["id"], "all_primary": candidate["validation_primary"], "template_primary": candidate["validation_template"]},
               "template_users": len(users), "candidates": len(pool), "generator_depth": config["depth"],
               "cold_users": sum(u not in bundle.warm for u in users), "comparisons": contrasts,
               "tie_policy": "MF score descending, ties retain PPR candidate order; all actual cold users keep popularity",
               "kaggle_status": "Prepared; awaiting user upload and returned scores", "created_csvs": [str(SUBMISSION.relative_to(ROOT))],
               "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["prepare_submission_003.py", "recommender_bundle.py", "run_semantic_hybrids.py", "semantic_hybrids.py"]}}
    dump(OUT / "summary.json", summary)
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Inputs or previously scored submissions changed")
    print(f"Prepared {SUBMISSION}: {len(users)} users; identical fitted models, PPR depth {config['depth']} -> MF.")
    print(f"SHA-256: {summary['submission_sha256']}")
    print(pd.DataFrame(contrasts).to_string(index=False))


if __name__ == "__main__":
    main()
