"""Inspectable metadata cosine filtering and exact pair association rules."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

import numpy as np
import pandas as pd
from scipy import sparse


def clean(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().strip().split())


def title_tokens(value):
    boilerplate = {"сезон", "сезона", "эп", "эпизод", "эпизода", "серия", "серии", "серий", "телесериал", "фильм", "часть"}
    return set(re.findall(r"(?u)\b[^\W\d_]{2,}\b", clean(value))) - boilerplate


def metadata_document(rows, item_id):
    """Collapse training airing metadata only; no programme ID identity feature."""
    document = {"tv_show_id": int(item_id)}
    categories = Counter(clean(x) for x in rows.tv_show_category if clean(x))
    document["category"] = [min(categories, key=lambda x: (-categories[x], x))] if categories else []
    document["genre"] = sorted({clean(x) for c in ["tv_show_genre_1", "tv_show_genre_2", "tv_show_genre_3"] for x in rows[c] if clean(x)})
    for family, field in [("director", "director"), ("actor", "actors")]:
        document[family] = sorted({clean(person) for raw in rows[field] for person in str(raw).split(",") if clean(person)})
    decades = set()
    for value in rows.year_of_production:
        match = re.match(r"^\s*(\d{4})", str(value))
        if match and 1800 <= int(match.group(1)) <= 2020:
            decades.add(str(int(match.group(1)) // 10 * 10))
    document["decade"] = sorted(decades)
    document["title"] = sorted({token for value in rows.tv_show_title for token in title_tokens(value)})
    return document


def l2_rows(matrix):
    matrix = matrix.astype(np.float64).tocsr()
    lengths = np.sqrt(np.asarray(matrix.multiply(matrix).sum(axis=1)).ravel())
    return (sparse.diags(np.divide(1, lengths, out=np.zeros_like(lengths), where=lengths > 0)) @ matrix).tocsr()


def content_vectors(documents, family_weights, idf=False, family_balance=True):
    """Binary tokens; smoothed training-item IDF; optional within-family norms."""
    blocks, names, idf_values = [], [], []
    for family, weight in family_weights.items():
        if weight <= 0:
            continue
        vocabulary = sorted({token for doc in documents for token in doc.get(family, [])})
        if not vocabulary:
            continue
        index = {token: i for i, token in enumerate(vocabulary)}
        row, col = [], []
        for r, doc in enumerate(documents):
            values = set(doc.get(family, []))
            row.extend([r] * len(values))
            col.extend(index[value] for value in values)
        block = sparse.csr_matrix((np.ones(len(row)), (row, col)), shape=(len(documents), len(vocabulary)))
        df = np.asarray((block > 0).sum(axis=0)).ravel()
        weights = np.log((1 + len(documents)) / (1 + df)) + 1 if idf else np.ones(len(vocabulary))
        block = block @ sparse.diags(weights)
        if family_balance:
            block = l2_rows(block)
        blocks.append(block * weight)
        names.extend(f"{family}:{token}" for token in vocabulary)
        idf_values.extend(float(w) for w in weights)
    if not blocks:
        raise ValueError("No usable content fields")
    return l2_rows(sparse.hstack(blocks).tocsr()), names, np.asarray(idf_values)


def count_weights(counts, weighting):
    result = counts.astype(np.float64).copy().tocsr()
    if weighting == "log1p":
        result.data = np.log1p(result.data)
    elif weighting == "binary":
        result.data[:] = 1
    elif weighting != "count":
        raise ValueError("Unknown history weighting")
    return result


def content_scores(counts, item_vectors, history_weighting="log1p"):
    profiles = l2_rows(count_weights(counts, history_weighting) @ item_vectors)
    return (profiles @ item_vectors.T).toarray(), profiles


def mine_pair_rules(baskets, item_ids, min_joint_count=5, min_confidence=.1, score_metric="confidence"):
    """Exact frequent 1/2-itemsets, yielding singleton A -> B rules, A != B."""
    binary = baskets.copy().tocsr().astype(np.int64)
    binary.data[:] = 1
    n_baskets = binary.shape[0]
    if n_baskets <= 0 or (np.asarray(binary.sum(axis=1)).ravel() == 0).any():
        raise ValueError("Use nonempty, explicitly defined training baskets")
    totals = np.asarray(binary.sum(axis=0)).ravel()
    joint = (binary.T @ binary).tocsr()
    joint.setdiag(0)
    joint.eliminate_zeros()
    pairs = joint.tocoo()
    confidence = pairs.data / totals[pairs.row]
    lift = pairs.data * n_baskets / (totals[pairs.row] * totals[pairs.col])
    # Exact integer lift>1 comparison prevents floating-point threshold artifacts.
    keep = (pairs.data >= min_joint_count) & (confidence >= min_confidence) & (
        pairs.data * n_baskets > totals[pairs.row] * totals[pairs.col])
    a, b, n = pairs.row[keep], pairs.col[keep], pairs.data[keep]
    confidence, lift = confidence[keep], lift[keep]
    if score_metric not in {"confidence", "lift"}:
        raise ValueError("Rule score must be confidence or lift")
    weights = confidence if score_metric == "confidence" else lift
    matrix = sparse.csr_matrix((weights, (a, b)), shape=(len(item_ids), len(item_ids)))
    ids = np.asarray(item_ids)
    rules = pd.DataFrame({"antecedent_id": ids[a], "consequent_id": ids[b],
                          "antecedent_index": a, "consequent_index": b,
                          "antecedent_count": totals[a], "consequent_count": totals[b], "joint_count": n,
                          "baskets": n_baskets, "support": n / n_baskets,
                          "confidence": confidence, "lift": lift, "score_weight": weights})
    return matrix, rules, binary, joint, totals


def rank_positive_with_backfill(scores, eval_users, trained_users, score_item_ids, candidates, popularity_order, k=5):
    """Same cold popularity fallback; also backfill slots lacking positive signal."""
    item_index = {int(item): i for i, item in enumerate(score_item_ids)}
    ids = np.asarray(candidates, dtype=np.int64)
    candidate_positions = np.array([i for i, item in enumerate(candidates) if item in item_index])
    score_positions = np.array([item_index[candidates[i]] for i in candidate_positions])
    predictions, records = {}, []
    for row, user in enumerate(eval_users):
        values = np.zeros(len(candidates))
        if user in trained_users:
            values[candidate_positions] = scores[row, score_positions]
        if not np.isfinite(values).all() or (values < -1e-12).any():
            raise AssertionError("Invalid nonnegative content/rule scores")
        valid = np.flatnonzero(values > 0)
        order = valid[np.lexsort((ids[valid], -values[valid]))][:k]
        chosen = [int(ids[i]) for i in order]
        records.extend({"user_id": user, "rank": rank, "tv_show_id": int(ids[i]),
                        "model_score": float(values[i]), "fallback": False,
                        "fallback_reason": ""} for rank, i in enumerate(order, 1))
        if len(chosen) < k:
            for item in popularity_order:
                if item not in chosen:
                    chosen.append(item)
                    records.append({"user_id": user, "rank": len(chosen), "tv_show_id": item,
                                    "model_score": None, "fallback": True,
                                    "fallback_reason": "cold_history" if user not in trained_users else "insufficient_positive_signal"})
                    if len(chosen) == k:
                        break
        if len(chosen) != k:
            raise AssertionError("Could not fill five slots from the shared pool")
        predictions[user] = chosen
    return predictions, records
