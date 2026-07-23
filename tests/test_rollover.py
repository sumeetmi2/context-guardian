import unittest

from lib import rollover

MONITORING = {
    "warningThresholdPercent": 72,
    "compactThresholdPercent": 84,
    "criticalThresholdPercent": 92,
    "sampleEveryTurns": 1,
    "renotifyAfterTurns": 8,
}


class RolloverTests(unittest.TestCase):
    def test_mode_off_never_triggers(self):
        self.assertFalse(
            rollover.should_trigger_rollover(99, MONITORING, {"mode": "off"})
        )

    def test_mode_wrapper_triggers_on_critical(self):
        self.assertTrue(
            rollover.should_trigger_rollover(95, MONITORING, {"mode": "wrapper"})
        )

    def test_mode_wrapper_does_not_trigger_below_critical(self):
        self.assertFalse(
            rollover.should_trigger_rollover(80, MONITORING, {"mode": "wrapper"})
        )

    def test_missing_mode_defaults_to_off(self):
        self.assertFalse(rollover.should_trigger_rollover(99, MONITORING, {}))

    def test_none_utilization_never_triggers(self):
        self.assertFalse(
            rollover.should_trigger_rollover(None, MONITORING, {"mode": "wrapper"})
        )


if __name__ == "__main__":
    unittest.main()
