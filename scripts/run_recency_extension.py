#!/usr/bin/env python3
"""Choose the next existing-method configuration using primary validation only."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from ranking_metrics import evaluate_rankings
from recency_extension import compose_bundle, variant_name
from refinement_models import fuse_bundle, phase_paths
from run_model_experiments import digest, dump
from run_refinement_study import signature
from segment_analysis import history_metrics, novelty_metrics, true_hit_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/recency_extension"
ART = ROOT / "artifacts/recency_extension/validation"


def main():
    plan_path = Path(__file__).parent / "recency_extension_plan.json"
    plan = json.loads(plan_path.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    dump(OUT / "plan.json", plan)
    paths = phase_paths("validation")
    paths.update(plan=plan_path, truth=ROOT / "reports/interactions/validation_ground_truth.csv",
                 primary=ROOT / "reports/popularity/cohort_primary.csv", template=ROOT / "reports/popularity/cohort_template_primary.csv",
                 protocol=ROOT / "reports/popularity/protocol.json", candidates=ROOT / "reports/popularity/validation_candidates.csv",
                 features=ROOT / "reports/training_study/reference_analysis/user_features.csv", truth_types=ROOT / "reports/training_study/reference_analysis/true_answer_attributes.csv",
                 rules_matrix=ROOT / "artifacts/training_study/full10_t80/association_rules/rule_weights.npz")
    prior = {"001": "reports/hybrids/runs/rrf_mf_ppr_rules_k0/predictions.csv", "002": "reports/hybrids/runs/rrf_mf_ppr_rules_pop_k0/predictions.csv",
             "003": "reports/semantic_hybrids/runs/ppr20_rerank_mf/predictions.csv", "004": "reports/semantic_hybrids/runs/implicit_mf/predictions.csv",
             "005": "reports/hybrids/runs/rrf_mf_ppr_k0/predictions.csv", "006": "reports/refinement/runs/recency_h8/predictions.csv"}
    paths.update({"prior_"+k: ROOT / v for k, v in prior.items()})
    for h in [4, 8]:
        for file in ["scores.npz", "weighted_counts.parquet", "users.json"]:
            paths[f"prior_h{h}_{file}"] = ROOT / "artifacts/refinement/validation" / f"h{h}" / file
    before = {name: digest(path) for name, path in paths.items()}
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    truth = read_rankings(paths["truth"])
    cohorts = {"all_primary": pd.read_csv(paths["primary"], dtype=str).user_id.tolist(), "template_primary": pd.read_csv(paths["template"], dtype=str).user_id.tolist()}
    features = pd.read_csv(paths["features"], dtype={"user_id": str})
    meta = pd.read_csv(paths["truth_types"], dtype={"user_id": str})
    old_signatures = {signature(read_rankings(ROOT / path)): name for name, path in prior.items()}
    configs = [plan["control"]]+plan["runs"]
    comparison, novel, hist, aps = [], [], [], {}
    for variant in dict.fromkeys(variant_name(c) for c in configs):
        group = [c for c in configs if variant_name(c) == variant]
        bundle = compose_bundle("validation", group[0], ART / variant, ART / "cf_cache", plan["seed"])
        for config in group:
            predicted = fuse_bundle(bundle, config)
            if config["id"] == "control_006" and predicted != read_rankings(paths["prior_006"]):
                raise AssertionError("006 control changed")
            folder = OUT / "runs" / config["id"]
            folder.mkdir(parents=True, exist_ok=True)
            dump(folder / "config.json", config)
            pd.DataFrame({"user_id": bundle.users, "tv_show_id": [" ".join(map(str, predicted[u])) for u in bundle.users]}).to_csv(folder / "predictions.csv", index=False)
            metrics, records = evaluate_rankings(truth, predicted, users=cohorts["all_primary"])
            pd.DataFrame(records).to_csv(folder / "per_user_metrics.csv", index=False)
            aps[config["id"]] = {r["user_id"]: r["ap_at_5"] for r in records}
            run_metrics = []
            for cohort, users in cohorts.items():
                metric, _ = evaluate_rankings(truth, predicted, users=users)
                row = {"run_id": config["id"], "variant": variant, "kind": "control" if config["id"] == "control_006" else "new",
                       "cohort": cohort, "duplicates_prior_upload": old_signatures.get(signature(predicted), ""), **metric}
                comparison.append(row)
                run_metrics.append(row)
            n = novelty_metrics(true_hit_rows(meta, predicted), cohorts)
            n["run_id"] = config["id"]
            n.to_csv(folder / "novelty_metrics.csv", index=False)
            novel.append(n)
            h = history_metrics(pd.DataFrame(records), features[["user_id", "history_distinct", "history_volume", "active_week_span", "last_activity_age"]], cohorts)
            h["run_id"] = config["id"]
            h.to_csv(folder / "history_metrics.csv", index=False)
            hist.append(h)
            dump(folder / "summary.json", {"config": config, "variant": variant, "metrics": run_metrics,
                 "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["recency_extension.py", "run_recency_extension.py", "refinement_models.py", "hybrid_models.py"]}})
            print(f"{config['id']}: all={metrics['map_at_5']:.8f}; template={run_metrics[1]['map_at_5']:.8f}", flush=True)
        del bundle
    frame = pd.DataFrame(comparison)
    control = frame.loc[frame.run_id == "control_006"].set_index("cohort").map_at_5
    frame["delta_vs_006"] = frame.map_at_5-frame.cohort.map(control)
    frame.to_csv(OUT / "comparison.csv", index=False)
    pd.concat(novel, ignore_index=True).to_csv(OUT / "novelty_metrics.csv", index=False)
    pd.concat(hist, ignore_index=True).to_csv(OUT / "history_metrics.csv", index=False)
    ranked = frame.loc[(frame.cohort == "all_primary") & (frame.kind == "new") & frame.duplicates_prior_upload.eq("")].sort_values(["map_at_5", "run_id"], ascending=[False, True])
    if ranked.empty:
        raise AssertionError("No new configuration")
    selected = ranked.iloc[0].run_id
    config = next(c for c in plan["runs"] if c["id"] == selected)
    dump(OUT / "selection.json", {"selected_id": selected, "selected_config": config, "primary_MAP": float(ranked.iloc[0].map_at_5),
         "template_MAP": float(frame.loc[(frame.run_id == selected) & (frame.cohort == "template_primary"), "map_at_5"].iloc[0]),
         "selection_rule": plan["selection"], "ranked_new_ids": ranked.run_id.tolist(), "public_private_scores_used_by_selector": False})
    rng = np.random.default_rng(plan["seed"])
    paired = []
    for cohort, users in cohorts.items():
        delta = np.array([aps[selected][u]-aps["control_006"][u] for u in users])
        samples = delta[rng.integers(0, len(users), size=(plan["bootstrap_resamples"], len(users)))].mean(axis=1)
        paired.append({"cohort": cohort, "selected": selected, "reference": "control_006", "mean_MAP_difference": float(delta.mean()),
                       "conditional_95pct_lower": float(np.quantile(samples, .025)), "conditional_95pct_upper": float(np.quantile(samples, .975)),
                       "better_users": int((delta > 1e-14).sum()), "worse_users": int((delta < -1e-14).sum()), "equal_users": int((np.abs(delta) <= 1e-14).sum())})
    pd.DataFrame(paired).to_csv(OUT / "paired_selected.csv", index=False)
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Frozen validation inputs changed")
    print(f"Selected by primary local MAP only: {selected}")


if __name__ == "__main__":
    main()
