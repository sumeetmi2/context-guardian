"""Pre-compaction / manual checkpoint (FR-8, FR-9).

Phase 1 has no PreToolUse/PostToolUse hooks wired up, so narrative fields
(objective, plan, next action, etc.) cannot be inferred automatically. They
carry forward from the previous checkpoint until explicitly updated via
`cg.py checkpoint --set field=value`, and start as null/[unverified] on the
first checkpoint of a session. This is a known Phase 1 limitation, not a bug.
"""

from . import gitstate, metrics, store

# Fields carried forward from the previous checkpoint until explicitly
# overwritten. Scalars default to None, lists default to [].
_SCALAR_NARRATIVE_FIELDS = [
    "objective",
    "currentPlan",
    "lastCompletedAction",
    "nextExpectedAction",
    "nextAction",
    "repositoryContext",
    "userCommunicationState",
]
_LIST_NARRATIVE_FIELDS = [
    "pendingQuestions",
    "decisions",
    "constraints",
    "filesInspected",
    "commandsExecuted",
    "evidence",
    "risks",
    "remainingWork",
    "doNotRepeat",
]
NARRATIVE_FIELDS = _SCALAR_NARRATIVE_FIELDS + _LIST_NARRATIVE_FIELDS + ["testStatus"]


def build_checkpoint(cwd: str, session_id: str, transcript_path=None, turn=None, overrides=None):
    previous = store.read_json(store.state_json_path(cwd, session_id), default={})
    git_state = gitstate.collect(cwd)
    sample = metrics.build_metric_sample(session_id, turn, transcript_path)

    checkpoint = {
        "sessionId": session_id,
        "timestamp": store._now_iso(),
        "modifiedFiles": gitstate.changed_files(git_state),
        "gitDiffSummary": git_state.get("diffStat"),
        "testStatus": previous.get("testStatus", "unknown"),
        "utilizationEstimate": sample,
        "gitState": git_state,
    }
    for field in _SCALAR_NARRATIVE_FIELDS:
        checkpoint[field] = previous.get(field)
    for field in _LIST_NARRATIVE_FIELDS:
        checkpoint[field] = previous.get(field, [])

    if overrides:
        for key, value in overrides.items():
            if key in NARRATIVE_FIELDS:
                checkpoint[key] = value

    return checkpoint


def write_checkpoint(cwd: str, session_id: str, checkpoint: dict) -> None:
    store.atomic_write_json(store.state_json_path(cwd, session_id), checkpoint)
    store.append_event(
        cwd,
        session_id,
        "checkpoint_created",
        utilizationPercent=checkpoint["utilizationEstimate"]["utilizationPercent"],
        measurementType=checkpoint["utilizationEstimate"]["measurementType"],
    )
