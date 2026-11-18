# Prototype limits and EDSL integration

The local planner has no fixed people or project cap. Include the whole backlog
in one plan. It supports one person per project, constant availability, hard
dependencies, and feature projects.

Ranking is approximate: start with each project and its unfinished prerequisites,
greedily add other prerequisite bundles when the combined value-to-effort ratio
improves, choose the best grown bundle, and repeat on the remaining projects.
Shared prerequisites can therefore benefit several projects without enumerating
all possible subsets. This deterministic local search can miss a better grouping;
there is no maximum-density or optimal-schedule guarantee. It uses median effort
and value, then simulates the resulting fixed priority policy.

Assignments use polynomial-time maximum-weight matching, accounting for skills,
availability and the priorities. This optimizes the immediate assignment score,
not the full discounted schedule. Active work and explicit commitments are
preserved; there is no automatic preemption. Plans expose the algorithms in
`method` and describe their qualifications in `limitations`.

Runtime still grows with backlog, roster and scenario count. To get a quicker
forecast, lower `--scenarios` (for example to 16); all projects still participate.
The old six-person/twelve-project restrictions no longer apply. Reducing scenarios
reduces Monte Carlo precision, not the number of projects considered.

Priors and agent-only evidence can make recommendations tentative. Calibration,
negative-value and mixed zero/positive beliefs, either-or dependencies, probes,
enablers, time-varying availability, deadlines, and joint staffing remain design
work. A speed multiplier of 1 is a neutral input default, not a performance rating.

Operator guidance is bundled with the installed CLI. The calling agent conducts
the conversation and writes planning input/output artifacts. The CLI remains
non-interactive and read-only. There is no automatic durable state writer, git
sync, authenticated approval integration, or stateful `next` command. The agent
must not invent `init`, `ask`, `why`, `diff`, or other target-spec commands.

There is no live EDSL survey adapter yet. No EDSL account, key, or model execution
is needed for first-plan onboarding. Question/send/answer events in the example
replay are fixture inputs, not evidence of real delivery or response collection.

For a future adapter, EDSL separates survey publication from invitation delivery.
Response start-time filters do not establish a completion cursor: someone may
open a survey Monday and complete it Friday. Response retrieval may return
`Results` or a fallback `ScenarioList`, which must be normalized and validated.
Git claims alone do not guarantee exactly-once delivery after a crash. Provider
idempotency and reconciliation need their own verified contract. Keep private
contact mappings and bearer respondent URLs out of committed event data.
