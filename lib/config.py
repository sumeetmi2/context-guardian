"""Configuration loading with precedence: overrides > project > user > defaults.

Matches PRD section 10. Phase 1 has no wrapper/CLI, so "overrides" is an
in-process dict callers (commands) can pass; hooks always use just
project + user + defaults.
"""

import json
import os
from pathlib import Path

DEFAULTS = {
    "enabled": True,
    "monitoring": {
        "warningThresholdPercent": 72,
        "compactThresholdPercent": 84,
        "criticalThresholdPercent": 92,
        "sampleEveryTurns": 1,
    },
    "compaction": {
        "automatic": False,  # Phase 1: never auto-trigger, see PRD critique pt. 2
        "minimumImprovementPoints": 18,
        "minimumPostCompactHeadroomPercent": 25,
        "maximumPerSession": 2,
        "minimumTurnsBetweenAttempts": 5,
    },
    "rollover": {
        "mode": "off",  # Phase 1 has no rollover; see plan Part 2
        "handoverDirectory": ".claude/context-guardian/sessions",
        "startNewSession": False,
        "verifyContinuation": False,
    },
    "handover": {
        "targetTokens": 2500,
        "maximumTokens": 5000,
        "includeGitState": True,
        "includeCommandHistory": True,
        "includeToolHistory": True,
        "redactSecrets": True,
    },
    "privacy": {
        "localOnly": True,
        "retainDays": 30,
        "includePromptText": False,
    },
}

USER_CONFIG_PATH = Path.home() / ".claude" / "context-guardian.json"


def project_config_path(cwd: str) -> Path:
    return Path(cwd) / ".claude" / "context-guardian.json"


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_json_file(path: Path):
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def get_effective_config(cwd: str, overrides: dict = None) -> dict:
    merged = DEFAULTS
    merged = _deep_merge(merged, _load_json_file(USER_CONFIG_PATH))
    merged = _deep_merge(merged, _load_json_file(project_config_path(cwd)))
    if overrides:
        merged = _deep_merge(merged, overrides)
    return merged


def write_project_config(cwd: str, patch: dict) -> dict:
    path = project_config_path(cwd)
    current = _load_json_file(path)
    updated = _deep_merge(current, patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(updated, f, indent=2)
        f.write("\n")
    return updated


def set_enabled(cwd: str, enabled: bool) -> dict:
    return write_project_config(cwd, {"enabled": enabled})
