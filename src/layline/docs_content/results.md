# Reading plans and errors

Planning command results are one JSON object on stdout. `guide`, `skills`, and
`docs` print readable instructions by default; use `--json` to parse their output
programmatically. Errors always return JSON. `--help` is conventional usage text.
On failure, inspect `ok: false`
and `error.code`, `error.message`, and `error.fix`.

Exit codes: 0 success, 1 unexpected failure, 2 usage error, 3 not found, 4 invalid
input/validation/conflict, and 5 approval required. `schema` currently describes
capabilities and required fields; it is not a complete JSON Schema registry.

For `solve`, `data` is the plan. For `demo` and `replay`, inspect each entry in
`data.checkpoints`: a successful replay may contain intentionally conflicting
checkpoints with nonempty `anomalies` and `plan: null`. Never present an earlier
checkpoint's plan as the answer for a later conflicted state.

| Plan field | Meaning |
|---|---|
| `now` | Recommended person-to-project assignments. These do not record work starting. |
| `queue` | Priority order with density, closed set, median remaining effort, median value rate, and supporting observation ids. |
| `forecast` | Probability of shipping within the horizon and unconditional p50/p90 ship times in weeks from `params.as_of`. |
| `warnings`, `tentative` | Prior use, stale evidence excluded, agent-only estimates, and unscheduled work. Explain these to the user. |
| `limitations` | Modeling and solver limits relevant to interpreting the output. |
| `objective`, `objective_se` | Sample mean and Monte Carlo standard error for this fixed baseline policy. Not evidence of optimality or all model uncertainty. |
| `params`, `solver_version`, `inputs_hash` | Reproducibility context. |
| `method` | Approximate prerequisite-bundle ranking and exact immediate assignment matching; `optimal_schedule` is false. |

A null ship percentile means that percentile exceeds the horizon, including
noncompletion. It does not mean zero weeks. Noncompletion can reflect dependencies,
skills, unavailable people, commitments, or the horizon. Inspect inputs before
claiming a particular cause.

In replay, `assignment_changes` compares with the preceding successful plan;
`work`, `commitments`, `accepted`, `questions`, and `responses` distinguish actual
work, constraints, decisions and evidence. Planning warnings are nested under
each checkpoint's plan; top-level warnings do not duplicate all of them.

`guide --json` returns structured `next` actions containing `argv` and `mutates_state`.
Other commands may return an empty `next`. This is discovery guidance, not a
persisted workflow engine or automatic question-selection policy.
