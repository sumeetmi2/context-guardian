---
description: View or update Context Guardian's effective configuration for this project
argument-hint: "[dotted.key=value]"
---

If $ARGUMENTS is empty, run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" config` via Bash and show the effective merged configuration (defaults < user config < project config) to the user as-is.

If $ARGUMENTS looks like `dotted.key=value` (e.g. `monitoring.warningThresholdPercent=70`), run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" config --set "$ARGUMENTS"` — this writes the change to the project config at `.claude/context-guardian.json`, not the user config. Confirm to the user what changed and that it's project-scoped.
