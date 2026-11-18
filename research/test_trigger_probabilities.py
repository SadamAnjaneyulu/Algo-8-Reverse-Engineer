import unittest

import numpy as np

from rank_trigger_probabilities import event_metrics, first_alert, numeric_features, select_threshold, wilson, predict_tree_probability


class ProbabilityChecks(unittest.TestCase):
    def test_precision_does_not_hide_low_event_coverage(self):
        truth = np.array([True] * 100 + [False] * 100)
        predicted = np.array([True] * 8 + [False] * 92 + [True] * 2 + [False] * 98)
        score = event_metrics(truth, predicted)
        self.assertEqual(score['precision'], .8)
        self.assertEqual(score['recall'], .08)
        self.assertEqual(score['false_signals'], 2)

    def test_empty_signals_have_no_claimed_precision(self):
        score = event_metrics([True, False], [False, False])
        self.assertIsNone(score['precision'])
        self.assertEqual(score['recall'], 0)

    def test_threshold_needs_support_across_cycles(self):
        rows = [dict(cycle='one')] * 30
        self.assertIsNone(select_threshold(rows, np.ones(30, bool), np.ones(30), .9))
        rows = [dict(cycle=str(i % 3)) for i in range(30)]
        selected = select_threshold(rows, np.ones(30, bool), np.ones(30), .9)
        self.assertIsNotNone(selected)
        self.assertEqual(selected['calibration']['recall'], 1)

    def test_high_precision_at_tiny_support_is_rejected(self):
        rows = [dict(cycle=str(i % 3)) for i in range(100)]
        truth = np.array([True] * 5 + [False] * 95)
        p = np.array([.99] * 5 + [.01] * 95)
        self.assertIsNone(select_threshold(rows, truth, p, .8))

    def test_first_alert_cannot_replace_a_wrong_early_signal(self):
        rows = [dict(cycle='a', available_at_ist='2026-07-07T09:30:00+05:30'),
                dict(cycle='a', available_at_ist='2026-07-07T10:00:00+05:30')]
        result = first_alert(rows, [.95, .95], .9, {'a': 600, 'b': 610})
        self.assertEqual(result[0]['predicted_minute'], 570)
        self.assertFalse(result[0]['matched_2m'])
        self.assertIsNone(result[1]['predicted_minute'])

    def test_prediction_inputs_exclude_target_and_future_labels(self):
        row = dict(target_quantity=100, observed_minute=600, paired_sale=1, short_cover=1,
                   x_short_units=3, x_net_equity_pct_capital=-.4, future_exit_time_ist='later')
        features = numeric_features([row])
        self.assertIn('x_short_units', features)
        self.assertNotIn('target_quantity', features)
        self.assertNotIn('observed_minute', features)
        self.assertNotIn('paired_sale', features)
        self.assertNotIn('future_exit_time_ist', features)

    def test_all_successes_still_have_uncertainty(self):
        low, high = wilson(10, 10)
        self.assertLess(low, .8)
        self.assertAlmostEqual(high, 1)
        self.assertEqual(wilson(0, 0), (None, None))

    def test_saved_probability_uses_leaf_frequency_and_sigmoid(self):
        program = dict(input_features=['x'], median_statistics=[0], missing_indicator_features=[],
                       tree=dict(children_left=[-1], children_right=[-1], feature=[-2], threshold=[-2],
                                 classes=[False, True], values=[[[.2, .8]]]),
                       sigmoid_coefficient=1, sigmoid_intercept=0)
        self.assertAlmostEqual(predict_tree_probability(program, [dict(x=None)])[0], .8)
        program['sigmoid_intercept'] = -np.log(4)
        self.assertAlmostEqual(predict_tree_probability(program, [dict(x=2)])[0], .5)


if __name__ == '__main__':
    unittest.main()
