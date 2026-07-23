# Context Guardian

A Claude Code plugin that watches context/token pressure in a session and lets you generate a durable, structured **handover document** before things get cramped — so a fresh session (or a teammate) can pick up exactly where you left off, without you re-explaining everything from scratch.

Phase 1 (this release): **visibility + manual checkpointing.** It observes, estimates, and hands you a ready-to-use continuation doc on request. It does **not** auto-compact or auto-start new sessions for you — see [Non-goals](#non-goals-phase-1) below.

## Why

Long Claude Code sessions eventually hit context limits. `/compact` helps, but compaction is lossy, and there's no built-in way to hand off an in-progress task to a brand-new session without losing the thread — objective, decisions made, what's been tried, what's next. Context Guardian's job is to make that handoff explicit, deterministic, and reviewable, instead of relying on memory or an ad-hoc summary at the worst possible moment (right when context is already tight).

## What it does

- Estimates context usage every turn (transcript-size heuristic — Claude Code doesn't expose exact token counts to hooks, so every number is labeled `estimated`/`low confidence`, never presented as exact).
- Classifies usage against configurable thresholds (`nominal` → `warning` → `compact` → `critical`) and surfaces a recommendation inline.
- Writes a checkpoint automatically right before compaction happens (`PreCompact` hook).
- On request, generates `HANDOVER.md` + `handover_state.json`: objective, decisions (tagged confirmed/inferred/user-provided/unverified), files touched, git state, remaining work, and — critically — a single **next action**, so the next session has an unambiguous starting point.
- Redacts known credential shapes (AWS keys, GitHub/Slack tokens, private key blocks, bearer tokens, etc.) from the handover before it ever touches disk.
- Refuses to write a handover that's missing a next action, over a token budget, or still contains a detected secret — validation failure prints the reason instead of silently producing a broken doc.

## Non-goals (Phase 1)

- **No automatic compaction.** There's no supported way for a hook to trigger `/compact` in an interactive session — Context Guardian tells you to run it, it doesn't run it for you.
- **No automatic rollover.** It never starts a new session on your behalf.
- **No fabrication.** Narrative fields (objective, decisions, plan) are never guessed — they render as "Not recorded in Phase 1" until you (or Claude, acting on your behalf during a session) explicitly set them.
- **No secret-detection guarantee.** Redaction is pattern-based and best-effort against known credential shapes, not a security boundary.

## Install

**Option A — load for one session, no install:**

```bash
git clone https://github.com/sumeetmi2/context-guardian.git
claude --plugin-dir ./context-guardian
```

**Option B — clone anywhere and point at it every time:**

```bash
claude --plugin-dir /path/to/context-guardian
```

There's no marketplace listing yet (Phase 1 is local-only by design). See [`docs/TUTORIAL.md`](docs/TUTORIAL.md) for a full walkthrough including troubleshooting.

## Quick example

```
$ claude --plugin-dir /path/to/context-guardian
> /context-guardian:context-status
Session: 6736435e-6ebb-4f77-a0d4-0d561152cfb3
Context: approximately 3.7% (estimated, low confidence)
Status: nominal — no action required
Turns: 1
Compactions this session: 0
Last checkpoint: none yet — run /context-checkpoint
```

## Commands

Once loaded, commands are namespaced under the plugin name:

| Command | What it does |
|---|---|
| `/context-guardian:context-status` | Show current session's estimated usage, status, turn/compaction counts |
| `/context-guardian:context-checkpoint` | Manually write a checkpoint (objective, decisions, next action, etc.) |
| `/context-guardian:context-handover` | Generate + validate `HANDOVER.md` for continuing in a new session |
| `/context-guardian:context-config` | View or update effective config (`key.path=value`) |
| `/context-guardian:context-disable` | Turn monitoring off/on for this project |

## Configuration

Precedence: CLI overrides > project config (`.claude/context-guardian.json`) > user config (`~/.claude/context-guardian.json`) > defaults.

```jsonc
{
  "monitoring": {
    "warningThresholdPercent": 72,
    "compactThresholdPercent": 84,
    "criticalThresholdPercent": 92
  },
  "handover": {
    "maximumTokens": 5000
  }
}
```

Set project-scoped values with `/context-guardian:context-config monitoring.warningThresholdPercent=60`.

## How it works

Five Claude Code hooks (`SessionStart`, `UserPromptSubmit`, `PreCompact`, `Stop`, `SessionEnd`) call a single Python CLI (`bin/cg.py`) that reads/writes plain JSON under `.claude/context-guardian/` in your project (gitignored by default). No background process, no daemon, no non-stdlib dependencies.

```
lib/
  metrics.py      estimate context usage from transcript size
  thresholds.py   classify usage, recommend an action
  gitstate.py     deterministic git state capture (subprocess, no inference)
  checkpoint.py   pre-compaction / manual checkpoint state
  handover.py     builds + validates HANDOVER.md
  redact.py       pattern-based secret redaction
  config.py       config precedence and merging
  store.py        atomic JSON/event-log persistence
```

## Development

Zero external dependencies — everything runs on the Python 3 standard library.

```bash
python3 -m unittest discover -s tests -t . -v
```

## Roadmap

- **Phase 2:** compaction intelligence (better usage signals, hysteresis).
- **Phase 3:** wrapper-based rollover for headless/Agent-SDK workflows, where structured usage output actually exists.
- **Phase 4:** quality tooling, session lineage history, ecosystem polish.

## License

MIT — see [LICENSE](LICENSE).
