---
description: Generate and validate a full session handover (HANDOVER.md + JSON) without ending the session
argument-hint: "[optional notes to fold into the handover]"
---

Generate a Context Guardian handover for the current session so a future session (or teammate) can continue the work without re-deriving it.

1. Review the conversation so far and any notes in $ARGUMENTS. Assemble, where you have real information (never fabricate — omit rather than guess):
   - `objective`, `currentPlan`, `lastCompletedAction`, `nextExpectedAction`, `testStatus` — plain strings.
   - `nextAction` — one concrete, specific next step (required — the handover will fail validation without it).
   - `decisions`, `constraints`, `filesInspected`, `commandsExecuted`, `evidence`, `pendingQuestions`, `risks`, `remainingWork`, `doNotRepeat` — JSON arrays of short strings (or `{"text": "...", "status": "confirmed|inferred|user-provided|unverified|superseded"}` objects for `decisions`/`constraints` to tag confidence per the PRD's fact-vs-assumption requirement).
2. Write these with the Bash tool, one `--set` per field, JSON-encoding array/object values, e.g.:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" checkpoint \
     --set nextAction="Run the failing integration test and inspect the fixture" \
     --set remainingWork='["Fix duplicate-event fixture", "Re-run integration test"]' \
     --set decisions='[{"text": "Retries handled via Resilience4j, not custom code", "status": "confirmed"}]'
   ```
3. Then run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" handover
   ```
4. If it reports validation failures, fix the underlying gap (most commonly a missing `nextAction`) and retry — do not tell the user it succeeded if it didn't.
5. On success, show the user the printed path and the ready-to-run continuation command it prints. Do not print the full HANDOVER.md contents unless asked — the path is enough.
