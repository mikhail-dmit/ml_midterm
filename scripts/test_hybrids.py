import unittest

from hybrid_models import history_switch, reciprocal_rank_fusion


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.pop = [60, 10, 20, 30, 40, 50, 70, 80, 90]
        self.lists = {"a": [10, 20, 30, 40, 50], "b": [60, 20, 70, 80, 90]}

    def test_offset_changes_consensus_vs_first_rank_tradeoff(self):
        direct, scores = reciprocal_rank_fusion(self.lists, {"a": 1, "b": 1}, self.pop)
        consensus, _ = reciprocal_rank_fusion(self.lists, {"a": 1, "b": 1}, self.pop, offset=10)
        self.assertEqual(direct[:3], [60, 10, 20])
        self.assertEqual(scores[10], scores[20])
        self.assertEqual(consensus[0], 20)

    def test_component_order_and_common_weight_scale_do_not_change_ranking(self):
        a, _ = reciprocal_rank_fusion(self.lists, {"a": .5, "b": .5}, self.pop)
        b, _ = reciprocal_rank_fusion(self.lists, {"b": 2, "a": 2}, self.pop)
        self.assertEqual(a, b)

    def test_short_lists_backfill_and_cold_lists_preserve_popularity(self):
        short, _ = reciprocal_rank_fusion({"a": [20]}, {"a": 1}, self.pop)
        cold, _ = reciprocal_rank_fusion({"a": self.pop[:5], "b": self.pop[:5]}, {"a": .5, "b": .25}, self.pop)
        self.assertEqual(short, [20, 60, 10, 30, 40])
        self.assertEqual(cold, self.pop[:5])

    def test_duplicate_votes_and_unavailable_ids_are_rejected(self):
        for ids in [[10, 10], [999]]:
            with self.assertRaises(ValueError):
                reciprocal_rank_fusion({"a": ids}, {"a": 1}, self.pop)
        for weights in [{"a": -1}, {"a": float("nan")}, {"a": 0}]:
            with self.assertRaises(ValueError):
                reciprocal_rank_fusion(self.lists, weights, self.pop)

    def test_switch_boundary_uses_only_supplied_training_history(self):
        self.assertEqual(history_switch(self.lists, 5, 5, "a", "b"), (self.lists["a"], "a"))
        self.assertEqual(history_switch(self.lists, 6, 5, "a", "b"), (self.lists["b"], "b"))
        with self.assertRaises(ValueError):
            history_switch(self.lists, -1, 5, "a", "b")


if __name__ == "__main__":
    unittest.main()
