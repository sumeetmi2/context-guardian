"""Metric collection (FR-1..FR-4).

Claude Code hook stdin does not expose exact token/context-utilization
numbers (PRD critique pt. 1/answer to Open Q1). Phase 1 therefore only has
source #5 in FR-2's priority list available: local heuristic estimation
from transcript size. Every value is labeled accordingly — never
represented as exact.
"""

import os

# Fallback denominator when no real window size is configured (see
# monitoring.contextWindowTokens). Current Claude models commonly ship
# large (500k-1M+) context windows, varying by tier/beta flags — this is a
# rough default, not authoritative for any specific session. Set
# monitoring.contextWindowTokens explicitly (check `/context` in Claude
# Code for the real number) for an accurate percentage.
_CONTEXT_WINDOW_FALLBACK = 1_000_000

_CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_effective_tokens(transcript_path, baseline_bytes=0):
    """Heuristic: transcript file size / chars-per-token. measurementType
    is always "estimated" with "low" confidence — this is a proxy, not a
    token count.

    `baseline_bytes` is the transcript size recorded at the last detected
    compaction. Claude Code's transcript JSONL is append-only and does not
    shrink after `/compact`, so without subtracting the baseline, usage
    would appear to keep climbing across a compaction instead of reflecting
    the actually-shrunk live context.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None, "unavailable", "none"
    try:
        size_bytes = os.path.getsize(transcript_path)
    except OSError:
        return None, "unavailable", "none"
    effective_bytes = max(0, size_bytes - baseline_bytes)
    estimated_tokens = effective_bytes // _CHARS_PER_TOKEN_ESTIMATE
    return estimated_tokens, "estimated", "low"


def build_metric_sample(session_id, turn, transcript_path, context_window_tokens=None, baseline_bytes=0):
    tokens, measurement_type, confidence = estimate_effective_tokens(transcript_path, baseline_bytes)
    window = context_window_tokens or _CONTEXT_WINDOW_FALLBACK
    utilization_percent = None
    if tokens is not None:
        utilization_percent = min(100, round((tokens / window) * 100, 1))

    return {
        "sessionId": session_id,
        "turn": turn,
        "effectiveContextTokens": tokens,
        "contextWindowTokens": window,
        "utilizationPercent": utilization_percent,
        "measurementType": measurement_type,
        "confidence": confidence,
    }
