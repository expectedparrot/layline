from copy import deepcopy
from dataclasses import asdict
from importlib.resources import files
import itertools
import json
import math
import random

import pytest

from layline import fold, solve
from layline.model import Distribution, LaylineError
from layline.planner import closed_set_densities, simulate

AS_OF = "2026-11-20T18:00:00Z"


def event(identifier, kind, subject, data, actor="human:dana"):
    return {"v": 1, "id": identifier, "ts": "2026-11-18T09:00:00Z", "actor": actor, "type": kind, "subject": subject, "data": data}


def simple_state(jobs):
    events = [event("000", "person.defined", "dana", {"name": "Dana"})]
    for index, (project, effort, value) in enumerate(jobs):
        events.append(event(f"{index+1}a", "project.defined", project, {"name": project, "scope_revision": "v1"}))
        for quantity, point in [("effort", effort), ("value_rate", value)]:
            events.append(event(f"{index+1}b{quantity}", "observation.recorded", f"{quantity}:{project}", {"project": project, "scope_revision": "v1", "source": "human", "by": "dana", "quantity": quantity, "estimate": {"point": point}}))
    return fold(events)


def team_events():
    return json.loads(files("layline").joinpath("examples/team.json").read_text())["initial_events"]


def test_replay_and_plan_are_invariant_to_input_order():
    events = team_events()
    expected = solve(fold(events), as_of=AS_OF, scenarios=8)
    for seed in range(5):
        shuffled = deepcopy(events)
        random.Random(seed).shuffle(shuffled)
        assert solve(fold(shuffled), as_of=AS_OF, scenarios=8) == expected


def test_identical_event_is_deduplicated_and_conflicting_id_is_quarantined():
    events = team_events()
    assert asdict(fold(events + [events[-1]])) == asdict(fold(events))
    bad = deepcopy(events[-1])
    bad["data"]["person"] = "lee"
    forward, reverse = fold(events + [bad]), fold(list(reversed(events + [bad])))
    assert asdict(forward) == asdict(reverse)
    assert any(a["code"] == "duplicate_id" for a in forward.anomalies)
    with pytest.raises(LaylineError, match="anomalies"):
        solve(forward, as_of=AS_OF)


@pytest.mark.parametrize("bad", [None, {}, {"v": 99}, {"v": 1, "id": "x"}])
def test_fold_reports_malformed_events(bad):
    assert fold([bad]).anomalies


def test_failed_multi_effect_closure_rolls_back_every_effect():
    state_events = [event("1", "project.defined", "p", {"name": "P", "scope_revision": "v1"}), event("2", "work.closed", "p", {"outcome": "shipped", "actual_effort": 3}, actor="human:unknown")]
    state = fold(state_events)
    assert state.anomalies
    assert "p" not in state.work
    assert not state.observations


def test_cycle_is_reported_and_not_solved():
    events = team_events()
    events.append(event("zzz", "edge.added", "audit>platform", {"src": "audit", "dst": "platform"}))
    state = fold(events)
    assert any(a["code"] == "dependency_cycle" for a in state.anomalies)
    assert ("audit", "platform") not in state.edges


def test_zero_value_prerequisite_inherits_value_and_precedes_dependents():
    state = simple_state([("foundation", 2, 0), ("feature", 1, 12)])
    state.edges = [("foundation", "feature")]
    priorities, groups = closed_set_densities(state, ["foundation", "feature"], {"foundation": 2, "feature": 1}, {"foundation": 0, "feature": 12})
    assert priorities == {"foundation": 4, "feature": 4}
    assert set(groups["foundation"]) == {"foundation", "feature"}
    trace = simulate(state, ["foundation", "feature"], {"foundation": 2, "feature": 1}, {"foundation": 0, "feature": 12}, priorities, 52, 0)
    assert trace["starts"]["feature"] == trace["finishes"]["foundation"] == 2
    assert trace["finishes"]["feature"] == 3


def test_undiscounted_baseline_matches_exhaustive_optimum():
    jobs = [("a", 1, 2), ("b", 3, 3), ("c", 2, 5)]
    plan = solve(simple_state(jobs), as_of=AS_OF, scenarios=8, horizon_weeks=20, discount_rate_annual=0)
    def objective(order):
        elapsed, result = 0, 0
        for _, effort, value in order:
            elapsed += effort
            result += value * (20 - elapsed)
        return result
    optimum = max(objective(order) for order in itertools.permutations(jobs))
    assert plan["objective"] == pytest.approx(optimum)
    assert plan["objective_se"] == 0


def test_discounted_density_is_not_claimed_to_be_optimal():
    rho = .25 / 52
    def objective(order):
        elapsed, result = 0, 0
        for effort, value in order:
            elapsed += effort
            result += value * (math.exp(-rho * elapsed) - math.exp(-rho * 52)) / rho
        return result
    assert 12.1 / 12 > 1 / 1
    assert objective([(1, 1), (12, 12.1)]) > objective([(12, 12.1), (1, 1)])


def test_unconditional_ship_quantiles_do_not_hide_noncompletion():
    plan = solve(simple_state([("too-large", 100, 10)]), as_of=AS_OF, scenarios=8, horizon_weeks=2)
    forecast = plan["forecast"]["too-large"]
    assert forecast == {"p50_ship_weeks": None, "p90_ship_weeks": None, "probability_shipped": 0}
    assert plan["objective"] == 0


def test_no_available_people_produces_idle_plan():
    state = simple_state([("a", 1, 10)])
    state.people["dana"]["availability"] = 0
    plan = solve(state, as_of=AS_OF, scenarios=8)
    assert plan["now"] == {}
    assert plan["forecast"]["a"]["probability_shipped"] == 0


def test_skill_and_availability_control_calendar_effort():
    state = simple_state([("a", 4, 10)])
    state.projects["a"]["skills"] = ["backend"]
    state.people["dana"].update(skills={"backend": 2}, availability=.5)
    plan = solve(state, as_of=AS_OF, scenarios=8)
    assert plan["forecast"]["a"]["p50_ship_weeks"] == pytest.approx(4)
    state.people["dana"]["skills"] = {}
    assert solve(state, as_of=AS_OF, scenarios=8)["now"] == {}


def test_shifted_remaining_estimate_is_not_refit_as_total_lognormal():
    d = Distribution.read({"p10": 2, "p50": 4, "p90": 8}, offset=6)
    assert d.remaining(6, .5) == pytest.approx(4)
    assert d.remaining(6, .9) == pytest.approx(8)
    assert d.remaining(7, .5) > 3


def test_exhausted_point_effort_requires_checkin():
    state = simple_state([("a", 1, 10)])
    state.work["a"] = {"status": "in_progress", "person": "dana", "spent": 2}
    with pytest.raises(LaylineError, match="check-in"):
        solve(state, as_of=AS_OF, scenarios=8)


def test_evaluation_time_cannot_precede_evidence():
    with pytest.raises(LaylineError, match="precedes"):
        solve(fold(team_events()), as_of="2026-11-01T00:00:00Z", scenarios=8)


@pytest.mark.parametrize("estimate", [{"p10": 9, "p50": 2, "p90": 3}, {"point": float("nan")}, {"point": True}, {"point": 1, "p50": 2}])
def test_invalid_estimates_are_rejected(estimate):
    with pytest.raises(LaylineError):
        Distribution.read(estimate)
