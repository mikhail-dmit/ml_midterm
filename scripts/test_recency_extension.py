import unittest

import numpy as np
import pandas as pd

from recency_extension import VoteBundle, strict_rule_counts


class RecencyExtensionTests(unittest.TestCase):
    def test_strict_rule_query_excludes_partial_cf_watches(self):
        events = pd.DataFrame({"user_id": ["u"]*3, "tv_show_id": [1, 2, 3], "watched_seconds": [50, 79, 80],
                               "duration": [100]*3, "last_overlap": [100]*3})
        counts, selected, scale = strict_rule_counts(events, 100, 8)
        self.assertEqual(counts.tv_show_id.tolist(), [3])
        self.assertEqual(len(selected), 1)
        self.assertEqual(counts.watched_airings.sum(), 1)

    def test_recency_pop_vote_changes_warm_votes_but_not_cold_or_tie_order(self):
        counts = pd.DataFrame({"user_id": ["warm", "warm"], "tv_show_id": [1, 2], "watched_airings": [10, 1]})
        scores = {m: np.array([[1., .5], [0., 0.]]) for m in ["implicit_mf", "ppr", "association_rules"]}
        items = {m: [1, 2] for m in scores}
        bundle = VoteBundle(["warm", "cold"], [1, 2, 3, 4, 5], counts, counts, scores, items, vote_counts={1: 1., 2: 20.})
        bundle.prepare_queues(depth=5)
        self.assertEqual(bundle.popularity, [1, 2, 3, 4, 5])
        self.assertEqual(bundle.queues[0]["popularity"]["global"], [2, 1, 3, 4, 5])
        self.assertEqual(bundle.queues[1]["popularity"]["global"], [1, 2, 3, 4, 5])
        self.assertEqual(bundle.score("popularity", 0, 2), 20)
        self.assertEqual(bundle.score("popularity", 1, 2), 1)


if __name__ == "__main__":
    unittest.main()
