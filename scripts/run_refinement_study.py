#!/usr/bin/env python3
"""Select a new configuration using local validation only, never Kaggle scores."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_rankings import read_rankings
from ranking_metrics import evaluate_rankings
from refinement_models import fit_recency, fuse_bundle, load_base, phase_paths
from run_model_experiments import digest, dump
from segment_analysis import history_metrics, novelty_metrics, true_hit_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/refinement"
ART = ROOT / "artifacts/refinement/validation"


def signature(predicted):
    text = "\n".join(u+":"+" ".join(map(str, predicted[u])) for u in sorted(predicted))
    return hashlib.sha256(text.encode()).hexdigest()


def save_components(bundle, folder):
    bundle.save(folder)
    for method in ["implicit_mf", "ppr", "association_rules", "popularity"]:
        pd.DataFrame({"user_id": bundle.users, "tv_show_id": [" ".join(map(str, q[method]["global"])) for q in bundle.queues]}).to_csv(folder / f"component_{method}_top20.csv", index=False)


def main():
    plan_path = Path(__file__).parent / "refinement_plan.json"
    plan = json.loads(plan_path.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    dump(OUT / "plan.json", plan)
    paths = phase_paths("validation")
    paths.update(plan=plan_path, truth=ROOT / "reports/interactions/validation_ground_truth.csv",
                 primary=ROOT / "reports/popularity/cohort_primary.csv", template=ROOT / "reports/popularity/cohort_template_primary.csv",
                 protocol=ROOT / "reports/popularity/protocol.json", candidates=ROOT / "reports/popularity/validation_candidates.csv",
                 features=ROOT / "reports/training_study/reference_analysis/user_features.csv",
                 truth_types=ROOT / "reports/training_study/reference_analysis/true_answer_attributes.csv")
    old_paths = {"001": "reports/hybrids/runs/rrf_mf_ppr_rules_k0/predictions.csv",
                 "002": "reports/hybrids/runs/rrf_mf_ppr_rules_pop_k0/predictions.csv",
                 "003": "reports/semantic_hybrids/runs/ppr20_rerank_mf/predictions.csv",
                 "004": "reports/semantic_hybrids/runs/implicit_mf/predictions.csv",
                 "005": "reports/hybrids/runs/rrf_mf_ppr_k0/predictions.csv"}
    paths.update({"prior_"+k: ROOT / p for k, p in old_paths.items()})
    before = {name: digest(path) for name, path in paths.items()}
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in paths.items()}, "sha256": before})
    truth = read_rankings(paths["truth"])
    cohorts = {"all_primary": pd.read_csv(paths["primary"], dtype=str).user_id.tolist(),
               "template_primary": pd.read_csv(paths["template"], dtype=str).user_id.tolist()}
    meta = pd.read_csv(paths["truth_types"], dtype={"user_id": str})
    features = pd.read_csv(paths["features"], dtype={"user_id": str})
    old_signatures = {signature(read_rankings(ROOT / path)): name for name, path in old_paths.items()}
    all_rows, novelties, histories, aps, run_signatures = [], [], [], {}, {}
    all_configs = plan["controls"]+plan["runs"]
    new_ids = {r["id"] for r in plan["runs"]}
    for half_life in [None, 4, 8]:
        variant = "base" if half_life is None else f"h{half_life}"
        folder = ART / variant
        bundle = load_base("validation")[0] if half_life is None else fit_recency("validation", half_life, folder, plan["seed"])
        bundle.prepare_queues(depth=20)
        save_components(bundle, folder)
        for config in [c for c in all_configs if c["half_life_weeks"] == half_life]:
            predicted = fuse_bundle(bundle, config)
            if config["id"] in {"control_001", "control_002"}:
                reference = paths["prior_"+config["id"].split("_")[1]]
                if predicted != read_rankings(reference):
                    raise AssertionError("Original control rankings changed")
            if set(predicted) != set(cohorts["all_primary"]):
                raise AssertionError("Primary user coverage changed")
            folder_run = OUT / "runs" / config["id"]
            folder_run.mkdir(parents=True, exist_ok=True)
            dump(folder_run / "config.json", config)
            pd.DataFrame({"user_id": bundle.users, "tv_show_id": [" ".join(map(str, predicted[u])) for u in bundle.users]}).to_csv(folder_run / "predictions.csv", index=False)
            overall, records = evaluate_rankings(truth, predicted, users=cohorts["all_primary"])
            pd.DataFrame(records).to_csv(folder_run / "per_user_metrics.csv", index=False)
            aps[config["id"]] = {r["user_id"]: r["ap_at_5"] for r in records}
            run_signatures[config["id"]] = signature(predicted)
            summary_rows = []
            for cohort, ids in cohorts.items():
                metrics, _ = evaluate_rankings(truth, predicted, users=ids)
                result = {"run_id": config["id"], "kind": "new" if config["id"] in new_ids else "control", "variant": variant,
                          "depth": config["depth"], "offset": config["offset"], "cohort": cohort,
                          "duplicates_prior_upload": old_signatures.get(run_signatures[config["id"]], ""), **metrics}
                all_rows.append(result)
                summary_rows.append(result)
            n = novelty_metrics(true_hit_rows(meta, predicted), cohorts)
            n["run_id"] = config["id"]
            novelties.append(n)
            n.to_csv(folder_run / "novelty_metrics.csv", index=False)
            h = history_metrics(pd.DataFrame(records), features[["user_id", "history_distinct", "history_volume", "active_week_span", "last_activity_age"]], cohorts)
            h["run_id"] = config["id"]
            histories.append(h)
            h.to_csv(folder_run / "history_metrics.csv", index=False)
            dump(folder_run / "summary.json", {"config": config, "metrics": summary_rows, "variant": variant,
                 "cold_users": sum(u not in bundle.warm for u in bundle.users),
                 "code_hashes": {f: digest(Path(__file__).parent / f) for f in ["refinement_models.py", "run_refinement_study.py", "hybrid_models.py"]}})
            print(f"{config['id']}: all={overall['map_at_5']:.8f}; template={summary_rows[1]['map_at_5']:.8f}", flush=True)
        del bundle
    comparison = pd.DataFrame(all_rows)
    for control in ["control_001", "control_002"]:
        baseline = comparison.loc[comparison.run_id == control].set_index("cohort").map_at_5
        comparison[f"delta_vs_{control}"] = comparison.map_at_5-comparison.cohort.map(baseline)
    comparison.to_csv(OUT / "comparison.csv", index=False)
    pd.concat(novelties, ignore_index=True).to_csv(OUT / "novelty_metrics.csv", index=False)
    pd.concat(histories, ignore_index=True).to_csv(OUT / "history_metrics.csv", index=False)
    eligible = comparison.loc[(comparison.cohort == "all_primary") & (comparison.kind == "new") & comparison.duplicates_prior_upload.eq("")]
    ranked = eligible.sort_values(["map_at_5", "run_id"], ascending=[False, True])
    if ranked.empty:
        raise AssertionError("No genuinely new local configuration")
    selected = ranked.iloc[0].run_id
    config = next(c for c in plan["runs"] if c["id"] == selected)
    dump(OUT / "selection.json", {"selected_id": selected, "selected_config": config, "selection_rule": plan["selection"],
         "primary_MAP": float(ranked.iloc[0].map_at_5), "template_MAP": float(comparison.loc[(comparison.run_id == selected) & (comparison.cohort == "template_primary"), "map_at_5"].iloc[0]),
         "ranked_new_ids": ranked.run_id.tolist(), "public_private_scores_used_by_selector": False})
    rng = np.random.default_rng(plan["seed"])
    paired = []
    for cohort, ids in cohorts.items():
        for control in ["control_001", "control_002"]:
            delta = np.array([aps[selected][u]-aps[control][u] for u in ids])
            samples = delta[rng.integers(0, len(ids), size=(plan["bootstrap_resamples"], len(ids)))].mean(axis=1)
            paired.append({"cohort": cohort, "selected": selected, "reference": control, "mean_MAP_difference": float(delta.mean()),
                           "conditional_95pct_lower": float(np.quantile(samples, .025)), "conditional_95pct_upper": float(np.quantile(samples, .975)),
                           "better_users": int((delta > 1e-14).sum()), "worse_users": int((delta < -1e-14).sum()), "equal_users": int((np.abs(delta) <= 1e-14).sum())})
    pd.DataFrame(paired).to_csv(OUT / "paired_selected.csv", index=False)
    if before != {name: digest(path) for name, path in paths.items()}:
        raise AssertionError("Frozen local validation inputs changed")
    print(f"Selected by primary local MAP only: {selected}")


if __name__ == "__main__":
    main()
