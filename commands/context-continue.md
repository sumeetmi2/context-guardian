---
description: Explicitly link this session as a continuation of a prior handover
argument-hint: "<handoverId or lineageId>"
---

Link the current session to a prior handover as its continuation.

1. If `$ARGUMENTS` is empty, ask the user for the handover ID (or lineage ID) printed by the `/context-guardian:context-handover` run they're continuing from — do not guess one.
2. Run via the Bash tool:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" continue $ARGUMENTS
   ```
3. Report its output verbatim. If it fails because no matching handover was found, tell the user to double-check the ID against the handover's "Handover ID" line, or run `/context-guardian:context-lineage` to see recorded sessions.

Use this when a session wasn't auto-linked at startup (usually because it started more than 30 minutes after the handover was generated, or in a different terminal/session than the one the auto-link marker was tied to).
