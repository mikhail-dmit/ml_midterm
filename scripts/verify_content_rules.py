#!/usr/bin/env python3
"""Independent metadata, cosine, basket/rule, ranking and exact-MAP checks.

No production model, ranking or evaluator helper is imported. Source metadata is
reconstructed from raw CSVs; weekly baskets from training airing events.
"""

import csv
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/content_rules"
ART = ROOT / "artifacts/content_rules"


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def fingerprint(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().strip().split())


def main():
    start_clock = time.perf_counter()
    checks = []
    def check(name, condition, evidence):
        if not condition:
            raise AssertionError(f"{name}: {evidence}")
        checks.append({"check": name, "passed": True, "evidence": evidence})
    snapshot = json.loads((ART / "metadata_snapshot.json").read_text())
    documents, provenance = snapshot["items"], snapshot["provenance"]
    zone = ZoneInfo("Europe/Kyiv")
    low = int(datetime(2020, 3, 9, tzinfo=zone).timestamp())
    cutoff = int(datetime(2020, 5, 18, tzinfo=zone).timestamp())
    print("Reconstructing pre-cutoff metadata from raw schedules ...", flush=True)
    raw_docs, used_rows = {}, 0
    for filename, info in provenance["sources"].items():
        path = ROOT / "sweettv-tv-program-recommender" / filename
        check(filename + ": source fingerprint", fingerprint(path) == info["sha256"], info["sha256"])
        file_rows = 0
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                item, duration = int(row["tv_show_id"]), int(row["duration"])
                if not item or duration <= 0:
                    continue
                dt = datetime.strptime(row["start_time"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=zone)
                epoch = int(dt.astimezone(timezone.utc).timestamp())
                if not (epoch < cutoff and epoch + duration > low):
                    continue
                used_rows += 1
                file_rows += 1
                doc = raw_docs.setdefault(item, {"category": Counter(), "genre": set(), "director": set(), "actor": set(), "decade": set(), "title": set()})
                if row["tv_show_category"].strip():
                    doc["category"][clean(row["tv_show_category"])] += 1
                for field in ["tv_show_genre_1", "tv_show_genre_2", "tv_show_genre_3"]:
                    if row[field].strip():
                        doc["genre"].add(clean(row[field]))
                for field, family in [("director", "director"), ("actors", "actor")]:
                    doc[family].update(clean(name) for name in row[field].split(",") if clean(name))
                year = re.match(r"^\s*(\d{4})", row["year_of_production"])
                if year and 1800 <= int(year.group(1)) <= 2020:
                    doc["decade"].add(str(int(year.group(1)) // 10 * 10))
                words = set(re.findall(r"(?u)\b[^\W\d_]{2,}\b", clean(row["tv_show_title"])))
                words -= {"сезон", "сезона", "эп", "эпизод", "эпизода", "серия", "серии", "серий", "телесериал", "фильм", "часть"}
                doc["title"].update(words)
        check(filename + ": only training snapshot rows used", file_rows == info["used_airing_rows"], file_rows)
    for doc in documents:
        reference = raw_docs[doc["tv_show_id"]]
        categories = reference["category"]
        expected_category = [sorted(categories, key=lambda c: (-categories[c], c))[0]] if categories else []
        if doc["category"] != expected_category or any(set(doc[family]) != reference[family] for family in ["genre", "director", "actor", "decade", "title"]):
            raise AssertionError(f"Metadata mismatch for programme {doc['tv_show_id']}")
    check("All frozen item documents match raw pre-cutoff attributes", len(documents) == len(raw_docs) == 5842 and used_rows == provenance["used_airing_rows"],
          {"programmes": len(documents), "airings": used_rows, "latest_start": provenance["max_airing_start_used"]})
    counts = sparse.load_npz(ROOT / "artifacts/models/training_counts.npz").tocsr()
    maps = json.loads((ROOT / "artifacts/models/training_indices.json").read_text())
    train_users, train_items = maps["users"], maps["items"]
    user_map = {user: i for i, user in enumerate(train_users)}
    truth = {r["user_id"]: list(map(int, r["tv_show_id"].split())) for r in read_csv(ROOT / "reports/interactions/validation_ground_truth.csv")}
    primary = [r["user_id"] for r in read_csv(ROOT / "reports/popularity/cohort_primary.csv")]
    template = [r["user_id"] for r in read_csv(ROOT / "reports/popularity/cohort_template_primary.csv")]
    pool_rows = read_csv(ROOT / "reports/popularity/validation_candidates.csv")
    pool = np.array(sorted(int(r["tv_show_id"]) for r in pool_rows), dtype=np.int64)
    popularity = [int(r["tv_show_id"]) for r in sorted(pool_rows, key=lambda r: int(r["rank"]))]
    warm_users = [u for u in primary if u in user_map]
    binary_user = counts.copy().astype(np.int64)
    binary_user.data[:] = 1
    user_joint = binary_user.T @ binary_user
    input_paths = {
        "interactions": ROOT / "artifacts/interactions/user_programme_interactions.parquet",
        "truth": ROOT / "reports/interactions/validation_ground_truth.csv", "users": ROOT / "reports/interactions/validation_users.csv",
        "candidates": ROOT / "reports/popularity/validation_candidates.csv", "baseline": ROOT / "reports/popularity/predictions_allow_repeats.csv",
        "protocol": ROOT / "reports/popularity/protocol.json"}
    hashes = {key: fingerprint(path) for key, path in input_paths.items()}
    expected_weekly = None
    verified_runs = []
    with threadpool_limits(limits=1):
        for path in sorted((OUT / "runs").glob("*/summary.json")):
            summary = json.loads(path.read_text())
            config, run_id = summary["config"], summary["config"]["id"]
            print(f"Verifying {run_id} ...", flush=True)
            artifact = ART / run_id
            check(run_id + ": frozen protocol/input fingerprints", summary["source_hashes"] == hashes, hashes["truth"])
            raw_predictions = read_csv(path.parent / "predictions.csv")
            predictions = {r["user_id"]: list(map(int, r["tv_show_id"].split())) for r in raw_predictions}
            check(run_id + ": unchanged primary cohort, five unique candidate IDs", len(predictions) == len(raw_predictions) == 4030 and set(predictions) == set(truth)
                  and all(len(ids) == len(set(ids)) == 5 and set(ids).issubset(pool) for ids in predictions.values()), len(predictions))
            item_ids = np.load(artifact / "item_ids.npy", allow_pickle=False).tolist()
            item_index = {item: i for i, item in enumerate(item_ids)}
            pool_positions = np.array([i for i, item in enumerate(pool) if int(item) in item_index])
            signal_positions = np.array([item_index[int(pool[i])] for i in pool_positions])
            if config["method"] == "content_based":
                vectors = sparse.load_npz(artifact / "item_vectors.npz").tocsr()
                profiles = sparse.load_npz(artifact / "query_profiles.npz").tocsr()
                profile_users = np.load(artifact / "profile_user_ids.npy", allow_pickle=False).tolist()
                names = json.loads((artifact / "feature_names.json").read_text())
                idfs = np.load(artifact / "feature_idf.npy", allow_pickle=False)
                reference_names, reference_idfs, block_values = [], [], []
                for family, weight in config["family_weights"].items():
                    vocabulary = sorted({token for doc in documents for token in doc[family]})
                    document_frequency = Counter(token for doc in documents for token in set(doc[family]))
                    family_idf = {token: np.log((1+len(documents))/(1+document_frequency[token]))+1 if config["idf"] else 1.0 for token in vocabulary}
                    reference_names.extend(f"{family}:{token}" for token in vocabulary)
                    reference_idfs.extend(family_idf[token] for token in vocabulary)
                    block_values.append((family, weight, family_idf))
                check(run_id + ": vocabulary and IDF fitted on frozen metadata only", names == reference_names and np.allclose(idfs, reference_idfs, rtol=0, atol=1e-12), len(names))
                feature_map = {name: i for i, name in enumerate(names)}
                max_vector_error = 0.0
                for row, doc in enumerate(documents):
                    values = {}
                    for family, weight, family_idf in block_values:
                        tokens = doc[family]
                        norm = np.sqrt(sum(family_idf[token]**2 for token in tokens)) if config["family_balance"] else 1
                        if not tokens:
                            continue
                        for token in tokens:
                            values[feature_map[f"{family}:{token}"]] = weight * family_idf[token] / norm
                    norm = np.sqrt(sum(value*value for value in values.values()))
                    expected = {i: v/norm for i, v in values.items()}
                    a, b = vectors.indptr[row:row+2]
                    actual = dict(zip(vectors.indices[a:b], vectors.data[a:b]))
                    if set(actual) != set(expected):
                        raise AssertionError(f"Feature support mismatch for {run_id}/{doc['tv_show_id']}")
                    max_vector_error = max(max_vector_error, max(abs(actual[i] - expected[i]) for i in expected))
                check(run_id + ": every item vector independently reconstructed", max_vector_error < 1e-12, max_vector_error)
                metadata_mapping = np.array([item_index[item] for item in train_items])
                aligned_counts = sparse.csr_matrix((counts.data.copy(), metadata_mapping[counts.indices], counts.indptr.copy()), shape=(len(train_users), len(item_ids)))
                weights = aligned_counts[[user_map[u] for u in profile_users]].astype(float)
                if config["history_weighting"] == "log1p":
                    weights.data = np.log1p(weights.data)
                expected_profiles = (weights @ vectors).tocsr()
                lengths = np.sqrt(np.asarray(expected_profiles.multiply(expected_profiles).sum(axis=1)).ravel())
                expected_profiles = sparse.diags(1/lengths) @ expected_profiles
                difference = (expected_profiles - profiles).tocsr()
                max_profile_error = float(np.max(np.abs(difference.data))) if difference.nnz else 0.0
                check(run_id + ": all profiles use training-only watched items/counts", max_profile_error < 1e-12 and set(profile_users) == set(warm_users), max_profile_error)
                signal_scores = (profiles @ vectors.T).toarray()
                score_user_map = {u: r for r, u in enumerate(profile_users)}
            else:
                baskets = sparse.load_npz(artifact / "baskets.npz").tocsr()
                basket_keys = json.loads((artifact / "basket_keys.json").read_text())
                if config["baskets"] == "user":
                    expected_baskets = binary_user
                    check(run_id + ": user baskets contain only training positives", basket_keys == train_users and (baskets != expected_baskets).nnz == 0, baskets.shape[0])
                else:
                    if expected_weekly is None:
                        events = pd.read_parquet(ROOT / "artifacts/interactions/airing_interactions.parquet", columns=["split", "user_id", "tv_show_id", "first_overlap", "watched_80pct"])
                        weekly = defaultdict(set)
                        for event in events.loc[(events.split == "train") & events.watched_80pct].itertuples(index=False):
                            iso = datetime.fromtimestamp(event.first_overlap, timezone.utc).astimezone(zone).isocalendar()
                            weekly[f"{event.user_id}|{iso.year}-W{iso.week:02d}"].add(int(event.tv_show_id))
                        keys = sorted(weekly)
                        rr, cc = [], []
                        for r, key in enumerate(keys):
                            rr.extend([r] * len(weekly[key]))
                            cc.extend(item_index[item] for item in weekly[key])
                        expected_weekly = (keys, sparse.csr_matrix((np.ones(len(rr), dtype=np.int64), (rr, cc)), shape=(len(keys), len(item_ids))))
                    keys, expected_baskets = expected_weekly
                    check(run_id + ": weekly baskets independently rebuilt from training airings", keys == basket_keys and (baskets != expected_baskets).nnz == 0, len(keys))
                n = baskets.shape[0]
                totals = np.asarray(baskets.sum(axis=0)).ravel()
                pair_counts = (baskets.T @ baskets).tocoo()
                confidence = pair_counts.data / totals[pair_counts.row]
                keep = (pair_counts.row != pair_counts.col) & (pair_counts.data >= config["min_joint_count"]) & (confidence >= config["min_confidence"]) & (
                    pair_counts.data*n > totals[pair_counts.row]*totals[pair_counts.col])
                aa, bb, joint = pair_counts.row[keep], pair_counts.col[keep], pair_counts.data[keep]
                expected = {(int(a), int(b)): int(j) for a, b, j in zip(aa, bb, joint)}
                rules = pd.read_parquet(artifact / "rules.parquet")
                actual = {(int(r.antecedent_index), int(r.consequent_index)): int(r.joint_count) for r in rules.itertuples(index=False)}
                check(run_id + ": exact frequent pairs and directional rule filters", actual == expected, {"baskets": n, "rules": len(rules)})
                a, b = rules.antecedent_index.to_numpy(), rules.consequent_index.to_numpy()
                joint = rules.joint_count.to_numpy()
                expected_confidence = joint / totals[a]
                expected_lift = expected_confidence / (totals[b]/n)
                expected_user_counts = np.asarray(user_joint[a, b]).ravel()
                check(run_id + ": all support/confidence/lift/count fields verified", bool(np.array_equal(rules.antecedent_count, totals[a])
                      and np.array_equal(rules.consequent_count, totals[b]) and np.allclose(rules.support, joint/n, rtol=0, atol=1e-12)
                      and np.allclose(rules.confidence, expected_confidence, rtol=0, atol=1e-12)
                      and np.allclose(rules.lift, expected_lift, rtol=1e-12, atol=1e-12)
                      and np.array_equal(rules.distinct_training_users_joint, expected_user_counts)), len(rules))
                values = expected_confidence if config["score_metric"] == "confidence" else expected_lift
                reference_weights = sparse.csr_matrix((values, (a, b)), shape=(len(item_ids), len(item_ids)))
                saved_weights = sparse.load_npz(artifact / "rule_weights.npz")
                delta = (reference_weights - saved_weights).tocsr()
                check(run_id + ": rule score matrix matches the declared metric", not delta.nnz or float(np.max(np.abs(delta.data))) < 1e-10, delta.nnz)
                history = counts[[user_map[u] for u in warm_users]].copy()
                if config["history_weighting"] == "log1p":
                    history.data = np.log1p(history.data)
                signal_scores = (history @ saved_weights).toarray()
                score_user_map = {u: r for r, u in enumerate(warm_users)}
            recs = {(r["user_id"], int(r["tv_show_id"])): r for r in read_csv(path.parent / "recommendations.csv")}
            max_score_error, fallback_slots = 0.0, 0
            for user in primary:
                available = np.zeros(len(pool))
                if user in score_user_map:
                    available[pool_positions] = signal_scores[score_user_map[user], signal_positions]
                order = np.argsort(-available, kind="stable")
                chosen = [int(pool[i]) for i in order if available[i] > 0][:5]
                expected_fallback = set()
                for item in popularity:
                    if len(chosen) == 5:
                        break
                    if item not in chosen:
                        chosen.append(item)
                        expected_fallback.add(item)
                if chosen != predictions[user]:
                    raise AssertionError(f"Ranking mismatch for {run_id}/{user}")
                for item in chosen:
                    record = recs[(user, item)]
                    if (record["fallback"] == "True") != (item in expected_fallback):
                        raise AssertionError("Incorrect fallback provenance")
                    if item in expected_fallback:
                        fallback_slots += 1
                    else:
                        score = signal_scores[score_user_map[user], item_index[item]]
                        max_score_error = max(max_score_error, abs(score - float(record["model_score"])))
            check(run_id + ": all predictions, repeat policy, score and fallback provenance reproduce", max_score_error < 1e-10,
                  {"max_score_error": max_score_error, "fallback_slots": fallback_slots})
            check(run_id + ": same cold-user fallback as other methods", all(predictions[u] == popularity[:5] for u in primary if u not in user_map), 59)
            exact_ap, hits = {}, {}
            for user, ids in predictions.items():
                positions = [r for r, item in enumerate(ids, 1) if item in set(truth[user])]
                exact_ap[user] = sum((Fraction(j, r) for j, r in enumerate(positions, 1)), Fraction(0)) / 5
                hits[user] = len(positions)
            per_user = {r["user_id"]: r for r in read_csv(path.parent / "per_user_metrics.csv")}
            error = max(abs(float(exact_ap[u]) - float(per_user[u]["ap_at_5"])) for u in primary)
            check(run_id + ": all per-user AP agrees with exact arithmetic", error < 1e-15, error)
            for metric in summary["metrics"]:
                cohort = primary if metric["cohort"] == "all_primary" else template
                exact = sum((exact_ap[u] for u in cohort), Fraction(0)) / len(cohort)
                check(run_id + " / " + metric["cohort"] + ": exact MAP and total hits", abs(float(exact)-metric["map_at_5"]) < 1e-15
                      and sum(hits[u] for u in cohort) == metric["total_hits"], {"users": len(cohort), "MAP_fraction": str(exact)})
            contribution_file = "example_feature_contributions.csv" if config["method"] == "content_based" else "example_rule_contributions.csv"
            contributions = pd.read_csv(path.parent / contribution_file, dtype={"user_id": str})
            errors = []
            for (user, rank), group in contributions.groupby(["user_id", "rank"]):
                item_col = "tv_show_id" if config["method"] == "content_based" else "consequent_id"
                item = int(group[item_col].iloc[0])
                errors.append(abs(float(group.score_contribution.sum()) - float(recs[(user, item)]["model_score"])))
            check(run_id + ": explanation contributions sum to reported scores", max(errors, default=0) < 1e-10, max(errors, default=0))
            verified_runs.append({"run_id": run_id, "verified": True, "metrics": summary["metrics"]})
    result = {"passed": True, "checks": checks, "runs": verified_runs, "elapsed_seconds": time.perf_counter()-start_clock,
              "method": "Raw-CSV cutoff metadata reconstruction, independent feature/IDF/profile algebra, independent user-week baskets and frequent-pair rule reconstruction, all-user ranking and Fraction AP/MAP",
              "student_personal_verification": "Not claimed; source attributes and complete score-contribution tables are exported for later inspection"}
    (OUT / "verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Passed {len(checks)} checks across {len(verified_runs)} runs in {result['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    main()
