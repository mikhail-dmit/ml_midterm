"""Deterministic rank fusion and switching; neither function accepts labels."""

import math
from fractions import Fraction
from numbers import Integral


def reciprocal_rank_fusion(rankings, weights, popularity, offset=0, k=5):
    """Fuse supplied (possibly truncated) lists, then backfill from popularity.

    Missing items contribute zero. The catalogue is the complete popularity
    ordering. Equal scores use that training-only order, then numeric item ID.
    Returned scores are ranking utilities, not watch probabilities.
    """
    if not math.isfinite(offset) or offset < 0:
        raise ValueError("RRF offset must be finite and nonnegative")
    if not isinstance(k, Integral) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be a positive integer")
    if len(popularity) < k or len(set(popularity)) != len(popularity):
        raise ValueError("Popularity must contain enough distinct candidate IDs")
    if any(not isinstance(i, Integral) or isinstance(i, bool) or i <= 0 for i in popularity):
        raise ValueError("Candidate IDs must be positive integers")
    if not weights or any(not math.isfinite(w) or w < 0 for w in weights.values()) or not any(weights.values()):
        raise ValueError("Weights must be finite, nonnegative and not all zero")
    pop_rank = {item: rank for rank, item in enumerate(popularity)}
    terms = {}
    for method, weight in weights.items():
        if method not in rankings:
            raise ValueError(f"Missing component {method}")
        ids = rankings[method]
        if len(ids) != len(set(ids)) or any(item not in pop_rank for item in ids):
            raise ValueError("Component lists must contain distinct eligible IDs")
        if weight:
            for rank, item in enumerate(ids, 1):
                terms.setdefault(item, []).append(Fraction(str(weight)) / (Fraction(str(offset)) + rank))
    exact_scores = {item: sum(values, Fraction(0)) for item, values in terms.items()}
    scores = {item: float(value) for item, value in exact_scores.items()}
    ordered = sorted(scores, key=lambda item: (-exact_scores[item], pop_rank[item], item))
    ordered.extend(item for item in popularity if item not in scores)
    return ordered[:k], scores


def history_switch(rankings, history_size, max_sparse_history, sparse_method, warm_method):
    if not isinstance(history_size, Integral) or isinstance(history_size, bool) or history_size < 0:
        raise ValueError("History size must be a nonnegative integer")
    if not isinstance(max_sparse_history, Integral) or isinstance(max_sparse_history, bool) or max_sparse_history < 0:
        raise ValueError("Sparse threshold must be a nonnegative integer")
    chosen = sparse_method if history_size <= max_sparse_history else warm_method
    return list(rankings[chosen]), chosen
