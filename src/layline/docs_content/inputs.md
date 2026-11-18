# Preparing planning inputs

`layline solve PATH --as-of TIME` reads a JSON array of events. The calling agent
prepares this local file from the user's information. The CLI does not write an
event repository. Keep an intake JSON alongside it for scope descriptions, the
shared value unit, assumptions, and facts that the prototype cannot model.

Every event needs `v: 1`, unique `id`, timezone-aware `ts`, `actor`, `type`,
`subject`, and a `data` object. Replay sorts by timestamp and then id. Define
referenced objects before using them. Choose explicit ordered ids for events
recorded at the same time; do not change their order to suppress a real conflict.
Use actual recording time and retain the original source time in intake notes.

## Runnable small input

This is an illustrative example in which Dana supplied the estimates. Replace
it with the user's real inputs; do not copy the example as evidence about their
team. Save the JSON array as `events.json`, then run:

```bash
layline solve events.json --as-of 2026-11-20T18:00:00Z --scenarios 64 --seed 7
```

```json
[
  {"v":1,"id":"001","ts":"2026-11-20T12:00:00Z","actor":"agent:planner","type":"person.defined","subject":"dana","data":{"name":"Dana","skills":{"backend":1},"availability":0.8}},
  {"v":1,"id":"002","ts":"2026-11-20T12:00:00Z","actor":"agent:planner","type":"project.defined","subject":"billing","data":{"name":"Billing","kind":"feature","skills":["backend"],"owner":"dana","scope_revision":"billing:v1"}},
  {"v":1,"id":"003","ts":"2026-11-20T12:00:00Z","actor":"human:dana","type":"observation.recorded","subject":"effort:billing","data":{"project":"billing","quantity":"effort","by":"dana","source":"human","scope_revision":"billing:v1","estimate":{"p10":1,"p50":2,"p90":4}}},
  {"v":1,"id":"004","ts":"2026-11-20T12:00:00Z","actor":"human:dana","type":"observation.recorded","subject":"value_rate:billing","data":{"project":"billing","quantity":"value_rate","by":"dana","source":"human","scope_revision":"billing:v1","estimate":{"p10":2,"p50":4,"p90":8}}}
]
```

## Supported input building blocks

| Event | Subject | Data |
|---|---|---|
| `person.defined` | person id | `name`, `skills` mapping skill to positive speed, `availability` from 0 to 1; optional `internal` defaults true. |
| `person.availability_changed` | existing person | `availability`. |
| `project.defined` | project id | `name`, `skills` list, optional `owner`, explicit `scope_revision`; only kind `feature` is supported. |
| `project.scope_changed` | existing project | `reason`, optional `name`; this event's id becomes the new scope revision. |
| `observation.recorded` | `effort:ID` or `value_rate:ID` | `project`, `quantity`, `by`, `source`, `scope_revision`, `estimate`. |
| `observation.retracted` | observation event id | `reason`. |
| `edge.added` | descriptive edge id | `src`, `dst`, `type: "hard"`; requires a human actor annotation. |
| `commitment.set` | person id | `project`, `reason`; requires a human actor annotation. |
| `commitment.released` | person id | `reason`; requires a human actor annotation. |
| `work.started` / `work.resumed` | project id | `person`; person must be free and eligible, and hard prerequisites shipped. |
| `work.paused` | active project | `reason`. |
| `work.checkin` | active/paused project | `spent`, `remaining` estimate, current `scope_revision`; actor is the assigned person. |
| `work.closed` | project id | `outcome` (`shipped`, `abandoned`, `descoped`), `actual_effort`; human actor must match owner if set. |

An estimate is `{"p10": 1, "p50": 2, "p90": 4}` with
`0 < p10 <= p50 <= p90`, or an explicitly deterministic `{"point": 2}`.
Do not supply both. Effort for open work must be positive. Value may be a point
zero for a prerequisite; pooling zero with positive value estimates is not yet
supported. Missing estimates get priors. All value rates must share a unit and
time basis; value-unit metadata belongs in the intake record for now.

For human observations, `by` is a defined person and `actor` must be
`human:<that-person>`. Attribute a user's estimate to its actual speaker, not
automatically the project owner. A non-engineering estimator can be defined with
availability 0; there is no fixed roster-size cap. Agent-inferred
estimates use `source: "agent"`, `by: "agent:planner"`, and
`actor: "agent:planner"`; they receive lower weight. Never invent a person's
answer or confirmation to satisfy validation. An actor annotation is not an
authenticated approval.

For ongoing work, record `work.started` and then a `work.checkin` with measured
person-effort spent and remaining quantiles. The planner preserves the shifted
remaining distribution. Calendar time is not a measurement of effort. Future
recommendations need no `work.started` event. Commitments preserve assignments
across solves; they do not state that work has begun.

For correcting inputs, preserve the previous file and prepare a new version.
Most person/project field amendments, edge removal, and review resolution are not
implemented. Where no transition exists, produce a separate corrected input
snapshot and describe it as a revised planning input, not an append-only history.
Do not invent unsupported events. Existing shipped prerequisites can be recorded
with an owner-confirmed closure and actual effort; do not fabricate closure to
make a dependent project ready.

The supplied scenario demo additionally illustrates question/answer and
plan-acceptance transitions. For ordinary first-plan onboarding, direct
observations are sufficient; no survey publication or delivery event is needed.
