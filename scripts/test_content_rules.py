import unittest

import numpy as np
import pandas as pd
from scipy import sparse

from content_rule_models import content_scores, content_vectors, metadata_document, mine_pair_rules, rank_positive_with_backfill, title_tokens


class ContentTests(unittest.TestCase):
    def test_cosine_profile_matches_hand_computation(self):
        docs = [{"genre": ["action"]}, {"genre": ["comedy"]}, {"genre": ["action", "comedy"]}]
        vectors, _, _ = content_vectors(docs, {"genre": 1}, family_balance=False)
        scores, profiles = content_scores(sparse.csr_matrix([[1., 1, 0]]), vectors, "binary")
        np.testing.assert_allclose(scores[0], [1/np.sqrt(2), 1/np.sqrt(2), 1], atol=1e-12)

    def test_idf_and_duplicate_tokens(self):
        docs = [{"genre": ["a", "a", "b"]}, {"genre": ["a"]}]
        _, names, weights = content_vectors(docs, {"genre": 1}, idf=True)
        self.assertEqual(names, ["genre:a", "genre:b"])
        np.testing.assert_allclose(weights, [1, np.log(3/2)+1])

    def test_family_balance_prevents_long_cast_norm_domination(self):
        docs = [{"category": ["film"], "actor": ["a", "b", "c", "d"]}]
        vectors, names, _ = content_vectors(docs, {"category": 1, "actor": 1}, family_balance=True)
        values = vectors.toarray()[0]
        self.assertAlmostEqual(sum(x*x for x, n in zip(values, names) if n.startswith("category:")), .5)
        self.assertAlmostEqual(sum(x*x for x, n in zip(values, names) if n.startswith("actor:")), .5)

    def test_title_numbers_and_boilerplate_are_not_identity_features(self):
        self.assertEqual(title_tokens("ТСН., 7 сезон, 3 эп."), {"тсн"})


class AssociationTests(unittest.TestCase):
    def test_directional_confidence_support_and_lift(self):
        # Four baskets: AB, AB, A, C. A->B confidence=2/3, B->A=1, lift=4/3.
        baskets = sparse.csr_matrix([[1, 1, 0], [1, 1, 0], [1, 0, 0], [0, 0, 1]])
        _, rules, _, _, _ = mine_pair_rules(baskets, [10, 20, 30], 1, 0)
        ab = rules.loc[(rules.antecedent_id == 10) & (rules.consequent_id == 20)].iloc[0]
        ba = rules.loc[(rules.antecedent_id == 20) & (rules.consequent_id == 10)].iloc[0]
        self.assertEqual(ab.joint_count, 2)
        self.assertAlmostEqual(ab.support, .5)
        self.assertAlmostEqual(ab.confidence, 2/3)
        self.assertAlmostEqual(ba.confidence, 1)
        self.assertAlmostEqual(ab.lift, 4/3)

    def test_no_self_rules_or_frequency_product_inflation(self):
        baskets = sparse.csr_matrix([[50, 7, 0], [3, 2, 0], [0, 0, 1]])
        _, rules, _, _, _ = mine_pair_rules(baskets, [10, 20, 30], 1, 0)
        self.assertTrue((rules.antecedent_id != rules.consequent_id).all())
        self.assertTrue((rules.joint_count == 2).all())

    def test_lift_equal_one_is_excluded(self):
        baskets = sparse.csr_matrix([[1, 1], [1, 1], [1, 0]])
        _, rules, _, _, _ = mine_pair_rules(baskets, [1, 2], 1, 0)
        self.assertTrue(rules.empty)

    def test_positive_rules_allow_repeats_and_popularity_fills_missing_slots(self):
        predicted, details = rank_positive_with_backfill(np.array([[0., 3], [0, 0]]), ["warm", "cold"],
                                                        {"warm"}, [1, 2], [1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1])
        self.assertEqual(predicted["warm"], [2, 6, 5, 4, 3])
        self.assertEqual(predicted["cold"], [6, 5, 4, 3, 2])
        self.assertEqual(sum(r["fallback"] for r in details), 9)


if __name__ == "__main__":
    unittest.main()
