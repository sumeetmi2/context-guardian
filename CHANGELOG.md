# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.4.0

### Changed — distinct handover identity fields (breaking `handover_state.json` schema)
- `lib/handover.py`: `handoverId` used to be minted once and reused as
  `lineageId` for an entire chain, so every handover in the same lineage
  reported the same `handoverId` — wrong, since one lineage can contain many
  handovers. `parentSessionId` also fell back to the session's own ID for
  root sessions, reading as "this session is its own parent."
  Now four distinct fields: `handoverId` (fresh per `generate()` call),
  `lineageId` (stable across the chain, unchanged behavior),
  `sourceSessionId` (replaces `sessionId`/`parentSessionId`'s self-fallback —
  the session that generated this handover), and `parentHandoverId` (the
  specific prior handover this session's lineage continued from, `none` for
  a root session — did not exist before). `HANDOVER.md`'s Identity section
  and `handover_state.json` both reflect the new fields.
- `bin/cg.py`: `session.json` gains `parentHandoverId`; `cg.py continue`
  resolves and links all four IDs from the target handover.
- README rewritten: tighter opener, a "Typical workflow" walkthrough, an
  automatic-vs-user-triggered table, explicit prerequisites, a post-install
  verification step, a richer sample handover, and clearer, separated
  usage-measurement explanation. Deep configuration and architecture detail
  moved to new `docs/CONFIGURATION.md` and `docs/ARCHITECTURE.md`.
- Fixed remaining shorthand command references (`/context-checkpoint`,
  `/context-handover`) in `bin/cg.py` and `lib/thresholds.py` output text to
  use the full `/context-guardian:context-*` names Claude Code actually
  registers.

## 0.3.0

### Fixed — lineage no longer auto-links unrelated sessions
- `bin/cg.py`/`lib/store.py`: `SessionStart` used to link a new session to
  the most recent prior session in the repo purely because that prior
  session had generated a handover at some point — even an unrelated one.
  Auto-linking now requires a single-use `pending_continuation.json` marker
  (30-minute TTL) written by `handover`, naming the exact session it
  continues. Added `cg.py continue <handoverId>` /
  `/context-guardian:context-continue` as an explicit fallback for later or
  cross-terminal resumes.

### Changed — checkpoint inference covers the full narrative schema
- `commands/context-checkpoint.md` now prompts for all 17 narrative fields
  (previously 5) so mid-session checkpoints carry as much as a handover
  does. `PreCompact`'s auto-checkpoint now warns when it captured git state
  only, with no objective/next action set.

### Added — defense-in-depth redaction, security config, CI
- `lib/redact.py`: `redact_value` recursively redacts narrative fields at
  every persistence boundary (`state.json`, `handover_state.json`), not
  just the final rendered handover markdown.
- New `security` config section: `redactBeforeStateWrite` (default on),
  `persistCommands`/`persistEvidence` (exclude from disk entirely).
- `lib/metrics.py`: `rawUtilizationPercent` (uncapped) alongside the capped
  `utilizationPercent`, surfaced by `cg.py status` as a misconfiguration
  warning when `contextWindowTokens` is set too small.
- `UserPromptSubmit` notifications now use `systemMessage` only — dropped
  the duplicate `hookSpecificOutput.additionalContext` injection, which
  repeated the same text into model context on every notified turn.
- `session.json.metricsSource` is now set from the first real sample
  instead of a hardcoded, often-wrong default.
- GitHub Actions CI (`.github/workflows/ci.yml`): tests across Python
  3.9–3.13 on Ubuntu/macOS/Windows, `ruff check`, advisory `mypy`.

## 0.2.1

### Fixed — real usage numbers instead of a byte-size guess
- `lib/metrics.py`: the numerator was a pure file-size heuristic
  (`transcript_bytes // 4`), always labeled `estimated`/`low confidence`.
  Every assistant turn in the transcript actually carries the API's real
  `usage` block (`input_tokens` + `cache_creation_input_tokens` +
  `cache_read_input_tokens`) — the same accounting Claude Code's own
  `/context` is built on. Now parsed from the transcript's most recent
  assistant turn and labeled `actual`/`high confidence`; the byte-size
  heuristic is kept only as a fallback if a real usage record can't be
  found. Fixes reports of the plugin showing ~100% utilization on a session
  where `/context` reported ~15%.
- The notification message in `bin/cg.py` no longer hardcodes the word
  "estimated" — it now reflects the sample's real `measurementType`.
- Since real usage numbers already reflect post-compaction context size on
  their own (the API only counts current context), the Phase 2 baseline
  tracking now only matters for the heuristic fallback path.

## 0.2.0

### Added — Phase 2: usage signals + hysteresis
- `lib/metrics.py`: usage estimate is now epoch-aware — subtracts the
  transcript size recorded at the last detected compaction instead of using
  raw transcript file size, since the transcript JSONL is append-only and
  doesn't shrink after `/compact`.
- `lib/thresholds.py:should_notify` — status notifications now fire on any
  status change, or at most every `monitoring.renotifyAfterTurns` turns
  (default 8) while sustained in a non-nominal status, instead of every
  single turn.
- Fixed: the usage percentage's denominator was hardcoded to 200,000 tokens
  (Sonnet-3-era), badly underestimating the window for current 500k-1M+
  models and inflating the reported percentage (e.g. showing ~100% when
  Claude Code's own `/context` reported ~15%). Bumped the fallback to
  1,000,000 and added `monitoring.contextWindowTokens` so it can be set
  accurately per environment instead of guessed.

### Added — Phase 3: headless/Agent-SDK rollover reference
- `lib/rollover.py:should_trigger_rollover` — pure decision function for a
  wrapper driving the Agent SDK directly, gated on the previously-unused
  `rollover.*` config keys.
- `examples/sdk_wrapper_rollover.py` — runnable reference wrapper
  (`--dry-run` exercises it without network/API key).
- `docs/PHASE3_SDK_ROLLOVER.md`.

### Added — Phase 4: session lineage history
- New sessions now link to the prior session's lineage at `SessionStart`
  when the prior session explicitly generated a handover — populating the
  previously-dead `lineageId`/`parentSessionId`/`childSessionId` fields on
  `session.json`.
- `lib/store.py:walk_lineage` and new `/context-guardian:context-lineage`
  command to show the chain.
- `lib/handover.py:generate` now inherits a linked lineage instead of always
  minting a fresh one per session.

## 0.1.1
- Surface threshold warnings directly to the user via `systemMessage`.

## 0.1.0
- Initial Phase 1 release: visibility + manual checkpointing.
