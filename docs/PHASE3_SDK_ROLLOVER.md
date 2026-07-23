# Phase 3: headless/Agent-SDK rollover

Phase 1/2 are visibility + manual checkpointing, driven by Claude Code hooks
(`SessionStart`, `UserPromptSubmit`, `PreCompact`, `Stop`, `SessionEnd`).
Hooks are the only supported integration point in the interactive CLI, and
there is no supported way for a hook to start a new session on your
behalf — so Context Guardian never does that for you there. See the
README's [Non-goals](../README.md#non-goals-phase-1).

A wrapper script driving the Agent SDK directly is a different situation:
it owns the loop, so it *can* start a new session, and — unlike hook
stdin — it has real token usage numbers straight off each API response
instead of the transcript-file-size heuristic `lib/metrics.py` has to fall
back to. Phase 3 is a reference for that integration, not a change to the
hook-based plugin.

## What's provided

- `lib/rollover.py:should_trigger_rollover(utilization_percent, monitoring_config, rollover_config)`
  — the one piece of new decision logic. Pure function, unit-tested in
  `tests/test_rollover.py`. Everything else a wrapper needs is existing
  library code: `lib/handover.py:generate()` and `lib/config.py`.
- `examples/sdk_wrapper_rollover.py` — a runnable reference wrapper. Computes
  utilization from real SDK usage tokens, calls `should_trigger_rollover`,
  and on a trigger calls `handover_mod.generate()` directly (same function
  `/context-guardian:context-handover` calls) to write `HANDOVER.md`.

Try it without an API key or network access:

```bash
python3 examples/sdk_wrapper_rollover.py --dry-run
```

This runs a scripted usage sequence through the same decision path a live
wrapper would use, so you can see a rollover get triggered and a handover
written (or see the validation failure if `nextAction` was never set —
Context Guardian never writes an invalid handover, live or dry-run).

## Config: `rollover.*`

These keys have existed in `lib/config.py`'s `DEFAULTS` since Phase 1 but
had no consumer until now. A wrapper reads them via
`config.get_effective_config(cwd)["rollover"]`:

| Key | Default | Meaning |
|---|---|---|
| `mode` | `"off"` | `"off"` never triggers; `"wrapper"` triggers at `CRITICAL` |
| `handoverDirectory` | `.claude/context-guardian/sessions` | Where handovers are read from |
| `startNewSession` | `false` | If `false`, the wrapper prints a manual continuation command instead of spawning a session itself |
| `verifyContinuation` | `false` | If `true`, a real wrapper should have the new session restate the "Next action" line before treating the old session as ended |

Set project-scoped: `/context-guardian:context-config rollover.mode=wrapper`.

## Wiring in a real client

`examples/sdk_wrapper_rollover.py`'s `_start_new_sdk_session` is a
placeholder — replace it with your actual SDK client call, seeding the new
session's first message with the generated handover markdown. The
usage-extraction and rollover-decision logic above it don't need to change.
