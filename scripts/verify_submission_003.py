#!/usr/bin/env python3
"""Independently rebuild PPR candidate generation and MF reranking for 003."""

import csv
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/submission_003"


def reconstruct(users, archive, popularity, cold, depth=20):
    """Independent full eligible PPR sort, then stable MF sort of the shortlist."""
    ppr, mf = archive["scores_ppr"], archive["scores_implicit_mf"]
    ppr_ids = archive["items_ppr"].astype(int).tolist()
    mf_index = {int(i): n for n, i in enumerate(archive["items_implicit_mf"])}
    pool = set(popularity)
    predictions, candidate_rows = {}, {}
    for row, user in enumerate(users):
        positive = [(item, float(ppr[row, n])) for n, item in enumerate(ppr_ids) if item in pool and ppr[row, n] > 0]
        positive.sort(key=lambda pair: (-pair[1], pair[0]))
        prefix = [item for item, value in positive]
        used = set(prefix)
        ordered = popularity if user in cold else prefix + [i for i in popularity if i not in used]
        shortlist = ordered[:depth]
        mf_scores = {item: float(mf[row, mf_index[item]]) if item in mf_index else 0.0 for item in shortlist}
        ranked = sorted(enumerate(shortlist), key=lambda pair: (-mf_scores[pair[1]], pair[0]))
        predictions[user] = popularity[:5] if user in cold else [item for rank, item in ranked[:5]]
        candidate_rows[user] = (shortlist, mf_scores)
    return predictions, candidate_rows


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    manifest = json.loads((OUT / "frozen_inputs.json").read_text())
    paths = {k: ROOT / p for k, p in manifest["paths"].items()}
    for name, path in paths.items():
        check(f"immutable preparation input: {name}", sha256(path) == manifest["sha256"][name])
    summary = json.loads((OUT / "summary.json").read_text())
    config = json.loads((OUT / "config.json").read_text())
    plan = json.loads(paths["plan"].read_text())
    declared = next(r for r in plan["submissions"] if r["id"] == "submission_003")
    check("exact previously declared semantic strategy", config == declared["strategy"] == summary["selected_config"] == json.loads(paths["validation_config"].read_text()) and config == {"id": "ppr20_rerank_mf", "type": "rerank", "generator": "ppr", "reranker": "implicit_mf", "depth": 20})
    check("preparation/inference code hashes", all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    original = json.loads(paths["training_manifest"].read_text())
    check("same fitted-model inference code as 001/002", all(sha256(ROOT / "scripts" / f) == h for f, h in original["code_hashes"].items()))
    snapshot = json.loads(paths["score_snapshot"].read_text())
    results = {r["submission_id"]: r for r in snapshot["results"]}
    for name, expected in [("submission_001", (.43347, .41452)), ("submission_002", (.43359, .41489))]:
        result = results[name]
        check(f"reported scores and CSV identity: {name}", (result["public_score"], result["private_score"]) == expected and sha256(ROOT / result["csv_path"]) == result["csv_sha256"])
        check(f"score screenshot retained: {name}", sha256(ROOT / result["screenshot_path"]) == result["screenshot_sha256"])
    submission = ROOT / summary["submission_path"]
    with submission.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.reader(stream))
    users = [r["user_id"] for r in read_csv(paths["template"])]
    check("exact two-column template schema, no index", raw[0] == ["user_id", "tv_show_id"] and all(len(r) == 2 for r in raw[1:]))
    check("1260 exact user strings in original order", len(raw)-1 == len(users) == len(set(users)) == 1260 and [r[0] for r in raw[1:]] == users and all(str(int(u)) == u for u in users))
    check("five distinct canonical positive integer IDs per cell", all(len(r[1].split()) == len(set(r[1].split())) == 5 and r[1] == " ".join(r[1].split()) and all(i.isdecimal() and int(i) > 0 and str(int(i)) == i for i in r[1].split()) for r in raw[1:]))
    check("submitted bytes match preparation manifest", sha256(submission) == summary["submission_sha256"])
    predictions = rankings(submission)
    pop_rows = read_csv(paths["popularity"])
    popularity = [int(r["tv_show_id"]) for r in pop_rows]
    pool = {int(r["tv_show_id"]) for r in read_csv(paths["candidates"])}
    check("same 6632 available candidates and eligible predictions", len(popularity) == len(pool) == 6632 and set(popularity) == pool and all(set(ids) <= pool for ids in predictions.values()))
    check("model score rows use the original template order", json.loads(paths["model_users"].read_text()) == users)
    cold = set(json.loads(paths["cold_users"].read_text()))
    check("same four cold users and exact common fallback", len(cold) == 4 and all(predictions[u] == popularity[:5] for u in cold))
    scores = np.load(paths["scores"], allow_pickle=False)
    expected, shortlists = reconstruct(users, scores, popularity, cold)
    check("every full-history PPR20 -> MF output independently reconstructed", predictions == expected)
    check("no selected item comes from outside the PPR20 shortlist", all(set(predictions[u]) <= set(shortlists[u][0]) for u in users))
    candidates = read_csv(OUT / "rerank_candidates.csv")
    candidate_groups = {}
    for record in candidates:
        candidate_groups.setdefault(record["user_id"], []).append(record)
    check("twenty unique generator candidates saved for every user", len(candidates) == 20*len(users) and set(candidate_groups) == set(users) and all(len(rows) == len({r["tv_show_id"] for r in rows}) == 20 for rows in candidate_groups.values()))
    for user, rows in candidate_groups.items():
        ids, mf_scores = shortlists[user]
        assert [int(r["tv_show_id"]) for r in rows] == ids and [int(r["ppr_generator_rank"]) for r in rows] == list(range(1, 21))
        assert all(close(r["mf_score"], mf_scores[int(r["tv_show_id"])]) and (r["selected"] == "True") == (int(r["tv_show_id"]) in predictions[user]) for r in rows)
    check("candidate order, actual reranking scores and selected flags", True)
    trace = read_csv(OUT / "recommendations.csv")
    check("every recommendation trace matches the actual submitted rank", len(trace) == 5*len(users) and all(predictions[r["user_id"]][int(r["rank"])-1] == int(r["tv_show_id"]) for r in trace))
    contrasts = {r["reference"]: r for r in summary["comparisons"]}
    for name, source in [("submission_001", paths["previous_001"]), ("submission_002", paths["previous_002"])]:
        previous = rankings(source)
        rows = read_csv(OUT / f"changes_vs_{name}.csv")
        check(f"change table exact user coverage: {name}", len(rows) == len(users) and [r["user_id"] for r in rows] == users)
        for record in rows:
            user = record["user_id"]
            a, b = previous[user], predictions[user]
            assert record["previous_ids"] == " ".join(map(str, a)) and record["new_ids"] == " ".join(map(str, b))
            assert (record["changed_order"] == "True") == (a != b) and (record["changed_set"] == "True") == (set(a) != set(b))
            assert int(record["shared_top5"]) == len(set(a)&set(b)) and record["entered_ids"] == " ".join(map(str, sorted(set(b)-set(a)))) and record["removed_ids"] == " ".join(map(str, sorted(set(a)-set(b))))
        changed = sum(previous[u] != predictions[u] for u in users)
        changed_set = sum(set(previous[u]) != set(predictions[u]) for u in users)
        check(f"all changes and summary counters rebuilt: {name}", contrasts[name]["changed_ordered_users"] == changed and contrasts[name]["changed_set_users"] == changed_set and contrasts[name]["order_only_users"] == changed-changed_set and contrasts[name]["unchanged_users"] == len(users)-changed and contrasts[name]["entered_user_item_pairs"] == sum(len(set(predictions[u])-set(previous[u])) for u in users))
    # Independently verify that final inference implements the exact earlier
    # locally evaluated method, including candidate truncation and tie rules.
    val_dir = ROOT / "artifacts/semantic_hybrids"
    val_users = json.loads((val_dir / "users.json").read_text())
    val_pop = [int(r["tv_show_id"]) for r in read_csv(ROOT / "reports/training_study/full10_t50/candidate_scores.csv")]
    val_cold = set(json.loads((val_dir / "cold_users.json").read_text()))
    local_archive = np.load(val_dir / "scores.npz", allow_pickle=False)
    val_expected, _ = reconstruct(val_users, local_archive, val_pop, val_cold)
    val_saved = rankings(ROOT / "reports/semantic_hybrids/runs/ppr20_rerank_mf/predictions.csv")
    check("exact earlier validation rankings reproduced independently", val_expected == val_saved)
    truth = rankings(ROOT / "reports/interactions/validation_ground_truth.csv")
    for cohort, filename, number in [("all_primary", "cohort_primary.csv", 4030), ("template_primary", "cohort_template_primary.csv", 1150)]:
        ids = [r["user_id"] for r in read_csv(ROOT / "reports/popularity" / filename)]
        mean = sum((exact_ap(set(truth[u]), val_expected[u])[0] for u in ids), Fraction(0))/len(ids)
        check(f"exact frozen local MAP and population: {cohort}", len(ids) == number and close(mean, summary["validation_source"][cohort]))
    check("004 and 005 remain plans", not (ROOT / "submissions/submission_004.csv").exists() and not (ROOT / "submissions/submission_005.csv").exists())
    report = {"status": "passed", "submission_path": str(submission.relative_to(ROOT)), "submission_sha256": sha256(submission),
              "checks": checks, "verifier_sha256": sha256(Path(__file__)), "kaggle_score": None,
              "meaning": "Assistant numerical verification; 003 actual Kaggle score awaits user upload"}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    lines = ["# Submission 003: PPR Top-20 candidates reranked by MF", "", "**Upload `submissions/submission_003.csv`. Its returned Kaggle score is pending.**", "",
             "## Recorded results and question", "",
             "| Submission | Local MAP all | Local MAP template | Kaggle public | Kaggle private |", "|---|---:|---:|---:|---:|",
             "| 001: RRF MF/PPR/rules | 0.37356245 | 0.40764638 | 0.43347 | 0.41452 |",
             "| 002: RRF with rules/popularity split | 0.37284202 | 0.40792464 | 0.43359 | 0.41489 |",
             "| 003: PPR20 -> MF | 0.36888503 | 0.40055652 | pending | pending |", "",
             "002 exceeds 001 by **0.00012 public** and **0.00037 private**. This observed pair agrees with the template-subset ordering and reverses the primary-cohort ordering. The difference is small; it does not establish that one validation cohort is generally superior.",
             "003 is the strongest previously tested semantic hybrid. Both local cohorts predict it below 001 and 002. This upload tests whether that larger RRF-versus-reranking distinction transfers after all-history refitting. Public score remains the exam selection metric; inspected private scores are recorded as secondary feedback.",
             "", "## Exact inference", "",
             "1. Reuse identical weeks 11–30 MF/PPR models trained on 50%-qualified counts; no model is retrained and no parameters are retuned.",
             "2. Rank all eligible positive PPR scores, breaking score ties by numeric programme ID, then backfill from the same training-popularity order if necessary.",
             "3. Keep the first 20 eligible PPR candidates, then sort only those by MF score descending. MF-score ties retain generator order; scores from different methods are not added.",
             "4. Return five unique IDs. All four actual cold users receive exactly the previous popularity fallback.", "",
             "The saved rerank_candidates.csv shows all twenty IDs, PPR ranks, MF/PPR scores and selected flags. recommendations.csv gives the submitted ranks and training-only features. No hidden future viewing or per-user Kaggle labels are available.",
             "", "## Difference from the scored uploads", "",
             "| Reference | Changed ordered lists | Changed item sets | Order only | Unchanged users | Mean shared Top-5 |", "|---|---:|---:|---:|---:|---:|"]
    for name, row in contrasts.items():
        lines.append(f"| {name} | {row['changed_ordered_users']:,} | {row['changed_set_users']:,} | {row['order_only_users']:,} | {row['unchanged_users']:,} | {row['mean_shared_top5']:.4f}/5 |")
    lines += ["", "These are recommendation changes, not known gains or losses in relevance. Both previously uploaded CSVs remain byte-identical to their recorded hashes.",
              "", "## Verification and reproduction", "",
              f"**{len(checks)} independent checks passed:** immutable fitted inputs and code; exact template header/user strings/order; five unique nonzero eligible IDs; all full-history candidate generation and stable MF reranking; cold fallback; every saved candidate and change; and reconstruction of the exact earlier validation predictions and rational MAP on both cohorts.",
              "", "SHA-256:", "", "```text", summary["submission_sha256"], "```", "",
              "```bash", "python3 scripts/prepare_submission_003.py", "python3 scripts/verify_submission_003.py", "```", "",
              "The appendable score ledger is snapshotted in results_at_preparation.json for reproducibility. Configuration, summary, model/input hashes and validation evidence are retained here. The plan remains 003, then standalone MF (004), then the rules ablation (005). The user-reported allowance is now up to 100 submissions; additional ideas are recorded in submissions/progress.json for later local validation. Only 003 is prepared in this stage.", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Passed {len(checks)} checks. READY: {submission}")
    print(f"SHA-256: {sha256(submission)}")


if __name__ == "__main__":
    main()
