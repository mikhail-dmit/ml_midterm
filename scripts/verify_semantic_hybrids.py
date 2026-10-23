#!/usr/bin/env python3
"""Independent full-score reconstruction of role/rerank/switch experiments."""

import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from verify_hybrid_experiments import close, exact_ap, rankings, read_csv, sha256

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/semantic_hybrids"
ART = ROOT / "artifacts/semantic_hybrids"


def main():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    manifest = json.loads((OUT / "frozen_inputs.json").read_text())
    for name, file in manifest["paths"].items():
        check(f"immutable input: {name}", sha256(ROOT / file) == manifest["sha256"][name])
    plan = json.loads((OUT / "plan.json").read_text())
    check("source plan equals scored plan", plan == json.loads((ROOT / manifest["paths"]["plan"]).read_text()))
    users = json.loads((ART / "users.json").read_text())
    template = [r["user_id"] for r in read_csv(ROOT / manifest["paths"]["template"])]
    truth = rankings(ROOT / manifest["paths"]["truth"])
    check("fixed 4030/1150 users and original truth", len(users) == len(set(users)) == 4030 and set(users) == set(truth) and len(template) == 1150 and set(template) <= set(users))
    scores = np.load(ART / "scores.npz", allow_pickle=False)
    methods = ["implicit_mf", "ppr", "association_rules", "popularity"]
    item_ids = {m: scores[f"items_{m}"].astype(int).tolist() for m in methods[:-1]}
    values = {m: scores[f"scores_{m}"] for m in methods[:-1]}
    item_index = {m: {i: n for n, i in enumerate(ids)} for m, ids in item_ids.items()}
    candidate_rows = read_csv(ART / "candidate_scores.csv")
    pop = [int(r["tv_show_id"]) for r in candidate_rows]
    pop_counts = {int(r["tv_show_id"]): int(r["training_watched_airings"]) for r in candidate_rows}
    pool = set(pop)
    check("original 6384 candidate eligibility", pool == {int(r["tv_show_id"]) for r in read_csv(ROOT / manifest["paths"]["candidates"])} and len(pop) == 6384 and 0 not in pool)
    counts50 = pd.read_parquet(ROOT / manifest["paths"]["counts_full10_t50"])
    counts80 = pd.read_parquet(ROOT / manifest["paths"]["counts_full10_t80"])
    check("only original training rows in component inputs", counts50.split.eq("train").all() and counts80.split.eq("train").all())
    warm = set(counts50.user_id)
    seen = {u: set(int(i) for i in f.tv_show_id) for u, f in counts80.groupby("user_id", sort=False)}
    stored_history = json.loads((ART / "history.json").read_text())
    check("strict familiarity/gate uses only training positives", stored_history == {u: sorted(seen.get(u, set())) for u in users})
    cold = {u for u in users if u not in warm}
    check("actual cold users preserved", len(cold) == 43 and cold == set(json.loads((ART / "cold_users.json").read_text())))
    total_counts = counts50.groupby("tv_show_id").watched_airings.sum().to_dict()
    check("popularity count magnitudes and ordering", pop == sorted(pool, key=lambda i: (-total_counts.get(i, 0), i)) and all(pop_counts[i] == total_counts.get(i, 0) for i in pool))
    configs = [{"id": m, "type": "single", "method": m} for m in methods] + [plan["rrf_control"]] + plan["runs"]
    predicted = {c["id"]: rankings(OUT / "runs" / c["id"] / "predictions.csv") for c in configs}
    reconstructed = {name: {} for name in predicted}
    # Build full eligible order from saved component scores independently of the
    # production queues; role filtering happens before the depth-20 truncation.
    for row, user in enumerate(users):
        global_orders, familiar_orders, new_orders = {}, {}, {}
        for method in methods:
            if method == "popularity" or user in cold:
                ordered = pop
            else:
                positive = [(item, float(values[method][row, n])) for n, item in enumerate(item_ids[method]) if item in pool and values[method][row, n] > 0]
                positive.sort(key=lambda pair: (-pair[1], pair[0]))
                prefix = [item for item, value in positive]
                used = set(prefix)
                ordered = prefix + [i for i in pop if i not in used]
            global_orders[method] = ordered[:20]
            familiar_orders[method] = [i for i in ordered if i in seen.get(user, set())][:20]
            new_orders[method] = [i for i in ordered if i not in seen.get(user, set())][:20]
        def score(method, item):
            if method == "popularity":
                return pop_counts[item]
            n = item_index[method].get(item)
            return float(values[method][row, n]) if n is not None else 0.0
        for config in configs:
            if user in cold or ("max_sparse_history" in config and len(seen.get(user, set())) <= config["max_sparse_history"]):
                chosen = pop[:5]
            elif config["type"] == "single":
                chosen = global_orders[config["method"]][:5]
            elif config["type"] == "switch":
                chosen = global_orders[config["warm_method"]][:5]
            elif config["type"] == "rerank":
                candidates = global_orders[config["generator"]][:config["depth"]]
                chosen = sorted(candidates, key=lambda i: (-score(config["reranker"], i), candidates.index(i)))[:5]
            elif config["type"] == "slots":
                fam, new = list(familiar_orders[config["favourite"]]), list(new_orders[config["new"]])
                if "new_reranker" in config:
                    candidates = new[:config["depth"]]
                    new = sorted(candidates, key=lambda i: (-score(config["new_reranker"], i), candidates.index(i)))
                chosen = []
                for n in range(5):
                    queue = fam if n < config["familiar_slots"] else new
                    other = new if n < config["familiar_slots"] else fam
                    chosen.append((queue if queue else other).pop(0))
            else:
                utility = defaultdict(Fraction)
                for method, weight in config["weights"].items():
                    for rank, item in enumerate(global_orders[method][:5], 1):
                        utility[item] += Fraction(str(weight)) / (config["offset"]+rank)
                chosen = sorted(utility, key=lambda i: (-utility[i], pop.index(i), i))[:5]
            assert predicted[config["id"]][user] == chosen, f"Independent inference {config['id']}/{user}"
            reconstructed[config["id"]][user] = chosen
    check("every output independently reconstructed from full scores and training-only roles", True)
    check("RRF control reproduces previous exact predictions", predicted[plan["rrf_control"]["id"]] == rankings(ROOT / manifest["paths"]["rrf_predictions"]))
    comparison = {(r["run_id"], r["cohort"]): r for r in read_csv(OUT / "comparison.csv")}
    for config in configs:
        name = config["id"]
        output = predicted[name]
        check(f"fixed users/valid Top-5/cold fallback: {name}", set(output) == set(users) and all(len(ids) == len(set(ids)) == 5 and set(ids) <= pool for ids in output.values()) and all(output[u] == pop[:5] for u in cold))
        result = {u: exact_ap(set(truth[u]), output[u]) for u in users}
        for cohort, ids in [("all_primary", users), ("template_primary", template)]:
            record = comparison[(name, cohort)]
            hits = sum(result[u][1] for u in ids)
            mean = sum((result[u][0] for u in ids), Fraction(0))/len(ids)
            check(f"exact MAP/hits and cohort denominator: {name}/{cohort}", int(record["users"]) == len(ids) and close(record["map_at_5"], mean) and int(record["total_hits"]) == hits and close(record["precision_at_5"], Fraction(hits, 5*len(ids))) and close(record["hit_rate_at_5"], Fraction(sum(result[u][1] > 0 for u in ids), len(ids))))
        saved = read_csv(OUT / "runs" / name / "per_user_metrics.csv")
        check(f"all per-user AP values: {name}", len(saved) == len(users) and all(close(r["ap_at_5"], result[r["user_id"]][0]) for r in saved))
        trace = read_csv(OUT / "runs" / name / "recommendations.csv")
        check(f"role/feature/hit explanation provenance: {name}", len(trace) == 5*len(users) and all(output[r["user_id"]][int(r["rank"])-1] == int(r["tv_show_id"]) and (r["familiar_training_80pct"] == "True") == (int(r["tv_show_id"]) in seen.get(r["user_id"], set())) and int(r["history_distinct_80pct"]) == len(seen.get(r["user_id"], set())) and (r["in_true_top5"] == "True") == (int(r["tv_show_id"]) in truth[r["user_id"]]) for r in trace))
        summary = json.loads((OUT / "runs" / name / "summary.json").read_text())
        check(f"config/code provenance: {name}", summary["config"] == config and all(sha256(ROOT / "scripts" / f) == h for f, h in summary["code_hashes"].items()))
    selection = json.loads((OUT / "selection.json").read_text())
    best = min(predicted, key=lambda name: (-float(comparison[(name, "all_primary")]["map_at_5"]), name))
    check("selection includes unchanged RRF and singles and uses primary only", selection["selected_id"] == best and selection["selected_config"] == next(c for c in configs if c["id"] == best))
    result = {"status": "passed", "checks": checks, "verified_runs": list(predicted), "verifier_sha256": sha256(Path(__file__)),
              "scope": "Assistant independent numerical reconstruction, not student personal verification"}
    (OUT / "verification.json").write_text(json.dumps(result, indent=2)+"\n")
    print(f"Passed {len(checks)} checks across {len(configs)} controls and semantic strategies.")


if __name__ == "__main__":
    main()
