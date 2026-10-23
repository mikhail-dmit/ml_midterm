"""Frozen-model depth fusion and training-only collaborative recency weighting."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

from collaborative_models import fit_implicit_als, personalized_pagerank, restart_profiles
from hybrid_models import reciprocal_rank_fusion
from interaction_core import boundary_epoch
from recommender_bundle import Bundle, matrix_from_counts
from run_model_experiments import dump

ROOT = Path(__file__).resolve().parents[1]


def phase_paths(phase):
    if phase == "validation":
        scores = ROOT / "artifacts/semantic_hybrids"
        train = ROOT / "artifacts/training_study"
        return {"scores": scores / "scores.npz", "users": scores / "users.json",
                "counts50": train / "full10_t50/training_counts.parquet", "counts80": train / "full10_t80/training_counts.parquet",
                "popularity": train.parent.parent / "reports/training_study/full10_t50/candidate_scores.csv",
                "transition": train / "full10_t50/ppr/transition.npz", "events": train / "windows/full10/events.parquet"}
    if phase == "final":
        folder = ROOT / "artifacts/final_11_30"
        return {"scores": folder / "scores.npz", "users": folder / "users.json", "counts50": folder / "training_counts_50.parquet",
                "counts80": folder / "training_counts_80.parquet", "popularity": folder / "candidate_scores.csv",
                "transition": folder / "transition.npz", "events": folder / "training_events.parquet"}
    raise ValueError(phase)


def load_base(phase):
    paths = phase_paths(phase)
    archived = np.load(paths["scores"], allow_pickle=False)
    methods = ["implicit_mf", "ppr", "association_rules"]
    scores = {m: archived[f"scores_{m}"] for m in methods}
    items = {m: archived[f"items_{m}"].astype(int).tolist() for m in methods}
    users = json.loads(paths["users"].read_text())
    counts50, counts80 = pd.read_parquet(paths["counts50"]), pd.read_parquet(paths["counts80"])
    pop = pd.read_csv(paths["popularity"]).sort_values("rank").tv_show_id.astype(int).tolist()
    bundle = Bundle(users, pop, counts50, counts80, scores, items)
    if bundle.popularity != pop:
        raise AssertionError("Original popularity order changed")
    return bundle, counts50, counts80


def recency_training_counts(events, cutoff, half_life_weeks):
    if not math.isfinite(half_life_weeks) or half_life_weeks <= 0:
        raise ValueError("Half-life must be finite and positive")
    selected = events.loc[events.watched_seconds*2 >= events.duration].copy()
    if selected.empty or (selected.last_overlap > cutoff).any():
        raise ValueError("Expected nonempty past-only training events")
    selected["age_weeks"] = (cutoff-selected.last_overlap)/(7*86400)
    selected["raw_recency_weight"] = np.exp2(-selected.age_weeks/half_life_weeks)
    scale = len(selected)/selected.raw_recency_weight.sum()
    selected["recency_weight"] = selected.raw_recency_weight*scale
    counts = selected.groupby(["user_id", "tv_show_id"], sort=True).recency_weight.sum().rename("watched_airings").reset_index()
    return counts, selected, float(scale)


def fit_recency(phase, half_life, folder, seed):
    base, original50, original80 = load_base(phase)
    folder.mkdir(parents=True, exist_ok=True)
    paths = phase_paths(phase)
    cutoff_text = "2020-05-18" if phase == "validation" else "2020-07-27"
    cutoff = boundary_epoch(cutoff_text)
    events = pd.read_parquet(paths["events"])
    counts, weighted, scale = recency_training_counts(events, cutoff, half_life)
    if list(counts[["user_id", "tv_show_id"]].itertuples(index=False, name=None)) != list(original50[["user_id", "tv_show_id"]].sort_values(["user_id", "tv_show_id"]).itertuples(index=False, name=None)):
        raise AssertionError("Recency changed binary pair support")
    matrix, train_users, items = matrix_from_counts(counts)
    if items != base.items["implicit_mf"] or items != base.items["ppr"]:
        raise AssertionError("Collaborative item indices changed")
    lookup = {u: n for n, u in enumerate(train_users)}
    rows = [n for n, u in enumerate(base.users) if u in lookup]
    training_rows = [lookup[base.users[n]] for n in rows]
    transition = sparse.load_npz(paths["transition"])
    with threadpool_limits(limits=1):
        x, y, curve = fit_implicit_als(matrix, factors=16, confidence_scale=1, regularization=1, weighting="log1p", preference="log1p", epochs=15, seed=seed)
        mf = np.zeros_like(base.scores["implicit_mf"])
        mf[rows] = np.maximum(x[training_rows] @ y.T, 0)
        ppr = np.zeros_like(mf)
        mass, solver = personalized_pagerank(transition, restart_profiles(matrix)[training_rows], .5)
        ppr[rows] = mass
    np.savez_compressed(folder / "factors.npz", user_factors=x, item_factors=y)
    pd.DataFrame(curve).to_csv(folder / "learning_curve.csv", index=False)
    counts.to_parquet(folder / "weighted_counts.parquet", index=False, compression="zstd")
    weighted[["user_id", "airing_id", "tv_show_id", "last_overlap", "age_weeks", "raw_recency_weight", "recency_weight"]].to_parquet(folder / "event_weights.parquet", index=False, compression="zstd")
    dump(folder / "training_indices.json", {"users": train_users, "items": items})
    dump(folder / "recency.json", {"phase": phase, "cutoff_local": cutoff_text, "cutoff_epoch": cutoff, "half_life_weeks": half_life,
         "event_count": len(weighted), "global_mass_preserving_scale": scale, "weighted_count_sum": float(matrix.sum()),
         "binary_support_unchanged": True, "graph_reused": str(paths["transition"].relative_to(ROOT)), "rules_popularity_unchanged": True, "ppr_solver": solver})
    bundle = Bundle(base.users, base.pool, original50, original80, {"implicit_mf": mf, "ppr": ppr, "association_rules": base.scores["association_rules"]}, base.items)
    return bundle


def fuse_bundle(bundle, config):
    """No truth, local scores or Kaggle feedback accepted by inference."""
    pop_rank = {i: n for n, i in enumerate(bundle.popularity)}
    predicted = {}
    for row, user in enumerate(bundle.users):
        if user not in bundle.warm:
            predicted[user] = bundle.popularity[:5]
            continue
        lists = {m: bundle.queues[row][m]["global"][:config["depth"]] for m in config["weights"]}
        union = set(bundle.popularity[:5]).union(*lists.values())
        local_pop = sorted(union, key=pop_rank.__getitem__)
        predicted[user], _ = reciprocal_rank_fusion(lists, config["weights"], local_pop, config["offset"])
    return predicted
