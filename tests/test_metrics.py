import json
import tempfile
import unittest
from pathlib import Path

from lib import metrics


def _assistant_line(input_tokens=0, cache_creation=0, cache_read=0, output_tokens=0):
    return json.dumps({
        "type": "assistant",
        "message": {
            "model": "claude-sonnet-5",
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
                "output_tokens": output_tokens,
            },
        },
    })


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

    def test_fallback_window_reflects_modern_context_sizes(self):
        # Regression guard: this was 200_000 (Sonnet-3-era), badly
        # underestimating the denominator for current 500k-1M+ windows and
        # inflating the reported percentage. See monitoring.contextWindowTokens
        # for the configurable, accurate override.
        self.assertGreaterEqual(metrics._CONTEXT_WINDOW_FALLBACK, 1_000_000)

    def test_build_metric_sample_caps_utilization_at_100(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 1_000_000)
        sample = metrics.build_metric_sample("s1", 1, str(transcript), context_window_tokens=1000)
        self.assertEqual(sample["utilizationPercent"], 100)

    def test_build_metric_sample_no_transcript_gives_none_utilization(self):
        sample = metrics.build_metric_sample("s1", 1, None)
        self.assertIsNone(sample["utilizationPercent"])
        self.assertIsNone(sample["effectiveContextTokens"])

    def test_baseline_subtracted_from_effective_tokens(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 40000)
        tokens, _, _ = metrics.estimate_effective_tokens(str(transcript), baseline_bytes=20000)
        self.assertEqual(tokens, 5000)

    def test_baseline_larger_than_size_floors_at_zero(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 100)
        tokens, _, _ = metrics.estimate_effective_tokens(str(transcript), baseline_bytes=1_000_000)
        self.assertEqual(tokens, 0)

    def test_build_metric_sample_applies_baseline(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("x" * 40000)
        sample = metrics.build_metric_sample(
            "s1", 3, str(transcript), context_window_tokens=100000, baseline_bytes=20000
        )
        self.assertEqual(sample["effectiveContextTokens"], 5000)
        self.assertEqual(sample["utilizationPercent"], 5.0)

    def test_real_usage_preferred_over_heuristic(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text(_assistant_line(input_tokens=100, cache_creation=200, cache_read=700) + "\n")
        tokens, measurement_type, confidence = metrics.estimate_effective_tokens(str(transcript))
        self.assertEqual(tokens, 1000)
        self.assertEqual(measurement_type, "actual")
        self.assertEqual(confidence, "high")

    def test_real_usage_uses_most_recent_assistant_turn(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        lines = [
            _assistant_line(input_tokens=10, cache_creation=0, cache_read=0),
            json.dumps({"type": "user", "message": {"content": "tool result"}}),
            _assistant_line(input_tokens=50, cache_creation=25, cache_read=25),
        ]
        transcript.write_text("\n".join(lines) + "\n")
        tokens, measurement_type, _ = metrics.estimate_effective_tokens(str(transcript))
        self.assertEqual(tokens, 100)
        self.assertEqual(measurement_type, "actual")

    def test_real_usage_ignores_baseline_bytes(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text(_assistant_line(input_tokens=100, cache_creation=0, cache_read=0) + "\n")
        tokens, _, _ = metrics.estimate_effective_tokens(str(transcript), baseline_bytes=1_000_000)
        self.assertEqual(tokens, 100)

    def test_falls_back_to_heuristic_when_no_assistant_usage_present(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        tokens, measurement_type, confidence = metrics.estimate_effective_tokens(str(transcript))
        self.assertEqual(measurement_type, "estimated")
        self.assertEqual(confidence, "low")
        self.assertIsNotNone(tokens)

    def test_falls_back_to_heuristic_on_corrupt_trailing_line(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text("not valid json at all\n")
        tokens, measurement_type, _ = metrics.estimate_effective_tokens(str(transcript))
        self.assertEqual(measurement_type, "estimated")
        self.assertIsNotNone(tokens)

    def test_build_metric_sample_uses_real_usage(self):
        transcript = Path(self.cwd) / "transcript.jsonl"
        transcript.write_text(_assistant_line(input_tokens=100, cache_creation=0, cache_read=900) + "\n")
        sample = metrics.build_metric_sample("s1", 1, str(transcript), context_window_tokens=1000)
        self.assertEqual(sample["effectiveContextTokens"], 1000)
        self.assertEqual(sample["utilizationPercent"], 100.0)
        self.assertEqual(sample["measurementType"], "actual")
        self.assertEqual(sample["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
