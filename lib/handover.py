"""Handover generation and validation (FR-16..FR-22).

Deterministic extraction from state.json + git state. Narrative fields that
Phase 1 cannot infer automatically (no PreToolUse/PostToolUse tracking yet)
render as "not recorded" rather than being fabricated — see PRD critique
pt. 8 and checkpoint.py's docstring.
"""

import uuid

from . import checkpoint as checkpoint_mod
from . import config as config_mod
from . import redact, store

_CHARS_PER_TOKEN_ESTIMATE = 4


def _bullet_list(items, empty_note="Not recorded in Phase 1."):
    if not items:
        return f"- {empty_note}"
    return "\n".join(f"- {item}" for item in items)


def _fact_tag(item):
    """Render an item that may be a plain string or {"text","status"} dict
    with an FR-18 status tag (confirmed/inferred/user-provided/unverified/superseded).
    """
    if isinstance(item, dict) and "text" in item:
        status = item.get("status", "unverified")
        return f"[{status}] {item['text']}"
    return f"[unverified] {item}"


def build_handover_markdown(cwd: str, session_id: str, parent_session_id, lineage_id, cp: dict) -> str:
    git_state = cp["gitState"]
    identity = "\n".join([
        f"- Handover ID: {lineage_id}",
        f"- Parent session ID: {parent_session_id or session_id}",
        f"- Session lineage ID: {lineage_id}",
        f"- Created time: {cp['timestamp']}",
        f"- Repository: {git_state.get('toplevel') or cwd}",
        f"- Branch: {git_state.get('branch') or 'unknown'}",
        f"- Commit: {git_state.get('head') or 'unknown'}",
        f"- Working directory: {cwd}",
    ])

    git_state_lines = [
        f"- Branch: {git_state.get('branch') or 'unknown'}",
        f"- HEAD: {git_state.get('head') or 'unknown'}",
        f"- Working tree is a git repo: {git_state.get('isRepo')}",
    ]
    if not git_state.get("isRepo"):
        git_state_lines.append(
            "- WARNING: no git repository detected here — branch/diff/changed-file tracking is unavailable for this handover."
        )
    git_state_lines.append("- Status (short):")
    git_state_lines.extend(
        [f"  {line}" for line in git_state.get("statusShort", [])] or ["  (clean)"]
    )
    git_state_section = "\n".join(git_state_lines)

    decisions = _bullet_list([_fact_tag(d) for d in cp.get("decisions", [])])
    constraints = _bullet_list([_fact_tag(c) for c in cp.get("constraints", [])])
    files_inspected = _bullet_list(cp.get("filesInspected", []))
    files_changed = _bullet_list(cp.get("modifiedFiles", []), empty_note="No changed files detected by `git status`.")
    commands = _bullet_list(cp.get("commandsExecuted", []))
    evidence = _bullet_list(cp.get("evidence", []))
    open_questions = _bullet_list(cp.get("pendingQuestions", []))
    risks = _bullet_list(cp.get("risks", []))
    remaining_work = _bullet_list(cp.get("remainingWork", []))
    do_not_repeat = _bullet_list(cp.get("doNotRepeat", []))

    md = f"""# Session Handover

## Identity
{identity}

## Objective
{cp.get('objective') or 'Not recorded in Phase 1 — set with `cg.py checkpoint --set objective="..."`.'}

## Current status
{cp.get('lastCompletedAction') or 'Not recorded.'}
{('Test status: ' + cp.get('testStatus')) if cp.get('testStatus') else ''}

## Decisions made
{decisions}

## Constraints
{constraints}

## Repository context
{cp.get('repositoryContext') or 'Not recorded in Phase 1.'}

## Files inspected
{files_inspected}

## Files changed
{files_changed}

Git diff summary:
```
{cp.get('gitDiffSummary') or '(no diff)'}
```

## Git state
{git_state_section}

## Commands executed
{commands}

## Validation status
{cp.get('testStatus') or 'unknown'}

## Evidence and references
{evidence}

## Open questions
{open_questions}

## Risks and caveats
{risks}

## Remaining work
{remaining_work}

## Next action
{cp.get('nextAction') or cp.get('nextExpectedAction') or 'NOT SET — required before this handover is valid.'}

## User communication state
{cp.get('userCommunicationState') or 'Not recorded in Phase 1.'}

## Do not repeat
{do_not_repeat}
"""
    return md


def build_handover_json(session_id, parent_session_id, lineage_id, cp: dict) -> dict:
    return {
        "handoverId": lineage_id,
        "parentSessionId": parent_session_id or session_id,
        "sessionId": session_id,
        "lineageId": lineage_id,
        "createdAt": cp["timestamp"],
        "objective": cp.get("objective"),
        "nextAction": cp.get("nextAction") or cp.get("nextExpectedAction"),
        "gitState": cp["gitState"],
        "modifiedFiles": cp.get("modifiedFiles", []),
        "testStatus": cp.get("testStatus"),
        "openQuestions": cp.get("pendingQuestions", []),
        "remainingWork": cp.get("remainingWork", []),
    }


def validate(markdown_text: str, handover_json: dict, effective_config: dict):
    """FR-22 checklist. Returns (ok, list_of_reasons)."""
    reasons = []

    required_headers = [
        "## Identity", "## Objective", "## Current status", "## Decisions made",
        "## Constraints", "## Repository context", "## Files inspected",
        "## Files changed", "## Git state", "## Commands executed",
        "## Validation status", "## Evidence and references", "## Open questions",
        "## Risks and caveats", "## Remaining work", "## Next action",
        "## User communication state", "## Do not repeat",
    ]
    for header in required_headers:
        if header not in markdown_text:
            reasons.append(f"missing required section: {header}")

    next_action = handover_json.get("nextAction")
    if not next_action or "NOT SET" in markdown_text.split("## Next action")[-1][:120]:
        reasons.append("next action is empty — set it before handing over")

    if not handover_json.get("sessionId"):
        reasons.append("sessionId missing")
    if not handover_json.get("parentSessionId"):
        reasons.append("parentSessionId missing")

    _clean, secret_count = redact.redact(markdown_text)
    if secret_count > 0:
        reasons.append(f"{secret_count} potential secret(s) detected — redaction required before writing")

    approx_tokens = len(markdown_text) // _CHARS_PER_TOKEN_ESTIMATE
    max_tokens = effective_config["handover"]["maximumTokens"]
    if approx_tokens > max_tokens:
        reasons.append(f"handover ~{approx_tokens} tokens exceeds maximumTokens={max_tokens}")

    return (len(reasons) == 0, reasons)


def generate(cwd: str, session_id: str, transcript_path=None, turn=None):
    effective_config = config_mod.get_effective_config(cwd)
    cp = checkpoint_mod.build_checkpoint(cwd, session_id, transcript_path=transcript_path, turn=turn)

    existing_handover_state = store.read_json(store.handover_state_json_path(cwd, session_id), default={})
    session = store.read_json(store.session_json_path(cwd, session_id), default={})
    # Prefer lineage inherited at session-start time (bin/cg.py:_maybe_link_lineage,
    # a real cross-session link) over a lineage_id previously minted for this same
    # session's own handover calls, over minting a fresh one for a root session.
    lineage_id = (
        session.get("lineageId")
        or existing_handover_state.get("lineageId")
        or f"cg-{uuid.uuid4().hex[:12]}"
    )
    parent_session_id = session.get("parentSessionId") or existing_handover_state.get("parentSessionId")

    markdown = build_handover_markdown(cwd, session_id, parent_session_id, lineage_id, cp)
    redacted_markdown, secret_count = redact.redact(markdown)
    handover_json = build_handover_json(session_id, parent_session_id, lineage_id, cp)

    ok, reasons = validate(redacted_markdown, handover_json, effective_config)

    if ok:
        store.atomic_write_text(store.handover_md_path(cwd, session_id), redacted_markdown)
        store.atomic_write_json(store.handover_state_json_path(cwd, session_id), handover_json)
        store.append_event(
            cwd, session_id, "handover_created",
            lineageId=lineage_id, redactedSecrets=secret_count,
        )
    else:
        store.append_event(
            cwd, session_id, "handover_validation_failed",
            reasons=reasons,
        )

    return {
        "ok": ok,
        "reasons": reasons,
        "redactedSecrets": secret_count,
        "path": str(store.handover_md_path(cwd, session_id)) if ok else None,
        "markdown": redacted_markdown,
    }
