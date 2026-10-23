"""Restore validation components or refit identical MF/PPR/weekly-rule models."""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

from collaborative_models import build_coview_graph, fit_implicit_als, personalized_pagerank, restart_profiles
from content_rule_models import count_weights, mine_pair_rules
from run_model_experiments import dump
from training_study import weekly_baskets

ROOT = Path(__file__).resolve().parents[1]
METHODS = ["implicit_mf", "ppr", "association_rules", "popularity"]


def matrix_from_counts(train):
    users, items = sorted(train.user_id.unique()), sorted(int(i) for i in train.tv_show_id.unique())
    ui, ii = {u: n for n, u in enumerate(users)}, {i: n for n, i in enumerate(items)}
    matrix = sparse.csr_matrix((train.watched_airings.to_numpy(dtype=float), (train.user_id.map(ui), train.tv_show_id.map(ii))), shape=(len(users), len(items)))
    return matrix, users, items


def counts_from_events(events, percent):
    selected = events.loc[events.watched_seconds*100 >= events.duration*percent].copy()
    train = selected.groupby(["user_id", "tv_show_id"], sort=True).size().rename("watched_airings").reset_index()
    return train, selected


class Bundle:
    def __init__(self, users, pool, train50, train80, scores, items):
        self.users, self.pool, self.scores, self.items = users, sorted(pool), scores, items
        self.indices = {m: {i: n for n, i in enumerate(ids)} for m, ids in items.items()}
        self.seen = {u: set(int(i) for i in f.tv_show_id) for u, f in train80.groupby("user_id", sort=False)}
        self.warm = set(train50.user_id)
        self.pop_counts = {int(i): int(n) for i, n in train50.groupby("tv_show_id").watched_airings.sum().items()}
        self.popularity = sorted(self.pool, key=lambda i: (-self.pop_counts.get(i, 0), i))
        self.queues = []

    def score(self, method, row, item):
        if method == "popularity":
            return float(self.pop_counts.get(item, 0))
        index = self.indices[method].get(item)
        return float(self.scores[method][row, index]) if index is not None else 0.0

    def prepare_queues(self, depth=20):
        eligible = set(self.pool)
        for row, user in enumerate(self.users):
            queues = {}
            seen = self.seen.get(user, set())
            for method in METHODS:
                if method == "popularity" or user not in self.warm:
                    ordered = self.popularity
                else:
                    ids = np.asarray(self.items[method], dtype=np.int64)
                    values = self.scores[method][row]
                    valid = np.flatnonzero((values > 0) & np.isin(ids, self.pool))
                    ordered = ids[valid[np.lexsort((ids[valid], -values[valid]))]].astype(int).tolist()
                    positive = set(ordered)
                    ordered += [i for i in self.popularity if i not in positive]
                queues[method] = {"global": ordered[:depth], "familiar": [i for i in ordered if i in seen][:depth], "new": [i for i in ordered if i not in seen][:depth]}
                if len(ordered) != len(eligible) or set(ordered) != eligible:
                    raise AssertionError("Component order changed candidate eligibility")
            self.queues.append(queues)

    def save(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        arrays = {f"scores_{m}": values for m, values in self.scores.items()}
        arrays.update({f"items_{m}": np.asarray(ids, dtype=np.int64) for m, ids in self.items.items()})
        np.savez_compressed(folder / "scores.npz", **arrays)
        dump(folder / "users.json", self.users)
        dump(folder / "history.json", {u: sorted(self.seen.get(u, set())) for u in self.users})
        dump(folder / "cold_users.json", [u for u in self.users if u not in self.warm])
        pd.DataFrame({"rank": np.arange(1, len(self.pool)+1), "tv_show_id": self.popularity,
                      "training_watched_airings": [self.pop_counts.get(i, 0) for i in self.popularity]}).to_csv(folder / "candidate_scores.csv", index=False)


def scores_from_models(users, train50, train80, x, y, transition, rules):
    counts50, ids50, items50 = matrix_from_counts(train50)
    counts80, ids80, items80 = matrix_from_counts(train80)
    lookup50, lookup80 = {u: n for n, u in enumerate(ids50)}, {u: n for n, u in enumerate(ids80)}
    rows50 = [n for n, u in enumerate(users) if u in lookup50]
    rows80 = [n for n, u in enumerate(users) if u in lookup80]
    train_rows50 = [lookup50[users[n]] for n in rows50]
    train_rows80 = [lookup80[users[n]] for n in rows80]
    mf = np.zeros((len(users), len(items50)))
    ppr = np.zeros_like(mf)
    ar = np.zeros((len(users), len(items80)))
    mf[rows50] = np.maximum(x[train_rows50] @ y.T, 0)
    mass, solver = personalized_pagerank(transition, restart_profiles(counts50)[train_rows50], .5)
    ppr[rows50] = mass
    ar[rows80] = (count_weights(counts80[train_rows80], "log1p") @ rules).toarray()
    return {"implicit_mf": mf, "ppr": ppr, "association_rules": ar}, {"implicit_mf": items50, "ppr": items50, "association_rules": items80}, solver


def restore_validation(users, pool):
    folder = ROOT / "artifacts/training_study"
    train50 = pd.read_parquet(folder / "full10_t50/training_counts.parquet")
    train80 = pd.read_parquet(folder / "full10_t80/training_counts.parquet")
    factors = np.load(folder / "full10_t50/implicit_mf/factors.npz", allow_pickle=False)
    transition = sparse.load_npz(folder / "full10_t50/ppr/transition.npz")
    rules = sparse.load_npz(folder / "full10_t80/association_rules/rule_weights.npz")
    with threadpool_limits(limits=1):
        scores, items, solver = scores_from_models(users, train50, train80, factors["user_factors"], factors["item_factors"], transition, rules)
    return Bundle(users, pool, train50, train80, scores, items), {"ppr_solver": solver, "component_refitting": False}


def fit_full_history(events, users, pool, folder, seed):
    folder.mkdir(parents=True, exist_ok=True)
    train50, _ = counts_from_events(events, 50)
    train80, events80 = counts_from_events(events, 80)
    train50.to_parquet(folder / "training_counts_50.parquet", index=False, compression="zstd")
    train80.to_parquet(folder / "training_counts_80.parquet", index=False, compression="zstd")
    counts50, users50, items50 = matrix_from_counts(train50)
    _, users80, items80 = matrix_from_counts(train80)
    dump(folder / "indices_50.json", {"users": users50, "items": items50})
    dump(folder / "indices_80.json", {"users": users80, "items": items80})
    started = time.perf_counter()
    with threadpool_limits(limits=1):
        x, y, curve = fit_implicit_als(counts50, factors=16, confidence_scale=1, regularization=1, weighting="log1p", preference="log1p", epochs=15, seed=seed)
        np.savez_compressed(folder / "factors.npz", user_factors=x, item_factors=y)
        pd.DataFrame(curve).to_csv(folder / "learning_curve.csv", index=False)
        _, transition, _, graph = build_coview_graph(counts50, "raw")
        sparse.save_npz(folder / "transition.npz", transition)
        baskets, basket_keys = weekly_baskets(events80, items80)
        rules, table, binary, _, _ = mine_pair_rules(baskets, items80, 5, .1, "confidence")
        sparse.save_npz(folder / "rule_weights.npz", rules)
        sparse.save_npz(folder / "baskets.npz", binary)
        dump(folder / "basket_keys.json", basket_keys)
        table.to_parquet(folder / "rules.parquet", index=False)
        scores, items, solver = scores_from_models(users, train50, train80, x, y, transition, rules)
    diagnostics = {"training_users_50": len(users50), "training_items_50": len(items50), "training_pairs_50": len(train50),
                   "training_airings_50": int(train50.watched_airings.sum()), "training_airings_80": int(train80.watched_airings.sum()),
                   "training_pairs_80": len(train80), "weekly_baskets": len(basket_keys), "rules": len(table), "graph": graph,
                   "ppr_solver": solver, "initial_MF_objective": curve[0]["training_objective"], "final_MF_objective": curve[-1]["training_objective"],
                   "fit_and_component_scoring_seconds": time.perf_counter()-started}
    return Bundle(users, pool, train50, train80, scores, items), diagnostics
