#!/usr/bin/env python3
"""Check a declared Kyiv-time interpretation against log durations and schedule continuity."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from interaction_core import TIMEZONE, local_epoch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sweettv-tv-program-recommender"


def continuity(frame):
    ordered = frame.loc[frame.end > frame.start].sort_values(["channel_id", "start", "end"])
    prior = ordered.groupby("channel_id").end.cummax().groupby(ordered.channel_id).shift()
    delta = ordered.start - prior
    return {"gaps": int((delta > 0).sum()), "overlaps": int((delta < 0).sum()),
            "one_hour_gaps": int((delta == 3600).sum())}


def main():
    output = {"assumed_timezone": TIMEZONE, "log": {}, "schedules": {}}
    counts = {"rows": 0, "naive_duration_mismatches": 0, "timezone_duration_mismatches": 0}
    for chunk in pd.read_csv(DATA / "dataset11-30.csv", usecols=["start_time", "stop_time", "duraton"], chunksize=250000):
        naive_start = pd.to_datetime(chunk.start_time, format="%Y-%m-%d %H:%M:%S")
        naive_end = pd.to_datetime(chunk.stop_time, format="%Y-%m-%d %H:%M:%S")
        counts["rows"] += len(chunk)
        counts["naive_duration_mismatches"] += int(((naive_end - naive_start).dt.total_seconds() != chunk.duraton).sum())
        start = local_epoch(chunk.start_time, "%Y-%m-%d %H:%M:%S")
        end = local_epoch(chunk.stop_time, "%Y-%m-%d %H:%M:%S")
        counts["timezone_duration_mismatches"] += int(((end - start) != chunk.duraton.to_numpy()).sum())
    output["log"] = counts
    combined_naive, combined_utc = [], []
    for filename in ["export_arh_11-20-final.csv", "export_arh_21-30-final.csv"]:
        frame = pd.read_csv(DATA / filename, usecols=["channel_id", "start_time", "duration"])
        naive = pd.to_datetime(frame.start_time, format="%d.%m.%Y %H:%M:%S").astype("int64").to_numpy() // 10**9
        actual = local_epoch(frame.start_time, "%d.%m.%Y %H:%M:%S")
        naive_frame = pd.DataFrame({"channel_id": frame.channel_id, "start": naive, "end": naive + frame.duration.to_numpy()})
        actual_frame = pd.DataFrame({"channel_id": frame.channel_id, "start": actual, "end": actual + frame.duration.to_numpy()})
        output["schedules"][filename] = {"naive": continuity(naive_frame), "timezone_elapsed": continuity(actual_frame)}
        combined_naive.append(naive_frame)
        combined_utc.append(actual_frame)
    output["combined_historical_schedule"] = {"naive": continuity(pd.concat(combined_naive, ignore_index=True)),
                                                "timezone_elapsed": continuity(pd.concat(combined_utc, ignore_index=True))}
    output["interpretation"] = "Empirical consistency check, not independent proof of the source timezone. Schedule end = localized start + supplied duration in elapsed seconds."
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
