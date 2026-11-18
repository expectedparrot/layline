"""Independent oracles and whole-backlog fixtures for the approximate planner."""
from copy import deepcopy
import itertools
import random

import pytest

from layline.model import State, eligible, speed
from layline.planner import closed_set_densities, match, simulate, solve

AS_OF = "2026-11-20T18:00:00Z"


def backlog(project_count=29, people_count=6):
    state = State()
    for i in range(people_count):
        state.people[f"person-{i:03}"] = {"name": f"Engineer {i}", "skills": {f"skill-{i % 3}": 1}, "availability": .8, "internal": True}
    for i in range(project_count):
        project = f"project-{i:03}"
        state.projects[project] = {"name": f"Project {i}", "skills": [f"skill-{i % 3}"], "owner": "person-000", "scope_revision": "v1"}
        if i >= 3 and i % 4:
            state.edges.append((f"project-{i % 3:03}", project))
        for quantity, median in [("effort", 1 + i % 4), ("value_rate", 0 if i < 3 else 1 + i % 11)]:
            identifier = f"{project}:{quantity}"
            estimate = {"point": 0} if median == 0 else {"p10": median / 2, "p50": median, "p90": median * 2}
            state.observations[identifier] = {"project": project, "quantity": quantity, "by": "person-000", "source": "human", "scope_revision": "v1", "basis": "total", "estimate": estimate, "ts": "2026-11-18T12:00:00Z", "event_id": identifier}
    return state


@pytest.mark.parametrize("people,projects", [(6, 29), (9, 40), (15, 100)])
def test_entire_backlog_and_roster_are_planned(people, projects):
    state = backlog(projects, people)
    plan = solve(state, as_of=AS_OF, scenarios=8)
    assert len(plan["queue"]) == len(plan["forecast"]) == projects
    assert {item["project"] for item in plan["queue"]} == set(state.projects)
    assert len(plan["now"]) == len(set(plan["now"].values()))
    assert all(eligible(state, p, j) for p, j in plan["now"].items())
    assert plan["method"]["optimal_schedule"] is False


def test_large_backlog_keeps_commitments_and_is_order_invariant():
    state = backlog()
    state.commitments["person-000"] = "project-000"
    state.work["project-000"] = {"status": "in_progress", "person": "person-000", "spent": .2}
    expected = solve(state, as_of=AS_OF, scenarios=8)
    reordered = deepcopy(state)
    for key in ("people", "projects", "observations", "work", "commitments"):
        setattr(reordered, key, dict(reversed(list(getattr(reordered, key).items()))))
    reordered.edges = [list(edge) for edge in reversed(reordered.edges)]
    assert solve(reordered, as_of=AS_OF, scenarios=8) == expected
    assert expected["now"]["person-000"] == "project-000"


def test_shared_prerequisite_union_beats_unrelated_project():
    state = State(edges=[("foundation", "a"), ("foundation", "b")])
    effort = {"foundation": 10, "a": 1, "b": 1, "unrelated": 1}
    value = {"foundation": 0, "a": 8, "b": 8, "unrelated": 1}
    density, groups = closed_set_densities(state, list(effort), effort, value)
    # Each child alone has density 8/11, below the unrelated project's 1.
    # Together they amortize the shared prerequisite and reach 16/12.
    assert density["foundation"] == pytest.approx(16 / 12)
    assert density["foundation"] > density["unrelated"]
    assert set(groups["foundation"]) == {"foundation", "a", "b"}


def test_matching_preserves_specialist_for_work_only_they_can_do():
    state = State(
        people={
            "generalist": {"skills": {"backend": 1}, "availability": 1},
            "specialist": {"skills": {"backend": 2, "data": 1}, "availability": 1},
        },
        projects={"backend": {"skills": ["backend"]}, "data": {"skills": ["data"]}},
    )
    # Greedy best-pair selection would put the specialist on backend for score 20.
    # Matching assigns both projects for the higher combined score of 25.
    assert match(state, list(state.people), list(state.projects), {"backend": 10, "data": 15}) == {"generalist": "backend", "specialist": "data"}


def brute_assignment(state, people, projects, priorities):
    best = 0
    for choices in itertools.product([None, *projects], repeat=len(people)):
        chosen = [j for j in choices if j is not None]
        if len(set(chosen)) != len(chosen):
            continue
        if any(j is not None and not eligible(state, p, j) for p, j in zip(people, choices)):
            continue
        score = sum(priorities[j] * speed(state, p, j) for p, j in zip(people, choices) if j is not None)
        best = max(best, score)
    return best


def test_matching_agrees_with_exhaustive_oracle_on_small_random_cases():
    rng = random.Random(47)
    for _ in range(60):
        projects = [f"j{i}" for i in range(rng.randrange(1, 6))]
        people = [f"p{i}" for i in range(rng.randrange(1, 5))]
        state = State(
            people={p: {"skills": {j: rng.choice([0, 0, .5, 1, 2]) for j in projects}, "availability": rng.choice([0, .5, 1])} for p in people},
            projects={j: {"skills": [j]} for j in projects},
        )
        priorities = {j: rng.choice([0, .5, 1, 3, 9]) for j in projects}
        matched = match(state, people, projects, priorities)
        score = sum(priorities[j] * speed(state, p, j) for p, j in matched.items())
        assert score == pytest.approx(brute_assignment(state, people, projects, priorities))
        assert match(state, list(reversed(people)), list(reversed(projects)), priorities) == matched
        assert len(set(matched.values())) == len(matched)
        assert all(eligible(state, p, j) and priorities[j] > 0 for p, j in matched.items())


def test_ranking_and_simulation_preserve_dependencies_on_random_dags():
    rng = random.Random(19)
    for _ in range(15):
        projects = [f"j{i}" for i in range(8)]
        edges = [(a, b) for i, a in enumerate(projects) for b in projects[i + 1:] if rng.random() < .2]
        state = State(
            people={"p": {"skills": {}, "availability": 1}},
            projects={j: {"skills": []} for j in projects}, edges=edges,
        )
        efforts = {j: rng.randrange(1, 5) for j in projects}
        values = {j: rng.randrange(1, 12) for j in projects}
        densities, groups = closed_set_densities(state, projects, efforts, values)
        assert set(densities) == set(projects)
        emitted = set()
        for project in densities:  # Groups are emitted in decomposition order.
            group = set(groups[project])
            assert all(src in group or src in emitted for src, dst in edges if dst in group)
            emitted |= group
        trace = simulate(state, projects, efforts, values, densities, 100, 0)
        assert set(trace["finishes"]) == set(projects)
        assert all(trace["starts"][dst] >= trace["finishes"][src] for src, dst in edges)
        assert all(trace["finishes"][j] - trace["starts"][j] == pytest.approx(efforts[j]) for j in projects)


def test_cyclic_library_input_is_rejected_without_looping():
    state = State(edges=[("a", "b"), ("b", "a")])
    with pytest.raises(ValueError, match="dependencies"):
        closed_set_densities(state, ["a", "b"], {"a": 1, "b": 1}, {"a": 1, "b": 1})
