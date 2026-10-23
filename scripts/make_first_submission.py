#!/usr/bin/env python3
"""Freeze the validation winner, refit weeks 11-30, and write submission 001."""

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from build_interactions import read_views
from interaction_core import boundary_epoch, local_epoch, merge_views
from recommender_bundle import fit_full_history
from run_model_experiments import digest, dump
from run_semantic_hybrids import predict_all
from training_study import clip_join_training_window

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sweettv-tv-program-recommender"
OUT = ROOT / "reports/final_11_30"
ART = ROOT / "artifacts/final_11_30"
SUBMISSION = ROOT / "submissions/submission_001.csv"


def main():
    started = time.perf_counter()
    selection_path = ROOT / "reports/semantic_hybrids/selection.json"
    plan_path = ROOT / "scripts/semantic_hybrid_plan.json"
    verification_path = ROOT / "reports/semantic_hybrids/verification.json"
    selection = json.loads(selection_path.read_text())
    plan = json.loads(plan_path.read_text())
    assert json.loads(verification_path.read_text())["status"] == "passed"
    refit = plan["final_refit"]
    lower = boundary_epoch(refit["training_start_local"])
    cutoff = boundary_epoch(refit["training_end_local_exclusive"])
    end = boundary_epoch(refit["prediction_end_local_exclusive"])
    paths = {"selected_strategy": selection_path, "plan": plan_path, "validation_verification": verification_path,
             "view_log": DATA / "dataset11-30.csv", "schedule_11_20": DATA / "export_arh_11-20-final.csv",
             "schedule_21_30": DATA / "export_arh_21-30-final.csv", "schedule_31_42": DATA / "export_arh_31-42-final.csv",
             "template": DATA / "submission.csv", "historical_airings": ROOT / "artifacts/interactions/airings.parquet"}
    before = {k: digest(p) for k, p in paths.items()}
    original = json.loads((ROOT / "reports/interactions/summary.json").read_text())
    for name in ["view_log", "schedule_11_20", "schedule_21_30", "template"]:
        if before[name] != original["source_files_sha256"][paths[name].name]:
            raise AssertionError("Original historical input changed")
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    SUBMISSION.parent.mkdir(parents=True, exist_ok=True)
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    dump(OUT / "selected_strategy.json", selection)
    template = pd.read_csv(paths["template"], dtype=str, keep_default_na=False)
    if template.columns.tolist() != ["user_id", "tv_show_id"] or template.user_id.duplicated().any() or len(template) != 1260:
        raise AssertionError("Unexpected competition template")
    # Read no test-period descriptive metadata: only airing ID/channel/time.
    schedule = pd.read_csv(paths["schedule_31_42"], usecols=["channel_id", "start_time", "duration", "tv_show_id"],
                           dtype={"channel_id": "int32", "duration": "int32", "tv_show_id": "int64"}, keep_default_na=False)
    schedule["start"] = local_epoch(schedule.start_time, "%d.%m.%Y %H:%M:%S")
    available = schedule.loc[(schedule.tv_show_id != 0) & (schedule.duration > 0) & (schedule.start < end) & (schedule.start+schedule.duration > cutoff)]
    pool = sorted(int(i) for i in available.tv_show_id.unique())
    pd.DataFrame({"tv_show_id": pool}).to_csv(OUT / "test_candidates.csv", index=False)
    cache_manifest = {"view_log": before["view_log"], "historical_airings": before["historical_airings"], "lower": lower, "upper": cutoff}
    cache = ART / "events_manifest.json"
    if cache.exists() and json.loads(cache.read_text()) == cache_manifest:
        events = pd.read_parquet(ART / "training_events.parquet")
    else:
        print("Rejoining all weeks 11-30 from raw views across the former validation boundary ...", flush=True)
        views, view_stats = read_views(DATA, 250000)
        merged = merge_views(views)
        del views
        airings = pd.read_parquet(paths["historical_airings"])
        events = clip_join_training_window(merged, airings, lower, cutoff)
        del merged, airings
        events["split"] = "refit_11_30"
        events.to_parquet(ART / "training_events.parquet", index=False, compression="zstd")
        dump(cache, cache_manifest)
        dump(OUT / "view_read_diagnostics.json", view_stats)
    if not ((events.first_overlap >= lower) & (events.last_overlap <= cutoff)).all():
        raise AssertionError("Final training observed behaviour after the prediction cutoff")
    users = template.user_id.tolist()
    bundle, diagnostics = fit_full_history(events, users, pool, ART, plan["seed"])
    bundle.prepare_queues()
    bundle.save(ART)
    predicted, recommendations = predict_all(bundle, selection["selected_config"])
    output = pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, predicted[u])) for u in users]})
    if output.user_id.tolist() != users or output.columns.tolist() != template.columns.tolist():
        raise AssertionError("Submission schema/order changed")
    output.to_csv(SUBMISSION, index=False)
    recommendations.to_csv(OUT / "recommendations.csv", index=False)
    # Retain component lists for independent fusion reconstruction.
    for method in ["implicit_mf", "ppr", "association_rules", "popularity"]:
        pd.DataFrame({"user_id": users, "tv_show_id": [" ".join(map(str, bundle.queues[n][method]["global"][:5])) for n in range(len(users))]}).to_csv(OUT / f"component_{method}.csv", index=False)
    if before != {k: digest(p) for k, p in paths.items()}:
        raise AssertionError("Input changed during final refitting")
    diagnostics.update({"selected_id": selection["selected_id"], "selected_config": selection["selected_config"],
                        "training_start_local": refit["training_start_local"], "training_end_local_exclusive": refit["training_end_local_exclusive"],
                        "prediction_end_local_exclusive": refit["prediction_end_local_exclusive"], "template_users": len(users),
                        "test_candidates": len(pool), "test_cold_users_50pct": sum(u not in bundle.warm for u in users),
                        "new_to_training_items_in_test_pool": sum(i not in set(bundle.items["implicit_mf"]) for i in pool),
                        "training_overlap_events": len(events), "submission_path": str(SUBMISSION.relative_to(ROOT)), "submission_sha256": digest(SUBMISSION),
                        "total_seconds": time.perf_counter()-started, "kaggle_status": "Not uploaded; awaiting user upload and returned score",
                        "refit_policy": "All past weeks 11-30 observations, including former validation-period behaviour, after freezing strategy/parameters; validation truth CSV is not read by final fitting",
                        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
                        "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["make_first_submission.py", "recommender_bundle.py", "semantic_hybrids.py", "hybrid_models.py", "collaborative_models.py", "content_rule_models.py", "training_study.py", "run_semantic_hybrids.py"]}})
    dump(OUT / "summary.json", diagnostics)
    print(f"Wrote {SUBMISSION}: {len(users)} users, {len(pool)} eligible programmes, {diagnostics['test_cold_users_50pct']} cold users.")


if __name__ == "__main__":
    main()
