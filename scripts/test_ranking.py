"""Check the teacher's numeric examples and metric/protocol failure cases."""

import unittest

import pandas as pd

from popularity_core import available_candidates, fit_popularity, rank_candidates, recommend_popularity
from ranking_metrics import average_precision_at_k, evaluate_rankings


class MetricTests(unittest.TestCase):
    def test_teacher_slide_x(self):
        self.assertAlmostEqual(average_precision_at_k(["A", "B", "C"], ["A", "B", "D", "C", "E"]), 11 / 12)

    def test_teacher_slide_y(self):
        self.assertAlmostEqual(average_precision_at_k(["A", "B", "C"], ["D", "A", "E", "B", "C"]), 8 / 15)

    def test_denominator_is_truth_not_hits(self):
        self.assertAlmostEqual(average_precision_at_k([1, 2, 3, 4, 5], [1, 99, 98, 97, 96]), .2)

    def test_duplicate_prediction_cannot_earn_extra_credit(self):
        self.assertAlmostEqual(average_precision_at_k([1, 2], [1, 1, 2, 3, 4]), (1 + 2 / 3) / 2)

    def test_generic_metric_empty_truth(self):
        self.assertEqual(average_precision_at_k([], [1, 2]), 0)

    def test_prediction_beyond_k_does_not_count(self):
        self.assertEqual(average_precision_at_k([1], [2, 3, 4, 5, 6, 1]), 0)

    def test_truth_order_does_not_matter(self):
        self.assertEqual(average_precision_at_k([1, 2, 3], [3, 9, 2, 8, 1]),
                         average_precision_at_k([3, 1, 2], [3, 9, 2, 8, 1]))

    def test_macro_average_includes_zero_hit_users(self):
        metric, _ = evaluate_rankings({"a": [1], "b": [9]}, {"a": [1, 2, 3, 4, 5], "b": [1, 2, 3, 4, 5]})
        self.assertEqual(metric["map_at_5"], .5)

    def test_missing_user_is_an_error(self):
        with self.assertRaises(ValueError):
            evaluate_rankings({"a": [1], "b": [9]}, {"a": [1, 2, 3, 4, 5]})

    def test_empty_truth_is_not_silently_excluded(self):
        with self.assertRaises(ValueError):
            evaluate_rankings({"a": []}, {"a": [1, 2, 3, 4, 5]})

    def test_submission_lists_must_have_five_distinct_ids(self):
        for predicted in [[1, 2], [1, 1, 2, 3, 4]]:
            with self.assertRaises(ValueError):
                evaluate_rankings({"a": [1]}, {"a": predicted})

    def test_explicit_subset_and_large_user_id(self):
        user = "18443832178892490378"
        result, _ = evaluate_rankings({user: [1], "2": [9]},
                                      {user: [1, 2, 3, 4, 5], "2": [1, 2, 3, 4, 5]}, users=[user])
        self.assertEqual(result["users"], 1)
        self.assertEqual(result["map_at_5"], 1)

    def test_reporting_cannot_mislabel_another_cutoff_as_map5(self):
        with self.assertRaises(ValueError):
            evaluate_rankings({"a": [1]}, {"a": [1, 2, 3, 4, 5]}, k=10)


class PopularityPolicyTests(unittest.TestCase):
    def test_fit_rejects_validation_rows(self):
        frame = pd.DataFrame({"split": ["train", "validation"], "user_id": ["1", "1"],
                              "tv_show_id": [1, 2], "watched_airings": [1, 999]})
        with self.assertRaises(ValueError):
            fit_popularity(frame)

    def test_counts_use_all_training_users_and_ignore_partial_only_pairs(self):
        frame = pd.DataFrame({"split": ["train"] * 3, "user_id": ["1", "2", "1"],
                              "tv_show_id": [1, 1, 2], "watched_airings": [3, 4, 0]})
        scores, seen = fit_popularity(frame)
        self.assertEqual(scores.training_watched_airings.tolist(), [7])
        self.assertEqual(seen, {"1": {1}, "2": {1}})

    def test_availability_uses_overlap_not_only_start_or_training_presence(self):
        frame = pd.DataFrame({"tv_show_id": [1, 2, 3, 0, 4], "duration": [20, 10, 10, 10, 0],
                              "start": [0, 20, 30, 21, 22], "end": [20, 30, 40, 31, 22]})
        self.assertEqual(available_candidates(frame, 10, 30), [1, 2])

    def test_zero_score_candidates_and_deterministic_tie_break(self):
        scores = pd.DataFrame({"tv_show_id": [3, 2], "training_watched_airings": [4, 4],
                               "training_distinct_viewers": [1, 2]})
        self.assertEqual(rank_candidates(scores, [1, 2, 3]).tv_show_id.tolist(), [2, 3, 1])

    def test_repeat_mask_and_cold_fallback(self):
        ranked = [1, 2, 3, 4, 5, 6, 7]
        seen = {"1": {1, 3}}
        self.assertEqual(recommend_popularity(ranked, "1", seen, True), [1, 2, 3, 4, 5])
        self.assertEqual(recommend_popularity(ranked, "1", seen, False), [2, 4, 5, 6, 7])
        self.assertEqual(recommend_popularity(ranked, "cold", seen, False), [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
