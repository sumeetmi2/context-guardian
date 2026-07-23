---
description: Write a durable checkpoint of current objective/plan/status without compacting or ending the session
argument-hint: "[optional notes about what to record]"
---

Write a Context Guardian checkpoint for the current session.

1. Based on the conversation so far (and any notes in $ARGUMENTS), determine concise values for whichever of these you have real information for — never fabricate, omit rather than guess:
   - `objective`, `currentPlan`, `lastCompletedAction`, `nextExpectedAction`, `nextAction`, `testStatus`, `repositoryContext`, `userCommunicationState` — plain strings, one or two sentences each.
   - `decisions`, `constraints`, `filesInspected`, `commandsExecuted`, `evidence`, `pendingQuestions`, `risks`, `remainingWork`, `doNotRepeat` — JSON arrays of short strings (or `{"text": "...", "status": "confirmed|inferred|user-provided|unverified|superseded"}` objects for `decisions`/`constraints` to tag confidence).
2. Run via the Bash tool, one `--set` per field you have a value for, JSON-encoding array/object values:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" checkpoint \
     --set objective="<objective>" \
     --set currentPlan="<plan>" \
     --set lastCompletedAction="<last completed action>" \
     --set nextExpectedAction="<next expected action>" \
     --set testStatus="<test status>" \
     --set filesInspected='["path/to/file.py"]' \
     --set remainingWork='["Next step still open"]'
   ```
   Only include `--set` flags for fields you actually have a confident value for — omitted fields carry forward from the previous checkpoint unchanged. Skip a field entirely if nothing has changed since the last checkpoint rather than restating identical content.
3. Report the path it printed and a one-line summary of what was recorded. Do not fabricate values you're not confident about — leave them out rather than guessing.
