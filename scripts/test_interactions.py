"""Meaningful edge-case checks for time handling, interval union, and the join."""

import unittest

import numpy as np
import pandas as pd

from interaction_core import clip_views, join_channel, local_epoch, merge_views, watched_mask


class InteractionTests(unittest.TestCase):
    def test_dst_elapsed_matches_actual_seconds(self):
        start = local_epoch(pd.Series(["2020-03-29 01:00:23"]), "%Y-%m-%d %H:%M:%S")
        end = local_epoch(pd.Series(["2020-03-29 04:02:23"]), "%Y-%m-%d %H:%M:%S")
        self.assertEqual(int(end[0] - start[0]), 7320)

    def test_nonexistent_time_is_not_silently_shifted(self):
        with self.assertRaises(Exception):
            local_epoch(pd.Series(["2020-03-29 03:30:00"]), "%Y-%m-%d %H:%M:%S")

    def test_union_preserves_large_ids_and_nested_intervals(self):
        user = 17226860011138219284
        views = pd.DataFrame({"user_id": np.array([user] * 4, dtype="uint64"),
                              "channel_id": [1] * 4, "start": [0, 2, 4, 10],
                              "end": [10, 3, 6, 12], "source_rows": [1] * 4})
        merged = merge_views(views)
        self.assertEqual(int(merged.user_id.iloc[0]), user)
        self.assertEqual(merged[["start", "end"]].values.tolist(), [[0, 12]])

    def test_union_does_not_merge_users_or_channels(self):
        views = pd.DataFrame({"user_id": [1, 1, 2], "channel_id": [1, 2, 1],
                              "start": [0] * 3, "end": [10] * 3, "source_rows": [1] * 3})
        self.assertEqual(len(merge_views(views)), 3)

    def test_join_spans_programmes_and_excludes_touching(self):
        views = pd.DataFrame({"user_id": [1, 1], "start": [5, 20], "end": [15, 25]})
        airings = pd.DataFrame({"airing_id": [0, 1], "start": [0, 10], "end": [10, 20]})
        result = join_channel(views, airings)
        self.assertEqual(result.airing_id.tolist(), [0, 1])
        self.assertEqual(result.overlap_seconds.tolist(), [5, 5])

    def test_nested_airings_are_all_considered(self):
        views = pd.DataFrame({"user_id": [1], "start": [5], "end": [7]})
        airings = pd.DataFrame({"airing_id": [0, 1, 2], "start": [0, 2, 4], "end": [10, 3, 8]})
        result = join_channel(views, airings)
        self.assertEqual(result.airing_id.tolist(), [0, 2])

    def test_cutoff_clips_time_without_changing_show_denominator(self):
        views = pd.DataFrame({"user_id": [1], "channel_id": [1], "start": [0],
                              "end": [100], "source_rows": [1]})
        left = clip_views(views, 0, 50)
        right = clip_views(views, 50, 100)
        self.assertEqual(int((left.end - left.start).sum()), 50)
        self.assertEqual(int((right.end - right.start).sum()), 50)
        self.assertFalse(watched_mask([50], [100])[0])

    def test_eighty_percent_boundary_is_exact(self):
        self.assertEqual(watched_mask([799, 800, 801], [1000] * 3).tolist(), [False, True, True])

    def test_future_views_do_not_change_clipped_training_union(self):
        before = pd.DataFrame({"user_id": [1, 1], "channel_id": [2, 2], "start": [10, 30],
                               "end": [20, 60], "source_rows": [1, 1]})
        future = pd.DataFrame({"user_id": [1, 1], "channel_id": [2, 2], "start": [50, 55],
                               "end": [70, 80], "source_rows": [1, 1]})
        left = clip_views(merge_views(before), 0, 50)
        right = clip_views(merge_views(pd.concat([before, future], ignore_index=True)), 0, 50)
        self.assertEqual(left[["start", "end"]].values.tolist(), right[["start", "end"]].values.tolist())

    def test_fast_join_matches_naive_enumeration(self):
        rng = np.random.default_rng(20261023)
        for _ in range(30):
            starts = rng.integers(0, 100, size=15)
            airings = pd.DataFrame({"airing_id": np.arange(15), "start": starts,
                                   "end": starts + rng.integers(1, 40, size=15)})
            vstarts = rng.integers(0, 120, size=9)
            views = pd.DataFrame({"user_id": np.arange(9), "start": vstarts,
                                 "end": vstarts + rng.integers(1, 20, size=9)})
            expected = sorted((u.user_id, a.airing_id, max(u.start, a.start), min(u.end, a.end))
                              for u in views.itertuples() for a in airings.itertuples()
                              if max(u.start, a.start) < min(u.end, a.end))
            fast = join_channel(views, airings)
            actual = sorted(fast[["user_id", "airing_id", "overlap_start", "overlap_end"]].itertuples(index=False, name=None)) if len(fast) else []
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
