import tempfile
import unittest
from pathlib import Path

from lib import metrics


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_transcript_path_is_unavailable(self):
        tokens, measurement_type, confidence = metrics.estimate_effective_tokens(None)
        self.assertIsNone(tokens)
        self.assertEqual(measurement_type, "unavailable")
        self.assertEqual(confidence, "none")

    def test_nonexistent_transcript_file_is_unavailable(self):
        tokens, measurement_type, confidence = metrics.estimate_effective_tokens(
            str(Path(self.cwd) / "does_not_exist.jsonl")
        )
        self.assertIsNone(tokens)
        self.assertEqual(measurement_type, "unavailable")

    def test_existing_transcript_estimates_tokens(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 4000)
        tokens, measurement_type, confidence = metrics.estimate_effective_tokens(str(transcript))
        self.assertEqual(tokens, 1000)
        self.assertEqual(measurement_type, "estimated")
        self.assertEqual(confidence, "low")

    def test_build_metric_sample_computes_utilization(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 40000)
        sample = metrics.build_metric_sample("s1", 3, str(transcript), context_window_tokens=100000)
        self.assertEqual(sample["sessionId"], "s1")
        self.assertEqual(sample["turn"], 3)
        self.assertEqual(sample["effectiveContextTokens"], 10000)
        self.assertEqual(sample["contextWindowTokens"], 100000)
        self.assertEqual(sample["utilizationPercent"], 10.0)
        self.assertEqual(sample["measurementType"], "estimated")

    def test_build_metric_sample_uses_fallback_window(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 4)
        sample = metrics.build_metric_sample("s1", 1, str(transcript))
        self.assertEqual(sample["contextWindowTokens"], metrics._CONTEXT_WINDOW_FALLBACK)

    def test_build_metric_sample_caps_utilization_at_100(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 1_000_000)
        sample = metrics.build_metric_sample("s1", 1, str(transcript), context_window_tokens=1000)
        self.assertEqual(sample["utilizationPercent"], 100)

    def test_build_metric_sample_no_transcript_gives_none_utilization(self):
        sample = metrics.build_metric_sample("s1", 1, None)
        self.assertIsNone(sample["utilizationPercent"])
        self.assertIsNone(sample["effectiveContextTokens"])


if __name__ == "__main__":
    unittest.main()
