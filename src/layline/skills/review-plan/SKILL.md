---
name: review-plan
description: Explain a Layline plan or compare it with a corrected estimate, changed scope, or alternative commitment using saved planning inputs.
---

# Review a Layline plan

Use this workflow for “why this assignment?”, “what if this estimate changes?”,
or corrections to an existing planning session. Locate the saved event inputs,
the JSON result, and intake assumptions. Reuse supplied context; do not restart
team onboarding when only one input changed.

Read `layline docs show results` before interpreting the plan. Inspect `ok`,
warnings, tentative status, queue evidence, and active commitments. Replays may
succeed while an individual checkpoint has anomalies and no plan.

For a comparison, make a separate input version and run `solve` on both at the
same explicit evaluation time, seed, scenario count, and horizon. The time must be
at or after both sets of events. This isolates the input change from aging and
sampling differences. Preserve both outputs. If comparing snapshots from different
dates is intentional, identify the time change as another difference.

Use `layline docs show inputs` to encode the correction. Retract a mistaken
observation with a reason or add the estimator's newer observation. A scope change
requires a new scope revision; collect new estimates or explicitly show the priors
that replace excluded old estimates. Do not silently relabel old evidence as if it
described the new scope. Review-resolution commands for held survey answers do
not exist yet; do not claim that a held correction was automatically applied.

Explain which assignments changed, which stayed fixed because of work or
commitments, and which evidence changed their priority. The current queue reports
density, closed sets and evidence; there is no `why`, `diff`, or computed question-
selection command. You can compare returned fields, but do not claim causal
attribution or a statistical improvement test that the solver did not perform.

If the user wants an unsupported constraint, such as two simultaneous engineers
or a hard deadline, explain the missing model and preserve the requirement in the
intake record. Do not encode it as an arbitrary value inflation and call it a
guaranteed feasible schedule. Acceptance and work-start remain separate facts;
read-only solving records neither.
