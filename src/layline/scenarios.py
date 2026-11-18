"""Replay authored scenarios through the same fold and planner used by the CLI."""
from __future__ import annotations

from .events import fold
from .model import require, timestamp
from .planner import solve


def run_scenario(document: dict, *, variant: str = "main", scenarios: int = 64, seed: int = 7) -> dict:
    require(document.get("schema_version") == 1, "Only scenario schema version 1 is supported.")
    require(variant == "main" or variant in document.get("variants", {}), f"Unknown scenario variant: {variant}.", "not_found")
    events = list(document["initial_events"])
    steps = document["steps"] if variant == "main" else document["variants"][variant]
    checkpoints, previous_plan = [], None
    for step in steps:
        events.extend(step.get("events", []))
        as_of = step["as_of"]
        require(all(timestamp(e["ts"]) <= timestamp(as_of) for e in events), "Scenario checkpoint precedes one of its events.")
        if step.get("accept"):
            require(previous_plan is not None, "Acceptance requires a previous plan.")
            events.append({"id": f"accept:{step['name']}", "v": 1, "ts": as_of, "type": "plan.accepted", "subject": previous_plan["id"], "actor": step["accept"], "data": {"plan_id": previous_plan["id"], "state_hash": previous_plan["state_hash"], "assignments": previous_plan["now"]}})
        state = fold(events)
        checkpoint = {"name": step["name"], "as_of": as_of, "anomalies": state.anomalies,
                      "questions": state.questions, "responses": state.responses, "work": state.work,
                      "commitments": state.commitments, "accepted": state.accepted,
                      "observation_count": len(state.observations), "state_hash": state.planning_hash()}
        if not state.anomalies:
            plan = solve(state, as_of=as_of, seed=seed, scenarios=scenarios, horizon_weeks=document.get("horizon_weeks", 52))
            checkpoint["plan"] = plan
            checkpoint["assignment_changes"] = [
                {"person": p, "from": (previous_plan or {}).get("now", {}).get(p), "to": plan["now"].get(p)}
                for p in sorted(state.people)
                if (previous_plan or {}).get("now", {}).get(p) != plan["now"].get(p)
            ]
            previous_plan = plan
        else:
            checkpoint["plan"] = None
        checkpoints.append(checkpoint)
    return {"name": document["name"], "variant": variant, "mode": "offline_design_replay", "checkpoints": checkpoints}
