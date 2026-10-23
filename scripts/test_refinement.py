import unittest

import numpy as np
import pandas as pd

from refinement_models import recency_training_counts
from hybrid_models import reciprocal_rank_fusion


class RefinementTests(unittest.TestCase):
    def test_half_life_and_mass_preservation_with_duplicate_pair(self):
        cutoff, week = 10000000, 7*86400
        events = pd.DataFrame({"user_id": ["u", "u", "v"], "tv_show_id": [1, 1, 2],
                               "watched_seconds": [50, 50, 50], "duration": [100]*3,
                               "last_overlap": [cutoff, cutoff-4*week, cutoff-8*week]})
        counts, weighted, scale = recency_training_counts(events, cutoff, 4)
        np.testing.assert_allclose(weighted.raw_recency_weight, [1, .5, .25])
        self.assertAlmostEqual(scale, 12/7)
        self.assertAlmostEqual(counts.watched_airings.sum(), 3)
        self.assertAlmostEqual(counts.iloc[0].watched_airings, 18/7)

    def test_future_event_and_invalid_half_life_rejected(self):
        events = pd.DataFrame({"user_id": ["u"], "tv_show_id": [1], "watched_seconds": [50], "duration": [100], "last_overlap": [101]})
        for h in [0, -1, float("inf"), float("nan")]:
            with self.assertRaises(ValueError):
                recency_training_counts(events, 100, h)
        with self.assertRaises(ValueError):
            recency_training_counts(events, 100, 4)

    def test_deeper_retrieval_can_promote_consensus_beyond_original_top5(self):
        lists = {"a": [1, 2, 3, 4, 5, 99], "b": [6, 7, 8, 9, 10, 99]}
        pop = [99, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        shallow, _ = reciprocal_rank_fusion({m: ids[:5] for m, ids in lists.items()}, {"a": 1, "b": 1}, pop, 10)
        deep, _ = reciprocal_rank_fusion(lists, {"a": 1, "b": 1}, pop, 10)
        self.assertNotIn(99, shallow)
        self.assertEqual(deep[0], 99)


if __name__ == "__main__":
    unittest.main()
