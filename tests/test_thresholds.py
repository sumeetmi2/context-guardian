import unittest

from lib import thresholds

MONITORING = {
    "warningThresholdPercent": 72,
    "compactThresholdPercent": 84,
    "criticalThresholdPercent": 92,
    "sampleEveryTurns": 1,
    "renotifyAfterTurns": 8,
}


class ThresholdsTests(unittest.TestCase):
    def test_none_is_unknown(self):
        self.assertEqual(thresholds.classify(None, MONITORING), "unknown")

    def test_below_warning_is_nominal(self):
        self.assertEqual(thresholds.classify(50, MONITORING), thresholds.NOMINAL)

    def test_at_warning_boundary(self):
        self.assertEqual(thresholds.classify(72, MONITORING), thresholds.WARNING)
        self.assertEqual(thresholds.classify(71.9, MONITORING), thresholds.NOMINAL)

    def test_at_compact_boundary(self):
        self.assertEqual(thresholds.classify(84, MONITORING), thresholds.COMPACT)
        self.assertEqual(thresholds.classify(83.9, MONITORING), thresholds.WARNING)

    def test_at_critical_boundary(self):
        self.assertEqual(thresholds.classify(92, MONITORING), thresholds.CRITICAL)
        self.assertEqual(thresholds.classify(91.9, MONITORING), thresholds.COMPACT)

    def test_above_critical(self):
        self.assertEqual(thresholds.classify(100, MONITORING), thresholds.CRITICAL)

    def test_should_notify_on_escalation(self):
        self.assertTrue(thresholds.should_notify(thresholds.WARNING, thresholds.NOMINAL, 0, MONITORING))

    def test_should_notify_on_deescalation(self):
        self.assertTrue(thresholds.should_notify(thresholds.NOMINAL, thresholds.WARNING, 0, MONITORING))

    def test_should_not_notify_within_renotify_window(self):
        self.assertFalse(thresholds.should_notify(thresholds.WARNING, thresholds.WARNING, 3, MONITORING))

    def test_should_notify_after_renotify_window(self):
        self.assertTrue(thresholds.should_notify(thresholds.WARNING, thresholds.WARNING, 8, MONITORING))

    def test_should_not_notify_repeated_nominal(self):
        self.assertFalse(thresholds.should_notify(thresholds.NOMINAL, thresholds.NOMINAL, 100, MONITORING))

    def test_recommended_action_covers_every_status(self):
        for status in [thresholds.NOMINAL, thresholds.WARNING, thresholds.COMPACT,
                       thresholds.CRITICAL, "unknown"]:
            action = thresholds.recommended_action(status)
            self.assertIsInstance(action, str)
            self.assertTrue(action)


if __name__ == "__main__":
    unittest.main()
