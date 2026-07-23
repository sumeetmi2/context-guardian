"""Rollover decision logic for headless/Agent-SDK wrappers (Phase 3).

Claude Code hooks cannot start a new interactive session on the user's
behalf — there is no supported trigger for that in the CLI (see README
non-goals). A wrapper script driving the Agent SDK directly *can*, and it
has real usage numbers from the SDK response instead of the transcript-size
heuristic hooks are stuck with. This module holds the one piece of decision
logic such a wrapper needs; everything else (handover generation, config
precedence) is the existing library code in `handover.py` / `config.py`.
"""

from . import thresholds


def should_trigger_rollover(utilization_percent, monitoring_config: dict, rollover_config: dict) -> bool:
    if rollover_config.get("mode", "off") == "off":
        return False
    status = thresholds.classify(utilization_percent, monitoring_config)
    return status == thresholds.CRITICAL
