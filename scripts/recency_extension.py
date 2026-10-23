"""Compose existing MF/PPR components and optional recency-weighted rule queries/votes."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from content_rule_models import count_weights
from interaction_core import boundary_epoch
from recommender_bundle import Bundle, matrix_from_counts
from refinement_models import fit_recency, load_base, phase_paths, recency_training_counts
from run_model_experiments import digest, dump
from run_refinement_study import save_components

ROOT = Path(__file__).resolve().parents[1]
SPEC_KEYS = ["mf_half_life", "ppr_half_life", "rules_half_life", "pop_half_life"]


def variant_name(config):
    return "_".join(f"{key.split('_')[0]}{config[key] if config[key] is not None else 'raw'}" for key in SPEC_KEYS)


def cf_source(phase, half_life, cache, seed):
    if half_life is None:
        return phase_paths(phase)["scores"].parent
    if phase == "validation" and half_life in [4, 8]:
        return ROOT / "artifacts/refinement/validation" / f"h{half_life}"
    if phase == "final" and half_life == 8:
        return ROOT / "artifacts/submission_006"
    folder = cache / f"cf_h{half_life}"
    paths = phase_paths(phase)
    expected = {"phase": phase, "half_life": half_life, "seed": seed,
                "sources": {k: digest(p) for k, p in paths.items()}, "code": digest(ROOT / "scripts/refinement_models.py")}
    marker = folder / "cache_manifest.json"
    if not marker.exists() or json.loads(marker.read_text()) != expected:
        bundle = fit_recency(phase, half_life, folder, seed)
        bundle.save(folder)
        dump(marker, expected)
    return folder


def strict_rule_counts(events, cutoff, half_life):
    strict = events.loc[events.watched_seconds*5 >= events.duration*4].copy()
    return recency_training_counts(strict, cutoff, half_life)


class VoteBundle(Bundle):
    """Weighted popularity votes may change; the shared tie/fallback order does not."""
    def __init__(self, *args, vote_counts=None):
        super().__init__(*args)
        self.vote_counts = self.pop_counts if vote_counts is None else vote_counts

    def prepare_queues(self, depth=20):
        super().prepare_queues(depth)
        order = sorted(self.pool, key=lambda i: (-self.vote_counts.get(i, 0), i))
        for row, user in enumerate(self.users):
            if user not in self.warm:
                continue
            seen = self.seen.get(user, set())
            self.queues[row]["popularity"] = {"global": order[:depth], "familiar": [i for i in order if i in seen][:depth], "new": [i for i in order if i not in seen][:depth]}

    def score(self, method, row, item):
        if method == "popularity" and self.users[row] in self.warm:
            return float(self.vote_counts.get(item, 0))
        return super().score(method, row, item)


def compose_bundle(phase, config, folder, cache, seed):
    folder.mkdir(parents=True, exist_ok=True)
    base, counts50, counts80 = load_base(phase)
    sources = {m: cf_source(phase, config[f"{m}_half_life"], cache, seed) for m in ["mf", "ppr"]}
    mf_archive = np.load(sources["mf"] / "scores.npz", allow_pickle=False)
    ppr_archive = np.load(sources["ppr"] / "scores.npz", allow_pickle=False)
    scores = {"implicit_mf": mf_archive["scores_implicit_mf"], "ppr": ppr_archive["scores_ppr"], "association_rules": base.scores["association_rules"]}
    for method, archive in [("implicit_mf", mf_archive), ("ppr", ppr_archive)]:
        if archive[f"items_{method}"].astype(int).tolist() != base.items[method]:
            raise AssertionError("Mixed component item indices changed")
    for source in sources.values():
        if json.loads((source / "users.json").read_text()) != base.users:
            raise AssertionError("Mixed component user order changed")
    paths = phase_paths(phase)
    rule_matrix = ROOT / ("artifacts/training_study/full10_t80/association_rules/rule_weights.npz" if phase == "validation" else "artifacts/final_11_30/rule_weights.npz")
    rules_metadata = None
    if config["rules_half_life"] is not None:
        cutoff = boundary_epoch("2020-05-18" if phase == "validation" else "2020-07-27")
        events = pd.read_parquet(paths["events"])
        weighted, event_weights, scale = strict_rule_counts(events, cutoff, config["rules_half_life"])
        matrix, train_users, items = matrix_from_counts(weighted)
        if items != base.items["association_rules"]:
            raise AssertionError("Rule query item support changed")
        query = count_weights(matrix, "log1p")
        weights = sparse.load_npz(rule_matrix)
        index = {u: n for n, u in enumerate(train_users)}
        rows = [n for n, u in enumerate(base.users) if u in index]
        score = np.zeros_like(scores["association_rules"])
        score[rows] = (query[[index[base.users[n]] for n in rows]] @ weights).toarray()
        scores["association_rules"] = score
        weighted.to_parquet(folder / "rule_query_counts.parquet", index=False, compression="zstd")
        event_weights[["user_id", "airing_id", "last_overlap", "recency_weight"]].to_parquet(folder / "rule_query_event_weights.parquet", index=False, compression="zstd")
        dump(folder / "rule_query_indices.json", {"users": train_users, "items": items})
        rules_metadata = {"half_life": config["rules_half_life"], "cutoff": cutoff, "strict_events": len(event_weights), "global_scale": scale,
                          "matrix_path": str(rule_matrix.relative_to(ROOT)), "matrix_sha256": digest(rule_matrix)}
    vote_counts = None
    pop_source = None
    if config["pop_half_life"] is not None:
        pop_source = cf_source(phase, config["pop_half_life"], cache, seed)
        weighted = pd.read_parquet(pop_source / "weighted_counts.parquet")
        vote_counts = {int(i): float(n) for i, n in weighted.groupby("tv_show_id").watched_airings.sum().items()}
    bundle = VoteBundle(base.users, base.pool, counts50, counts80, scores, base.items, vote_counts=vote_counts)
    bundle.prepare_queues(depth=20)
    save_components(bundle, folder)
    vote_order = sorted(base.pool, key=lambda i: (-bundle.vote_counts.get(i, 0), i))
    pd.DataFrame({"rank": np.arange(1, len(vote_order)+1), "tv_show_id": vote_order,
                  "vote_count": [bundle.vote_counts.get(i, 0) for i in vote_order]}).to_csv(folder / "popularity_votes.csv", index=False)
    dump(folder / "extension.json", {"phase": phase, "config": config, "component_spec": {k: config[k] for k in SPEC_KEYS}, "mf_source": str(sources["mf"].relative_to(ROOT)),
         "ppr_source": str(sources["ppr"].relative_to(ROOT)), "rules_query": rules_metadata,
         "pop_source": str(pop_source.relative_to(ROOT)) if pop_source else None,
         "source_scores_sha256": {m: digest(p / "scores.npz") for m, p in sources.items()},
         "original_rules_matrix": str(rule_matrix.relative_to(ROOT)), "original_rules_matrix_sha256": digest(rule_matrix),
         "tie_and_cold_policy": "Original unweighted popularity; all actual cold component lists and predictions unchanged"})
    return bundle
