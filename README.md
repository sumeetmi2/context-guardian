# Context Guardian

[![CI](https://github.com/sumeetmi2/context-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/sumeetmi2/context-guardian/actions/workflows/ci.yml)

Context Guardian is a Claude Code plugin that watches context/token pressure during a session and produces a validated, structured handover — objective, decisions, files touched, and one concrete next action — so a fresh session or a teammate can continue the work instead of losing it to compaction or a rushed summary.

## Typical workflow

1. **Work normally.** Hooks watch usage in the background — nothing to run per turn.
2. **Checkpoint** (`/context-guardian:context-checkpoint`) as things develop — records objective, decisions, and next action so far. Optional, but makes step 3 faster and more complete.
3. **Handover** (`/context-guardian:context-handover`) assembles everything into a validated `HANDOVER.md`. Missing a next action or a required section fails validation — nothing gets written until it's fixed.
4. **Continue** in a fresh session: tell Claude to read the handover. Starting within 30 minutes auto-links the new session to the old one; otherwise link explicitly with `/context-guardian:context-continue <handoverId>`.

## What gets captured

Objective, decisions (tagged confirmed/inferred/user-provided/unverified/superseded), files changed, commands run, validation status, risks, remaining work, and a required next action.

## Automatic vs. user-triggered

| | Trigger |
|---|---|
| Usage monitoring + threshold notifications | Automatic, every turn (`/context-guardian:context-status` to check anytime) |
| Pre-compaction git-state checkpoint | Automatic, right before compaction |
| Narrative checkpoint (objective, decisions, next action) | `/context-guardian:context-checkpoint` |
| Handover generation + validation | `/context-guardian:context-handover` |
| Lineage link on session start | Automatic, but short-lived (30 min), single-use, and repo-scoped — see [Limitations](#limitations) |
| Explicit lineage link | `/context-guardian:context-continue <handoverId>` — the safe choice when starting an unrelated parallel task in the same repo |

## Prerequisites

- Claude Code with plugin support
- Python 3.9+ (standard library only — nothing to install)
- Git (most features assume a git repository; the plugin degrades gracefully without one)

## Install from the repository marketplace

```bash
claude plugin marketplace add sumeetmi2/context-guardian
claude plugin install context-guardian@context-guardian
```

The first command registers this repository as a plugin source; the second installs the plugin from that source into every Claude Code session, in any directory.

**Verify it's working:**

```
/context-guardian:context-status
```

```
Session: 6736435e-6ebb-4f77-a0d4-0d561152cfb3
Context: approximately 3.7% (actual, high confidence)
Status: nominal — no action required
Turns: 1
Compactions this session: 0
Last checkpoint: none yet — run /context-guardian:context-checkpoint
```

**No-install option** (one session only): `git clone https://github.com/sumeetmi2/context-guardian.git && claude --plugin-dir ./context-guardian`.

## Terminal demo

```
$ claude
> ...working for a while...
Context Guardian: actual context usage ~86% (high confidence). run /compact now, or /context-guardian:context-handover immediately

> /context-guardian:context-checkpoint
Checkpoint written: .claude/context-guardian/sessions/6736435e.../state.json

> /context-guardian:context-handover
Handover written: .claude/context-guardian/sessions/6736435e.../HANDOVER.md

Continue in a new session with:
  claude "Read @.../HANDOVER.md and continue from the documented next action."

$ claude "Read @.../HANDOVER.md and continue from the documented next action."
> /context-guardian:context-status
Session: 9a1f2c3e-...  (auto-linked, same lineage)
Context: approximately 2.1% (actual, high confidence)
Status: nominal — no action required
```

## Sample handover

```markdown
## Identity
- Handover ID: cg-4c0b764f7d0f
- Source session ID: 6736435e-6ebb-4f77-a0d4-0d561152cfb3
- Lineage ID: cg-07509a743d42
- Parent handover ID: none
- Created time: 2026-07-23T14:49:35+00:00
- Repository: /path/to/repo
- Branch: main
- Commit: a1b2c3d

## Objective
Migrate the billing webhook consumer from the deprecated v1 event format to v2 without changing retry, idempotency, or failure-handling semantics.

## Current status
v2 parser and event mapping are implemented. Focused unit tests pass; the integration test still fails because its fixture sends a v1 payload.
Test status: 18 passed, 1 failed

## Decisions made
- [confirmed] Retry handling stays in Resilience4j, not custom retry code in the handler.
- [unverified] The staging webhook simulator supports the v2 signature header format.

## Files changed
- src/billing/webhook_handler.py
- src/billing/webhook_mapper.py
- tests/fixtures/webhooks/payment_succeeded_v2.json

## Validation status
18 unit tests passed. 1 integration test failed: `test_billing_webhooks.py::test_payment_succeeded` — the fixture still sends the v1 payload shape, so the v2 parser never sees a valid input.

## Risks and caveats
Do not remove the v1 feature flag until staging has processed real v2 events successfully.

## Remaining work
1. Update the integration fixture to send the v2 payload and signature headers.
2. Re-run the full billing test suite.

## Next action
Update `tests/integration/test_billing_webhooks.py` to load the v2 fixture and headers, then run `pytest tests/integration/test_billing_webhooks.py -x`.

## Do not repeat
Do not add retry handling to `webhook_handler.py` — retry behavior is already centrally configured via Resilience4j.
```

Trimmed for length — a real handover also includes Constraints, Repository context, Files inspected, Git state, Commands executed, Evidence and references, Open questions, and User communication state. Full schema in `lib/handover.py`.

## How context is measured

Three things determine the reported percentage, kept separate on purpose:

- **Used-token source** — real per-turn API usage from the transcript when available (`actual`, high confidence — the same accounting Claude Code's own `/context` uses); a byte-size heuristic (`estimated`, low confidence) only if that record can't be found.
- **Context-window denominator** — `monitoring.contextWindowTokens`, set explicitly to your real window (check `/context`) or a rough built-in constant if unset.
- **Confidence label** — `high` or `low`, always shown next to the percentage.

The percentage is only as accurate as its denominator and source — treat it as a signal for when to checkpoint or hand over, not an exact reading.

## Commands

| Command | What it does |
|---|---|
| `/context-guardian:context-status` | Show current session's usage, status, turn/compaction counts |
| `/context-guardian:context-checkpoint` | Write a checkpoint (objective, decisions, next action, etc.) |
| `/context-guardian:context-handover` | Generate + validate `HANDOVER.md` for continuing in a new session |
| `/context-guardian:context-lineage` | Show the chain of sessions this one was continued from |
| `/context-guardian:context-continue` | Explicitly link this session as a continuation of a prior handover |
| `/context-guardian:context-config` | View or update effective config (`key.path=value`) |
| `/context-guardian:context-disable` | Turn monitoring off/on for this project |

## Limitations

- **No automatic `/compact`.** No supported way for a hook to trigger it in an interactive session — Context Guardian tells you to run it.
- **No automatic rollover in the interactive CLI.** A headless/Agent-SDK wrapper can start a new session on your behalf; hooks can't. See [`docs/PHASE3_SDK_ROLLOVER.md`](docs/PHASE3_SDK_ROLLOVER.md).
- **No fabrication.** Narrative fields render as "not recorded" until explicitly set — never guessed.
- **Usage-source fallback.** Falls back to a size heuristic when real per-turn usage isn't available; always labeled so you know which one you're looking at.
- **Redaction is best-effort**, pattern-based against known credential shapes — not a security boundary.
- **Lineage auto-link is short-lived, single-use, and repo-scoped**, not "any prior handover in this repo." Starting an unrelated task right after a handover in the same repo won't accidentally link to it; starting the *intended* continuation more than 30 minutes later needs `/context-guardian:context-continue`.

## Documentation

[Tutorial](docs/TUTORIAL.md) · [Configuration reference](docs/CONFIGURATION.md) · [Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md) · [SDK rollover reference](docs/PHASE3_SDK_ROLLOVER.md)

## Features

Real transcript-usage tracking, notification hysteresis, pre-compaction checkpointing, validated handovers with secret redaction, session lineage with explicit continuation, a headless/Agent-SDK rollover reference, and CI (tests + lint + type-check) are all shipped — see the [Changelog](CHANGELOG.md).

## Roadmap

- Pluggable metric providers — a native context-percentage source, if/once the hook payload exposes one, alongside today's transcript-usage and size-heuristic sources.

## Contributing

Issues and PRs welcome at [github.com/sumeetmi2/context-guardian](https://github.com/sumeetmi2/context-guardian). Run `python3 -m unittest discover -s tests -t . -v` (and `ruff check .`) before submitting — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#development).

## License

MIT — see [LICENSE](LICENSE).
