"""Metric collection (FR-1..FR-4).

Claude Code hook stdin itself doesn't expose token/context-utilization
numbers, but the transcript file it points to (`transcript_path`) does:
every assistant turn is logged with the API's real `usage` block
(`input_tokens` + `cache_creation_input_tokens` + `cache_read_input_tokens`
= the actual context size for that call — the same accounting Claude
Code's own `/context` command is built on). We parse that first and label
it `actual`/`high` confidence. Only if a real usage block can't be found
(corrupt line, non-standard transcript, mid-write truncation) do we fall
back to the old file-size heuristic, labeled `estimated`/`low` — a proxy,
never presented as exact.
"""

import json
import os

# Fallback denominator when no real window size is configured (see
# monitoring.contextWindowTokens). Current Claude models commonly ship
# large (500k-1M+) context windows, varying by tier/beta flags — this is a
# rough default, not authoritative for any specific session. Set
# monitoring.contextWindowTokens explicitly (check `/context` in Claude
# Code for the real number) for an accurate percentage.
_CONTEXT_WINDOW_FALLBACK = 1_000_000

_CHARS_PER_TOKEN_ESTIMATE = 4

# How far from the end of the transcript to scan for the last assistant
# usage block, in bytes. One bounded tail read — cheap even for a
# multi-megabyte transcript — instead of parsing the whole file every turn.
_TAIL_SCAN_BYTES = 2_000_000


def _find_last_assistant_usage(transcript_path):
    """Scan the tail of the transcript JSONL for the most recent
    `{"type": "assistant", "message": {"usage": {...}}}` entry. Returns the
    usage dict, or None if none is found within the scanned tail.
    """
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return None
    try:
        with open(transcript_path, "rb") as f:
            read_size = min(_TAIL_SCAN_BYTES, size)
            f.seek(size - read_size)
            chunk = f.read(read_size)
    except OSError:
        return None

    for raw_line in reversed(chunk.split(b"\n")):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if obj.get("type") == "assistant":
            usage = (obj.get("message") or {}).get("usage")
            if usage:
                return usage
    return None


def _total_tokens_from_usage(usage: dict) -> int:
    return (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )


def estimate_effective_tokens(transcript_path, baseline_bytes=0):
    """Real usage from the transcript's last assistant turn when available
    (`measurementType="actual"`, `confidence="high"`); otherwise the
    file-size heuristic (`"estimated"`/`"low"`).

    `baseline_bytes` (transcript size at the last detected compaction) only
    matters for the heuristic fallback — real usage numbers already reflect
    post-compaction context size on their own, since that's what the API
    actually charged for that call.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None, "unavailable", "none"

    usage = _find_last_assistant_usage(transcript_path)
    if usage is not None:
        return _total_tokens_from_usage(usage), "actual", "high"

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
    raw_utilization_percent = None
    if tokens is not None:
        raw_utilization_percent = round((tokens / window) * 100, 1)
        utilization_percent = min(100, raw_utilization_percent)

    return {
        "sessionId": session_id,
        "turn": turn,
        "effectiveContextTokens": tokens,
        "contextWindowTokens": window,
        "utilizationPercent": utilization_percent,
        # Uncapped — >100 signals a misconfigured contextWindowTokens (too
        # small) rather than real over-capacity usage, since the API would
        # reject a request that actually exceeded the window.
        "rawUtilizationPercent": raw_utilization_percent,
        "measurementType": measurement_type,
        "confidence": confidence,
    }
