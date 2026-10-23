"""Standard AP@K / macro MAP@K with explicit cohort and validity checks.

AP@K = sum_r precision@r * first-relevant-hit(r) / min(K, |distinct truth|).
Repeated predicted IDs consume a rank but cannot earn credit twice. The
submission-style evaluator additionally rejects anything except K unique IDs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def average_precision_at_k(actual, predicted, k=5):
    if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
        raise ValueError("k must be a positive integer")
    relevant = set(actual)
    if not relevant:
        return 0.0
    seen, hits, terms = set(), 0, []
    for rank, item in enumerate(predicted[:k], start=1):
        if item in relevant and item not in seen:
            hits += 1
            terms.append(hits / rank)
        seen.add(item)
    return math.fsum(terms) / min(k, len(relevant))


def rank_contributions(actual, predicted, k=5):
    relevant, seen, hits = set(actual), set(), 0
    denominator = min(k, len(relevant))
    rows = []
    for rank, item in enumerate(predicted[:k], start=1):
        hit = item in relevant and item not in seen
        hits += int(hit)
        precision = hits / rank
        rows.append({"rank": rank, "tv_show_id": item, "relevant_first_hit": hit,
                     "hits_so_far": hits, "precision_at_rank": precision,
                     "ap_contribution": precision / denominator if hit and denominator else 0.0})
        seen.add(item)
    return rows


def evaluate_rankings(truth: Mapping, predictions: Mapping, users: Sequence | None = None,
                      k=5, require_exact_k=True):
    """Evaluate a fixed cohort. Never silently drop missing users or empty truth.

    With users=None the cohort is every truth key. An explicit subset may be
    passed for segment reporting; predictions outside that subset are ignored.
    """
    if k != 5:
        raise ValueError("Cohort reporting is fixed to MAP@5; use average_precision_at_k for other cutoffs")
    cohort = list(truth) if users is None else list(users)
    if not cohort or len(cohort) != len(set(cohort)):
        raise ValueError("The evaluation cohort must be nonempty and contain unique users")
    records = []
    for user in cohort:
        if user not in truth or user not in predictions:
            raise ValueError(f"Missing truth/prediction for cohort user {user}")
        actual, predicted = list(truth[user]), list(predictions[user])
        if not actual or len(actual) != len(set(actual)):
            raise ValueError(f"Truth must contain distinct nonempty relevant IDs: {user}")
        if require_exact_k and (len(predicted) != k or len(set(predicted)) != k):
            raise ValueError(f"Expected exactly {k} distinct predicted IDs: {user}")
        ap = average_precision_at_k(actual, predicted, k)
        hits = len(set(actual).intersection(predicted[:k]))
        records.append({"user_id": user, "ap_at_5": ap, "hits_at_5": hits,
                        "precision_at_5": hits / k, "recall_at_5": hits / len(actual),
                        "hit_rate_at_5": int(hits > 0)})
    n = len(records)
    summary = {"users": n, "map_at_5": math.fsum(r["ap_at_5"] for r in records) / n,
               "precision_at_5": math.fsum(r["precision_at_5"] for r in records) / n,
               "recall_at_5": math.fsum(r["recall_at_5"] for r in records) / n,
               "hit_rate_at_5": sum(r["hit_rate_at_5"] for r in records) / n,
               "users_with_hits": sum(r["hit_rate_at_5"] for r in records),
               "total_hits": sum(r["hits_at_5"] for r in records)}
    return summary, records
