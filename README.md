# Layline

An agent-facing Python planning CLI, currently an **offline executable design
prototype**. It replays a small team's decisions and evidence through a pure event
fold and a deterministic baseline planner. See [spec.md](spec.md) for the product
specification and the scenario-driven decisions in section 18.

## Copy and paste into your coding agent

Paste this entire block into your coding agent. It installs Layline from GitHub
and starts the guided planning conversation:

```text
Help me plan my team's project work using Layline.

Install Layline from https://github.com/expectedparrot/layline.git in a local
virtual environment. Python 3.11+ and Git are required. Use a suitable existing
task environment if one exists; otherwise run these commands in our working
directory:

python3 -m venv .venv-layline
.venv-layline/bin/python -m pip install "layline @ git+https://github.com/expectedparrot/layline.git"
.venv-layline/bin/layline guide

Read the guide and follow its instructions in this conversation. Use that same
installed executable for subsequent commands, including skills and docs. Start
by loading the plan-team skill:

.venv-layline/bin/layline skills show plan-team

First check whether you can access our company repositories through local
checkouts, Git remotes, connected repository tools or an already authenticated
hosting CLI. Verify access with a small read and use relevant repos to learn
about the team before asking me to list sources or describe everyone from scratch.
Build context from contributor history and product or strategy docs. Ask which
company or sources to use only if discovery leaves that unclear.
Draft engineer profiles from concrete work examples with source references;
confirm inferred skills and current roles with me. Don't infer productivity or
speed from commit counts. Learn our company goals and priorities, then walk me
through availability, projects and scope, effort and value estimates,
dependencies, existing work, and commitments. Ask a small batch of questions at
a time and reuse information I've already provided. If sources are unavailable,
continue from what I can tell you.

Prepare the input files yourself and run the planner; don't ask me to write JSON.
Keep company context, engineer profiles and their sources in our intake notes,
alongside versioned inputs and plan outputs under planning/ in our working
directory. Preserve unknowns rather than inventing estimates or approvals.
Explain the proposed assignments, why they rank that way, and any important
uncertainty or unsupported requirements. Then help me correct and compare the plan.

Use the installed guidance to discover supported commands. Check errors and
warnings before presenting results. Plan my actual team rather than substituting
the bundled demo. No EDSL account or API key is needed for this local workflow.
```

If the agent uses an existing environment, it should substitute that environment's
Python and `layline` executable for the `.venv-layline/bin/` paths above.

## Using Layline

Agents using Layline: start with `layline guide`. It routes to bundled skills and
references available from any installed copy. [AGENTS.md](AGENTS.md) is for agents
developing the package.

Start with **`layline guide`** and follow its instructions. It first directs the
agent to discover and verify company repository access, then use contributor
history and docs to draft team profiles. It asks for missing context and leads
through projects, estimates and commitments, confirming planning facts with the user.
An agent reading the guide follows the skill in the current conversation,
prepares local inputs, and explains the first plan. No agent-launch command is
needed. The CLI prints guidance; it does not wait for terminal answers.

```bash
source .venv/bin/activate  # if using this checkout's local installation
layline guide
layline skills list
layline skills show plan-team
layline docs list
layline docs show context
layline docs show inputs
layline docs search "remaining effort"
```

Run directly from this checkout with Python 3.11 or newer:

```bash
PYTHONPATH=src python -m layline demo --list
PYTHONPATH=src python -m layline demo
PYTHONPATH=src python -m layline demo --variant scope-change
PYTHONPATH=src python -m layline demo --variant concurrent-assignment
```

Or install with `python -m pip install -e .` and use `layline` directly. The
prototype has no runtime dependencies and makes no network calls.

The bundled scenario has three engineers, eight projects, a shared prerequisite,
and an existing commitment. A delayed survey answer moves Dana's recommendation
from platform work to billing. Acceptance does not start work. A subsequent
overrun preserves the remaining-effort estimate; an explicit pause permits
reassignment, and abandonment records effort spent without pretending the
project was completed.

Variants cover repeated and corrected answers, scope changes, partial and invalid
responses, concurrent assignments, stale acceptance, and a shipped outcome.
Conflicting scenarios replay successfully but report anomalies and produce no
new plan at the conflicting checkpoint.

`guide`, `skills`, and `docs` print readable text by default. Add `--json` for
structured guidance. Planning commands and all errors return one JSON envelope
on stdout. `--help` returns conventional usage text.

The `guide --json` response includes a structured next action to load the
onboarding skill. `skills` exposes workflows; `docs` exposes context research,
input formats, result interpretation, examples, and limits. These resources are
bundled in the wheel. Repository research uses the calling agent's tools; Layline
has no built-in repository reader or engineer-profile store.

```bash
layline replay my-scenario.json --scenarios 64 --seed 7
layline solve events.json --as-of 2026-11-20T18:00:00Z
layline schema
```

`replay` takes the same structure as
[the bundled fixture](src/layline/examples/team.json). `solve` takes a JSON array
of events. Evaluation time is mandatory; replay checkpoints carry it explicitly.
Results include assignments, ranking evidence, forecast quantiles, warnings,
input hashes, and the solver's limitations. A null ship percentile means that
percentile lies beyond the modeled horizon, including noncompletion.

The baseline uses approximate prerequisite-bundle ranking, efficient maximum-weight
assignment matching, and reproducible simulation. It considers the entire backlog
without a fixed people or project cap. Shared prerequisites can improve a group's
priority, but the heuristic does not guarantee the best grouping or optimal
discounted schedule. Plans expose their `method` and `limitations`.

Active work and explicit commitments stay assigned until completion or an explicit
transition. Runtime grows with the inputs and scenario count; reduce `--scenarios`
for a quicker forecast instead of excluding projects from the plan. The former
six-person/twelve-project restrictions have been removed.

There are **no durable repository writes, git synchronization, live EDSL survey
calls, authenticated approvals, automated question selection, calibration, or
policy search yet**. Human actor fields in fixtures exercise approval semantics;
they are not authentication. Question proposal/send events are authored fixture
inputs, not proof that a survey was created or delivered. Calibration eligibility
is recorded for future use; no calibration is fitted.

Run the acceptance tests:

```bash
python -m pytest -q
```
