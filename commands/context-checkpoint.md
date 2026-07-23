---
description: Write a durable checkpoint of current objective/plan/status without compacting or ending the session
argument-hint: "[optional notes about what to record]"
---

Write a Context Guardian checkpoint for the current session.

1. Based on the conversation so far (and any notes in $ARGUMENTS), determine concise values for: the current objective, the current plan, the last completed action, the next expected action, and test status (pass/fail/unknown). Keep each to one or two sentences.
2. Run via the Bash tool:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/cg.py" checkpoint \
     --set objective="<objective>" \
     --set currentPlan="<plan>" \
     --set lastCompletedAction="<last completed action>" \
     --set nextExpectedAction="<next expected action>" \
     --set testStatus="<test status>"
   ```
   Only include `--set` flags for fields you actually have a confident value for — omitted fields carry forward from the previous checkpoint unchanged.
3. Report the path it printed and a one-line summary of what was recorded. Do not fabricate values you're not confident about — leave them out rather than guessing.
