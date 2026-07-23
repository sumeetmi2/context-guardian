# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
