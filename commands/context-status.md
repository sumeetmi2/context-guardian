---
description: Show current Context Guardian session status (context estimate, turns, checkpoints)
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" status` via the Bash tool and print its output to the user verbatim (no extra commentary). If it reports "no session recorded yet," tell the user that means no Context Guardian hook events have fired in this project yet, and that's expected on a brand-new session before the first prompt has been submitted.
