from copy import deepcopy
from importlib.resources import files
import json

import pytest

from layline.events import fold
from layline.scenarios import run_scenario


@pytest.fixture
def team():
    return json.loads(files("layline").joinpath("examples/team.json").read_text())


def replay(team, variant="main"):
    return {c["name"]: c for c in run_scenario(team, variant=variant, scenarios=8)["checkpoints"]}


def test_answer_changes_assignment_without_breaking_commitment(team):
    result = replay(team)
    assert result["initial-plan"]["plan"]["now"] == {"dana": "platform", "priya": "exports", "lee": "onboarding"}
    assert result["late-completed-answer"]["plan"]["now"] == {"dana": "billing", "priya": "exports", "lee": "onboarding"}
    assert all(c["plan"]["now"]["priya"] == "exports" for c in result.values())
    assert result["late-completed-answer"]["assignment_changes"] == [{"person": "dana", "from": "platform", "to": "billing"}]


def test_acceptance_is_not_a_work_start(team):
    result = replay(team)
    accepted = result["accept-does-not-start-work"]
    assert accepted["accepted"]["assignments"]["dana"] == "billing"
    assert "billing" not in accepted["work"]
    assert result["work-started"]["work"]["billing"]["status"] == "in_progress"


def test_checkin_preserves_remaining_distribution_and_does_not_preempt(team):
    result = replay(team)
    checkin = result["overrun-checkin"]
    billing = next(j for j in checkin["plan"]["queue"] if j["project"] == "billing")
    assert billing["remaining_effort_p50"] == pytest.approx(6)
    assert billing["evidence"]["effort"]["offset"] == 2
    assert checkin["plan"]["now"]["dana"] == "billing"
    assert result["explicit-pause"]["plan"]["now"]["dana"] == "platform"


def test_abandoned_effort_is_not_a_completion_actual(team):
    events = team["initial_events"] + [e for s in team["steps"] for e in s["events"]]
    state = fold(events)
    assert not state.anomalies
    assert state.work["billing"]["spent"] == 2
    assert state.work["billing"]["calibration_eligible"] is False
    assert not any(o["source"] == "actual" for o in state.observations.values())


def test_shipped_effort_is_an_actual(team):
    steps = team["variants"]["shipped"]
    state = fold(team["initial_events"] + [e for s in steps for e in s["events"]])
    assert not state.anomalies
    actuals = [o for o in state.observations.values() if o["source"] == "actual"]
    assert len(actuals) == 1
    assert actuals[0]["estimate"] == {"point": 3}
    assert state.work["billing"]["calibration_eligible"]


def test_duplicate_download_is_noop_and_correction_needs_review(team):
    result = replay(team, "duplicate-and-corrected-answer")
    first, duplicate, correction = (result[name] for name in ["late-completed-answer", "duplicate-download", "correction-needs-review"])
    assert first["observation_count"] == duplicate["observation_count"] == correction["observation_count"]
    assert first["state_hash"] == duplicate["state_hash"] == correction["state_hash"]
    assert any(r.get("reason") == "changed_response" for r in correction["responses"].values())


def test_scope_change_excludes_old_evidence_and_holds_answer(team):
    result = replay(team, "scope-change")
    final = result["late-completed-answer"]
    assert final["plan"]["now"]["dana"] == "platform"
    assert final["plan"]["tentative"]
    assert final["observation_count"] == result["initial-plan"]["observation_count"]
    assert any(r.get("reason") == "stale_scope" for r in final["responses"].values())
    assert any(w["code"] == "prior_used" for w in final["plan"]["warnings"])


def test_partial_invalid_then_valid_response(team):
    result = replay(team, "partial-and-invalid-answer")
    for name, status in [("partial-response", "in_progress"), ("invalid-complete-response", "rejected")]:
        assert list(result[name]["responses"].values())[0]["status"] == status
        assert result[name]["questions"]["q-billing"]["status"] == "sent"
        assert result[name]["observation_count"] == 16
    assert result["late-completed-answer"]["observation_count"] == 17


@pytest.mark.parametrize("variant,code", [("concurrent-assignment", "assignment_conflict"), ("stale-acceptance", "stale_plan")])
def test_conflicts_block_new_plan(team, variant, code):
    final = list(replay(team, variant).values())[-1]
    assert final["plan"] is None
    assert any(a["code"] == code for a in final["anomalies"])


def test_agent_cannot_accept_plan(team):
    team = deepcopy(team)
    team["steps"] = team["steps"][:4]
    team["steps"][-1]["accept"] = "agent:planner"
    last = list(replay(team).values())[-1]
    assert last["accepted"] is None
    assert last["anomalies"][0]["code"] == "approval_required"
