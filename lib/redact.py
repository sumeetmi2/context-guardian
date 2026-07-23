"""Pattern-based secret redaction (PRD 13.2 / FR-13).

Best-effort only: catches known credential *shapes*, not arbitrary secrets.
Never claim complete coverage — see PRD critique point 6.
"""

import re

REPLACEMENT = "[REDACTED: potential secret]"

_PATTERNS = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_key", re.compile(r"(?i)\baws_secret_access_key\s*[:=]\s*\S+")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key_block", re.compile(
        r"-----BEGIN[ A-Z]*PRIVATE KEY-----[\s\S]*?-----END[ A-Z]*PRIVATE KEY-----"
    )),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-_.]{16,}\b")),
    ("generic_authorization_header", re.compile(r"(?i)\bauthorization\s*:\s*\S+")),
    ("connection_string", re.compile(
        r"(?i)\b\w+://[^\s:@/]+:[^\s:@/]+@[^\s/]+"
    )),
    ("keyish_assignment", re.compile(
        r"(?i)\b([A-Za-z0-9_]*(?:api[_-]?key|secret|token|password|passwd)[A-Za-z0-9_]*)\s*[:=]\s*['\"]?[A-Za-z0-9\-_./+=]{8,}['\"]?"
    )),
]


def redact(text: str):
    """Returns (clean_text, redaction_count). Never returns the raw matches."""
    if not text:
        return text, 0
    count = 0
    clean = text
    for _name, pattern in _PATTERNS:
        clean, n = pattern.subn(REPLACEMENT, clean)
        count += n
    return clean, count


def redact_value(value):
    """Recursively apply `redact` to every string inside a JSON-shaped
    value (dict/list/str), leaving other types untouched. Used to sanitize
    narrative fields at every persistence boundary (state.json,
    handover_state.json), not just the final rendered handover markdown —
    a checkpoint field can hold a secret even if it never makes it into a
    generated handover.
    """
    if isinstance(value, str):
        clean, _count = redact(value)
        return clean
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    return value
