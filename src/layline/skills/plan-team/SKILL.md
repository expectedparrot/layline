---
name: plan-team
description: Research company context and engineer experience, then guide a user through projects, estimates and constraints to a first Layline baseline plan using the local CLI.
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

## Build company context and draft engineer profiles

Read `layline docs show context`. First try to discover accessible company repos:
list or search the company's remote organization/group through available GitHub,
GitLab or other repository connectors, or an existing authenticated hosting CLI.
Include accessible private repos and public company repos. Do this even without
local checkouts or configured Git remotes; read remote files and history directly
when supported. Also inspect relevant local checkouts. Verify relevant
repository access with a small read; a configured remote or login alone is not
proof of access. Use the company/team identified in the conversation or workspace
to scope discovery. If that identity is ambiguous or discovery leaves gaps, ask
only for the missing context. Do not start by asking the user to list repos or
describe every engineer when accessible sources can supply a draft.

Use discovered repositories and product or strategy docs to build team knowledge.
Inspect contributor history, representative changes, ownership files and
architecture docs to learn what people have worked on. Include review and issue
history when available. Learn the product, customers, current goals and priorities
so project outcomes and the shared value scale have a meaningful basis.

Draft engineer profiles with areas of experience, concrete examples, source links
or paths and dates, confidence, and open questions. Distinguish authors from
committers and resolve aliases, bots and uncertain identity matches with the user.
Treat experience as evidence for candidate skills, not proof of current ownership,
availability, speed or commitment. Commit counts and lines changed are not
productivity measures; missing activity is not evidence of missing ability.

Present a short context summary and draft profiles for correction before using
inferred skills to constrain assignments. Ask only about consequential gaps,
including current team membership, work outside Git, availability and priorities.
If repositories or docs are unavailable, continue from the user's account. Keep
the richer profiles and provenance in intake notes; the current planner accepts
skill multipliers and availability, not a profile or company-context schema.

## Collect the planning context

1. **Engineers.** Confirm the draft roster and skills. Ask who is available and what
   fraction of a normal week remains after support, on-call, and other duties.
   Example follow-up: “Dana appears to have worked on billing and backend APIs.
   Is that still a good fit, and how much of Dana's week is available?” Use speed 1 for
   listed skills unless the user supplies another multiplier; disclose this
   modeling default rather than inventing performance differences.
2. **Projects and scope.** Ask for project names, the outcome that counts as done,
   an owner if known, and required skills. Keep scope notes in the intake record
   and give each scope a stable revision. Include the whole roster and backlog:
   there is no fixed people/project cap. The planner uses approximate prerequisite-
   bundle ranking and efficient assignment matching. Do not split a backlog just
   to work around the former six-person/twelve-project limits. If turnaround
   matters, reduce `--scenarios` (for example to 16); this reduces forecast sampling
   precision without excluding projects or changing the ranking heuristic.
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
intake JSON recording company context, engineer profiles, source references,
units, scope descriptions, assumptions, and supplied facts.
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
