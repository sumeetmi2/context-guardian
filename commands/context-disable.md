---
description: Disable (or re-enable) Context Guardian for this project
argument-hint: "[--enable to turn it back on]"
---

If $ARGUMENTS contains `--enable`, run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" disable --enable` via Bash to re-enable Context Guardian for this project. Otherwise run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" disable` to turn it off. Report the confirmation message it prints. Note for the user: this only affects hook-driven monitoring/checkpointing in this project (`.claude/context-guardian.json`) — it does not delete any existing session state under `.claude/context-guardian/sessions/`.
