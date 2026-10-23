import unittest

import pandas as pd

from segment_analysis import complementarity, true_hit_rows
from training_study import training_watch_mask


class SegmentTests(unittest.TestCase):
    def test_training_thresholds_do_not_renormalize_short_boundary_fragments(self):
        events = pd.DataFrame({"watched_seconds": [199, 200, 499, 500, 799, 800], "duration": [1000]*6})
        self.assertEqual(training_watch_mask(events, 20).tolist(), [False, True, True, True, True, True])
        self.assertEqual(training_watch_mask(events, 50).tolist(), [False, False, False, True, True, True])
        self.assertEqual(training_watch_mask(events, 80).tolist(), [False, False, False, False, False, True])
    def test_ap_credit_partition_keeps_full_truth_denominator(self):
        truth = pd.DataFrame({"user_id": ["u"]*5, "tv_show_id": [1, 2, 3, 4, 5],
                              "familiarity": ["familiar", "new", "new", "familiar", "new"]})
        result = true_hit_rows(truth, {"u": [1, 99, 2, 98, 97]})
        self.assertAlmostEqual(result.AP_contribution.sum(), (1+2/3)/5)
        self.assertAlmostEqual(result.loc[result.familiarity == "familiar", "AP_contribution"].sum(), 1/5)
        self.assertAlmostEqual(result.loc[result.familiarity == "new", "AP_contribution"].sum(), (2/3)/5)

    def test_user_overlap_differs_from_correct_answer_overlap(self):
        truth = {"a": [1, 2, 3, 4, 5], "b": [1, 2, 3, 4, 5]}
        predictions = {"x": {"a": [1, 9, 8, 7, 6], "b": [9, 8, 7, 6, 10]},
                       "y": {"a": [2, 9, 8, 7, 6], "b": [3, 9, 8, 7, 6]}}
        ap = {"x": {"a": .2, "b": 0}, "y": {"a": .2, "b": .2}}
        pairs, _, _ = complementarity(predictions, truth, ap, {"all": ["a", "b"]})
        self.assertEqual(pairs.both_hit_users.iloc[0], 1)
        self.assertEqual(pairs.both_correct_user_item_pairs.iloc[0], 0)
        self.assertEqual(pairs.b_only_hit_users.iloc[0], 1)


if __name__ == "__main__":
    unittest.main()
