# Replaying example scenarios

Run `layline demo --list` to discover bundled variants, and `layline demo` to
replay the main three-engineer, eight-project story. These are authored examples,
not the user's team or live surveys. For the user's own team, read
`layline skills show plan-team` instead.

The main story recommends platform work for Dana, preserves Priya's exports
commitment, and assigns Lee to onboarding. A delayed effort answer shifts Dana's
recommendation to billing. Acceptance does not start work. A remaining-effort
check-in records an overrun, an explicit pause allows reassignment, and abandonment
does not become a completion-effort actual.

| Variant | What to inspect |
|---|---|
| `duplicate-and-corrected-answer` | Repeated download adds no evidence; a changed accepted answer is held for review. |
| `scope-change` | Old estimates excluded; late answer held; prior use visible. |
| `partial-and-invalid-answer` | Neither incomplete nor malformed estimates enter beliefs; valid completion does. |
| `concurrent-assignment` | Conflicting work starts create an anomaly and block planning. |
| `stale-acceptance` | Changed planning inputs invalidate acceptance of the previous plan. |
| `shipped` | Confirmed shipped effort becomes an actual. |

For example: `layline demo --variant scope-change --scenarios 64 --seed 7`.

`layline replay PATH` accepts an authored scenario object with `schema_version: 1`,
`name`, `initial_events`, and `steps`. Each step has `name`, timezone-aware `as_of`,
and `events`. Optional `variants` map names to alternative step lists, each starting
from the same initial events. Optional `horizon_weeks` defaults to 52.

A step's optional `accept` actor accepts the previous successful checkpoint's
plan after applying that step's events, which permits stale-acceptance testing.
These actor fields test domain semantics, not authentication. When writing new
examples, make their causal event order explicit with timestamps and ids.
