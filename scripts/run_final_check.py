#!/usr/bin/env python3
"""Fresh isolated raw-data replay, followed by comparison-only reference reads."""

import filecmp
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from evaluate_rankings import read_rankings
from run_model_experiments import digest, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/final_check"
DATA = ROOT / "sweettv-tv-program-recommender"


def main():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    number = 1
    while (OUT / f"rebuild_{number:03d}").exists():
        number += 1
    work = OUT / f"rebuild_{number:03d}"
    work.mkdir()
    (work / "logs").mkdir()
    sources = {"hybrid_config": ROOT / "reports/submission_007/config.json",
               "cbf_config": ROOT / "reports/content_rules/runs/cbf_title_tfidf_count/config.json",
               "final_choice": ROOT / "submissions/final_selection.json",
               "published_submission": ROOT / "submissions/submission_007.csv"}
    sources.update({name: DATA / name for name in ["dataset11-30.csv", "export_arh_11-20-final.csv", "export_arh_21-30-final.csv", "export_arh_31-42-final.csv", "submission.csv"]})
    for filename in ["audit_data.py", "build_interactions.py", "interaction_core.py", "collaborative_models.py", "content_rule_models.py",
                     "recommender_bundle.py", "refinement_models.py", "training_study.py", "run_content_rules.py",
                     "final_check_sandbox.py", "final_check_models.py"]:
        sources["code_"+filename] = ROOT / "scripts" / filename
    frozen = {name: digest(path) for name, path in sources.items()}
    dump(work / "input_manifest.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in sources.items()}, "sha256": frozen})
    dump(work / "configuration.json", {"hybrid": json.loads(sources["hybrid_config"].read_text()), "cbf": json.loads(sources["cbf_config"].read_text()),
         "policy": "Frozen selected recipe only; source configs are inputs. All observations, interactions and learned quantities rebuilt from raw; references compared only after model process exits."})
    commands = []
    def stage(label, script, arguments):
        command = [sys.executable, str(ROOT / "scripts/final_check_sandbox.py"), "--work-dir", str(work),
                   "--access-log", str(work / "logs" / f"{label}_access.json"), "--script", str(ROOT / "scripts" / script), "--", *arguments]
        print(f"Running fresh stage: {label} ...", flush=True)
        t = time.perf_counter()
        with (work / "logs" / f"{label}.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        record = {"stage": label, "command": command, "shell_display": shlex.join(command), "seconds": time.perf_counter()-t, "returncode": result.returncode}
        commands.append(record)
        dump(work / "commands.json", commands)
        if result.returncode:
            dump(OUT / "latest_run.json", {"status": "failed", "run_directory": str(work.relative_to(ROOT)), "failed_stage": label})
            raise RuntimeError(f"Scratch stage {label} failed; inspect {work / 'logs' / (label+'.log')}")
        access = json.loads((work / "logs" / f"{label}_access.json").read_text())
        if access["forbidden_old_derived_accesses"] or access["status"] != "passed":
            raise AssertionError("Scratch stage accessed an old derived artifact")
        print(f"  {label} passed in {record['seconds']:.1f}s; no old derived-artifact access.", flush=True)

    stage("raw_audit", "audit_data.py", ["--data-dir", str(DATA), "--output-dir", str(work / "raw_audit")])
    stage("interactions", "build_interactions.py", ["--data-dir", str(DATA), "--artifact-dir", str(work / "interactions"), "--report-dir", str(work / "interaction_reports")])
    stage("models", "final_check_models.py", ["--work-dir", str(work), "--data-dir", str(DATA)])
    # Only now inspect previously computed tables/model arrays for reconciliation.
    reconciliation = []
    def table(name, new, previous, columns=None):
        if new.suffix == ".parquet":
            a, b = pd.read_parquet(new), pd.read_parquet(previous)
        else:
            a, b = pd.read_csv(new, dtype={"user_id": str}), pd.read_csv(previous, dtype={"user_id": str})
        if columns:
            a, b = a[columns], b[columns]
        same = a.equals(b)
        reconciliation.append({"stage": name, "logical_values_identical": same, "new_rows": len(a), "old_rows": len(b), "note": "Compare values/dtypes/order, not Parquet/JSON container timestamps"})
        if not same:
            try:
                pd.testing.assert_frame_equal(a, b)
            except AssertionError as exc:
                (work / f"difference_{name}.txt").write_text(str(exc), encoding="utf-8")
    def array(name, a, b):
        same_shape = a.shape == b.shape
        exact = same_shape and np.array_equal(a, b)
        maximum = float(np.max(np.abs(a-b))) if same_shape and a.size and np.issubdtype(a.dtype, np.number) else None
        reconciliation.append({"stage": name, "logical_values_identical": exact, "new_rows": a.shape[0] if a.ndim else 1,
                               "old_rows": b.shape[0] if b.ndim else 1, "max_abs_difference": maximum,
                               "note": "" if exact else "Numerical-only difference" if same_shape and np.allclose(a, b, rtol=1e-12, atol=1e-12) else "Difference requires investigation"})
    def sparse_matrix(name, new, previous):
        a, b = sparse.load_npz(new), sparse.load_npz(previous)
        difference = (a-b).tocsr() if a.shape == b.shape else None
        exact = difference is not None and (not difference.nnz or np.max(np.abs(difference.data)) == 0)
        reconciliation.append({"stage": name, "logical_values_identical": exact, "new_rows": a.shape[0], "old_rows": b.shape[0],
                               "max_abs_difference": float(np.max(np.abs(difference.data))) if difference is not None and difference.nnz else 0. if exact else None,
                               "note": "Sparse mathematical entries compared"})
    for filename in ["airings.parquet", "airing_interactions.parquet", "user_programme_interactions.parquet"]:
        table("interactions_"+filename.split(".")[0], work / "interactions" / filename, ROOT / "artifacts/interactions" / filename)
    for filename in ["validation_ground_truth.csv", "validation_users.csv"]:
        table(filename.split(".")[0], work / "interaction_reports" / filename, ROOT / "reports/interactions" / filename)
    table("full_window_events", work / "full_training_events.parquet", ROOT / "artifacts/final_11_30/training_events.parquet")
    for phase, reference in [("validation", ROOT / "artifacts/training_study"), ("final", ROOT / "artifacts/final_11_30")]:
        folder = work / phase
        for threshold in [50, 80]:
            previous = reference / f"full10_t{threshold}/training_counts.parquet" if phase == "validation" else reference / f"training_counts_{threshold}.parquet"
            table(f"{phase}_raw_counts{threshold}", folder / f"counts{threshold}.parquet", previous, ["user_id", "tv_show_id", "watched_airings"])
        weighted_reference = ROOT / "artifacts/refinement/validation/h8" if phase == "validation" else ROOT / "artifacts/submission_006"
        table(f"{phase}_weighted_counts", folder / "weighted_counts.parquet", weighted_reference / "weighted_counts.parquet")
        new_factors, old_factors = np.load(folder / "factors.npz", allow_pickle=False), np.load(weighted_reference / "factors.npz", allow_pickle=False)
        for key in ["user_factors", "item_factors"]:
            array(f"{phase}_{key}", new_factors[key], old_factors[key])
        source_scores = ROOT / "artifacts/refinement/validation/h8/scores.npz" if phase == "validation" else ROOT / "artifacts/submission_007/scores.npz"
        new_scores, previous_scores = np.load(folder / "scores.npz", allow_pickle=False), np.load(source_scores, allow_pickle=False)
        for key in previous_scores.files:
            array(f"{phase}_{key}", new_scores[key], previous_scores[key])
        graph_reference = reference / "full10_t50/ppr/transition.npz" if phase == "validation" else reference / "transition.npz"
        rule_reference = reference / "full10_t80/association_rules/rule_weights.npz" if phase == "validation" else reference / "rule_weights.npz"
        sparse_matrix(f"{phase}_transition", folder / "transition.npz", graph_reference)
        sparse_matrix(f"{phase}_rules", folder / "rule_weights.npz", rule_reference)
    cbf = ROOT / "artifacts/content_rules/cbf_title_tfidf_count"
    sparse_matrix("CBF_vectors", work / "validation/cbf_item_vectors.npz", cbf / "item_vectors.npz")
    sparse_matrix("CBF_profiles", work / "validation/cbf_profiles.npz", cbf / "query_profiles.npz")
    prediction_refs = {"popularity": ROOT / "reports/training_study/full10_t50/runs/popularity/predictions.csv",
                       "implicit_mf": ROOT / "artifacts/refinement/validation/h8/component_implicit_mf_top20.csv",
                       "ppr": ROOT / "artifacts/refinement/validation/h8/component_ppr_top20.csv",
                       "association_rules": ROOT / "reports/training_study/full10_t80/runs/association_rules/predictions.csv",
                       "content_based": ROOT / "reports/content_rules/runs/cbf_title_tfidf_count/predictions.csv",
                       "hybrid_007": ROOT / "reports/recency_extension/runs/h8_rules01875_pop00625/predictions.csv"}
    for method, previous in prediction_refs.items():
        current = read_rankings(work / "validation" / f"predictions_{method}.csv")
        ref = {u: ids[:5] for u, ids in read_rankings(previous).items()}
        same = current == ref
        reconciliation.append({"stage": f"validation_predictions_{method}", "logical_values_identical": same, "new_rows": len(current), "old_rows": len(ref), "note": "All users and ordered Top-5s compared"})
        if not same:
            pd.DataFrame({"user_id": [u for u in current if current[u] != ref.get(u)],
                          "rebuilt": [" ".join(map(str, current[u])) for u in current if current[u] != ref.get(u)],
                          "original": [" ".join(map(str, ref.get(u, []))) for u in current if current[u] != ref.get(u)]}).to_csv(work / f"difference_predictions_{method}.csv", index=False)
    rebuilt = work / "final/submission_007.csv"
    reference = sources["published_submission"]
    byte_identical = filecmp.cmp(rebuilt, reference, shallow=False)
    new_predictions, old_predictions = read_rankings(rebuilt), read_rankings(reference)
    changed = [u for u in set(new_predictions)|set(old_predictions) if new_predictions.get(u) != old_predictions.get(u)]
    if changed:
        pd.DataFrame({"user_id": sorted(changed), "rebuilt": [" ".join(map(str, new_predictions.get(u, []))) for u in sorted(changed)],
                      "original": [" ".join(map(str, old_predictions.get(u, []))) for u in sorted(changed)]}).to_csv(OUT / "submission_differences.csv", index=False)
    pd.DataFrame(reconciliation).to_csv(OUT / "stage_reconciliation.csv", index=False)
    unchanged = frozen == {name: digest(path) for name, path in sources.items()}
    result = {"status": "passed" if byte_identical and unchanged else "difference_needs_investigation", "run_directory": str(work.relative_to(ROOT)),
              "rebuilt_submission": str(rebuilt.relative_to(ROOT)), "published_submission": str(reference.relative_to(ROOT)),
              "rebuilt_sha256": digest(rebuilt), "published_sha256": digest(reference), "byte_identical": byte_identical,
              "ordered_predictions_identical": new_predictions == old_predictions, "changed_users": len(changed),
              "rows": len(new_predictions), "all_inputs_and_published_csv_unchanged": unchanged,
              "logical_stage_comparisons": len(reconciliation), "logical_stage_differences": [r["stage"] for r in reconciliation if not r["logical_values_identical"]],
              "old_artifact_accesses_during_fitting": 0, "elapsed_seconds": time.perf_counter()-started,
              "scope": "Fresh raw audit, interaction/label build, all six selected validation strategies, full-window join and final007 refit. Frozen parameters; no tuning replay.",
              "code_sha256": digest(Path(__file__))}
    dump(OUT / "rebuild_result.json", result)
    dump(OUT / "latest_run.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    if not byte_identical or not unchanged:
        raise AssertionError("Investigate the saved differences before claiming reproducibility")


if __name__ == "__main__":
    main()
