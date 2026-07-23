# Configuration

Precedence: CLI overrides > project config (`.claude/context-guardian.json`) > user config (`~/.claude/context-guardian.json`) > defaults.

```jsonc
{
  "monitoring": {
    "warningThresholdPercent": 72,
    "compactThresholdPercent": 84,
    "criticalThresholdPercent": 92,
    "sampleEveryTurns": 1,
    "renotifyAfterTurns": 8,
    "contextWindowTokens": null
  },
  "compaction": {
    "automatic": false,
    "minimumImprovementPoints": 18,
    "minimumPostCompactHeadroomPercent": 25,
    "maximumPerSession": 2,
    "minimumTurnsBetweenAttempts": 5
  },
  "rollover": {
    "mode": "off",
    "handoverDirectory": ".claude/context-guardian/sessions",
    "startNewSession": false,
    "verifyContinuation": false
  },
  "handover": {
    "targetTokens": 2500,
    "maximumTokens": 5000,
    "includeGitState": true,
    "includeCommandHistory": true,
    "includeToolHistory": true,
    "redactSecrets": true
  },
  "privacy": {
    "localOnly": true,
    "retainDays": 30,
    "includePromptText": false
  },
  "security": {
    "redactBeforeStateWrite": true,
    "persistCommands": true,
    "persistEvidence": true
  }
}
```

Set project-scoped values with `/context-guardian:context-config monitoring.warningThresholdPercent=60`, or view the full effective config (defaults + user + project merged) with `/context-guardian:context-config`.

## Field notes

**`monitoring`**
- `warningThresholdPercent` / `compactThresholdPercent` / `criticalThresholdPercent` — usage percentage boundaries for the `nominal → warning → compact → critical` classification.
- `renotifyAfterTurns` — notification hysteresis: once past `warning`, you're renotified on any status change, or every N turns as a periodic reminder — not every single turn.
- `contextWindowTokens` — the denominator for the usage percentage. `null` (default) falls back to a rough constant in `lib/metrics.py`, since Claude Code's hook payload doesn't expose the real context window size. Set it explicitly to match your actual window (check `/context` in Claude Code) for an accurate percentage.

**`compaction`** — read by the plugin but not acted on automatically in Phase 1 (`automatic` is always effectively `false` for the interactive CLI); reserved for a future auto-compaction mode.

**`rollover`** — read by the Phase 3 Agent-SDK wrapper reference (`examples/sdk_wrapper_rollover.py`), not by the hooks. See [`PHASE3_SDK_ROLLOVER.md`](PHASE3_SDK_ROLLOVER.md).

**`handover`** — `maximumTokens` is the hard cap `cg.py handover` validates against (using a `chars / 4` approximation, not a real tokenizer); a handover exceeding it fails validation and is not written.

**`security`**
- `redactBeforeStateWrite` (default `true`) — applies the same pattern-based redaction used on the rendered handover markdown to every narrative field the moment it's written to `state.json`/`handover_state.json`, not just the final document.
- `persistCommands` / `persistEvidence` (default `true`) — let you exclude `commandsExecuted`/`evidence` from disk entirely for stricter setups.
- None of this makes redaction a security boundary — it's pattern-based and best-effort against known credential shapes. See the README's Limitations section.

**`privacy`** — currently informational; `localOnly`/`retainDays`/`includePromptText` are not yet enforced by any cleanup or scrubbing logic.
