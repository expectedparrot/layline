---
name: plan-team
description: Guide a user from engineers, projects, estimates and constraints to a first Layline baseline plan using the local CLI.
---

# Plan a team with Layline

Use this workflow when the user wants to try Layline with their own team. You are
the conversational interface: ask questions in chat, prepare inputs, run the CLI,
and explain its results. Do not send the user away to author event JSON or run a
demonstration in place of planning their team.

Start with information already in the conversation or supplied files. Ask a small
batch of related questions at a time; do not turn the following stages into a
long questionnaire. Resume at the first missing piece when returning to a task.
`layline guide` describes this workflow; it does not remember completed stages.

## Collect the planning context

1. **Engineers.** Ask who is available, what kinds of work they can do, and what
   fraction of a normal week remains after support, on-call, and other duties.
   Example opening: “Who are the engineers, what kinds of work can each do, and
   roughly how much of their week is available for project work?” Use speed 1 for
   listed skills unless the user supplies another multiplier; disclose this
   modeling default rather than inventing performance differences.
2. **Projects and scope.** Ask for project names, the outcome that counts as done,
   an owner if known, and required skills. Keep scope notes in the intake record
   and give each scope a stable revision. Start with a manageable shortlist if the
   team exceeds the prototype's 6-person or 12-open-project limit; let the user
   choose the subset rather than silently dropping people or projects.
3. **Effort and value.** Ask for person-weeks, separately from elapsed calendar
   weeks. Explain p10/p50/p90 as roughly a 10%, 50%, and 90% chance of finishing
   within that effort. For ongoing work, ask for effort spent and effort remaining.
   Agree on one value-per-week scale across projects, with concrete anchors. If
   using rough points, make that assumption explicit. Do not mix revenue, urgency,
   customer preference and points as interchangeable numbers. Do not fabricate
   ranges or convert an uncertain single guess into an exact point.
4. **Dependencies and existing work.** Ask what must ship before something else
   starts, who is already working on what, and which assignments are commitments
   that replanning should preserve. Distinguish “Dana knows this project” from
   “Dana must remain assigned.” Ask whether deadlines or joint staffing are
   essential: these are unsupported and must be explained before interpreting a
   baseline as a feasible answer.

Unknown estimates may remain absent; Layline uses explicit priors and warns.
Explain their influence and focus follow-up questions on the comparison the user
cares about. This conversational prioritization is not a computed value-of-
information score. Never record your inferred estimate as somebody else's answer.

## Prepare and run

Read `layline docs show inputs` for the supported event fields and a runnable
example. Prepare the event array yourself in a task directory, alongside an
intake JSON recording units, scope descriptions, assumptions, and supplied facts.
These are local planning artifacts written by you; the CLI has no state writer.
Use unique filenames/revisions for later alternatives so the earlier inputs and
outputs remain available. Keep the package's bundled demo unchanged.

Define people and projects before events that reference them. Add observations,
hard dependencies, commitments, and actual work only from supplied information;
use the correct actor and estimator attribution described in the inputs reference.
Actor labels are audit annotations, not authenticated approvals.

Run `layline solve EVENTS_PATH --as-of TIME --scenarios 64 --seed 7`, using an
explicit timezone-aware evaluation time at or after all input events. Capture the
JSON output in the task directory. Check exit status and `ok`; resolve validation
errors before presenting a plan. Do not hide a conflict by changing event order
to make a preferred outcome win.

## Present and iterate

Read `layline docs show results`. Present assignments by name, why leading work
ranks ahead of alternatives, the constraints being preserved, and the consequential
uncertainty. Separate today's recommendation from work already underway. Report
prior use, blocked work, and modeling limits alongside the recommendation.

Ask what is wrong or missing in the inputs or recommendations. Use
`layline skills show review-plan` when comparing a correction or alternative.
Completion means the user has a saved input, an actual CLI result, and a clear
explanation of the first plan and its limitations. A fictional approval or send
event does not establish that a person accepted the plan or received a survey.
