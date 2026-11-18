"""Pure replay for the scenario prototype; this is not a durable repository writer."""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from .model import Distribution, LaylineError, State, canonical, digest, eligible, is_open, number, require, timestamp


def human(event: dict) -> None:
    require(event["actor"].startswith("human:"), "This transition needs a human actor.", "approval_required")


def known(state: State, collection: str, key: str) -> dict:
    items = getattr(state, collection)
    require(key in items, f"Unknown {collection} id: {key}.", "not_found")
    return items[key]


def observation(state: State, event: dict, data: dict, *, identifier: str | None = None) -> None:
    project = known(state, "projects", data["project"])
    require(data["quantity"] in {"effort", "value_rate"}, "Supported quantities are effort and value_rate.")
    require(data["source"] in {"human", "agent", "survey", "actual"}, "Unsupported observation source.")
    require(isinstance(data["scope_revision"], str), "An estimate must identify its scope revision.")
    require(bool(data["by"]), "An observation needs an estimator identity.")
    if data["source"] != "agent":
        known(state, "people", data["by"])
    basis = data.get("basis", "total")
    require(basis in {"total", "remaining"}, "Unknown effort basis.")
    require(basis == "total" or data["quantity"] == "effort", "Only effort can have a remaining basis.")
    if basis == "remaining":
        number(data["spent"])
    Distribution.read(data["estimate"], positive=data["quantity"] == "effort" and data["source"] != "actual")
    # Keep stale evidence for audit; the belief builder filters by scope revision.
    state.observations[identifier or event["id"]] = {
        **deepcopy(data), "basis": basis, "ts": event["ts"], "event_id": event["id"],
        "project_name": project["name"],
    }


def has_cycle(edges: list[tuple[str, str]]) -> bool:
    nodes = {v for edge in edges for v in edge}
    done: set[str] = set()
    while nodes - done:
        ready = {n for n in nodes - done if all(a in done for a, b in edges if b == n)}
        if not ready:
            return True
        done |= ready
    return False


def apply(state: State, e: dict) -> None:
    kind, key, d = e["type"], e["subject"], e["data"]
    if kind == "person.defined":
        require(key not in state.people, f"Person {key} already exists.")
        availability = number(d.get("availability", 1))
        require(availability <= 1, "Availability must be between 0 and 1.")
        require(isinstance(d.get("skills", {}), dict), "Person skills must map names to speed multipliers.")
        skills = {k: number(v) for k, v in d.get("skills", {}).items()}
        state.people[key] = {"name": d["name"], "skills": skills, "availability": availability, "internal": d.get("internal", True)}
    elif kind == "person.availability_changed":
        person = known(state, "people", key)
        availability = number(d["availability"])
        require(availability <= 1, "Availability must be between 0 and 1.")
        person["availability"] = availability
    elif kind == "project.defined":
        require(key not in state.projects, f"Project {key} already exists.")
        require(d.get("kind", "feature") == "feature", "This prototype supports feature projects only.")
        if d.get("owner"):
            known(state, "people", d["owner"])
        require(isinstance(d.get("skills", []), list), "Project skills must be a list.")
        state.projects[key] = {"name": d["name"], "skills": sorted(set(d.get("skills", []))), "owner": d.get("owner"), "scope_revision": d.get("scope_revision", e["id"])}
    elif kind == "project.scope_changed":
        p = known(state, "projects", key)
        require(bool(d["reason"]), "A scope change needs a reason.")
        p["scope_revision"] = e["id"]
        if "name" in d:
            p["name"] = d["name"]
    elif kind == "edge.added":
        human(e)
        require(d.get("type", "hard") == "hard", "This prototype supports hard dependencies only.")
        src, dst = d["src"], d["dst"]
        known(state, "projects", src)
        known(state, "projects", dst)
        edges = sorted(set(state.edges + [(src, dst)]))
        require(not has_cycle(edges), "Dependency creates a cycle.", "dependency_cycle")
        state.edges = edges
    elif kind == "observation.recorded":
        require(d["source"] not in {"actual", "survey"}, "Actuals and survey observations must come through closure or answer ingestion.")
        if d["source"] == "human":
            require(e["actor"] == f"human:{d['by']}", "Human estimates must be attributed to their actor.")
        observation(state, e, d)
    elif kind == "observation.retracted":
        known(state, "observations", key)
        require(bool(d["reason"]), "A retraction needs a reason.")
        state.observations[key]["retracted"] = True
    elif kind == "commitment.set":
        human(e)
        known(state, "people", key)
        project = d["project"]
        known(state, "projects", project)
        require(bool(d["reason"]), "A commitment needs a reason.")
        require(is_open(state, project), "Cannot commit to closed work.")
        require(eligible(state, key, project), "Person is not available or lacks a required skill.")
        require(key not in state.commitments, "Release an existing commitment before replacing it.")
        require(project not in state.commitments.values(), "Project already has a commitment.")
        require(all(w.get("person") != key or p == project or w["status"] != "in_progress" for p, w in state.work.items()), "Pause conflicting work before setting a commitment.")
        active = state.work.get(project, {})
        require(active.get("status") != "in_progress" or active["person"] == key, "Project is already assigned to another person.")
        state.commitments[key] = project
    elif kind == "commitment.released":
        human(e)
        require(key in state.commitments, "No commitment to release.")
        require(bool(d["reason"]), "A release needs a reason.")
        del state.commitments[key]
    elif kind in {"work.started", "work.resumed"}:
        known(state, "projects", key)
        person = d["person"]
        known(state, "people", person)
        current = state.work.get(key, {})
        require(is_open(state, key) and current.get("status") != "in_progress", "Project is closed or already in progress.")
        require(eligible(state, person, key), "Person is not available or lacks a required skill.")
        require(all(w.get("person") != person or w["status"] != "in_progress" for w in state.work.values()), "Person is already working on another project.", "assignment_conflict")
        require(state.commitments.get(person, key) == key, "Assignment conflicts with a commitment.")
        require(all(p == person or j != key for p, j in state.commitments.items()), "Project is committed to another person.")
        require(all(state.work.get(src, {}).get("status") == "shipped" for src, dst in state.edges if dst == key), "A hard prerequisite has not shipped.")
        state.work[key] = {**current, "status": "in_progress", "person": person, "spent": current.get("spent", 0)}
    elif kind == "work.paused":
        w = known(state, "work", key)
        require(w["status"] == "in_progress", "Only active work can be paused.")
        require(bool(d["reason"]), "A pause needs a reason.")
        w["status"] = "paused"
    elif kind == "work.checkin":
        w = known(state, "work", key)
        p = known(state, "projects", key)
        require(w["status"] in {"in_progress", "paused"}, "Cannot check in on closed work.")
        spent = number(d["spent"])
        require(spent >= w["spent"], "Cumulative effort cannot go backwards.")
        require(d["scope_revision"] == p["scope_revision"], "Check-in describes an old scope.", "stale_scope")
        require(e["actor"] == f"human:{w['person']}", "Check-in must come from the assigned person.")
        observation(state, e, {"project": key, "quantity": "effort", "source": "human", "by": w["person"], "scope_revision": p["scope_revision"], "basis": "remaining", "spent": spent, "estimate": d["remaining"]})
        w["spent"] = spent
    elif kind == "work.closed":
        human(e)
        p = known(state, "projects", key)
        require(is_open(state, key), "Project is already closed.")
        if p["owner"]:
            require(e["actor"] == f"human:{p['owner']}", "Closure needs the project owner's confirmation.", "approval_required")
        outcome = d["outcome"]
        require(outcome in {"shipped", "abandoned", "descoped"}, "Invalid closure outcome.")
        spent = number(d["actual_effort"])
        require(spent >= state.work.get(key, {}).get("spent", 0), "Closure effort cannot be below previously recorded effort.")
        state.work[key] = {**state.work.get(key, {}), "status": outcome, "spent": spent, "calibration_eligible": outcome == "shipped", "scope_revision": p["scope_revision"]}
        if outcome == "shipped":
            observation(state, e, {"project": key, "quantity": "effort", "source": "actual", "by": e["actor"].removeprefix("human:"), "scope_revision": p["scope_revision"], "estimate": {"point": spent}}, identifier=f"{e['id']}:actual")
        state.commitments = {person: project for person, project in state.commitments.items() if project != key}
    elif kind == "question.proposed":
        require(key not in state.questions, "Question already exists.")
        project = known(state, "projects", d["project"])
        known(state, "people", d["person"])
        require(d["scope_revision"] == project["scope_revision"], "Question describes an old scope.", "stale_scope")
        require(d["quantity"] in {"effort", "value_rate"}, "Unsupported quantity.")
        require(bool(d["prompt"]), "Question needs a prompt.")
        require(timestamp(d["expires_at"]) > timestamp(e["ts"]), "Question is already expired.")
        state.questions[key] = {**deepcopy(d), "status": "proposed", "approved": False}
    elif kind == "question.approved":
        human(e)
        q = known(state, "questions", key)
        require(q["status"] == "proposed", "Only proposed questions can be approved.")
        q["approved"] = True
    elif kind == "question.sent":
        q = known(state, "questions", key)
        require(q["status"] == "proposed", "Question has already been sent.")
        require(timestamp(e["ts"]) < timestamp(q["expires_at"]), "Question is expired.")
        require(state.projects[q["project"]]["scope_revision"] == q["scope_revision"], "Question describes an old scope.", "stale_scope")
        require(state.people[q["person"]]["internal"] or q["approved"], "External questions need approval.", "approval_required")
        q["status"] = "sent"
    elif kind == "answer.ingested":
        ingest(state, e)
    elif kind == "plan.accepted":
        human(e)
        require(d["state_hash"] == state.planning_hash(), "Plan inputs changed before acceptance.", "stale_plan")
        require(isinstance(d["assignments"], dict), "Plan assignments must be a mapping.")
        require(len(set(d["assignments"].values())) == len(d["assignments"]), "Plan assigns a project twice.")
        for person, project in d["assignments"].items():
            known(state, "people", person)
            known(state, "projects", project)
            require(eligible(state, person, project) and is_open(state, project), "Invalid accepted assignment.")
            require(all(state.work.get(src, {}).get("status") == "shipped" for src, dst in state.edges if dst == project), "Accepted assignment has an unfinished prerequisite.")
            require(state.commitments.get(person, project) == project, "Accepted assignment breaks a commitment.")
            require(all(p == person or j != project for p, j in state.commitments.items()), "Accepted project is committed to another person.")
        for project, work in state.work.items():
            if work["status"] == "in_progress" and eligible(state, work["person"], project):
                require(d["assignments"].get(work["person"]) == project, "Pause existing work before accepting a different assignment.")
        state.accepted = deepcopy(d)
    else:
        raise LaylineError("unsupported_event", f"Unsupported event type: {kind}.")


def ingest(state: State, e: dict) -> None:
    """Normalize one complete answer without treating repeated downloads as evidence."""
    d = e["data"]
    q = known(state, "questions", e["subject"])
    require(q["status"] in {"sent", "answered"}, "Question has not been sent.")
    require(d["person"] == q["person"], "Response belongs to another respondent.")
    require(isinstance(d["response_id"], str) and bool(d["response_id"]), "Response needs a stable id.")
    response_key = canonical([e["subject"], d["response_id"]])
    fingerprint = digest(d)
    if state.responses.get(response_key, {}).get("fingerprint") == fingerprint:
        return
    result = {"fingerprint": fingerprint, "question": e["subject"], "response_id": d["response_id"]}
    status = d.get("status", "complete")
    require(status in {"complete", "in_progress"}, "Unknown response status.")
    previous = state.responses.get(response_key)
    if previous and previous["status"] == "accepted":
        # Corrections are held for explicit review; they do not replace accepted evidence.
        state.responses[f"{response_key}:revision:{fingerprint}"] = {**result, "status": "needs_review", "reason": "changed_response"}
        return
    if status != "complete":
        state.responses[response_key] = {**result, "status": "in_progress"}
        return
    if q["scope_revision"] != state.projects[q["project"]]["scope_revision"]:
        state.responses[response_key] = {**result, "status": "needs_review", "reason": "stale_scope"}
        return
    if timestamp(e["ts"]) >= timestamp(q["expires_at"]):
        state.responses[response_key] = {**result, "status": "needs_review", "reason": "expired_question"}
        return
    if q["status"] == "answered":
        state.responses[response_key] = {**result, "status": "needs_review", "reason": "already_answered"}
        return
    try:
        require("point" not in d["answer"], "This question requires p10, p50 and p90.")
        Distribution.read(d["answer"], positive=q["quantity"] == "effort")
    except (KeyError, TypeError, ValueError) as exc:
        state.responses[response_key] = {**result, "status": "rejected", "reason": str(exc)}
        return
    observation(state, e, {"project": q["project"], "quantity": q["quantity"], "scope_revision": q["scope_revision"], "source": "survey", "by": q["person"], "estimate": d["answer"], "question": e["subject"], "response_id": d["response_id"]})
    state.responses[response_key] = {**result, "status": "accepted"}
    q["status"] = "answered"


def fold(events: Iterable[dict]) -> State:
    """Order-independent replay; reject invalid transitions and report every rejection."""
    state = State()
    unique: dict[str, dict] = {}
    collisions: set[str] = set()
    anomalies: list[dict] = []
    for event in events:
        try:
            require(isinstance(event, dict), "Event must be an object.")
            require(event.get("v") == 1, "Only event schema version 1 is supported.")
            for field in ("id", "ts", "actor", "type", "subject"):
                require(isinstance(event.get(field), str) and bool(event[field]), f"Event needs {field}.")
            require(isinstance(event.get("data"), dict), "Event data must be an object.")
            timestamp(event["ts"])
            canonical(event)
            identifier = event["id"]
            if identifier in unique and unique[identifier] != event:
                collisions.add(identifier)
            unique[identifier] = event
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            anomalies.append({"code": "invalid_event", "message": str(exc)})
    for identifier in sorted(collisions):
        unique.pop(identifier)
        anomalies.append({"code": "duplicate_id", "event_id": identifier, "message": "Conflicting events share an id; neither was applied."})
    for e in sorted(unique.values(), key=lambda event: (timestamp(event["ts"]), event["id"])):
        candidate = deepcopy(state)
        try:
            apply(candidate, e)
            candidate.latest_event_at = e["ts"]
            state = candidate
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            anomalies.append({"code": getattr(exc, "code", "invalid_event"), "event_id": e["id"], "message": str(exc)})
    state.anomalies = sorted(anomalies, key=canonical)
    return state
