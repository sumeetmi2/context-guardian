#!/usr/bin/env python3
"""Reference wrapper: Agent-SDK-driven rollover (Phase 3).

Demonstrates the piece Claude Code hooks cannot do themselves: reading real
usage numbers from an SDK response, deciding when to hand off, generating
the handover with the existing library code, and — if configured — starting
a fresh session seeded with it.

This is a reference implementation, not a supported CLI. Adapt the model
call to whichever SDK client you're actually driving; the rollover decision
and handover generation below are the reusable parts (`lib.rollover`,
`lib.handover`), and they don't depend on which client you used.

Run with --dry-run to exercise the full decision + handover-generation path
against a scripted usage sequence, without hitting the network or requiring
an API key:

    python3 examples/sdk_wrapper_rollover.py --dry-run
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import config as config_mod  # noqa: E402
from lib import handover as handover_mod  # noqa: E402
from lib import rollover  # noqa: E402
from lib import store  # noqa: E402

CONTEXT_WINDOW_TOKENS = 200_000


def utilization_percent_from_usage(usage: dict, context_window_tokens: int = CONTEXT_WINDOW_TOKENS):
    """Real usage, straight off the SDK response — no file-size heuristic.

    `usage` is expected to look like an Anthropic Messages API usage block:
    {"input_tokens": ..., "output_tokens": ..., "cache_creation_input_tokens": ...,
     "cache_read_input_tokens": ...}. Adjust field names for whichever SDK you use.
    """
    total = (
        usage.get("input_tokens", 0)
        + usage.get("output_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    return min(100.0, round((total / context_window_tokens) * 100, 1))


def maybe_roll_over(cwd: str, session_id: str, usage: dict):
    """Call after every turn. Returns the handover path if a rollover was
    triggered and generated, else None.
    """
    cfg = config_mod.get_effective_config(cwd)
    utilization = utilization_percent_from_usage(usage)

    if not rollover.should_trigger_rollover(utilization, cfg["monitoring"], cfg["rollover"]):
        return None

    result = handover_mod.generate(cwd, session_id)
    if not result["ok"]:
        print(f"rollover triggered but handover validation failed: {result['reasons']}", file=sys.stderr)
        return None

    print(f"Rollover triggered at ~{utilization}% utilization. Handover written: {result['path']}")

    if not cfg["rollover"].get("startNewSession"):
        print(f'Continue manually with:\n  claude "Read @{result["path"]} and continue from the documented next action."')
        return result["path"]

    new_session_id = _start_new_sdk_session(cwd, result["path"], verify=cfg["rollover"].get("verifyContinuation"))
    print(f"New session started: {new_session_id}")
    return result["path"]


def _start_new_sdk_session(cwd: str, handover_path: str, verify: bool):
    """Placeholder for spawning a fresh SDK session seeded with the handover.

    Wire this to your actual SDK client (e.g. anthropic.Anthropic().messages.create
    with the handover markdown as the first user message). If `verify` is set,
    have the new session restate the "Next action" line before treating the
    old session as ended — a cheap sanity check that continuation worked.
    """
    with open(handover_path) as f:
        handover_markdown = f.read()
    # real implementation: client.messages.create(..., messages=[{"role": "user",
    #   "content": f"Read this handover and continue:\n\n{handover_markdown}"}])
    del handover_markdown  # placeholder — not sent anywhere in this reference script
    return "new-session-placeholder"


def _dry_run():
    """Exercise the decision + handover path with scripted usage, no network."""
    cwd = os.getcwd()
    session_id = store.get_current_session(cwd) or "dry-run-session"
    config_mod.write_project_config(cwd, {"rollover": {"mode": "wrapper", "startNewSession": False}})

    for turn, usage in enumerate([
        {"input_tokens": 5_000, "output_tokens": 500},
        {"input_tokens": 90_000, "output_tokens": 5_000},
        {"input_tokens": 185_000, "output_tokens": 5_000},
    ], start=1):
        pct = utilization_percent_from_usage(usage)
        print(f"turn {turn}: ~{pct}% utilization")
        maybe_roll_over(cwd, session_id, usage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="scripted usage sequence, no network/API key")
    args = parser.parse_args()

    if args.dry_run:
        _dry_run()
        return

    print("Live mode needs a real SDK client wired into _start_new_sdk_session — see module docstring.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
