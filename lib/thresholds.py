"""Threshold classification (FR-5). Phase 1 only classifies/displays —
it never triggers compaction or rollover automatically (PRD critique pt. 2, 8).
"""

NOMINAL = "nominal"
WARNING = "warning"
COMPACT = "compact"
CRITICAL = "critical"


def classify(utilization_percent, monitoring_config: dict) -> str:
    if utilization_percent is None:
        return "unknown"
    if utilization_percent >= monitoring_config["criticalThresholdPercent"]:
        return CRITICAL
    if utilization_percent >= monitoring_config["compactThresholdPercent"]:
        return COMPACT
    if utilization_percent >= monitoring_config["warningThresholdPercent"]:
        return WARNING
    return NOMINAL


def should_notify(status: str, previous_status, turns_since_last_notify: int, monitoring_config: dict) -> bool:
    """Hysteresis (FR-2 phase 2): notify on any status change, or as a
    periodic reminder every `renotifyAfterTurns` turns while sustained in a
    non-nominal status. Prevents nagging every single turn once past
    warning.
    """
    if status != previous_status:
        return True
    if status == NOMINAL:
        return False
    return turns_since_last_notify >= monitoring_config["renotifyAfterTurns"]


def recommended_action(status: str) -> str:
    return {
        NOMINAL: "no action required",
        WARNING: "monitor; consider wrapping up the current sub-task soon",
        COMPACT: "run /compact soon, or /context-guardian:context-handover before starting new work",
        CRITICAL: "run /compact now, or /context-guardian:context-handover immediately",
        "unknown": "utilization unavailable; monitor turn count manually",
    }[status]
