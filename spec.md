# layline: specification

Status: draft v0.3, 2026-11-18

Implementation status: an offline scenario-replay prototype now exercises the
planning and evidence rules. Bundled `guide`, `skills list/show`, and
`docs list/show/search` commands support agent-led onboarding of a real team into
local planning inputs. It does not yet write a state repository, send
surveys, authenticate approvals, or implement the complete CLI below. Section 18
records the design decisions from scenario testing and the first executable
acceptance cases; its refinements take precedence over earlier draft details.

`layline` is a Python library and command-line tool that decides what each engineer should work on next. It treats projects as bets with uncertain value and uncertain effort, keeps its estimates current by asking people targeted questions through a survey platform, and re-plans whenever something finishes, overruns, or new information arrives. The CLI is designed to be operated by an agent, with humans approving the actions that matter. All state lives in a shared git repository as append-only text files: nothing is edited in place, and there is no database.

`layline` is a working name. It is used for the package, the import name, and the command throughout; changing it is a find-and-replace.

## Contents

1. Goals and non-goals
2. Concepts
3. Architecture
4. Data model
5. Beliefs and calibration
6. Solver
7. Dependencies
8. Questions and the survey adapter
9. Links and provider adapters
10. CLI
11. Agent operation
12. Configuration
13. Git workflow
14. Package layout
15. Testing
16. Milestones
17. Open questions
18. Scenario-driven implementation design

---

## 1. Goals and non-goals

### Goals

- Recommend, at any moment, an assignment of people to projects and a ranked queue behind it, chosen to maximize expected long-term value.
- Represent uncertainty in effort and value explicitly, and improve it over time by comparing estimates with outcomes.
- Ask people questions only when the answer could change a decision, and within a per-person attention budget.
- Explain every recommendation: why a project ranks where it does, and what changed since the last plan.
- Be safe and convenient for an agent to operate: machine-readable, idempotent, non-interactive, with approval gates.
- Keep all state in a shared git repository as append-only text files, so that history, review, merging and access control come from git. No binary files in the repository.

### Non-goals

- Issue tracking. GitHub, Linear and similar remain the systems of record for tasks; `layline` links to them.
- Task-level scheduling. The unit is a project of roughly days to months, not a ticket.
- A fixed calendar schedule. The output is a policy and a forecast, not a Gantt chart.
- Survey delivery. The survey platform sends questions and collects answers; `layline` specifies and ingests them.
- A web interface.

---

## 2. Concepts

| Term | Meaning |
|---|---|
| Project | A unit of work with uncertain effort and uncertain value. Kinds: `feature`, `probe`, `enabler`. |
| Probe | A project whose main output is information: finishing it narrows the uncertainty on other projects. |
| Enabler | A project that raises the team's velocity once shipped. |
| Edge | A typed dependency between two projects. |
| Quantity | One uncertain number the solver needs, such as the effort of a project. |
| Observation | An immutable record of what one source said about one quantity at one time. |
| Belief | The pooled, calibrated distribution for a quantity, derived from its observations. |
| Question | A request to a person for one or more observations, with a recorded justification. |
| Closure (record) | The event that ends a project: shipped, abandoned, or descoped, with actual effort. |
| Closed set | A set of projects that contains every unfinished prerequisite of its members. Used for ranking. |
| Policy | A rule that maps the current state to assignments. The solver searches over policies. |
| Plan | A snapshot of the policy's output: current assignments, queue, forecast, sensitivity. |
| Link | A pointer from a project (or other record) to an external artifact such as a PR or a doc. |
| Event | One immutable line in the log. Every change to state is an event. |
| Fold | The pure function that computes current state from the full set of events. |

The central modelling choice: estimates are never stored as fields on a project. They are observations, and the numbers the solver uses are beliefs derived from them. This is what lets several people estimate the same thing, lets estimates be corrected for each person's track record, and lets every plan be traced back to its inputs.

---

## 3. Architecture

```
            +-------------------+        +------------------+
            |  Survey platform  |        | GitHub, Docs ... |
            +---------^---------+        +---------^--------+
                      | SurveyAdapter              | ProviderAdapter
+---------+   +-------+----------------------------+--------+
|  Agent  +-->|                    CLI                      |
+---------+   +----+---------+-----------+-----------+------+
                   |         |           |           |
              +----v---+ +---v----+ +----v----+ +----v----+
              |  Log   | | Beliefs| | Solver  | | Planner |
              | append | | pool + | | sim +   | | next,   |
              | + fold | | calib. | | search  | | diff    |
              +---+----+ +--------+ +---------+ +---------+
                  |
          +-------v--------+
          | git repository |
          |  (text files)  |
          +----------------+
```

- **Log** appends events to JSON Lines files and folds them into current state. It is the only component that writes to the repository. There is no database.
- **Beliefs** turns observations into distributions.
- **Solver** is pure: it takes projects, people, edges, beliefs and parameters, and returns a plan. It does not touch the repository.
- **Planner** compares plans, generates questions from sensitivity results, and produces the agent's action list.
- **Adapters** isolate the survey platform and link providers behind small interfaces.

The library is usable without the CLI or a repository: `layline.solve(...)` on in-memory objects must work for tests and notebooks.

---

## 4. Data model

All durable state is an append-only log of events, stored as JSON Lines text files in a git repository. No line is ever edited or deleted, and the repository contains no binary files. Current state (projects, people, edges, beliefs, open questions) is computed by folding the log.

### Repository layout

```
layline.toml                      # configuration (the one ordinary, edited file)
events/
  2026-11/
    human-dana.k3f9.jsonl         # one file per writer per month
    agent-planner.x7q2.jsonl
plans/
  01JD4M....json                  # plan snapshots that a decision refers to
.gitignore                        # ignores .layline/
.layline/                         # local only, never committed: clone id, draft plans, adapter outbox
```

A writer is an actor on one clone. The file name is `<actor>.<clone_id>.jsonl`, where `clone_id` is four random characters generated on first use and kept in `.layline/`. Each clone therefore appends only to files that no other clone touches, so merges never conflict on event files, whatever the host's merge behaviour. Files are split by month to keep them small. The directory and file names carry no meaning to the fold, which reads every `*.jsonl` under `events/`.

### Event envelope

One JSON object per line:

```json
{"id": "01JD4K7Q2M8X0V5T3W9R6ZB1NC",
 "v": 1,
 "ts": "2026-11-18T16:12:03Z",
 "actor": "human:dana",
 "type": "observation.recorded",
 "subject": "effort:sso-login",
 "prev": null,
 "idem": "9f2c41d0",
 "data": {"source": "human", "person": "dana", "p10": 2, "p50": 4, "p90": 9,
          "rationale": "Similar to the SAML work last spring."}}
```

(Shown wrapped for reading; on disk each event is a single line.)

| Field | Meaning |
|---|---|
| `id` | ULID, unique across all writers |
| `v` | Schema version of this event type |
| `ts` | Writer's clock, ISO-8601 UTC |
| `actor` | `human:<person_id>`, `agent:<name>`, or `system` |
| `type` | Event type, below |
| `subject` | The id of the thing the event is about |
| `prev` | For amendments and state changes: the id of the latest event on this subject that the writer had seen |
| `idem` | Optional idempotency key |
| `data` | Type-specific payload |

### Event types

| Type | Subject | Payload |
|---|---|---|
| `project.defined` | project id | name, kind, skills, owner, notes |
| `project.amended` | project id | only the fields being changed |
| `person.defined`, `person.amended` | person id | name, internal, assignable, availability, questions_per_week, skills |
| `edge.added`, `edge.removed` | `src>dst:type` | param, group |
| `observation.recorded` | quantity id | source, person, p10/p50/p90 or point, rationale, question |
| `observation.retracted` | observation event id | reason |
| `comparison.recorded` | question id | person, winner, loser, strength |
| `question.proposed` | question id | kind, quantities, person, prompt, answer schema, voi, flips, dedup_key, expires_at |
| `question.approved`, `.claimed`, `.sent`, `.answered`, `.answer_rejected`, `.expired`, `.withdrawn` | question id | external_ref, answer, or reason as relevant |
| `work.started`, `.paused`, `.resumed`, `.checkin`, `.closed`, `.signal` | project id | person; check-in and closure payloads |
| `link.added`, `link.removed` | link id | target subject, url, provider, kind, role, external_id, title |
| `link.state_changed` | link id | state, title |
| `plan.accepted`, `plan.overridden` | plan id | inputs_hash, override assignments, reason |

Field values and allowed kinds:

- Project `kind`: `feature`, `probe`, `enabler`.
- Edge `type`: `hard`, `soft`, `either_or`, `complement`, `informs` (section 7).
- Observation `source`: `survey`, `human`, `agent`, `actual`, `metric`, `derived`.
- Question `kind`: `three_point`, `pairwise`, `checkin`, `dependency`, `closure`, `retro_value` (section 8).
- Link `provider`: `github`, `linear`, `gdocs`, `figma`, `slack`, `other`. Link `kind`: `pr`, `issue`, `doc`, `design`, `dashboard`, `thread`, `other`. Link `role`: `spec`, `implementation`, `tracking`, `evidence`, `discussion`.

Quantities are not events. They exist implicitly: every project has `effort:<id>` and `value_rate:<id>`; probes also have `p_success:<id>`; enablers also have `speedup:<id>`; people have `speed:<id>/<skill>`. Effort and value rate are lognormal; probabilities are points.

Person contact details are deliberately not in the log. The survey adapter resolves a person id to an address from its own directory, so addresses can be changed or erased without rewriting history.

### The fold

`state = fold(events)` is a pure function with these properties:

- **Order-independent input.** Events are sorted by `(ts, id)` before folding. The result does not depend on which files they came from or the order the files are read.
- **Total.** The fold never fails. An event that cannot be applied is skipped and reported as an anomaly.
- **Last writer wins, per field.** An amendment sets only the fields it names. For each field, the latest event in `(ts, id)` order wins.
- **Forks are detected.** Two events on the same subject with the same `prev` were written concurrently. The fold still resolves them by order, and reports the fork so a person can confirm the outcome.
- **Removal is an event.** `edge.removed`, `link.removed` and `observation.retracted` hide earlier events; the earlier events remain in the log.
- **Idempotency.** Among events sharing an `idem` key, only the earliest counts.
- **Question deduplication.** Among open `question.proposed` events sharing a `dedup_key`, only the earliest counts; the others fold to `withdrawn`.
- **Invariants are checked at fold time.** A write-time check cannot see events on other clones, so two valid branches can merge into an invalid whole. If the `hard` and `either_or` edges contain a cycle after a merge, the latest edge that closes the cycle is ignored and reported. An event that refers to an unknown project or person is held as an anomaly until the definition appears.
- **Versioned.** Old events are never rewritten. Each event type has upcasters from older `v` values, applied on read.

Anomalies (skipped events, forks, ignored edges, dangling references) are listed by `layline doctor` and included as warnings in command output.

Ordering relies on writers' clocks. Skew between machines can misorder near-simultaneous events; `prev` makes that visible as a fork instead of a silent overwrite.

### Derived state

The fold produces these in-memory collections; the rest of the system reads only these.

| Collection | Key | Built from |
|---|---|---|
| Projects | project id | `project.*`, with `status` derived from the latest `work.*` event |
| People | person id | `person.*` |
| Edges | src, dst, type | `edge.*` |
| Observations | event id | `observation.*`, minus retracted |
| Comparisons | event id | `comparison.recorded` |
| Questions | question id | `question.*`, with `status` as the latest lifecycle event |
| Work history | project id | `work.*`, including effort spent per person from start, pause and resume intervals |
| Links | link id | `link.*` |
| Decisions | plan id | `plan.accepted`, `plan.overridden` |

Project status values: `proposed`, `ready`, `in_progress`, `paused`, `shipped`, `abandoned`, `descoped`, `blocked`.

### Closure payload

A `work.closed` event carries:

```json
{"outcome": "shipped", "actual_effort_weeks": 6.5, "confirmed_by": "human:dana"}
```

For a shipped project with unchanged scope, the same command appends an
`observation.recorded` event with source `actual` on `effort:<id>`. For abandonment,
actual effort is effort spent, not effort to completion: it must not become a
completion-effort observation or an ordinary calibration target. Descoping also
needs a scope-specific outcome before it can be used for calibration. Realized
value arrives later as a measurement on `value_rate:<id>`; its observation window,
uncertainty and attribution must be recorded rather than automatically treating
every retrospective opinion as an exact point.

### Plans

`solve` is deterministic given the event set, configuration, explicit evaluation
time (`as_of`), solver version, seed, and deterministic work budget. These all
participate in `inputs_hash`. A wall-clock cutoff may interrupt a solve but cannot
define a reproducible search result. Draft plans are written to `.layline/plans/`
and are not committed. When a plan is accepted or overridden, its snapshot is
written once to `plans/<plan_id>.json` and committed with the decision event.
Snapshot files are never modified. Acceptance is a decision, not evidence that
work started; `work.started` records that separately.

A snapshot contains: `id`, `ts`, `inputs_hash`, `solver_version`, `seed`, `params`, `now`, `queue`, `forecast`, `sensitivity`, `objective`, `objective_se`, `baseline_objective`.

### What is not in the log

| Item | Where it lives | Why |
|---|---|---|
| Configuration | `layline.toml`, edited normally | Git already records its history; it is part of `inputs_hash` |
| Draft plans | `.layline/plans/`, not committed | Reproducible; committing each would add noise |
| Link sync timestamps, reachability | `.layline/`, not committed | They change on every sync without carrying information |
| Contact details | Survey adapter's directory | Must be erasable |

---

## 5. Beliefs and calibration

A belief is computed from the log on every run, never entered and never stored.

### From three points to a distribution

For `lognormal` quantities (effort, value rate):

```
mu    = ln(p50)
sigma = ln(p90 / p10) / 2.5631        # 2 x 1.2816, the z-score of the 90th percentile
```

Inputs must satisfy `0 < p10 <= p50 <= p90`. The raw three points are kept; the fit is recomputed on read.

### Pooling

For one quantity:

1. If an `actual` observation exists, the belief is that point. Stop.
2. Keep each person's most recent observation; older ones from the same person are superseded.
3. Correct each observation for its author's calibration (below).
4. Weight each observation by `source_weight x recency_weight`. Recency decays with a configurable half-life. Agent-sourced observations get a lower source weight.
5. Combine in log space:

```
mu_pool     = weighted mean of mu_i
sigma_pool^2 = weighted mean of sigma_i^2  +  weighted variance of mu_i
```

The second term widens the belief when people disagree, which in turn raises the value of asking a further question.

A quantity with no observations gets a wide prior from config, by project kind. `layline next` flags these.

### Calibration

For each person and quantity kind, over projects that have an actual:

- **Bias** `b = median( ln(actual / p50) )`. Positive means they underestimate.
- **Spread factor** `s`, chosen so that the stated 10 to 90 range would have contained the actual 80% of the time.

Both are shrunk toward the team-wide figures with a prior worth `k` observations (default 5), so a new person starts at the team average. The corrected observation is `mu + b`, `sigma x s`.

`layline calibrate` reports these per person. The report is for improving estimates; it should not be used to rank people.

### In-progress projects

A `checkin` preserves cumulative person-effort spent, the three-point estimate of
remaining person-effort, its scope revision and measurement time. Total effort is
the shifted distribution `spent + remaining`, not a new lognormal fitted to
shifted percentiles. Elapsed calendar time is not an actual effort measurement.
Without a recent check-in, remaining effort is the total-effort belief conditioned
on exceeding measured effort spent. If a deterministic effort estimate has already
been exhausted, the system requests a check-in instead of inventing a remainder.

### Pairwise comparisons

`comparison` rows are fitted with a Bradley-Terry model to give each project a relative value score. The scale is anchored by projects that also have absolute `value_rate` observations (at least two are needed). The fit produces `derived` observations on `value_rate`.

---

## 6. Solver

### Objective

Default, `discounted_value`:

```
J = E[ sum over shipped projects j of  v_j x (exp(-rho x C_j) - exp(-rho x H)) / rho ]
```

where `v_j` is the value rate, `C_j` the ship time, `H` the horizon and `rho` the discount rate, plus complement bonuses that accrue from the time both ends of a `complement` edge have shipped. Abandoned projects earn nothing.

Alternative, `log_growth`: value rates are read as fractional uplifts to a growth rate, and the objective is the expected log of the end-of-horizon metric. This penalizes plans in which one failed bet dominates. Implemented after the default.

### Simulator

Discrete-event Monte Carlo. One scenario:

1. Sample a true total effort and true value rate for every open project from its belief. Sample success for probes.
2. Advance time from event to event. Events: a project completes; a project hits its timebox; a person becomes available.
3. A person burns effort on their project at `availability x speed`, where `speed` is the lowest of their multipliers for the project's required skills, times the product of `speedup` for all shipped enablers.
4. At each event, call the policy to decide assignments.
5. When a probe completes, the policy's beliefs about each target of its `informs` edges move toward the scenario's true value, with variance reduced by the edge's `param`.
6. Stop at the horizon; return the objective.

v1 restrictions: one person per project at a time; reassignment only at events; each switch away from unfinished work costs `switch_cost_weeks`.

All policies are compared on the same set of scenarios (common random numbers), using paired differences.

### Baseline policy

Priority index for project `j`:

```
I_j = density(j) x (1 + w_depth x depth_j)  +  w_var x sd(v_j) / E[effort_j]
```

- `density(j)` is the value-to-effort ratio of the best closed set containing `j` (section 7).
- `depth_j` is the length of the longest chain of dependents below `j`. It keeps the set of startable work wide.
- The last term is an optimism bonus for high-variance value, which favors cheap exploration.

At each decision point, for the free people `F` and ready projects `R`, solve the assignment problem maximizing the sum of `I_j x speed(p, j)` over chosen pairs (`scipy.optimize.linear_sum_assignment`). Ineligible pairs (missing a required skill) are excluded. The number of in-progress projects is capped at `wip_limit`.

A person stays on their in-progress project unless:

- it hits its timebox: effort spent exceeds `timebox_k x` the median of the original belief. The project is then re-ranked on its conditional remaining effort and may be paused or abandoned; or
- a ready alternative's score exceeds the current project's by more than `switch_threshold`.

### Policy search

Parameters `theta = (w_depth, w_var, wip_limit, timebox_k, switch_threshold)` plus a per-project multiplier on the index.

1. Evaluate the baseline with default parameters on `N` scenarios.
2. Local search: perturb one parameter or one multiplier, or swap two adjacent queue positions; re-evaluate on the same scenarios.
3. Accept a change if the mean paired improvement exceeds two paired standard errors.
4. Stop at a time budget or after a fixed number of non-improving moves.

The plan records the final objective, its standard error, and the baseline's objective, so the gain from search is always visible. If the search does not beat the baseline, the baseline is the plan.

### Forecast

From the final policy's scenarios: for each project, the p50 and p90 ship date, the probability of shipping within the horizon, and the criticality (share of scenarios in which it lies on the longest chain to a value-bearing ship date).

### Sensitivity and value of information

For each quantity whose belief is not a point:

1. Fix the quantity at its p10, p50 and p90 in turn.
2. Under each, find the best `now` assignment using the tuned policy on a reduced scenario set.
3. `voi = sum over the three cases of weight x (J(best assignment for that case) - J(current assignment in that case))`, with weights 0.3, 0.4, 0.3.
4. `flips` lists the assignments that differ from the current plan in any case.

An empty `flips` means this screen found no benefit for the current assignment; it
does not establish zero value for future decisions. Question selection must also
consider decisions within a configurable window, response lead time, expected
answer informativeness, attention cost, and overlapping questions. Until those
are modeled, this three-point calculation is labeled a sensitivity screening
score, not a calibrated estimate of the value of asking a particular person.

For each `hard` or `either_or` edge: remove it, re-evaluate, and report the gain. This is the price of the dependency.

### Library interface

```python
from layline import Project, Person, Edge, LogNormal, solve

plan = solve(
    projects=[Project("sso-login", kind="feature", skills={"backend"},
                      effort=LogNormal.from_p10_p50_p90(2, 4, 9),
                      value_rate=LogNormal.from_p10_p50_p90(1, 3, 8))],
    people=[Person("dana", skills={"backend": 1.2}, availability=0.8)],
    edges=[],
    horizon_weeks=52,
    seed=7,
)
plan.now          # {"dana": "sso-login"}
plan.queue        # ranked list with index values
plan.forecast     # per-project ship-date percentiles
plan.sensitivity  # per-quantity voi and flips; per-edge price
```

`solve` is deterministic for a given input and seed.

---

## 7. Dependencies

### Edge types

| Type | Meaning | Effect in the solver |
|---|---|---|
| `hard` | `dst` cannot start before `src` ships | Precedence constraint |
| `soft` | `dst` can start early, with rework | Effort of `dst` is multiplied by `param` if started before `src` ships |
| `either_or` | `dst` needs any one of the edges sharing its `group_id` | Ready when one alternative has shipped |
| `complement` | `src` and `dst` are worth more together | Extra value rate `param` once both have shipped |
| `informs` | `src` (a probe) narrows the uncertainty on `dst` | Variance of the belief on `dst` value is reduced by `param` when `src` completes |

### Ready set

A project is ready when all its `hard` prerequisites have shipped and each of its `either_or` groups has at least one shipped member. If a `hard` prerequisite is abandoned, its dependents are marked blocked and surfaced by `layline next`.

### Ranking by closed sets

A prerequisite with no value of its own must inherit the value of what it unblocks. Following Sidney's decomposition for precedence-constrained scheduling:

1. Among sets of open projects that are closed under `hard` prerequisites, find the set `S` maximizing `sum of E[v] / sum of E[effort]`.
2. Every project in `S` gets that ratio as its `density`.
3. Remove `S` and repeat on the remainder.

Step 1 is a maximum-density closure problem. Solve it by Dinkelbach iteration: for a trial ratio `lambda`, find the maximum-weight closure with node weights `E[v_j] - lambda x E[effort_j]` using a min-cut (`networkx`), and update `lambda` until the best closure has weight zero. Expected sizes are tens to low hundreds of projects, so this is fast. `either_or` groups are resolved before the computation by picking the alternative with the lower expected effort.

Implementation note: this is the target exact closure formulation. The current
baseline uses the approximate prerequisite-bundle procedure in section 18 and
reports that method explicitly. It does not enumerate all project subsets.

### Uncertain prerequisites

A prerequisite with a wide effort belief or a meaningful chance of abandonment puts its whole subtree at risk. The simulator captures this directly; no special rule is needed. In practice the search tends to pull such prerequisites forward, because resolving them early improves every later decision.

---

## 8. Questions and the survey adapter

### Lifecycle

```
proposed --> approved --> claimed --> sent --> answered
    |            |                      |
    +------------+----------------------+--> withdrawn | expired
```

Questions are proposed by the planner from sensitivity results and operational triggers. Each carries `voi` and `flips`, so a reviewer can see why it is being asked.

### Kinds

| Kind | Typical respondent | Answer | Writes |
|---|---|---|---|
| `three_point` | Engineer, or product owner for value | p10, p50, p90, rationale | Observation |
| `pairwise` | Sales, founders, customers | Winner, optional strength | Comparison |
| `checkin` | Person on the project | Effort spent; p10, p50, p90 remaining | Work event and observation |
| `dependency` | Tech lead | Keep, change type, or remove | Edge change (approval required) |
| `closure` | Project owner | Outcome, actual effort | Work event and observation |
| `retro_value` | Owner or customer | Realized value rate | Observation with source `actual` |

### Selection

`layline ask propose`:

1. Rank open quantities by `voi`.
2. For each, choose a respondent: someone with the relevant skill or role who has not answered recently, preferring those with remaining weekly budget and better calibration.
3. Prefer `pairwise` for value when fewer than two absolute anchors exist or the respondent is external.
4. Drop candidates with `voi` below `min_voi`, and candidates whose `dedup_key` matches a question that is open or was answered within the cooldown.
5. Add operational questions: check-ins overdue by more than `checkin_interval_days`; closure confirmations suggested by link signals.

`dedup_key` is `kind:quantity_ids:person_id:iso_week`.

### Adapter interface

```python
class SurveyAdapter(Protocol):
    def send(self, spec: QuestionSpec) -> str: ...          # returns external_ref
    def poll(self, since: datetime) -> list[Answer]: ...
    def withdraw(self, external_ref: str) -> None: ...
```

Question spec, as sent:

```json
{
  "id": "01JD3Q8X...",
  "kind": "three_point",
  "to": {"person_id": "dana", "contact": "dana@example.com"},
  "prompt": "How many person-weeks do you expect SSO login to take from here?",
  "context": {
    "project": "sso-login",
    "links": [{"role": "spec", "title": "SSO design", "url": "https://docs.google.com/..."}]
  },
  "answer_schema": {
    "type": "object",
    "required": ["p10", "p50", "p90"],
    "properties": {
      "p10": {"type": "number", "exclusiveMinimum": 0},
      "p50": {"type": "number", "exclusiveMinimum": 0},
      "p90": {"type": "number", "exclusiveMinimum": 0},
      "rationale": {"type": "string"}
    }
  },
  "expires_at": "2026-11-25T17:00:00Z"
}
```

`ask ingest` validates each answer against the schema. Invalid answers are recorded as `question.answer_rejected` events and reported, never coerced; the question stays `sent`.

A `file` adapter ships first: `send` writes the spec to a directory, `poll` reads answer files from it. This makes the whole loop testable without the survey platform.

---

## 9. Links and provider adapters

Links attach external artifacts to projects, and to observations, questions and work events as evidence. Only pointers and a small cached state are stored, never content.

### Adapter interface

```python
class ProviderAdapter(Protocol):
    def parse_url(self, url: str) -> ParsedLink | None: ...   # canonical url, kind, external_id
    def fetch_state(self, link: Link) -> LinkState: ...       # title, state, reachable, meta
    def scan(self, scope: str, slugs: list[str]) -> list[ParsedLink]: ...   # optional
```

First adapters: GitHub (PRs and issues) and Google Docs. Unknown URLs are stored with provider `other` and are never synced.

### Signals

`link sync` checks each link with its provider and appends a `link.state_changed` event, and a `work.signal` event on the project, only when the state has changed. The planner turns signals into proposals:

| Signal | Proposal |
|---|---|
| First implementation PR opened, project not started | `started` event |
| All implementation PRs merged and tracking issue closed | `closure` question to the owner |
| New PRs still opening after the timebox | Re-rank; `checkin` question |
| No link activity for `stall_days` on an in-progress project | Stall flag in `next` |

Signals propose; they do not write closures. A config flag can allow automatic `started` events.

`link scan` finds PRs and issues whose branch name or title contains a project slug, and proposes links for them.

---

## 10. CLI

### Conventions

- Planning commands default to JSON. Discovery commands (`guide`, `skills`, `docs`) print readable guidance by default and accept `--json` for a single structured envelope. All errors are JSON; logs go to stderr. `--help` is conventional usage text.
- Global flags: `--repo PATH`, `--actor ACTOR`, `--dry-run`, `--no-commit`, `--idempotency-key KEY`.
- Every writing command appends events and makes one git commit (section 13). No command modifies or removes an existing line.
- No command prompts for input. Missing arguments are an error.
- Writes are idempotent given the same `--idempotency-key`: the key is stored on the event, and a repeat finds it in the log, writes nothing, and returns the original result.
- `--dry-run` is available on every command that writes or sends, and returns what would happen.

Success envelope:

```json
{"ok": true, "data": {}, "warnings": [], "next": ["layline solve"]}
```

Error envelope:

```json
{"ok": false,
 "error": {"code": "approval_required",
           "message": "Question 01JD3Q8X targets an external person.",
           "fix": "layline ask approve 01JD3Q8X --actor human:<id>"}}
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected failure |
| 2 | Usage error |
| 3 | Not found |
| 4 | Validation failure or conflict |
| 5 | Approval required |
| 6 | Adapter failure |

### Commands

```
layline init [--repo PATH]             # creates the layout, .gitignore and clone id

layline project add ID --name NAME --kind KIND [--skill S ...] [--owner PERSON]
layline project amend ID [...]         # appends a project.amended event
layline project show ID
layline project list [--status S] [--kind K]

layline person add ID --name NAME [--skill S=SPEED ...] [--availability F]
layline person amend | show | list

layline dep add SRC DST --type TYPE [--param X] [--group G]
layline dep rm SRC DST --type TYPE
layline dep list [PROJECT]
layline dep check                      # cycles, orphans, blocked projects

layline observe QUANTITY --p10 X --p50 Y --p90 Z [--by PERSON] [--rationale TEXT]
layline observe QUANTITY --point X     # probabilities and actuals
layline retract OBSERVATION_ID --reason TEXT
layline belief show QUANTITY           # pooled distribution and the observations behind it

layline start PROJECT --by PERSON
layline pause PROJECT
layline checkin PROJECT --spent W --p10 X --p50 Y --p90 Z
layline close PROJECT --outcome OUTCOME --actual-effort W

layline solve [--seed N] [--scenarios N] [--time-budget S]
layline now | queue | forecast [--plan ID]
layline why PROJECT                    # index, closed set, criticality, deciding observations
layline diff PLAN_A PLAN_B             # changed assignments and the inputs that caused them
layline accept PLAN
layline override PLAN --assign PERSON=PROJECT ... --reason TEXT

layline ask propose [--limit N]
layline ask list [--status S]
layline ask approve | withdraw ID
layline ask send [ID ...]
layline ask ingest

layline link add SUBJECT URL [--role ROLE]
layline link list SUBJECT [--kind K]
layline link rm ID
layline link find URL
layline link scan --repo OWNER/REPO
layline link sync [PROJECT]

layline calibrate [--person ID]
layline next                           # ordered actions for the operator
layline schema [COMMAND]               # JSON Schemas for inputs and outputs
layline sync                           # pull, re-fold, report anomalies, push
layline log [--subject ID] [--type T] [--since TS]
layline doctor [--ci]                  # anomalies; append-only, layout and identity checks
```

Quantities are addressed as `kind:subject`, for example `effort:sso-login`, `value_rate:sso-login`, `speed:dana/backend`.

### `layline why`

Returns, for one project: its index and each term of it; the closed set it was ranked with; its queue position and assignee; its criticality; the three observations with the largest influence on its rank; and the nearest alternative with the change in inputs that would swap them.

---

## 11. Agent operation

### `layline next`

Returns an ordered list of actions. This keeps the operating logic in tested code instead of the agent's prompt.

```json
{"ok": true, "data": {"actions": [
  {"command": "layline ask ingest", "reason": "3 answers waiting", "requires_approval": false},
  {"command": "layline solve", "reason": "inputs changed since plan 01JD...", "requires_approval": false},
  {"command": "layline ask send 01JD3Q8X", "reason": "voi 4.2; could move dana from sso-login to billing-v2",
   "requires_approval": false},
  {"command": "layline close sso-login --outcome shipped --actual-effort 6.5",
   "reason": "all implementation PRs merged; owner confirmed", "requires_approval": true}
]}}
```

### Loop

Triggered by an answer arriving, a work event, a link signal, or a weekly tick:

1. `sync`
2. `ask ingest`
3. `link sync`
4. `solve`
5. `diff` against the last accepted plan. If `now` changed, notify the owner with the `why` output and wait for `accept` or `override`.
6. `ask propose`, then `ask send` for questions that pass the gates, using claim-then-push (section 13).
7. `sync`

### Approval gates

Each action class is `auto` or `approve` in config. Defaults:

| Action | Default |
|---|---|
| Add observation with source `agent` | auto |
| Send `three_point`, `checkin` to an internal person, within budget | auto |
| Send any question to an external person | approve |
| Send beyond a person's weekly budget | approve |
| Record a closure | approve (owner confirmation) |
| Add, change or remove an edge | approve |
| Accept a plan that changes `now` | approve |

Approval is an event with a `human:` actor, committed under that person's git identity; `doctor --ci` verifies the match (section 13). An agent actor attempting a gated action receives exit code 5 and the fixing command.

### Attribution

Agent-sourced observations are permitted, so that the agent can seed estimates from linked specs, and are down-weighted in pooling. `belief show` separates them from human-sourced ones.

---

## 12. Configuration

`layline.toml`, at the repository root:

```toml
[model]
value_unit = "points_per_week"   # the single unit of account for value
horizon_weeks = 52
discount_rate_annual = 0.25
objective = "discounted_value"   # or "log_growth"

[solver]
scenarios = 500
time_budget_seconds = 30
switch_cost_weeks = 0.2
wip_limit = "people"             # an integer, or "people" for one project per person

[beliefs]
recency_half_life_days = 60
agent_source_weight = 0.25
calibration_prior_strength = 5

[questions]
min_voi = 0.5
cooldown_days = 14
checkin_interval_days = 10
expires_days = 7

[signals]
stall_days = 10
auto_start = false

[approval]
send_internal = "auto"
send_external = "approve"
closure = "approve"
edge_change = "approve"
accept_plan = "approve"

[git]
auto_commit = true
auto_push = false
claim_timeout_minutes = 30

[identities]                     # commit author email -> actor
"dana@example.com" = "human:dana"
"planner-bot@example.com" = "agent:planner"

[adapters.survey]
type = "file"
dir = "./.layline/survey-outbox"

[adapters.github]
enabled = true
```

---

## 13. Git workflow

### Commits

Every writing command appends its events and makes one commit containing only those lines, with a message that summarizes the command, for example `layline: observe effort:sso-login (human:dana)`. `--no-commit` leaves the change staged, for batching. Commands never amend commits, rewrite published history, or force-push.

### Sync

`layline sync` runs `git pull --rebase`, re-folds, reports new anomalies, and pushes. Because each clone writes only to its own files, the rebase cannot conflict on event files. Conflicts are possible only in `layline.toml`, which is resolved by hand like any other file.

### Claim, then act

Some actions have effects outside the repository, chiefly sending a question to a person. Two clones must not both do it. The push to the shared branch is used as the lock:

1. Append a `question.claimed` event and commit.
2. Push. If the push is rejected, pull, re-fold, and stop if another writer's claim now comes first.
3. Only after a successful push, call the adapter.
4. Append `question.sent` with the `external_ref`, commit, push.

A claim with no recorded result after `claim_timeout_minutes` is reported by
`doctor`. A timeout is not evidence that sending failed. If the provider might
have sent before the process crashed, the action enters `outcome_unknown` and is
reconciled against provider records or reviewed before retrying. Exactly-once
delivery requires a provider idempotency/reconciliation contract; git claims alone
do not provide it. The same pattern applies to future side-effecting actions.

### Checks

`layline doctor --ci` is intended to run on the repository host for every push or pull request to the main branch. It fails if:

- any existing line under `events/` or any file under `plans/` was modified or removed, or a file was renamed or deleted;
- the change adds a binary file, or any file outside the layout in section 4;
- a new event fails schema validation or reuses an existing `id`;
- a new event's `actor` does not match the identity of the commit that introduced it, according to the `[identities]` table in `layline.toml`;
- a gated action (section 11) was taken without an approval event from a human actor.

The `actor` field and ordinary git author email are claims, not authentication.
Commit identity matching is an audit consistency check. Enforced approvals need
an authenticated host approval or verified signing identity bound to the exact
action and inputs, with protected checks and protected identity configuration.
Until that integration exists, actor-based gates are conventions and must not be
described as authenticated human approval.

### Triggers

A push to the main branch is a natural trigger for the agent loop: the host's automation runs `layline next` when new events land. This replaces polling.

### Privacy and permanence

Everything in the log is visible to everyone with repository access and is permanent: per-person estimates and the calibration derivable from them, rationale text, and survey answers. Erasing a line later means rewriting git history for every clone. For that reason contact details are kept out of the log, and answers from external respondents should be recorded against a pseudonymous person id. Whether customer answers belong in this repository at all is an open question (section 17).

### Scale

Folding is linear in the number of events. A year of use by a small team should produce thousands to tens of thousands of events; the target is to fold that in under a second, to be confirmed by a benchmark in milestone 2. v1 folds from scratch on every command and keeps no cache. If a cache is ever needed, it is a plain file under `.layline/`, keyed on a hash of the event files, never committed, and safe to delete.

---

## 14. Package layout

```
layline/
  __init__.py        # public API: Project, Person, Edge, distributions, solve
  model.py           # dataclasses
  dist.py            # LogNormal, Normal, Beta, Point; three-point fitting; conditioning
  log.py             # event envelope, writer files, append, schema validation, upcasters
  fold.py            # events -> state; anomaly detection
  gitops.py          # commit, sync, claim-then-push, commit identity lookup
  beliefs.py         # pooling, calibration, Bradley-Terry fit
  graph.py           # validation, ready set, closed-set densities
  sim.py             # discrete-event simulator
  policy.py          # index, assignment, timebox and switch rules
  search.py          # policy search with common random numbers
  sensitivity.py     # value of information, edge prices
  planner.py         # question proposal, diff, next
  doctor.py          # anomalies; append-only, layout and identity checks
  adapters/
    survey.py        # protocol and file adapter
    github.py
    gdocs.py
  cli/               # one module per command group
tests/
```

Dependencies: `numpy`, `scipy`, `networkx`, `click`, `python-ulid`, `jsonschema`. Git is driven through the `git` executable. Python 3.11 or later.

---

## 15. Testing

- **Known optima.** One person, no dependencies, deterministic effort, zero discount, and enough horizon to finish all projects: compare with value-over-effort order. For discounted, finite-horizon and dependency cases, enumerate feasible schedules on small fixtures and evaluate the actual objective. Closed-set ranking is a baseline heuristic, not a general optimality claim for this objective.
- **Simulator invariants** (property-based): no project starts before it is ready; no person is on two projects; effort burned equals effort sampled for every shipped project; the objective is invariant to project insertion order.
- **Determinism.** Same inputs and seed give an identical plan.
- **Search never regresses.** The plan's objective is at least the baseline's on the evaluation scenarios.
- **Calibration recovery.** Generate synthetic estimators with known bias and spread; the fitted corrections must recover them within tolerance.
- **CLI contract.** Every command's JSON output validates against `layline schema`. Repeating a write with the same idempotency key changes nothing.
- **Fold determinism.** Shuffling the events, or splitting them across files differently, gives identical state.
- **Merge behaviour.** Two clones write concurrently, including forked amendments, edges that together form a cycle, and duplicate question proposals. After merging, both clones fold to identical state and the expected anomalies are reported.
- **Append-only.** After any sequence of commands, the diff under `events/` and `plans/` contains additions only.
- **Claim race and ambiguous outcomes.** Two clones race to send the same question; only the winning live claim may initiate delivery. Separately inject failure after provider acceptance but before recording success: recovery must reconcile or hold, not blindly send again.
- **End-to-end** with the file survey adapter: propose, send, answer, ingest, re-solve, and confirm the plan changes as the injected answer implies.

---

## 16. Milestones

| # | Deliverable | Rough size |
|---|---|---|
| 1 | Model, distributions, simulator, baseline index without dependencies, forecast; `solve` as a library call | 1 week |
| 2 | Event log, fold, auto-commit, `sync`, fold benchmark; CLI core (`project`, `person`, `observe`, `solve`, `now`, `queue`, `forecast`), JSON envelope, idempotency | 1 to 2 weeks |
| 3 | Dependencies: edge types, ready set, closed-set densities, `why` | 1 week |
| 4 | Work events, check-ins, closures, belief pooling, calibration | 1 week |
| 5 | Policy search, sensitivity, edge prices, `diff` | 1 to 2 weeks |
| 6 | Questions: proposal, file adapter, claim-then-push, ingest, approval gates, `doctor --ci`, `next` | 2 weeks |
| 7 | Links: GitHub and Google Docs adapters, signals | 1 week |
| 8 | Survey platform adapter, pairwise comparisons, push-triggered agent runs | 1 to 2 weeks |
| 9 | Probes and enablers in the simulator, `log_growth` objective | 1 week |

Milestones 1 to 3 give a usable planner fed by hand. Milestones 4 to 6 close the loop with people. The sizes assume one engineer and are estimates to be checked against the first two.

---

## 17. Open questions

1. **Unit of value.** What is the single unit of account: revenue, a growth metric, or abstract points? Everything in the objective depends on it, and it determines who can sensibly answer value questions.
2. **Who estimates value.** Founders only, or sales and customers through pairwise questions? This sets how much of milestone 8 is needed early.
3. **Multi-person projects.** v1 assumes one person per project. If most real projects need two or more people at once, the simulator needs a staffing model with a coordination penalty sooner.
4. **Survey platform interface.** What does the platform's API look like, and can it carry a JSON answer schema, or must answers be parsed from free text?
5. **Non-project work.** Support, on-call and meetings are covered only by `availability`. Is a per-person constant enough, or does it vary enough to need a calendar?
6. **Deadlines.** Some work has a hard external date. The current objective has no deadline term; adding one means a value rate that drops to zero, or a penalty, after a date.
7. **Privacy of calibration.** Who may see per-person bias reports? With the log in git, anyone with repository access can compute them.
8. **Name.** `layline` is unregistered on PyPI and npm as of 2026-11-18, but a software company trades as layline.io. `tack` and `tack-cli` are taken on PyPI.
9. **Repository host and enforcement.** Where does the repository live, and can the main branch be protected with a required check? Without that, the append-only and approval rules are conventions, not guarantees.
10. **External answers in git.** Should customer survey answers be committed, given that the log is permanent and visible to everyone with access? The alternative is to keep raw answers in the survey platform and commit only the derived observation.
11. **Direct push or pull requests.** Does every writer push to the main branch, or do humans and the agent go through pull requests? Pull requests give review and a place for the check to run, at the cost of latency in the agent loop.

---

## 18. Scenario-driven implementation design

The first slice is a read-only Python CLI and library for replaying authored
scenarios and solving local event inputs. Operator workflows ship inside the
package: `guide` prints a readable starting point and routes to `skills show plan-team`; `skills list/show` exposes
onboarding and plan-review instructions, and `docs list/show/search` exposes
context research and input/result references. Onboarding asks the calling agent
to read available company repositories, contributor history and product/strategy
docs, draft engineer profiles with provenance, and confirm inferred skills,
current availability and priorities with the user. Commit activity does not set
speed multipliers or establish commitments. Rich profiles and company context
stay in companion intake notes; repository access uses the agent's existing tools,
not a built-in connector or new event schema.
The calling agent asks questions and prepares files;
the CLI does not prompt or maintain onboarding state. Guidance commands print
readable text by default and expose the same information with `--json`.
Repository `AGENTS.md`
contains development guidance. This establishes domain behavior before adding a durable writer or live
external effects. The product command inventory above remains the target, not a
claim that every command exists. `layline schema` reports the prototype's actual
interfaces and omissions.

### Boundaries and concrete decisions

1. **Three distinct records:** recommendations, accepted decisions, and observed
   work. Accepting a plan does not emit a work-start event. Persistent commitments
   constrain subsequent plans until explicitly released or their project closes.
   The prototype supports explicit release, not expiration or deadline penalties.
2. **Scope is versioned.** Every estimate and question identifies a scope revision.
   Old evidence stays inspectable but is excluded from the current scope's belief.
   A delayed answer about old scope enters review, not the current estimate pool.
3. **Effort has a basis.** Preserve reported person-effort spent and the distribution
   of remaining effort. Calendar intervals are not measured effort. Abandoned and
   descoped outcomes do not become ordinary completion-effort calibration targets.
4. **Logical question, instrument, and delivery are separate.** The production
   adapter will map several logical questions to a survey and separately track
   publication and delivery attempts. One `send(spec) -> str` is insufficient to
   describe publication success followed by uncertain invitation delivery.
5. **Ingestion is attributable and repeatable.** Identify an answer by instrument,
   response, and logical question; preserve revision/content identity and scope.
   Completed, partial, skipped, invalid, and abstaining answers are distinct.
   Duplicate completed answers are no-ops. Changed accepted answers enter review;
   an explicit review operation will supersede the old observation. The prototype
   implements the hold, not the review-resolution command.
6. **Conflicts are visible.** A fold can return usable portions of state plus
   anomalies. The prototype refuses to solve when any anomaly exists, including
   conflicting assignments and stale acceptance. Production may distinguish
   blocking anomalies from advisory ones; it must not silently overwrite operational
   conflicts. Timestamp sorting is the prototype's deterministic replay order,
   not a proof of causality between distributed writers.
7. **Idempotency belongs to an operation.** A durable command receipt must bind a
   request key to its request digest, complete event batch, and original result.
   Reusing a key for another request is an error. Sharing one event-level `idem`
   across a closure and its actual observation must not discard either effect.
   The repository writer must guarantee complete batches and concurrent-process
   exclusion; the prototype only applies each in-memory event atomically.
8. **Approvals bind inputs.** Acceptance checks that the planning state has not
   changed since the proposed plan. Production approval also binds the full plan
   snapshot, configuration, evaluation time, allowed action, and authenticated
   identity. Editable actor strings and author emails do not establish identity.
9. **Uncertainty does not justify false precision.** Priors, excluded stale
   evidence, agent-only estimates, blocked forecasts, and solver limitations are
   explicit output. Zero direct value is valid for a prerequisite. The prototype
   supports point-zero value but refuses to pool zero and positive estimates until
   a mixture model is specified. Negative value and uncertain zero outcomes remain
   design work.
10. **Replay must be reproducible.** Evaluation time, seed, scenario count, model
    parameters, and solver version are explicit. Random streams are stable by
    project and scenario. Policy decisions use beliefs, not sampled latent truth.
    Exact small-fixture comparisons evaluate the actual objective. A density
    ranking is not asserted to optimize discounted or horizon-limited value.
11. **Approximation replaces size caps.** All projects and people participate in
    one plan. For ranking, compute each project's unfinished-prerequisite closure.
    For every seed closure, greedily union the candidate bundle that most improves
    its value/effort ratio, until no single addition improves it. Pick the best
    grown bundle, assign its density, remove it and repeat. Inputs and ties use a
    deterministic order. This is polynomial local search, not a guarantee of the
    maximum-density decomposition; it can miss improvements requiring multiple
    individually unhelpful additions. Priorities still use median effort/value.
    Immediate assignment uses rectangular Hungarian maximum-weight matching,
    with dummy idle choices and exclusion of ineligible pairs from the output.
    Its cost is O(P²(R+P)) for P free people and R ready projects. The six-person
    and twelve-project rejection thresholds are removed. No new arbitrary
    roster/backlog cap replaces them; runtime grows with input size and scenario
    count. Plans expose `method`, `solver_version`, and the heuristic's limitations.

### Executable acceptance scenario

`src/layline/examples/team.json` describes Dana (backend), Priya (backend/data),
and Lee (frontend), with eight projects. Platform work unlocks audit and SSO.
Priya is committed to exports and has started it. Billing has a wide effort
estimate. The checkpoints are:

1. Recommend platform for Dana, exports for Priya, onboarding for Lee.
2. Record a proposed/sent billing-effort question; assignments do not change.
3. Ingest an answer started earlier but completed later; recommend billing for
   Dana while preserving Priya's commitment.
4. Accept the recommendation; billing still has no observed work-start record.
5. Record billing starting, then a check-in with two person-weeks spent and a
   remaining-effort median of six. Keep active work until an explicit transition.
6. Pause billing; platform becomes Dana's recommendation again.
7. Abandon billing with two person-weeks spent. Record no completion-effort actual.

The tests assert outcomes, not just schema shape. Variants exercise:

| Variant | Required result |
|---|---|
| `duplicate-and-corrected-answer` | Repeat adds no observation; correction enters review without replacing evidence. |
| `scope-change` | Old estimates excluded; late answer held for scope review; prior use visible. |
| `partial-and-invalid-answer` | Partial and malformed estimates add no evidence; valid completion is ingested once. |
| `concurrent-assignment` | Conflicting work starts produce an anomaly and block a new plan. |
| `stale-acceptance` | A changed estimate invalidates acceptance of the earlier planning state. |
| `shipped` | Confirmed shipped effort becomes an actual for the corresponding scope. |

Additional unit scenarios cover input-order invariance, duplicate event IDs,
atomic rejection of multi-effect transitions, dependency cycles, zero-value
prerequisites, unavailable/missing-skill people, exhausted point estimates,
unconditional ship percentiles, and the discounted-density counterexample.
Whole-backlog acceptance cases cover 29 projects/6 people, 40/9, and 100/15.
Independent exhaustive oracles validate immediate matching on small random cases;
random dependency graphs check prerequisite ordering and effort conservation.
Shared-prerequisite fixtures check that combined downstream benefit can outrank
unrelated work even when individual child bundles cannot.

### EDSL integration findings and next contracts

The local EDSL implementation supports `Jobs.humanize()` with surveys, scenarios,
and respondent agent lists, without model lists. Publishing a survey and creating
an invitation delivery are separate operations. Human response exports preserve
response UUIDs and per-question timing. They may return either `Results` or a
fallback `ScenarioList`; the adapter must validate and normalize both explicitly.

`Coop.get_human_survey_responses` date bounds filter response **start time**, not
completion time. For small active surveys, initially re-fetch completed responses
and deduplicate by stable identity. Do not advance a start-time watermark and
assume all later completions will appear. The `humanize events` cursor is for
custom survey telemetry; it is not a general response-change cursor.

The inspected create-survey and create-delivery Python interfaces expose no
explicit idempotency-key parameter. Provider-side guarantees remain to be checked
before enabling retryable delivery. The next adapter design should expose local
instrument preparation, publication, delivery, reconciliation, and normalized
response retrieval. All private contact mappings and bearer respondent URLs stay
outside committed event data. Attribution comes from the acquisition workflow,
not a model label on an EDSL Results object.

### Scenarios still requiring design or implementation

- Automate persistence and progress tracking for backlog onboarding. The bundled
  skill currently guides the agent through company/repository research, engineer
  profiles, scope, comparable value anchors and estimates, and exposes tentative
  recommendations through local input files.
- Temporary unavailability, multi-person staffing, deadlines, and expiring
  commitments. The current simulator supports only constant availability and one
  person per project.
- Questions whose benefit is a future decision, survey batching, shared attention
  budgets, cooldown across week boundaries, and informative abstention.
- Either-or dependencies with specialist constraints and shared downstream value.
- Real delivery ambiguity, git claim races, clock skew, malformed on-disk batches,
  and crash recovery across event append/commit/push boundaries.
- Authentication and exact action-bound approvals; review and resolution of held
  answers and operational conflicts.
- Calibration with scope-matched outcomes, noisy realized-value measurements,
  censored abandoned work, and review of initial versus near-completion estimates.

These are intentionally visible gaps, not passing acceptance cases. Production
persistence and sending should follow their contracts rather than extending the
prototype's fixture shortcuts into external effects.
