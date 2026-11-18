# Prototype limits and EDSL integration

The local planner supports at most 12 open projects and 6 people, one person per
project, constant availability, hard dependencies, and feature projects. It ranks
closed sets using median effort/value and performs exact small-instance assignment
matching before simulating a fixed priority policy. This is not a guarantee of an
optimal discounted schedule. It preserves active work and explicit commitments;
there is no automatic preemption.

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
