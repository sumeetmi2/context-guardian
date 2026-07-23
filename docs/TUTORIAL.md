# Tutorial: using Context Guardian

This walks through loading the plugin and using it in a real Claude Code session, end to end.

## 1. Load the plugin

Clone the repo, then start Claude Code pointed at it:

```bash
git clone https://github.com/sumeetmi2/context-guardian.git
cd context-guardian
claude --plugin-dir .
```

`--plugin-dir` loads the plugin for that session only — no marketplace or global install needed. You can point it at the repo from any other project directory too:

```bash
cd ~/my-real-project   # must be a git repo for full functionality — see Troubleshooting
claude --plugin-dir /path/to/context-guardian
```

Note: `--plugin-dir` only controls where the plugin code is *loaded from*. Your project's state and git status are read from wherever you actually run `claude` — your terminal's current directory.

## 2. Confirm it's running

Send any prompt. In the background, the `SessionStart` and `UserPromptSubmit` hooks have already fired and written to `.claude/context-guardian/` in your project. Check status:

```
/context-guardian:context-status
```

You'll see something like:

```
Session: 6736435e-6ebb-4f77-a0d4-0d561152cfb3
Context: approximately 3.7% (estimated, low confidence)
Status: nominal — no action required
Turns: 1
Compactions this session: 0
Last checkpoint: none yet — run /context-checkpoint
```

The percentage is a heuristic (transcript size ÷ estimated context window), not an exact token count — Claude Code doesn't expose that to hooks today. It's always labeled with its measurement type and confidence so you know how much to trust it.

## 3. Work normally

Nothing changes about how you use Claude Code. As your session grows, `Context Guardian` keeps sampling usage on every prompt. Once you cross the `warning` threshold (72% by default), it injects a short note into context telling you so.

## 4. Write a checkpoint

Before you plan to compact, or any time you want a durable snapshot, ask Claude to record one:

```
/context-guardian:context-checkpoint
```

The command instructs Claude to fill in what it actually knows — objective, decisions made, files touched, next action — from the real conversation, never fabricated. Fields you don't set carry forward from the previous checkpoint.

A `PreCompact` hook also writes a checkpoint automatically right before any compaction (manual `/compact` or automatic), so you always have a fallback snapshot even if you forget to check-point manually.

## 5. Generate a handover

When you're ready to hand off to a fresh session (context is tight, or you're stopping for the day):

```
/context-guardian:context-handover
```

This produces `.claude/context-guardian/sessions/<session-id>/HANDOVER.md`, validated against a checklist (all required sections present, a next action is set, no detected secrets, under the token budget). If validation fails, it tells you exactly why instead of writing a broken doc — most commonly, a missing next action.

On success it prints a ready-to-run continuation command:

```
claude "Read @/path/to/HANDOVER.md and continue from the documented next action."
```

Run that in a new terminal/session to pick up exactly where you left off.

## 6. Configure thresholds

```
/context-guardian:context-config
```

with no arguments shows the effective merged config. To change a value for this project only:

```
/context-guardian:context-config monitoring.warningThresholdPercent=60
```

This writes to `.claude/context-guardian.json` in your project (not the global user config).

## 7. Disable/enable

```
/context-guardian:context-disable
/context-guardian:context-disable --enable
```

Turns hook-driven monitoring off/on for this project. Existing session state under `.claude/context-guardian/sessions/` is untouched either way.

## Troubleshooting

**"Unknown command: /context-status"** — commands are namespaced by plugin name. Use `/context-guardian:context-status`, not the bare form.

**Handover used to fail outside a git repo** — as of the current version it no longer does; it writes the handover with a visible warning that file-change tracking is unavailable, instead of hard-failing.

**Testing via a non-interactive shell (`!` in Claude Code, CI, etc.)** — `claude` detects the missing TTY and falls back to `--print` mode, which requires a prompt argument (`claude --plugin-dir . -p "..."`) — you can't drive the real interactive TUI that way. Open an actual terminal app for a true interactive test.

**No metric on the very first `UserPromptSubmit`** — the transcript file for the current turn may not exist yet at that point in the hook lifecycle; the estimate becomes available on the next sample (e.g. at `Stop`). This is expected, not a bug.
