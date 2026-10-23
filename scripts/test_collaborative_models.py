import unittest

import numpy as np
from scipy import sparse

from collaborative_models import (
    als_objective, als_update, build_coview_graph, fit_implicit_als,
    personalized_pagerank, rank_model_scores, restart_profiles,
)


class ImplicitALSTests(unittest.TestCase):
    def test_sparse_update_matches_dense_normal_equations(self):
        counts = sparse.csr_matrix([[2., 0, 1], [0, 3, 0]])
        fixed = np.array([[.2, .4], [.8, .1], [.5, .9]])
        actual = als_update(counts, fixed, 10, 1)
        for row in range(2):
            values = counts.toarray()[row]
            c = 1 + 10 * np.log1p(values)
            p = (values > 0).astype(float)
            expected = np.linalg.solve(fixed.T @ np.diag(c) @ fixed + np.eye(2), fixed.T @ (c * p))
            np.testing.assert_allclose(actual[row], expected, atol=1e-12)

    def test_objective_matches_full_dense_sum(self):
        counts = sparse.csr_matrix([[2., 0, 1], [0, 3, 0]])
        x = np.array([[.3, .1], [.2, .6]])
        y = np.array([[.2, .4], [.8, .1], [.5, .9]])
        raw = counts.toarray()
        expected = np.sum((1 + 10 * np.log1p(raw)) * ((raw > 0) - x @ y.T)**2) + np.sum(x*x) + np.sum(y*y)
        self.assertAlmostEqual(als_objective(counts, x, y, 10, 1), expected)

    def test_fit_decreases_objective_and_is_reproducible(self):
        counts = sparse.csr_matrix([[2., 0, 1], [0, 3, 1], [1, 1, 0]])
        x, y, h = fit_implicit_als(counts, factors=2, epochs=4)
        x2, y2, _ = fit_implicit_als(counts, factors=2, epochs=4)
        self.assertTrue(all(b["training_objective"] <= a["training_objective"] for a, b in zip(h, h[1:])))
        np.testing.assert_array_equal(x, x2)
        np.testing.assert_array_equal(y, y2)

    def test_log_count_target_update_matches_dense_system(self):
        counts = sparse.csr_matrix([[2., 0, 8]])
        y = np.array([[.2, .4], [.8, .1], [.5, .9]])
        raw = counts.toarray()[0]
        c, target = 1 + np.log1p(raw), np.log1p(raw)
        expected = np.linalg.solve(y.T @ np.diag(c) @ y + np.eye(2), y.T @ (c * target))
        actual = als_update(counts, y, 1, 1, preference="log1p")
        np.testing.assert_allclose(actual[0], expected, atol=1e-12)
        x = np.array([[.3, .1]])
        objective = np.sum(c * (target - (x @ y.T)[0])**2) + np.sum(x*x) + np.sum(y*y)
        self.assertAlmostEqual(als_objective(counts, x, y, 1, 1, preference="log1p"), objective)


class PageRankTests(unittest.TestCase):
    def test_graph_counts_distinct_users_not_frequency_products(self):
        counts = sparse.csr_matrix([[4., 2, 0], [1, 1, 0], [0, 1, 1]])
        adjacency, transition, dangling, _ = build_coview_graph(counts)
        self.assertEqual(adjacency[0, 1], 2)
        np.testing.assert_array_equal(adjacency.diagonal(), 0)
        np.testing.assert_allclose(np.asarray(transition.sum(axis=1)).ravel(), 1)

    def test_direct_solution_matches_independent_power_iteration_with_dangling(self):
        transition = sparse.csr_matrix([[0., 1, 0], [1., 0, 0], [0, 0, 0]])
        restart = np.array([[.2, .3, .5], [0., 0, 1.]])
        result, checks = personalized_pagerank(transition, restart, .85)
        reference = restart.copy()
        for _ in range(1000):
            nxt = .85 * (reference @ transition.toarray() + reference[:, 2, None] * restart) + .15 * restart
            if np.max(np.abs(nxt - reference)) < 1e-14:
                break
            reference = nxt
        np.testing.assert_allclose(result, reference, atol=1e-12)
        self.assertLess(checks["max_L1_fixed_point_residual"], 1e-12)

    def test_restart_and_raw_cosine_normalization(self):
        counts = sparse.csr_matrix([[4., 2, 0], [1, 1, 0], [0, 1, 1]])
        v = restart_profiles(counts, "count").toarray()
        np.testing.assert_allclose(v[0], [2/3, 1/3, 0])
        adjacency, _, _, _ = build_coview_graph(counts, "cosine")
        self.assertAlmostEqual(adjacency[0, 1], 2 / np.sqrt(2 * 3))

    def test_full_pool_repeat_policy_and_identical_cold_fallback(self):
        predictions, _ = rank_model_scores(np.array([[.1, .2], [0, 0]]), ["warm", "cold"],
                                            {"warm"}, [5, 3], [1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1])
        self.assertEqual(predictions["warm"], [3, 5, 1, 2, 4])
        self.assertEqual(predictions["cold"], [6, 5, 4, 3, 2])


if __name__ == "__main__":
    unittest.main()
