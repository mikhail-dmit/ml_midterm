"""Fixed-label familiarity decomposition and method-overlap diagnostics."""

import itertools

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def distinct_bucket(n):
    return "0 (cold)" if n == 0 else "1-5" if n <= 5 else "6-20" if n <= 20 else "21-50" if n <= 50 else "51+"


def volume_bucket(n):
    return "0 (cold)" if n == 0 else "1-5" if n <= 5 else "6-20" if n <= 20 else "21-100" if n <= 100 else "101+"


def true_hit_rows(truth_meta, predictions):
    """Keep original AP denominators and precision; partition credit by hit type."""
    actual = {u: set(f.tv_show_id) for u, f in truth_meta.groupby("user_id", sort=False)}
    hits = {}
    for user, predicted in predictions.items():
        running = 0
        for rank, item in enumerate(predicted, 1):
            if item in actual[user]:
                running += 1
                hits[(user, item)] = (rank, running / (rank * len(actual[user])))
    frame = truth_meta.copy()
    frame["hit_rank"] = [hits.get((u, int(i)), (0, 0))[0] for u, i in frame[["user_id", "tv_show_id"]].itertuples(index=False, name=None)]
    frame["AP_contribution"] = [hits.get((u, int(i)), (0, 0))[1] for u, i in frame[["user_id", "tv_show_id"]].itertuples(index=False, name=None)]
    frame["hit"] = frame.hit_rank > 0
    return frame


def novelty_metrics(hit_rows, cohorts):
    rows = []
    for cohort, users in cohorts.items():
        subset = hit_rows.loc[hit_rows.user_id.isin(users)]
        for axis in ["familiarity", "exposure", "global_support"]:
            for label, group in subset.groupby(axis, sort=True):
                rows.append({"cohort": cohort, "axis": axis, "segment": label, "cohort_users": len(users),
                             "true_slots": len(group), "true_slot_fraction": len(group)/(5*len(users)),
                             "users_with_this_true_type": int(group.user_id.nunique()),
                             "hits": int(group.hit.sum()), "recall_of_true_type_micro": float(group.hit.mean()),
                             "users_with_this_type_hit": int(group.loc[group.hit, "user_id"].nunique()),
                             "AP_contribution_full_cohort": float(group.AP_contribution.sum()/len(users))})
    return pd.DataFrame(rows)


def history_metrics(per_user, user_features, cohorts):
    merged = per_user.merge(user_features, on="user_id", validate="one_to_one")
    rows = []
    for cohort, users in cohorts.items():
        subset = merged.loc[merged.user_id.isin(users)]
        for axis in ["history_distinct", "history_volume", "active_week_span", "last_activity_age"]:
            for label, group in subset.groupby(axis, sort=True):
                rows.append({"cohort": cohort, "axis": axis, "segment": label, "users": len(group),
                             "map_at_5": float(group.ap_at_5.mean()), "precision_at_5": float(group.precision_at_5.mean()),
                             "hit_rate_at_5": float(group.hit_rate_at_5.mean())})
    return pd.DataFrame(rows)


def complementarity(predictions_by_method, truth, ap_by_method, cohorts):
    pairs, unique, distributions = [], [], []
    for cohort, users in cohorts.items():
        methods = list(predictions_by_method)
        hit_sets = {m: {(u, item) for u in users for item in predictions_by_method[m][u] if item in set(truth[u])} for m in methods}
        hit_users = {m: {u for u, item in hits} for m, hits in hit_sets.items()}
        for a, b in itertools.combinations(methods, 2):
            both = hit_users[a] & hit_users[b]
            union = hit_users[a] | hit_users[b]
            hit_union = hit_sets[a] | hit_sets[b]
            delta = np.array([ap_by_method[a][u] - ap_by_method[b][u] for u in users])
            av = [ap_by_method[a][u] for u in users]
            bv = [ap_by_method[b][u] for u in users]
            pairs.append({"cohort": cohort, "method_a": a, "method_b": b, "users": len(users),
                          "both_hit_users": len(both), "a_only_hit_users": len(hit_users[a]-hit_users[b]),
                          "b_only_hit_users": len(hit_users[b]-hit_users[a]), "neither_hit_users": len(users)-len(union),
                          "hit_user_jaccard": len(both)/len(union) if union else 0,
                          "both_correct_user_item_pairs": len(hit_sets[a] & hit_sets[b]),
                          "a_only_correct_pairs": len(hit_sets[a]-hit_sets[b]), "b_only_correct_pairs": len(hit_sets[b]-hit_sets[a]),
                          "union_correct_pairs": len(hit_union), "correct_pair_jaccard": len(hit_sets[a]&hit_sets[b])/len(hit_union) if hit_union else 0,
                          "mean_shared_recommended_ids": float(np.mean([len(set(predictions_by_method[a][u]) & set(predictions_by_method[b][u])) for u in users])),
                          "a_better_AP_users": int((delta>0).sum()), "b_better_AP_users": int((delta<0).sum()), "equal_AP_users": int((delta==0).sum()),
                          "AP_spearman": float(spearmanr(av, bv).statistic) if len(set(av)) > 1 and len(set(bv)) > 1 else None})
        for method in methods:
            others_hits = set().union(*(hit_sets[m] for m in methods if m != method))
            others_users = set().union(*(hit_users[m] for m in methods if m != method))
            unique.append({"cohort": cohort, "method": method, "hit_users": len(hit_users[method]),
                           "correct_pairs": len(hit_sets[method]), "exclusive_hit_users": len(hit_users[method]-others_users),
                           "exclusive_correct_pairs": len(hit_sets[method]-others_hits)})
        for level in ["users", "true_answers"]:
            objects = users if level == "users" else [(u, item) for u in users for item in truth[u]]
            frequency = {n: 0 for n in range(len(methods)+1)}
            for obj in objects:
                frequency[sum(obj in (hit_users[m] if level == "users" else hit_sets[m]) for m in methods)] += 1
            for n, count in frequency.items():
                distributions.append({"cohort": cohort, "level": level, "methods_hitting": n, "count": count, "total": len(objects)})
    return pd.DataFrame(pairs), pd.DataFrame(unique), pd.DataFrame(distributions)
