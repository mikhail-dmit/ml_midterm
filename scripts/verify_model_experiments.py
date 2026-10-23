#!/usr/bin/env python3
"""Independent MF score/normal-equation, PPR power-iteration and MAP checks.

Does not import the model implementations or shared evaluator. Uses the saved
training matrix and factors/graphs plus the original programme table and truth.
"""

import csv
import hashlib
import json
import random
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    started = time.perf_counter()
    output, artifacts = ROOT / "reports/models", ROOT / "artifacts/models"
    checks = []
    def check(name, passed, evidence):
        if not passed:
            raise AssertionError(f"{name}: {evidence}")
        checks.append({"check": name, "passed": True, "evidence": evidence})
    counts = sparse.load_npz(artifacts / "training_counts.npz").tocsr()
    indices = json.loads((artifacts / "training_indices.json").read_text())
    users, items = indices["users"], indices["items"]
    user_map, item_map = {u: i for i, u in enumerate(users)}, {i: j for j, i in enumerate(items)}
    programmes = pd.read_parquet(ROOT / "artifacts/interactions/user_programme_interactions.parquet")
    train = programmes.loc[(programmes.split == "train") & (programmes.watched_airings > 0)]
    independent_counts = sparse.csr_matrix((train.watched_airings.to_numpy(dtype=float),
                                            (train.user_id.map(user_map), train.tv_show_id.map(item_map))), shape=counts.shape)
    check("Saved training matrix equals training-only input aggregates", (independent_counts != counts).nnz == 0,
          {"shape": list(counts.shape), "positive_pairs": counts.nnz, "qualifying_airings": int(counts.sum())})
    truth = {r["user_id"]: list(map(int, r["tv_show_id"].split())) for r in csv_rows(ROOT / "reports/interactions/validation_ground_truth.csv")}
    cohort = list(truth)
    template = [r["user_id"] for r in csv_rows(ROOT / "reports/popularity/cohort_template_primary.csv")]
    pool_rows = csv_rows(ROOT / "reports/popularity/validation_candidates.csv")
    pool = np.array(sorted(int(r["tv_show_id"]) for r in pool_rows), dtype=np.int64)
    popularity = [int(r["tv_show_id"]) for r in sorted(pool_rows, key=lambda r: int(r["rank"]))[:5]]
    supported = np.array([i for i, item in enumerate(pool) if int(item) in item_map])
    map_supported = np.array([item_map[int(pool[i])] for i in supported])
    examples = json.loads((output / "example_users.json").read_text())["users"]
    warm_cohort = [u for u in cohort if u in user_map]
    sample_users = list(dict.fromkeys([r["user_id"] for r in examples] + random.Random(20261023).sample(warm_cohort, 2)))
    input_paths = {
        "interactions": ROOT / "artifacts/interactions/user_programme_interactions.parquet",
        "truth": ROOT / "reports/interactions/validation_ground_truth.csv",
        "users": ROOT / "reports/interactions/validation_users.csv",
        "candidates": ROOT / "reports/popularity/validation_candidates.csv",
        "baseline": ROOT / "reports/popularity/predictions_allow_repeats.csv",
        "protocol": ROOT / "reports/popularity/protocol.json",
    }
    current_hashes = {name: digest(path) for name, path in input_paths.items()}
    selected = json.loads((output / "selected_models.json").read_text())
    experiment_results = []
    with threadpool_limits(limits=1):
        for path in sorted((output / "runs").glob("*/summary.json")):
            result = json.loads(path.read_text())
            config, run_id = result["config"], result["config"]["id"]
            print(f"Verifying {run_id} ...", flush=True)
            check(run_id + ": identical frozen input fingerprints", result["source_hashes"] == current_hashes, current_hashes["truth"])
            prediction_rows = csv_rows(path.parent / "predictions.csv")
            predictions = {r["user_id"]: list(map(int, r["tv_show_id"].split())) for r in prediction_rows}
            check(run_id + ": unchanged cohort and full-pool valid Top-5", len(predictions) == len(prediction_rows) == 4030 and set(predictions) == set(truth)
                  and all(len(set(ids)) == len(ids) == 5 and set(ids).issubset(pool) for ids in predictions.values()), len(predictions))
            check(run_id + ": all cold users get the same popularity fallback", all(predictions[u] == popularity for u in cohort if u not in user_map),
                  sum(u not in user_map for u in cohort))
            exact_ap = {}
            hits = {}
            for user, predicted in predictions.items():
                positions = [rank for rank, item in enumerate(predicted, 1) if item in set(truth[user])]
                exact_ap[user] = sum((Fraction(j, rank) for j, rank in enumerate(positions, 1)), Fraction(0)) / 5
                hits[user] = len(positions)
            saved_per_user = {r["user_id"]: r for r in csv_rows(path.parent / "per_user_metrics.csv")}
            max_ap_error = max(abs(float(exact_ap[u]) - float(saved_per_user[u]["ap_at_5"])) for u in cohort)
            check(run_id + ": every user AP agrees with rational arithmetic", max_ap_error < 1e-15, max_ap_error)
            for metric in result["metrics"]:
                selected_users = cohort if metric["cohort"] == "all_primary" else template
                exact_mean = sum((exact_ap[u] for u in selected_users), Fraction(0)) / len(selected_users)
                check(run_id + " / " + metric["cohort"] + ": MAP and hit counts", abs(float(exact_mean) - metric["map_at_5"]) < 1e-15
                      and sum(hits[u] for u in selected_users) == metric["total_hits"], {"MAP_fraction": str(exact_mean), "users": len(selected_users)})
            recs = {(r["user_id"], int(r["tv_show_id"])): r for r in csv_rows(path.parent / "recommendations.csv")}
            if config["method"] == "implicit_mf":
                factors = np.load(artifacts / run_id / "factors.npz", allow_pickle=False)
                x, y = factors["user_factors"], factors["item_factors"]
                check(run_id + ": factor index maps preserve original IDs", factors["user_ids"].tolist() == users and factors["item_ids"].tolist() == items, list(x.shape))
                max_score_error = 0.0
                for user in warm_cohort:
                    dot_scores = y @ x[user_map[user]]
                    available_scores = np.zeros(len(pool))
                    available_scores[supported] = dot_scores[map_supported]
                    # Stable sort over numeric-ID-sorted pool is independent of the model's lexsort.
                    expected = pool[np.argsort(-available_scores, kind="stable")[:5]].tolist()
                    if predictions[user] != expected:
                        raise AssertionError(f"MF rank mismatch for {run_id}, user {user}")
                    for item in expected:
                        actual = float(recs[(user, item)]["model_score"])
                        max_score_error = max(max_score_error, abs(actual - dot_scores[item_map[item]]))
                check(run_id + ": all warm-user rankings reproduce from factor dot products", max_score_error < 1e-11, max_score_error)
                # The last ALS half-step solves items conditional on the saved users.
                transposed = counts.T.tocsr()
                residuals = []
                for item in list(range(5)) + random.Random(20261023).sample(range(len(items)), 5):
                    a, b = transposed.indptr[item:item+2]
                    row_indices, raw = transposed.indices[a:b], transposed.data[a:b]
                    c = 1 + config["confidence_scale"] * np.log1p(raw)
                    target = np.log1p(raw) if config.get("preference", "binary") == "log1p" else np.ones(len(raw))
                    observed_x = x[row_indices]
                    normal = x.T @ x + observed_x.T @ ((c - 1)[:, None] * observed_x) + config["regularization"] * np.eye(x.shape[1])
                    rhs = observed_x.T @ (c * target)
                    residuals.append(float(np.linalg.norm(normal @ y[item] - rhs) / max(1, np.linalg.norm(rhs))))
                check(run_id + ": item-factor normal equations hold", max(residuals) < 1e-9, max(residuals))
                curve = csv_rows(path.parent / "learning_curve.csv")
                losses = [float(r["training_objective"]) for r in curve]
                check(run_id + ": objective decreases each epoch", all(b <= a + 1e-7 * max(1, a) for a, b in zip(losses, losses[1:])), {"first": losses[0], "last": losses[-1]})
                checkpoints = csv_rows(path.parent / "validation_checkpoints.csv")
                best_epoch = int(max(checkpoints, key=lambda r: float(r["all_primary_map_at_5"]))["epoch"])
                check(run_id + ": best validation checkpoint restored", best_epoch == result["diagnostics"]["selected_epoch"], best_epoch)
                if selected["implicit_mf"]["run_id"] == run_id:
                    user = next(r["user_id"] for r in examples if r["role"] == "heavy")
                    item = predictions[user][0]
                    xf, yf = x[user_map[user]], y[item_map[item]]
                    pd.DataFrame({"factor": np.arange(1, len(xf) + 1), "user_factor": xf, "item_factor": yf, "product": xf * yf}).to_csv(output / "manual_mf_dot_product.csv", index=False)
                    (output / "manual_mf_dot_product.json").write_text(json.dumps({"user_id": user, "tv_show_id": item,
                        "run_id": run_id, "sum_of_factor_products": float(sum(xf * yf)),
                        "reported_score": float(recs[(user, item)]["model_score"]), "student_verification": "Not performed or claimed"}, indent=2) + "\n")
            else:
                adjacency = sparse.load_npz(artifacts / run_id / "adjacency.npz").tocsr()
                transition = sparse.load_npz(artifacts / run_id / "transition.npz").tocsr()
                degrees = np.asarray(adjacency.sum(axis=1)).ravel()
                row_sums = np.asarray(transition.sum(axis=1)).ravel()
                check(run_id + ": graph has no self-loops, nonnegative weights and normalized transitions", bool((adjacency.diagonal() == 0).all()
                      and (adjacency.data >= 0).all() and np.allclose(row_sums[degrees > 0], 1, atol=1e-12)), {"nodes": adjacency.shape[0], "nonzeros": adjacency.nnz})
                columns = counts.tocsc()
                sample_pairs = [(i, j) for i in range(5) for j in range(i+1, 5)] + [tuple(random.Random(20261023 + n).sample(range(len(items)), 2)) for n in range(10)]
                max_edge_error = 0.0
                for i, j in sample_pairs:
                    ui = set(columns.indices[columns.indptr[i]:columns.indptr[i+1]])
                    uj = set(columns.indices[columns.indptr[j]:columns.indptr[j+1]])
                    expected = len(ui & uj)
                    if config["normalization"] == "cosine":
                        expected /= np.sqrt(len(ui) * len(uj))
                    max_edge_error = max(max_edge_error, abs(float(adjacency[i, j]) - expected))
                check(run_id + ": graph edge weights match independent viewer-set intersections", max_edge_error < 1e-12, max_edge_error)
                restart = np.zeros((len(sample_users), len(items)))
                for row, user in enumerate(sample_users):
                    history = counts.getrow(user_map[user])
                    weights = np.log1p(history.data) if config["weighting"] == "log1p" else history.data
                    restart[row, history.indices] = weights / weights.sum()
                mass = restart.copy()
                alpha = config["alpha"]
                dangling = row_sums == 0
                for iteration in range(1, 10001):
                    nxt = alpha * (transition.T @ mass.T).T + (1 - alpha + alpha * mass[:, dangling].sum(axis=1)[:, None]) * restart
                    residual = float(np.max(np.abs(nxt - mass).sum(axis=1)))
                    mass = nxt
                    if residual < 1e-13:
                        break
                check(run_id + ": independent power iteration converges and conserves mass", residual < 1e-13 and np.allclose(mass.sum(axis=1), 1, atol=1e-12),
                      {"iterations": iteration, "max_L1_change": residual, "sampled_users": sample_users})
                max_score_error, max_rank_violation = 0.0, 0.0
                for row, user in enumerate(sample_users):
                    available_scores = np.zeros(len(pool))
                    available_scores[supported] = mass[row, map_supported]
                    cutoff = np.sort(available_scores)[-5]
                    for item in predictions[user]:
                        score = mass[row, item_map[item]]
                        max_score_error = max(max_score_error, abs(score - float(recs[(user, item)]["model_score"])))
                        max_rank_violation = max(max_rank_violation, cutoff - score)
                check(run_id + ": saved PPR scores/ranking agree with independent iteration", max_score_error < 1e-10 and max_rank_violation < 1e-10,
                      {"max_score_error": max_score_error, "max_top5_cutoff_violation": max_rank_violation})
            experiment_results.append({"run_id": run_id, "verified": True, "metrics": result["metrics"]})
    result = {"passed": True, "checks": checks, "experiments": experiment_results,
              "elapsed_seconds": time.perf_counter() - started,
              "verification_scope": "All runs: fixed-input/cohort/candidate/cold-fallback checks and exact AP/MAP; MF: all-user dot-product rankings and sampled normal equations; PPR: sampled co-view edges and independent iterative solver",
              "student_personal_verification": "Not claimed; manual_mf_dot_product.csv/json exported for a later student calculation"}
    dump_path = output / "verification.json"
    dump_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Passed {len(checks)} checks across {len(experiment_results)} runs in {result['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    main()
