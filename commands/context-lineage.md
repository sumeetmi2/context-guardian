---
description: Show the chain of sessions this one was continued from, if any
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" lineage` via the Bash tool and print its output to the user verbatim (no extra commentary). If it reports the session is a root session with no recorded lineage, tell the user that's expected unless a previous session generated a handover via `/context-guardian:context-handover` and this session was started to continue it.
