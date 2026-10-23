#!/usr/bin/env python3
"""Independently verify 002, the scored anchor and its exact local counterpart."""

import csv
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_002"


def exact_fusion(components, user, config, pop_rank):
    utility = defaultdict(Fraction)
    for method, weight in config["weights"].items():
        for rank, item in enumerate(components[method][user], 1):
            utility[item] += Fraction(str(weight))/(config["offset"]+rank)
    return sorted(utility, key=lambda item: (-utility[item], pop_rank[item], item))[:5]


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    manifest = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in manifest["paths"].items()}
    for key, path in paths.items():
        check(f"immutable input: {key}", sha256(path) == manifest["sha256"][key])
    summary = json.loads((OUT / "summary.json").read_text())
    plan = json.loads(paths["plan"].read_text())
    candidate = next(r for r in plan["submissions"] if r["id"] == "submission_002")
    config = candidate["strategy"]
    check("declared/scored/final configurations agree", config == summary["selected_config"] == json.loads((OUT / "config.json").read_text()) == json.loads(paths["validation_config"].read_text()))
    check("generation code fingerprints", all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    training = json.loads(paths["training_manifest"].read_text())
    check("original model code unchanged", all(sha256(ROOT / "scripts" / f) == h for f, h in training["code_hashes"].items()))
    ledger = json.loads(paths["ledger"].read_text())
    scored = next(r for r in ledger["results"] if r["submission_id"] == "submission_001")
    check("reported anchor scores and exact submitted bytes recorded", scored["public_score"] == .43347 and scored["private_score"] == .41452 and scored["csv_sha256"] == sha256(paths["anchor_csv"]) == training["submission_sha256"] == plan["anchor"]["csv_sha256"])
    check("original score screenshot retained", scored["screenshot_path"] is not None and sha256(ROOT / scored["screenshot_path"]) == scored["screenshot_sha256"])
    check("only 002 prepared among the four planned follow-ups", len(plan["submissions"]) == 4 and all(not (ROOT / "submissions" / f"{r['id']}.csv").exists() for r in plan["submissions"] if r["id"] != "submission_002"))
    users = [r["user_id"] for r in read_csv(paths["template"])]
    submitted_path = ROOT / summary["submission_path"]
    with submitted_path.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.reader(stream))
    check("two-column template header and no extra index", raw[0] == ["user_id", "tv_show_id"] and all(len(r) == 2 for r in raw[1:]))
    check("1260 exact uint64-safe user strings in template order", len(raw)-1 == len(users) == len(set(users)) == 1260 and [r[0] for r in raw[1:]] == users and all(str(int(u)) == u for u in users))
    check("five unique canonical nonzero integer tokens per cell", all(len(r[1].split()) == len(set(r[1].split())) == 5 and r[1] == " ".join(r[1].split()) and all(i.isdecimal() and int(i) > 0 and str(int(i)) == i for i in r[1].split()) for r in raw[1:]))
    submitted = rankings(submitted_path)
    pool = {int(r["tv_show_id"]) for r in read_csv(paths["test_candidates"])}
    pop_rows = read_csv(paths["popularity"])
    pop = [int(r["tv_show_id"]) for r in pop_rows]
    pop_rank = {i: n for n, i in enumerate(pop)}
    check("same complete 6632 eligible IDs and all predictions eligible", len(pop) == len(pool) == 6632 and set(pop) == pool and all(set(ids) <= pool for ids in submitted.values()))
    check("CSV SHA-256 matches generation manifest", sha256(submitted_path) == summary["submission_sha256"])
    cold = set(json.loads(paths["cold_users"].read_text()))
    check("same four actual cold users and fallback", len(cold) == 4 and all(submitted[u] == pop[:5] for u in cold))
    components = {m: rankings(paths[f"component_{m}"]) for m in config["weights"]}
    model_users = json.loads(paths["model_users"].read_text())
    check("model score rows match exact template order", model_users == users)
    model = np.load(paths["model_scores"], allow_pickle=False)
    for method, output in components.items():
        check(f"component users and five eligible distinct IDs: {method}", set(output) == set(users) and all(len(ids) == len(set(ids)) == 5 and set(ids) <= pool for ids in output.values()))
        if method == "popularity":
            check("popularity component equals common training Top-5", all(ids == pop[:5] for ids in output.values()))
            continue
        values, item_ids = model[f"scores_{method}"], model[f"items_{method}"].astype(int).tolist()
        for row, user in enumerate(users):
            positive = [(item, float(values[row, n])) for n, item in enumerate(item_ids) if item in pool and values[row, n] > 0]
            positive.sort(key=lambda pair: (-pair[1], pair[0]))
            prefix = [i for i, value in positive]
            prefix_set = set(prefix)
            order = prefix+[i for i in pop if i not in prefix_set]
            assert output[user] == (pop[:5] if user in cold else order[:5])
        check(f"Top-5 rebuilt from identical all-history model scores: {method}", True)
    anchor = rankings(paths["anchor_csv"])
    check("all anchor ranks reproduced with original weights", all(anchor[u] == exact_fusion(components, u, training["selected_config"], pop_rank) for u in users))
    check("all 002 ranks independently reproduced with exact rational utilities", all(submitted[u] == exact_fusion(components, u, config, pop_rank) for u in users))
    check("precise ablation: fixed MF/PPR and total auxiliary weight", config["offset"] == training["selected_config"]["offset"] == 0 and config["weights"]["implicit_mf"] == config["weights"]["ppr"] == .5 and config["weights"]["association_rules"] == config["weights"]["popularity"] == .125 and training["selected_config"]["weights"]["association_rules"] == .25)
    changes = read_csv(OUT / "changes_vs_001.csv")
    check("change table has every exact user once", len(changes) == len(users) and [r["user_id"] for r in changes] == users)
    for record in changes:
        user = record["user_id"]
        a, b = anchor[user], submitted[user]
        assert record["anchor_ids"] == " ".join(map(str, a)) and record["new_ids"] == " ".join(map(str, b))
        assert (record["changed_order"] == "True") == (a != b) and (record["changed_set"] == "True") == (set(a) != set(b))
        assert int(record["shared_top5"]) == len(set(a)&set(b)) and int(record["new_items"]) == len(set(b)-set(a))
        assert record["entered_ids"] == " ".join(map(str, sorted(set(b)-set(a)))) and record["removed_ids"] == " ".join(map(str, sorted(set(a)-set(b))))
    check("all per-user changes independently reconstructed", True)
    changed_order = sum(anchor[u] != submitted[u] for u in users)
    changed_set = sum(set(anchor[u]) != set(submitted[u]) for u in users)
    check("aggregate comparison counters", summary["changed_ordered_users"] == changed_order and summary["changed_set_users"] == changed_set and summary["order_only_users"] == changed_order-changed_set and summary["unchanged_users"] == len(users)-changed_order and summary["replaced_user_item_pairs"] == sum(len(set(submitted[u])-set(anchor[u])) for u in users))
    # Reconstruct the exact previously evaluated validation setting as well.
    validation_components = {}
    for method in config["weights"]:
        setting = "full10_t80" if method == "association_rules" else "full10_t50"
        validation_components[method] = rankings(ROOT / "reports/training_study" / setting / "runs" / method / "predictions.csv")
    validation_pop = [int(r["tv_show_id"]) for r in read_csv(ROOT / "reports/training_study/full10_t50/candidate_scores.csv")]
    val_pop_rank = {i: n for n, i in enumerate(validation_pop)}
    val_saved = rankings(ROOT / "reports/hybrids/runs" / config["id"] / "predictions.csv")
    truth = rankings(ROOT / "reports/interactions/validation_ground_truth.csv")
    check("same validation predictions as the already evaluated near-leader", set(val_saved) == set(truth) and all(val_saved[u] == exact_fusion(validation_components, u, config, val_pop_rank) for u in truth))
    for cohort, path, expected in [("all_primary", "cohort_primary.csv", candidate["validation_primary"]), ("template_primary", "cohort_template_primary.csv", candidate["validation_template"])]:
        ids = [r["user_id"] for r in read_csv(ROOT / "reports/popularity" / path)]
        mean = sum((exact_ap(set(truth[u]), val_saved[u])[0] for u in ids), Fraction(0))/len(ids)
        check(f"exact local MAP and frozen cohort: {cohort}", close(mean, expected) and close(mean, summary["validation_source"][cohort]))
    report = {"status": "passed", "submission_path": summary["submission_path"], "submission_sha256": sha256(submitted_path),
              "checks": checks, "verifier_sha256": sha256(Path(__file__)), "kaggle_result": None,
              "meaning": "Numerical/format verification; submission_002 has not been uploaded by the assistant"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    lines = ["# Submission 002: split the auxiliary RRF weight between rules and popularity", "",
             "**Upload `submissions/submission_002.csv`. Kaggle scores are pending.**", "",
             "## Hypothesis and fixed comparison", "",
             "Submission 001 returned public **0.43347**, private **0.41452**, recorded against its exact CSV SHA-256 with the user's screenshot. One submission alone does not establish validation rank transfer.",
             "002 keeps the identical weeks 11–30 MF/PPR50 and weekly-rule80 fits and source Top-5s. It changes RRF weights from MF=.5/PPR=.5/rules=.25 to MF=.5/PPR=.5/rules=.125/popularity=.125; offset remains zero. Total auxiliary weight stays .25. The full popularity Top-5 contributes to fusion, with the same popularity tie-break and actual-cold fallback as before.",
             "", "| Strategy | Primary validation MAP@5 | Template validation MAP@5 |", "|---|---:|---:|",
             "| 001 | 0.37356245 | 0.40764638 |", f"| 002 | {candidate['validation_primary']:.8f} | {candidate['validation_template']:.8f} |", "",
             "Primary validation slightly favours 001; template validation slightly favours 002. This is a close challenger for score improvement and a direct test of which local ordering transfers. Candidate weights were chosen from the existing validation runs rather than fitted to hidden user labels. Track both returned scores; use public for submission decisions per the exam.",
             "", "## Actual change in the upload", "",
             f"- **{changed_order:,}/{len(users):,}** users have a changed ordered Top-5; **{changed_set:,}** change the set of IDs and **{changed_order-changed_set:,}** change order only.",
             f"- **{len(users)-changed_order:,}** users are unchanged; mean list overlap is **{summary['mean_shared_top5']:.4f}/5**.",
             f"- **{summary['replaced_user_item_pairs']}** user–programme pairs enter and the same number leave. These are recommendation changes, not known relevance gains; Kaggle per-user truth is unavailable.",
             "- All **four actual cold users** retain the identical popularity Top-5.",
             "", "## Verification and evidence", "",
             f"**{len(checks)} independent checks passed:** exact template header/order and user strings, five unique nonzero eligible IDs, immutable scored anchor and model inputs, reconstruction of all component Top-5s from full-history scores, exact-rational fusion for both CSVs, per-user changes, and exact reconstruction of the prior local validation result.",
             "", "SHA-256:", "", "```text", summary["submission_sha256"], "```", "",
             "See summary.json, config.json, frozen_inputs.json, verification.json, recommendations.csv and changes_vs_001.csv. The four-upload sequence is in submissions/next_four_plan.md and scripts/kaggle_comparison_plan.json. Only 002 is prepared; 003–005 remain plans.",
             "", "```bash", "python3 scripts/prepare_submission_002.py", "python3 scripts/verify_submission_002.py", "```", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Passed {len(checks)} checks. READY: {submitted_path}")
    print(f"Changed lists: {changed_order}; changed sets: {changed_set}; order only: {changed_order-changed_set}.")


if __name__ == "__main__":
    main()
