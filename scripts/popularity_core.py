"""Training-only global popularity and shared candidate/repeat policies."""

from collections import defaultdict

import pandas as pd


def fit_popularity(training_programmes):
    if training_programmes.empty or not training_programmes.split.eq("train").all():
        raise ValueError("fit_popularity requires nonempty training-only rows")
    positive = training_programmes.loc[training_programmes.watched_airings > 0]
    scores = positive.groupby("tv_show_id", sort=True).agg(
        training_watched_airings=("watched_airings", "sum"),
        training_distinct_viewers=("user_id", "nunique"),
    ).reset_index()
    seen = defaultdict(set)
    for user, item in positive[["user_id", "tv_show_id"]].itertuples(index=False, name=None):
        seen[str(user)].add(int(item))
    return scores, dict(seen)


def available_candidates(airings, lower, upper):
    eligible = airings.loc[(airings.tv_show_id != 0) & (airings.duration > 0)
                           & (airings.start < upper) & (airings.end > lower)]
    return sorted(int(item) for item in eligible.tv_show_id.unique())


def rank_candidates(scores, candidate_ids):
    pool = pd.DataFrame({"tv_show_id": candidate_ids})
    if pool.tv_show_id.duplicated().any() or (pool.tv_show_id <= 0).any():
        raise ValueError("Candidate IDs must be distinct and positive")
    pool = pool.merge(scores, on="tv_show_id", how="left", validate="one_to_one")
    for col in ["training_watched_airings", "training_distinct_viewers"]:
        pool[col] = pool[col].fillna(0).astype("int64")
    return pool.sort_values(["training_watched_airings", "tv_show_id"],
                            ascending=[False, True], kind="stable").reset_index(drop=True)


def recommend_popularity(ranked_ids, user, seen, allow_repeats=True, k=5):
    excluded = set() if allow_repeats else seen.get(str(user), set())
    result = []
    for item in ranked_ids:
        if item not in excluded:
            result.append(item)
            if len(result) == k:
                return result
    raise ValueError(f"Fewer than {k} eligible candidates for user {user}; no repeat-violating backfill")
