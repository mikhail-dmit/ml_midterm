#!/usr/bin/env python3
"""Factorial shared training-input study; validation labels remain immutable."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

from analyze_method_segments import build_reference_tables
from build_interactions import read_views
from collaborative_models import build_coview_graph, fit_implicit_als, personalized_pagerank, restart_profiles
from content_rule_models import content_scores, count_weights, mine_pair_rules, rank_positive_with_backfill
from interaction_core import boundary_epoch, clip_views, join_channel, merge_views
from popularity_core import fit_popularity, rank_candidates
from ranking_metrics import evaluate_rankings
from run_model_experiments import digest, dump, load_data, save_run
from segment_analysis import history_metrics, novelty_metrics, true_hit_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/training_study"
ART = ROOT / "artifacts/training_study"
METHODS = ["popularity", "implicit_mf", "ppr", "content_based", "association_rules"]


def training_watch_mask(events, threshold_percent):
    return events.watched_seconds.to_numpy(dtype=np.int64)*100 >= events.duration.to_numpy(dtype=np.int64)*threshold_percent


def clip_join_training_window(merged, airings, lower, upper):
    views = clip_views(merged, lower, upper)
    eligible = airings.loc[(airings.start < upper) & (airings.end > lower)]
    schedule_by_channel = {int(c): f for c, f in eligible.groupby("channel_id", sort=False)}
    parts = []
    for channel, frame in views.groupby("channel_id", sort=False):
        if int(channel) in schedule_by_channel:
            overlaps = join_channel(frame, schedule_by_channel[int(channel)])
            if len(overlaps):
                parts.append(overlaps)
    segments = pd.concat(parts, ignore_index=True)
    events = segments.groupby(["user_id", "airing_id"], sort=False).agg(
        watched_seconds=("overlap_seconds", "sum"), first_overlap=("overlap_start", "min"),
        last_overlap=("overlap_end", "max")).reset_index()
    events = events.merge(airings[["airing_id", "tv_show_id", "duration", "start", "end"]], on="airing_id", validate="many_to_one")
    events["user_id"] = events.user_id.astype(str)
    events["split"] = "train"
    if not ((events.watched_seconds > 0) & (events.watched_seconds <= events.duration)
            & (events.first_overlap >= lower) & (events.last_overlap <= upper)).all():
        raise AssertionError("Window clipping/coverage invariant violated")
    return events


def prepare_window_events(windows):
    source = ROOT / "artifacts/interactions/airing_interactions.parquet"
    airings_path = ROOT / "artifacts/interactions/airings.parquet"
    log_path = ROOT / "sweettv-tv-program-recommender/dataset11-30.csv"
    original = json.loads((ROOT / "reports/interactions/summary.json").read_text())
    hashes = {"view_log": digest(log_path), "airings": digest(airings_path), "original_events": digest(source)}
    if hashes["view_log"] != original["source_files_sha256"]["dataset11-30.csv"]:
        raise AssertionError("Raw log changed: rebuild the validated interaction pipeline first")
    events_by_window, merged, airings = {}, None, None
    for window in windows:
        lower, upper = boundary_epoch(window["start_local"]), boundary_epoch(window["end_local"])
        folder = ART / "windows" / window["id"]
        folder.mkdir(parents=True, exist_ok=True)
        manifest = {"sources": hashes, "lower": lower, "upper": upper, "full_duration_denominator": True}
        if (folder / "manifest.json").exists() and json.loads((folder / "manifest.json").read_text()) == manifest:
            events = pd.read_parquet(folder / "events.parquet")
        elif window["id"] == "full10":
            events = pd.read_parquet(source)
            events = events.loc[events.split == "train"].copy()
            events.to_parquet(folder / "events.parquet", index=False, compression="zstd")
            dump(folder / "manifest.json", manifest)
        else:
            if merged is None:
                print("Rebuilding merged raw views once for exact early/recent boundary clipping ...", flush=True)
                views, _ = read_views(log_path.parent, 250000)
                merged = merge_views(views)
                del views
                airings = pd.read_parquet(airings_path)
            print(f"Joining clipped {window['id']} window ...", flush=True)
            events = clip_join_training_window(merged, airings, lower, upper)
            events.to_parquet(folder / "events.parquet", index=False, compression="zstd")
            dump(folder / "manifest.json", manifest)
        events_by_window[window["id"]] = events
    return events_by_window


def make_setting_data(base, selected_events, setting_id):
    train = selected_events.groupby(["user_id", "tv_show_id"], sort=True).size().rename("watched_airings").reset_index()
    train["split"] = "train"
    users, items = sorted(train.user_id.unique()), sorted(int(x) for x in train.tv_show_id.unique())
    user_map, item_map = {u: i for i, u in enumerate(users)}, {item: i for i, item in enumerate(items)}
    counts = sparse.csr_matrix((train.watched_airings.to_numpy(dtype=np.float64),
                                (train.user_id.map(user_map), train.tv_show_id.map(item_map))), shape=(len(users), len(items)))
    pop, seen = fit_popularity(train)
    candidates = rank_candidates(pop, base["pool"])
    candidates = candidates.merge(base["candidates"][["tv_show_id", "tv_show_title", "tv_show_category"]], on="tv_show_id", validate="one_to_one")
    candidates["rank"] = np.arange(1, len(candidates)+1)
    setting_art, setting_out = ART / setting_id, OUT / setting_id
    setting_art.mkdir(parents=True, exist_ok=True)
    setting_out.mkdir(parents=True, exist_ok=True)
    train.to_parquet(setting_art / "training_counts.parquet", index=False, compression="zstd")
    sparse.save_npz(setting_art / "counts.npz", counts)
    dump(setting_art / "indices.json", {"users": users, "items": items})
    candidates.to_csv(setting_out / "candidate_scores.csv", index=False)
    data = dict(base)
    data.update(train=train, counts=counts, user_ids=users, item_ids=items, user_map=user_map,
                history=seen, candidates=candidates, popularity=[int(x) for x in candidates.tv_show_id],
                own_counts={(u, int(i)): int(n) for u, i, n in train[["user_id", "tv_show_id", "watched_airings"]].itertuples(index=False, name=None)})
    data["baseline"] = {u: data["popularity"][:5] for u in base["eval_users"]}
    data["paths"] = dict(base["paths"])
    data["paths"].update(interactions=setting_art / "training_counts.parquet", candidates=setting_out / "candidate_scores.csv",
                         baseline=setting_out / "runs/popularity/predictions.csv")
    return data


def weekly_baskets(events, items):
    frame = events[["user_id", "tv_show_id", "first_overlap"]].copy()
    iso = pd.to_datetime(frame.first_overlap, unit="s", utc=True).dt.tz_convert("Europe/Kyiv").dt.isocalendar()
    frame["basket"] = frame.user_id + "|" + iso.year.astype(str) + "-W" + iso.week.astype(str).str.zfill(2)
    frame = frame.drop_duplicates(["basket", "tv_show_id"])
    keys = sorted(frame.basket.unique())
    key_map, item_map = {k: i for i, k in enumerate(keys)}, {item: i for i, item in enumerate(items)}
    return sparse.csr_matrix((np.ones(len(frame), dtype=np.int64), (frame.basket.map(key_map), frame.tv_show_id.map(item_map))), shape=(len(keys), len(items))), keys


def run_one_model(method, setting, selected_events, data, reference_meta, user_features, cohorts, frozen_content):
    started = time.perf_counter()
    artifact = ART / setting["id"] / method
    artifact.mkdir(parents=True, exist_ok=True)
    config = {"id": setting["id"] + "__" + method, "method": method, "shared_setting": setting,
              "hyperparameters": "Frozen original selected configuration; no per-setting tuning"}
    eval_rows = [r for r, u in enumerate(data["eval_users"]) if u in data["user_map"]]
    training_rows = [data["user_map"][data["eval_users"][r]] for r in eval_rows]
    diagnostics = {"active_training_users": len(data["user_ids"]), "trained_items": len(data["item_ids"]),
                   "trained_positive_pairs": data["counts"].nnz, "training_events": len(selected_events),
                   "cold_users_in_setting": len(data["eval_users"])-len(eval_rows)}
    item_ids = data["item_ids"]
    if method == "popularity":
        predictions = data["baseline"]
        pop_counts = data["candidates"].set_index("tv_show_id").training_watched_airings.to_dict()
        details = [{"user_id": u, "rank": rank, "tv_show_id": item, "model_score": float(pop_counts[item]),
                    "fallback": u not in data["user_map"]} for u in data["eval_users"] for rank, item in enumerate(predictions[u], 1)]
    else:
        if method == "implicit_mf":
            x, y, curve = fit_implicit_als(data["counts"], factors=16, confidence_scale=1, regularization=1,
                                            weighting="log1p", preference="log1p", epochs=15, seed=20261023)
            scores = np.zeros((len(data["eval_users"]), len(item_ids)))
            scores[eval_rows] = x[training_rows] @ y.T
            # Negative raw MF estimates carry no positive ranking signal. This
            # does not alter the ordering of positive scores; no rating clamp.
            scores = np.maximum(scores, 0)
            np.savez_compressed(artifact / "factors.npz", user_factors=x, item_factors=y)
            pd.DataFrame(curve).to_csv(artifact / "learning_curve.csv", index=False)
            diagnostics["objective_initial"] = curve[0]["training_objective"]
            diagnostics["objective_final"] = curve[-1]["training_objective"]
        elif method == "ppr":
            adjacency, transition, _, graph_stats = build_coview_graph(data["counts"], "raw")
            profiles = restart_profiles(data["counts"], "log1p")
            mass, solver = personalized_pagerank(transition, profiles[training_rows], .5)
            scores = np.zeros((len(data["eval_users"]), len(item_ids)))
            scores[eval_rows] = mass
            sparse.save_npz(artifact / "transition.npz", transition)
            diagnostics.update(graph=graph_stats, solver=solver)
        elif method == "content_based":
            item_ids, vectors = frozen_content
            index = {item: i for i, item in enumerate(item_ids)}
            remap = np.array([index[item] for item in data["item_ids"]])
            counts = data["counts"]
            aligned = sparse.csr_matrix((counts.data.copy(), remap[counts.indices], counts.indptr.copy()), shape=(len(data["user_ids"]), len(item_ids)))
            warm_scores, profiles = content_scores(aligned[training_rows], vectors, "count")
            scores = np.zeros((len(data["eval_users"]), len(item_ids)))
            scores[eval_rows] = warm_scores
            sparse.save_npz(artifact / "profiles.npz", profiles)
            np.save(artifact / "profile_user_ids.npy", np.asarray([data["eval_users"][r] for r in eval_rows], dtype="U20"))
            diagnostics["metadata_vectors_frozen_across_settings"] = True
        elif method == "association_rules":
            baskets, keys = weekly_baskets(selected_events, item_ids)
            rules, table, binary, _, _ = mine_pair_rules(baskets, item_ids, 5, .1, "confidence")
            history = count_weights(data["counts"], "log1p")
            scores = np.zeros((len(data["eval_users"]), len(item_ids)))
            scores[eval_rows] = (history[training_rows] @ rules).toarray()
            sparse.save_npz(artifact / "baskets.npz", binary)
            sparse.save_npz(artifact / "rule_weights.npz", rules)
            dump(artifact / "basket_keys.json", keys)
            table.to_parquet(artifact / "rules.parquet", index=False)
            diagnostics.update(baskets=len(keys), rules=len(table))
        else:
            raise ValueError(method)
        predictions, details = rank_positive_with_backfill(scores, data["eval_users"], data["user_map"], item_ids, data["pool"], data["popularity"])
    metrics, records = evaluate_rankings(data["truth"], predictions, users=data["eval_users"])
    template_metric, _ = evaluate_rankings(data["truth"], predictions, users=data["template_users"])
    metrics = [dict(cohort="all_primary", **metrics), dict(cohort="template_primary", **template_metric)]
    run_dir = OUT / setting["id"] / "runs" / method
    save_run(run_dir, artifact, config, data, predictions, details, metrics, records, diagnostics,
             {"total_seconds": time.perf_counter()-started})
    summary = json.loads((run_dir / "summary.json").read_text())
    summary["diagnostics"]["cold_fallback_users"] = len(data["eval_users"])-len(eval_rows)
    summary["code_hashes"]["training_study.py"] = digest(Path(__file__))
    dump(run_dir / "summary.json", summary)
    novel = novelty_metrics(true_hit_rows(reference_meta, predictions), cohorts)
    novel.to_csv(run_dir / "fixed_novelty_metrics.csv", index=False)
    history_metrics(pd.DataFrame(records), user_features[["user_id", "history_distinct", "history_volume", "active_week_span", "last_activity_age"]], cohorts).to_csv(
        run_dir / "fixed_history_metrics.csv", index=False)
    if setting["id"] == "full10_t80":
        from analyze_method_segments import prediction_sources
        from evaluate_rankings import read_rankings
        old_predictions = read_rankings(prediction_sources()[method])
        if predictions != old_predictions:
            raise AssertionError(f"Reference setting failed to reproduce {method}")
    return metrics


def refresh_results():
    rows = []
    for path in sorted(OUT.glob("*_t*/runs/*/summary.json")):
        result = json.loads(path.read_text())
        config = result["config"]
        for metric in result["metrics"]:
            rows.append({"setting": config["shared_setting"]["id"], "window": config["shared_setting"]["window"],
                         "threshold_percent": config["shared_setting"]["threshold_percent"], "method": config["method"],
                         "training_events": result["diagnostics"]["training_events"], "training_users": result["diagnostics"]["active_training_users"],
                         "training_items": result["diagnostics"]["trained_items"], "cold_primary_users": result["diagnostics"]["cold_users_in_setting"], **metric})
    frame = pd.DataFrame(rows)
    if len(frame):
        pop = frame.loc[frame.method == "popularity", ["setting", "cohort", "map_at_5"]].rename(columns={"map_at_5": "popularity_same_setting"})
        frame = frame.merge(pop, on=["setting", "cohort"], validate="many_to_one")
        frame["delta_vs_popularity_same_setting"] = frame.map_at_5-frame.popularity_same_setting
        base = frame.loc[frame.setting == "full10_t80", ["method", "cohort", "map_at_5"]].rename(columns={"map_at_5": "own_original_MAP"})
        frame = frame.merge(base, on=["method", "cohort"], how="left", validate="many_to_one")
        frame["delta_vs_own_original"] = frame.map_at_5-frame.own_original_MAP
        frame.to_csv(OUT / "comparison.csv", index=False)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setting", help="One declared setting, e.g. recent4_t50")
    args = parser.parse_args()
    plan = json.loads((Path(__file__).parent / "training_study_plan.json").read_text())
    settings = [{"id": f"{w['id']}_t{t}", "window": w["id"], "start_local": w["start_local"], "end_local": w["end_local"],
                 "threshold_percent": t} for w in plan["windows"] for t in plan["thresholds_percent"]]
    if args.setting:
        settings = [s for s in settings if s["id"] == args.setting]
    if not settings:
        parser.error("Unknown setting")
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    dump(OUT / "plan.json", plan)
    base = load_data()
    frozen_paths = {"truth": base["paths"]["truth"], "user_cohorts": base["paths"]["users"],
                    "candidate_pool": base["paths"]["candidates"], "original_protocol": base["paths"]["protocol"],
                    "content_vectors": ROOT / "artifacts/content_rules/cbf_title_tfidf_count/item_vectors.npz",
                    "content_item_ids": ROOT / "artifacts/content_rules/cbf_title_tfidf_count/item_ids.npy"}
    frozen_hashes = {key: digest(path) for key, path in frozen_paths.items()}
    dump(OUT / "frozen_inputs.json", {"paths": {k: str(p.relative_to(ROOT)) for k, p in frozen_paths.items()}, "sha256": frozen_hashes})
    truth, reference_meta, user_features, cohorts = build_reference_tables()
    assert truth == base["truth"]
    content_ids = np.load(frozen_paths["content_item_ids"], allow_pickle=False).tolist()
    content_vectors_fixed = sparse.load_npz(frozen_paths["content_vectors"])
    needed_windows = [w for w in plan["windows"] if w["id"] in {s["window"] for s in settings}]
    window_events = prepare_window_events(needed_windows)
    with threadpool_limits(limits=1):
        for setting in settings:
            print(f"Shared setting {setting['id']} ...", flush=True)
            events = window_events[setting["window"]]
            selected = events.loc[training_watch_mask(events, setting["threshold_percent"])].copy()
            data = make_setting_data(base, selected, setting["id"])
            data["paths"].update(training_events=ART / "windows" / setting["window"] / "events.parquet", content_vectors=frozen_paths["content_vectors"])
            stats = {"setting": setting, "positive_airings": len(selected), "positive_user_programme_pairs": data["counts"].nnz,
                     "training_users": len(data["user_ids"]), "training_items": len(data["item_ids"]),
                     "cold_primary_users": sum(u not in data["user_map"] for u in base["eval_users"]),
                     "true_slots_supported_by_this_history": sum(item in data["history"].get(u, set()) for u, ids in truth.items() for item in ids),
                     "true_slots_without_global_training_support": sum(item not in set(data["item_ids"]) for ids in truth.values() for item in ids),
                     "qualified_watch_seconds_below_60": int((selected.watched_seconds < 60).sum()),
                     "median_qualified_coverage": float((selected.watched_seconds/selected.duration).median()),
                     "earliest_observation": int(selected.first_overlap.min()), "latest_observation": int(selected.last_overlap.max())}
            dump(OUT / setting["id"] / "training_summary.json", stats)
            if setting["id"] == "full10_t80":
                if data["user_ids"] != base["user_ids"] or data["item_ids"] != base["item_ids"] or (data["counts"] != base["counts"]).nnz:
                    raise AssertionError("Reference training matrix changed")
            for method in METHODS:
                run_one_model(method, setting, selected, data, reference_meta, user_features, cohorts, (content_ids, content_vectors_fixed))
                refresh_results()
            if any(digest(path) != frozen_hashes[key] for key, path in frozen_paths.items()):
                raise AssertionError("Frozen validation/protocol/metadata input was modified")
    final = refresh_results()
    print(final.loc[final.cohort == "all_primary"].pivot(index="setting", columns="method", values="map_at_5").to_string())


if __name__ == "__main__":
    main()
