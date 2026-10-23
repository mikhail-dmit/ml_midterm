import unittest

from semantic_hybrids import allocate_slots, predict_user, rerank_candidates


class SemanticHybridTests(unittest.TestCase):
    def test_slots_reserve_new_positions_and_borrow_only_when_exhausted(self):
        self.assertEqual(allocate_slots([1, 2, 3, 4, 5], [6, 7, 8], 3), ([1, 2, 3, 6, 7], ["familiar"]*3+["new"]*2))
        self.assertEqual(allocate_slots([1], [6, 7, 8, 9, 10], 4)[0], [1, 6, 7, 8, 9])
        self.assertEqual(allocate_slots([1, 2, 3, 4, 5], [], 3)[0], [1, 2, 3, 4, 5])

    def test_role_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            allocate_slots([1, 2], [2, 3, 4, 5], 3)

    def test_reranking_never_introduces_items_and_ties_keep_generator_order(self):
        values = {8: .1, 9: .8, 10: .8, 11: 0, 12: 0, 99: 100}
        self.assertEqual(rerank_candidates([8, 10, 9, 11, 12], values.__getitem__), [10, 9, 8, 11, 12])

    def test_cold_and_sparse_switch_precede_role_allocation(self):
        config = {"type": "slots", "max_sparse_history": 5}
        pop = [9, 8, 7, 6, 5]
        self.assertEqual(predict_user(config, {}, None, 0, True, pop), (pop, ["cold_popularity"]*5))
        self.assertEqual(predict_user(config, {}, None, 5, False, pop), (pop, ["sparse_popularity"]*5))

    def test_familiarity_comes_from_supplied_role_queues(self):
        queues = {"ppr": {"familiar": [1, 2, 3, 4]}, "association_rules": {"new": [5, 6, 7]}}
        result, roles = predict_user({"type": "slots", "favourite": "ppr", "new": "association_rules", "familiar_slots": 4}, queues, None, 4, False, [9, 8, 7, 6, 5])
        self.assertEqual(result, [1, 2, 3, 4, 5])
        self.assertEqual(roles[-1], "new")


if __name__ == "__main__":
    unittest.main()
