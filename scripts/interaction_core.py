"""Time and interval primitives for the SWEET.TV interaction builder."""

from __future__ import annotations

import numpy as np
import pandas as pd

TIMEZONE = "Europe/Kyiv"
LOCAL_WINDOWS = {
    "train": ("2020-03-09 00:00:00", "2020-05-18 00:00:00"),
    "validation": ("2020-05-18 00:00:00", "2020-07-27 00:00:00"),
}


def local_epoch(values, fmt, timezone=TIMEZONE):
    naive = pd.to_datetime(values, format=fmt, errors="raise")
    aware = naive.dt.tz_localize(timezone, ambiguous="raise", nonexistent="raise")
    return aware.astype("int64").to_numpy() // 10**9


def boundary_epoch(value, timezone=TIMEZONE):
    return int(pd.Timestamp(value).tz_localize(timezone).timestamp())


def local_text(epoch, timezone=TIMEZONE):
    return pd.Timestamp(int(epoch), unit="s", tz="UTC").tz_convert(timezone).isoformat()


def utc_text(epoch):
    return pd.Timestamp(int(epoch), unit="s", tz="UTC").isoformat()


def merge_views(views):
    """Union intervals per user/channel; touching intervals can be coalesced."""
    keys = ["user_id", "channel_id"]
    ordered = views.sort_values(keys + ["start", "end"], kind="stable").reset_index(drop=True)
    previous_max = ordered.groupby(keys, sort=False).end.cummax().groupby(
        [ordered[c] for c in keys], sort=False
    ).shift()
    new_group = previous_max.isna() | (ordered.start > previous_max)
    group_ids = new_group.cumsum()
    return ordered.groupby(group_ids, sort=False).agg(
        user_id=("user_id", "first"), channel_id=("channel_id", "first"),
        start=("start", "min"), end=("end", "max"), source_rows=("source_rows", "sum"),
    ).reset_index(drop=True)


def clip_views(views, lower, upper):
    clipped = views.loc[(views.start < upper) & (views.end > lower)].copy()
    clipped["start"] = clipped.start.clip(lower=lower)
    clipped["end"] = clipped.end.clip(upper=upper)
    return clipped


def join_channel(views, airings):
    """All positive overlaps; prefix ends make this safe for nested airings too."""
    if views.empty or airings.empty:
        return pd.DataFrame()
    airings = airings.sort_values(["start", "end", "airing_id"], kind="stable").reset_index(drop=True)
    starts, ends = airings.start.to_numpy(), airings.end.to_numpy()
    a, b = views.start.to_numpy(), views.end.to_numpy()
    lower = np.searchsorted(np.maximum.accumulate(ends), a, side="right")
    upper = np.searchsorted(starts, b, side="left")
    counts = upper - lower
    if (counts < 0).any():
        raise AssertionError("Negative candidate range")
    total = int(counts.sum())
    if not total:
        return pd.DataFrame()
    view_idx = np.repeat(np.arange(len(views)), counts)
    offsets = np.repeat(np.cumsum(counts) - counts, counts)
    airing_idx = np.repeat(lower, counts) + np.arange(total) - offsets
    overlap_start = np.maximum(a[view_idx], starts[airing_idx])
    overlap_end = np.minimum(b[view_idx], ends[airing_idx])
    positive = overlap_end > overlap_start
    return pd.DataFrame({
        "user_id": views.user_id.to_numpy()[view_idx[positive]],
        "airing_id": airings.airing_id.to_numpy()[airing_idx[positive]],
        "overlap_start": overlap_start[positive], "overlap_end": overlap_end[positive],
        "overlap_seconds": (overlap_end - overlap_start)[positive],
    })


def watched_mask(seconds, duration):
    # Exact >= 4/5 comparison, no floating-point threshold rounding.
    return np.asarray(seconds) * 5 >= np.asarray(duration) * 4
