"""Implicit weighted ALS and Personalized PageRank on a programme co-view graph.

Both algorithms consume only a nonnegative training user–programme count matrix.
Missing implicit observations are not explicit dislikes; ALS gives them low
confidence, while PPR builds no co-view evidence from them.
"""

from __future__ import annotations

import numpy as np
from scipy import linalg, sparse
from scipy.sparse.csgraph import connected_components


def transform_counts(values, weighting):
    if weighting == "log1p":
        return np.log1p(values)
    if weighting == "count":
        return np.asarray(values, dtype=np.float64)
    if weighting == "binary":
        return np.ones_like(values, dtype=np.float64)
    raise ValueError(f"Unknown count weighting: {weighting}")


def preference_targets(values, preference):
    if preference == "binary":
        return np.ones_like(values, dtype=np.float64)
    if preference == "log1p":
        return np.log1p(values)
    raise ValueError("Preference target must be binary or log1p")


def als_update(counts, fixed, confidence_scale, regularization, weighting="log1p", preference="binary"):
    """Exact HKV normal equations; baseline confidence is one for every pair."""
    counts = counts.tocsr()
    gram = fixed.T @ fixed + regularization * np.eye(fixed.shape[1])
    result = np.zeros((counts.shape[0], fixed.shape[1]), dtype=np.float64)
    for row in range(counts.shape[0]):
        a, b = counts.indptr[row:row + 2]
        indices, raw = counts.indices[a:b], counts.data[a:b]
        if not len(indices):
            continue
        factors = fixed[indices]
        extra = confidence_scale * transform_counts(raw, weighting)
        normal = gram + (factors.T * extra) @ factors
        rhs = factors.T @ ((1 + extra) * preference_targets(raw, preference))
        result[row] = linalg.cho_solve(linalg.cho_factor(normal, lower=True, check_finite=False),
                                      rhs, check_finite=False)
    return result


def als_objective(counts, users, items, confidence_scale, regularization, weighting="log1p", preference="binary"):
    """Exact all-pair objective without materializing the dense user–item matrix."""
    observed = counts.tocoo()
    dots = np.einsum("ij,ij->i", users[observed.row], items[observed.col])
    confidence = 1 + confidence_scale * transform_counts(observed.data, weighting)
    all_zero_preference_error = float(np.sum((users.T @ users) * (items.T @ items)))
    correction = float(np.sum(confidence * (preference_targets(observed.data, preference) - dots)**2 - dots**2))
    penalty = regularization * float(np.sum(users**2) + np.sum(items**2))
    return all_zero_preference_error + correction + penalty


def fit_implicit_als(counts, factors=16, confidence_scale=1.0, regularization=1.0,
                     weighting="log1p", epochs=15, seed=20261023, callback=None, preference="binary"):
    counts = counts.astype(np.float64).tocsr()
    if counts.nnz == 0 or (counts.data <= 0).any() or regularization <= 0 or confidence_scale < 0:
        raise ValueError("ALS requires positive observed counts and regularization")
    rng = np.random.default_rng(seed)
    items = rng.normal(0, .01, (counts.shape[1], factors))
    users = np.zeros((counts.shape[0], factors), dtype=np.float64)
    transposed = counts.T.tocsr()
    previous = als_objective(counts, users, items, confidence_scale, regularization, weighting, preference)
    history = [{"epoch": 0, "training_objective": previous}]
    for epoch in range(1, epochs + 1):
        users = als_update(counts, items, confidence_scale, regularization, weighting, preference)
        items = als_update(transposed, users, confidence_scale, regularization, weighting, preference)
        objective = als_objective(counts, users, items, confidence_scale, regularization, weighting, preference)
        if not np.isfinite(objective) or objective > previous + 1e-7 * max(1, previous):
            raise AssertionError("Exact alternating minimization did not decrease the objective")
        previous = objective
        record = {"epoch": epoch, "training_objective": objective}
        if callback is not None:
            record.update(callback(epoch, users, items))
        history.append(record)
    return users, items, history


def build_coview_graph(counts, normalization="raw"):
    binary = counts.copy().tocsr().astype(np.float64)
    binary.data[:] = 1
    support = np.asarray(binary.sum(axis=0)).ravel()
    adjacency = (binary.T @ binary).tocsr()
    adjacency.setdiag(0)
    adjacency.eliminate_zeros()
    if normalization == "cosine":
        inv = np.divide(1.0, np.sqrt(support), out=np.zeros_like(support), where=support > 0)
        adjacency = (sparse.diags(inv) @ adjacency @ sparse.diags(inv)).tocsr()
    elif normalization != "raw":
        raise ValueError("Graph normalization must be raw or cosine")
    degrees = np.asarray(adjacency.sum(axis=1)).ravel()
    transition = (sparse.diags(np.divide(1, degrees, out=np.zeros_like(degrees), where=degrees > 0)) @ adjacency).tocsr()
    n_components, _ = connected_components(adjacency, directed=False)
    row_sums = np.asarray(transition.sum(axis=1)).ravel()
    if not np.allclose(row_sums[degrees > 0], 1, atol=1e-12):
        raise AssertionError("Non-dangling transition rows must sum to one")
    return adjacency, transition, degrees == 0, {
        "nodes": counts.shape[1], "directed_nonzeros": adjacency.nnz,
        "undirected_edges": adjacency.nnz // 2, "dangling_nodes": int((degrees == 0).sum()),
        "connected_components": int(n_components),
        "max_row_sum_error": float(np.max(np.abs(row_sums[degrees > 0] - 1))) if (degrees > 0).any() else 0,
        "max_adjacency_asymmetry": float(np.max(np.abs((adjacency - adjacency.T).data))) if (adjacency - adjacency.T).nnz else 0.0,
    }


def restart_profiles(counts, weighting="log1p"):
    profiles = counts.copy().astype(np.float64).tocsr()
    profiles.data = transform_counts(profiles.data, weighting)
    totals = np.asarray(profiles.sum(axis=1)).ravel()
    profiles = (sparse.diags(np.divide(1, totals, out=np.zeros_like(totals), where=totals > 0)) @ profiles).tocsr()
    return profiles


def personalized_pagerank(transition, restart, alpha=.85):
    """Solve PPR for a batch of row-vector restart distributions.

    For substochastic P (dangling rows zero), solve q(I-alpha P)=(1-alpha)v
    and normalize q. This exactly redistributes dangling mass through each v.
    The full fixed-point equation, including dangling mass, is checked below.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha is the link-following probability, in (0,1)")
    restart = restart.toarray() if sparse.issparse(restart) else np.asarray(restart, dtype=np.float64)
    if (restart < 0).any() or not np.allclose(restart.sum(axis=1), 1, atol=1e-12):
        raise ValueError("Every restart row must be a probability distribution")
    system = np.eye(transition.shape[0]) - alpha * transition.T.toarray()
    factorization = linalg.lu_factor(system, check_finite=False)
    raw = linalg.lu_solve(factorization, ((1 - alpha) * restart).T, check_finite=False).T
    if not np.isfinite(raw).all() or float(raw.min()) < -1e-11:
        raise AssertionError("PPR linear solve produced invalid mass")
    raw = np.maximum(raw, 0)
    result = raw / raw.sum(axis=1, keepdims=True)
    dangling = np.asarray(transition.sum(axis=1)).ravel() == 0
    dangling_mass = result[:, dangling].sum(axis=1)
    next_step = alpha * (transition.T @ result.T).T + (
        1 - alpha + alpha * dangling_mass[:, None]) * restart
    residual = np.abs(next_step - result).sum(axis=1)
    if float(residual.max()) > 1e-9:
        raise AssertionError("PPR fixed-point residual exceeds tolerance")
    return result, {
        "solver": "Dense LU solve of I-alpha*P.T, then exact dangling normalization",
        "max_L1_fixed_point_residual": float(residual.max()),
        "max_mass_error": float(np.max(np.abs(result.sum(axis=1) - 1))),
        "min_mass": float(result.min()), "max_dangling_mass": float(dangling_mass.max()),
        "users_above_1e_9_residual": int((residual > 1e-9).sum()),
    }


def rank_model_scores(score_matrix, eval_users, trained_users, trained_items, candidates, popularity_order, k=5):
    """Same full schedule pool and cold-start fallback for both methods.

    Unsupported candidate IDs receive score zero, not a learned vector. Ties use
    numeric ID. Cold users receive the already fixed popularity Top-5.
    """
    item_index = {int(item): i for i, item in enumerate(trained_items)}
    candidate_array = np.asarray(candidates, dtype=np.int64)
    supported = np.array([i for i, item in enumerate(candidates) if item in item_index])
    corresponding = np.array([item_index[candidates[i]] for i in supported])
    predictions, detail = {}, []
    for row, user in enumerate(eval_users):
        if user not in trained_users:
            chosen = popularity_order[:k]
            predictions[user] = chosen
            detail.extend({"user_id": user, "rank": rank, "tv_show_id": item,
                           "model_score": None, "fallback": True} for rank, item in enumerate(chosen, 1))
            continue
        scores = np.zeros(len(candidates), dtype=np.float64)
        scores[supported] = score_matrix[row, corresponding]
        if not np.isfinite(scores).all():
            raise AssertionError("Non-finite ranking score")
        ordering = np.lexsort((candidate_array, -scores))[:k]
        chosen = [int(candidate_array[i]) for i in ordering]
        predictions[user] = chosen
        detail.extend({"user_id": user, "rank": rank, "tv_show_id": int(candidate_array[i]),
                       "model_score": float(scores[i]), "fallback": False} for rank, i in enumerate(ordering, 1))
    return predictions, detail
