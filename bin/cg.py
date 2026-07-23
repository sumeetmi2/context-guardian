#!/usr/bin/env python3
"""Context Guardian CLI. Used both as the Claude Code hook entry point
(`cg.py hook <event>`, reads hook JSON from stdin) and as the backend for
the plugin's slash commands (`cg.py status|checkpoint|handover|config|disable`).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import checkpoint as checkpoint_mod  # noqa: E402
from lib import config as config_mod  # noqa: E402
from lib import gitstate  # noqa: E402
from lib import handover as handover_mod  # noqa: E402
from lib import metrics, store, thresholds  # noqa: E402


def _read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _init_or_touch_session(cwd, session_id, hook_input):
    session_path = store.session_json_path(cwd, session_id)
    session = store.read_json(session_path, default=None)
    if session is None:
        session = {
            "sessionId": session_id,
            "lineageId": None,
            "parentSessionId": None,
            "childSessionId": None,
            "repository": cwd,
            "branch": gitstate.collect(cwd).get("branch"),
            "startedAt": store._now_iso(),
            "endedAt": None,
            "model": hook_input.get("model", "unknown"),
            "metricsSource": "heuristic-estimation",
            "compactionCount": 0,
            "turnCount": 0,
            "status": "active",
            "transcriptBytesAtLastCompaction": 0,
            "lastNotifiedStatus": thresholds.NOMINAL,
            "lastNotifiedTurn": 0,
        }
    store.atomic_write_json(session_path, session)
    store.set_current_session(cwd, session_id)
    return session


def _maybe_link_lineage(cwd, session_id, session, previous_session_id):
    """Link a brand-new session to the prior one iff the prior session
    explicitly ran /context-handover. That's an intentional continuation
    signal from the user, not a fabricated inference — see
    lib/handover.py's lineageId minting.
    """
    previous_handover = store.read_json(store.handover_state_json_path(cwd, previous_session_id), default=None)
    if previous_handover is None:
        return

    session["parentSessionId"] = previous_session_id
    session["lineageId"] = previous_handover.get("lineageId")
    store.atomic_write_json(store.session_json_path(cwd, session_id), session)
    store.append_event(
        cwd, session_id, "lineage_linked",
        parentSessionId=previous_session_id, lineageId=session["lineageId"],
    )

    previous_session_path = store.session_json_path(cwd, previous_session_id)
    previous_session = store.read_json(previous_session_path, default=None)
    if previous_session is not None:
        previous_session["childSessionId"] = session_id
        store.atomic_write_json(previous_session_path, previous_session)
        store.append_event(cwd, previous_session_id, "lineage_linked", childSessionId=session_id)


def cmd_hook_session_start(args):
    hook_input = _read_stdin_json()
    cwd = hook_input.get("cwd") or os.getcwd()
    session_id = hook_input.get("session_id") or "unknown-session"
    source = hook_input.get("source", "startup")

    cfg = config_mod.get_effective_config(cwd)
    if not cfg.get("enabled", True):
        return

    is_new_session = store.read_json(store.session_json_path(cwd, session_id), default=None) is None
    previous_session_id = store.get_current_session(cwd) if is_new_session else None

    session = _init_or_touch_session(cwd, session_id, hook_input)
    store.append_event(cwd, session_id, "session_started", source=source)

    if is_new_session and previous_session_id and previous_session_id != session_id:
        _maybe_link_lineage(cwd, session_id, session, previous_session_id)

    if source == "compact":
        session["compactionCount"] = session.get("compactionCount", 0) + 1
        transcript_path = hook_input.get("transcript_path")
        if transcript_path and os.path.exists(transcript_path):
            try:
                session["transcriptBytesAtLastCompaction"] = os.path.getsize(transcript_path)
            except OSError:
                pass
        store.atomic_write_json(store.session_json_path(cwd, session_id), session)
        store.append_event(cwd, session_id, "compaction_completed", detectedVia="SessionStart:compact")

    print(json.dumps({}))


def cmd_hook_user_prompt_submit(args):
    hook_input = _read_stdin_json()
    cwd = hook_input.get("cwd") or os.getcwd()
    session_id = hook_input.get("session_id") or "unknown-session"

    cfg = config_mod.get_effective_config(cwd)
    if not cfg.get("enabled", True):
        return

    session = _init_or_touch_session(cwd, session_id, hook_input)
    session["turnCount"] = session.get("turnCount", 0) + 1
    store.atomic_write_json(store.session_json_path(cwd, session_id), session)

    sample = metrics.build_metric_sample(
        session_id, session["turnCount"], hook_input.get("transcript_path"),
        baseline_bytes=session.get("transcriptBytesAtLastCompaction", 0),
    )
    store.append_event(cwd, session_id, "metric_sampled", **sample)

    status = thresholds.classify(sample["utilizationPercent"], cfg["monitoring"])
    previous_status = session.get("lastNotifiedStatus", thresholds.NOMINAL)
    turns_since_last_notify = session["turnCount"] - session.get("lastNotifiedTurn", 0)
    output = {}
    if status in (thresholds.WARNING, thresholds.COMPACT, thresholds.CRITICAL) and thresholds.should_notify(
        status, previous_status, turns_since_last_notify, cfg["monitoring"]
    ):
        note = (
            f"Context Guardian: estimated context usage ~{sample['utilizationPercent']}% "
            f"({sample['confidence']} confidence). {thresholds.recommended_action(status)}"
        )
        store.append_event(cwd, session_id, "threshold_crossed", status=status, note=note)
        output = {
            "systemMessage": note,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": note,
            },
        }
        session["lastNotifiedTurn"] = session["turnCount"]
    session["lastNotifiedStatus"] = status
    store.atomic_write_json(store.session_json_path(cwd, session_id), session)
    print(json.dumps(output))


def cmd_hook_pre_compact(args):
    hook_input = _read_stdin_json()
    cwd = hook_input.get("cwd") or os.getcwd()
    session_id = hook_input.get("session_id") or "unknown-session"
    trigger = hook_input.get("trigger", "unknown")

    cfg = config_mod.get_effective_config(cwd)
    if not cfg.get("enabled", True):
        return

    _init_or_touch_session(cwd, session_id, hook_input)
    cp = checkpoint_mod.build_checkpoint(
        cwd, session_id, transcript_path=hook_input.get("transcript_path")
    )
    checkpoint_mod.write_checkpoint(cwd, session_id, cp)
    store.append_event(cwd, session_id, "compaction_requested", trigger=trigger)
    print(json.dumps({}))


def cmd_hook_stop(args):
    hook_input = _read_stdin_json()
    cwd = hook_input.get("cwd") or os.getcwd()
    session_id = hook_input.get("session_id") or "unknown-session"

    cfg = config_mod.get_effective_config(cwd)
    if not cfg.get("enabled", True):
        return

    session = _init_or_touch_session(cwd, session_id, hook_input)
    sample = metrics.build_metric_sample(
        session_id, session.get("turnCount", 0), hook_input.get("transcript_path"),
        baseline_bytes=session.get("transcriptBytesAtLastCompaction", 0),
    )
    status = thresholds.classify(sample["utilizationPercent"], cfg["monitoring"])
    store.append_event(cwd, session_id, "metric_sampled", **sample)
    if status != thresholds.NOMINAL:
        store.append_event(cwd, session_id, "threshold_crossed", status=status, atBoundary="stop")
    # Phase 1: observe and log only. No automatic checkpoint/compaction/rollover here.
    print(json.dumps({}))


def cmd_hook_session_end(args):
    hook_input = _read_stdin_json()
    cwd = hook_input.get("cwd") or os.getcwd()
    session_id = hook_input.get("session_id") or "unknown-session"

    cfg = config_mod.get_effective_config(cwd)
    if not cfg.get("enabled", True):
        return

    session = store.read_json(store.session_json_path(cwd, session_id), default=None)
    if session is not None:
        session["status"] = "ended"
        session["endedAt"] = store._now_iso()
        store.atomic_write_json(store.session_json_path(cwd, session_id), session)
    store.append_event(cwd, session_id, "session_ended", reason=hook_input.get("reason"))
    print(json.dumps({}))


HOOK_DISPATCH = {
    "session-start": cmd_hook_session_start,
    "user-prompt-submit": cmd_hook_user_prompt_submit,
    "pre-compact": cmd_hook_pre_compact,
    "stop": cmd_hook_stop,
    "session-end": cmd_hook_session_end,
}


def cmd_hook(args):
    handler = HOOK_DISPATCH.get(args.event)
    if handler is None:
        print(f"unknown hook event: {args.event}", file=sys.stderr)
        sys.exit(1)
    handler(args)


def cmd_status(args):
    cwd = os.getcwd()
    cfg = config_mod.get_effective_config(cwd)
    session_id = store.get_current_session(cwd)
    if not session_id:
        print("Context Guardian: no session recorded yet in this project.")
        return

    session = store.read_json(store.session_json_path(cwd, session_id), default={})
    events = store.read_events(cwd, session_id)
    last_sample = next((e for e in reversed(events) if e.get("type") == "metric_sampled"), None)

    print(f"Session: {session_id}")
    if last_sample and last_sample.get("utilizationPercent") is not None:
        pct = last_sample["utilizationPercent"]
        status = thresholds.classify(pct, cfg["monitoring"])
        print(f"Context: approximately {pct}% ({last_sample['measurementType']}, {last_sample['confidence']} confidence)")
        print(f"Status: {status} — {thresholds.recommended_action(status)}")
    else:
        print("Context: unavailable (no metric samples recorded yet)")
    print(f"Turns: {session.get('turnCount', 0)}")
    print(f"Compactions this session: {session.get('compactionCount', 0)}")

    checkpoints = [e for e in events if e.get("type") == "checkpoint_created"]
    if checkpoints:
        print(f"Last checkpoint: {checkpoints[-1]['timestamp']}")
    else:
        print("Last checkpoint: none yet — run /context-checkpoint")


def cmd_checkpoint(args):
    cwd = os.getcwd()
    session_id = store.get_current_session(cwd)
    if not session_id:
        print("No active session recorded. A checkpoint needs at least one prior hook event.")
        sys.exit(1)

    overrides = {}
    for item in args.set or []:
        if "=" not in item:
            print(f"ignoring malformed --set value (expected field=value): {item}", file=sys.stderr)
            continue
        key, value = item.split("=", 1)
        try:
            overrides[key] = json.loads(value)
        except json.JSONDecodeError:
            overrides[key] = value

    cp = checkpoint_mod.build_checkpoint(cwd, session_id, overrides=overrides)
    checkpoint_mod.write_checkpoint(cwd, session_id, cp)
    print(f"Checkpoint written: {store.state_json_path(cwd, session_id)}")


def cmd_handover(args):
    cwd = os.getcwd()
    session_id = store.get_current_session(cwd)
    if not session_id:
        print("No active session recorded. A handover needs at least one prior hook event.")
        sys.exit(1)

    result = handover_mod.generate(cwd, session_id)
    if result["ok"]:
        print(f"Handover written: {result['path']}")
        if result["redactedSecrets"]:
            print(f"Redacted {result['redactedSecrets']} potential secret(s) before writing.")
        print()
        print(f'Continue in a new session with:\n  claude "Read @{result["path"]} and continue from the documented next action."')
    else:
        print("Handover validation FAILED — not written:")
        for reason in result["reasons"]:
            print(f"  - {reason}")
        sys.exit(1)


def cmd_lineage(args):
    cwd = os.getcwd()
    session_id = store.get_current_session(cwd)
    if not session_id:
        print("No active session recorded. Lineage needs at least one prior hook event.")
        sys.exit(1)

    chain = store.walk_lineage(cwd, session_id)
    if len(chain) <= 1:
        print(f"Session {session_id} has no recorded lineage — it's a root session (or handovers were never generated).")
        return

    print(f"Lineage for {session_id} ({len(chain)} sessions, oldest first):")
    for entry in chain:
        marker = " <- current" if entry["sessionId"] == session_id else ""
        print(f"  {entry['sessionId']}  started {entry['startedAt']}  status={entry['status']}{marker}")


def cmd_config(args):
    cwd = os.getcwd()
    if args.set:
        if "=" not in args.set:
            print("--set expects field=value (e.g. monitoring.warningThresholdPercent=70)", file=sys.stderr)
            sys.exit(1)
        key, value = args.set.split("=", 1)
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value
        patch = {}
        cursor = patch
        parts = key.split(".")
        for part in parts[:-1]:
            cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = parsed_value
        updated = config_mod.write_project_config(cwd, patch)
        print(json.dumps(updated, indent=2))
        return

    print(json.dumps(config_mod.get_effective_config(cwd), indent=2))


def cmd_disable(args):
    cwd = os.getcwd()
    enabled = args.enable
    config_mod.set_enabled(cwd, enabled)
    print(f"Context Guardian {'enabled' if enabled else 'disabled'} for this project.")


def main():
    parser = argparse.ArgumentParser(prog="cg.py")
    sub = parser.add_subparsers(dest="command", required=True)

    hook_parser = sub.add_parser("hook")
    hook_parser.add_argument("event", choices=list(HOOK_DISPATCH.keys()))
    hook_parser.set_defaults(func=cmd_hook)

    status_parser = sub.add_parser("status")
    status_parser.set_defaults(func=cmd_status)

    checkpoint_parser = sub.add_parser("checkpoint")
    checkpoint_parser.add_argument("--set", action="append", help="field=value, repeatable")
    checkpoint_parser.set_defaults(func=cmd_checkpoint)

    handover_parser = sub.add_parser("handover")
    handover_parser.set_defaults(func=cmd_handover)

    config_parser = sub.add_parser("config")
    config_parser.add_argument("--set", help="dotted.key=value")
    config_parser.set_defaults(func=cmd_config)

    lineage_parser = sub.add_parser("lineage")
    lineage_parser.set_defaults(func=cmd_lineage)

    disable_parser = sub.add_parser("disable")
    disable_parser.add_argument("--enable", action="store_true", default=False)
    disable_parser.set_defaults(func=cmd_disable)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
