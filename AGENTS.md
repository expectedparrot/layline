# Developing Layline

This file is for agents changing Layline's source. Operator instructions ship in
the Python package and are discoverable through the CLI:

```bash
PYTHONPATH=src python3 -m layline guide
PYTHONPATH=src python3 -m layline skills list
PYTHONPATH=src python3 -m layline skills show plan-team
PYTHONPATH=src python3 -m layline docs list
```

Keep the developer/operator separation: do not put the conversational onboarding
workflow here. Update the bundled skill when that workflow changes, so installed
agents can discover it without access to the source checkout.

## Development setup

Python 3.11 or newer is required. The package has no runtime dependencies; the
optional `dev` extra supplies pytest. Use `PYTHONPATH=src python3 -m layline` to
run source directly, or `python3 -m pip install -e '.[dev]'` for editable development.
A wheel installed in `.venv` does not automatically pick up source edits.

```bash
python3 -m pytest -q
PYTHONPATH=src python3 -m layline demo --scenarios 8
```

Read [spec.md](spec.md), especially section 18, before changing event semantics,
planning behavior, or the CLI contract. The earlier command inventory is a target,
not an implementation inventory; `layline schema` reports current capabilities.

## Code boundaries

- `model.py`: domain primitives, distributions and state.
- `events.py`: pure event replay, validation and atomic in-memory transitions.
- `planner.py`: pure baseline planning and simulation.
- `scenarios.py`: authored workflow replay.
- `cli.py`: argument handling, input loading and JSON envelopes.
- `guidance.py`: discovery and reading of bundled operator resources.
- `skills/*/SKILL.md`: operator workflows, with name/description frontmatter.
- `docs_content/*.md`: operator references exposed by `docs` commands.
- `examples/*.json`: authored acceptance scenarios, not live user state.

Keep the fold and solver free of filesystem, git and network effects. Discover
operator resources through `importlib.resources`, not checkout-relative paths.
Keep resource names constrained to the bundled catalog. The lightweight skill
catalog reader expects plain single-line name and description frontmatter.

## Contracts and domain invariants

Commands remain non-interactive. The calling agent conducts conversations and
prepares planning artifacts. `guide`, `skills`, and `docs` print readable guidance
by default; `--json` returns their structured envelope. Planning commands and all
errors return one JSON envelope on stdout. Reserve stderr for diagnostics.
`--help` is conventional usage text. Preserve explicit `--json` whether placed
before or after a guidance command, including nested subcommands.
Preserve structured exit codes and executable `argv` arrays in guidance actions.

A successful scenario replay is not necessarily an anomaly-free plan. Conflicted
checkpoints report anomalies and have `plan: null`; standalone solving refuses
conflicted state. Surface nested planning warnings when interpreting replay.

Keep these distinctions intact:

- Recommendations, accepted decisions, observed work, and persistent commitments
  are separate. Accepting a plan does not start work.
- Estimates/questions bind scope revisions; stale evidence is excluded, not erased.
- Person-effort spent is distinct from calendar time and remaining effort. Preserve
  shifted remaining distributions instead of refitting them as total lognormals.
- Abandonment/descoping do not produce ordinary completion-effort calibration targets.
- Duplicate answers add no evidence; changed accepted answers enter review.
- Actor strings and git author emails do not authenticate human approval.

Retain explicit evaluation time, deterministic work budgets and stable random
streams. Policy decisions must not inspect sampled latent truth. Density ranking
is a baseline heuristic, not a general optimum for the discounted objective.
Ranking uses greedy prerequisite-bundle growth; immediate assignments use
polynomial Hungarian matching. Do not reintroduce exhaustive production subset
or assignment enumeration or fixed roster/backlog caps. Small exhaustive oracles
belong in tests. Cover whole-backlog planning, shared prerequisites, eligibility,
idle assignments, deterministic ties, and comparison with those oracles.

## Scope and validation

The prototype has no durable state writer, git synchronization, live EDSL adapter,
authenticated approvals, calibration, or policy search. Keep these omissions
visible until implemented. Guidance can support real local planning inputs without
claiming that operational persistence or survey delivery exists.

For EDSL integration work, inspect the neighboring `../edsl` checkout and its
`AGENTS.md`. Survey publication and invitation delivery are separate; response
start-time filters are not completion cursors; git claims do not provide
exactly-once external delivery.

Add behavioral acceptance tests for domain changes. For guidance changes, verify
resource discovery, structured failures, and executable examples. For packaging
changes, build a wheel and run it outside the checkout with no source `PYTHONPATH`
to verify that skills, references, and example files are included.

Update README, the capability description, spec implementation status, and bundled
operator guidance when supported behavior changes. Keep this file focused on
maintaining that implementation.
