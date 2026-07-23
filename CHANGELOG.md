# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
