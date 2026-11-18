"""Bounded baseline planner for small, executable design scenarios.

Ranks hard-prerequisite closed sets exactly, matches free people exactly, then
simulates that fixed priority policy. It does not optimize the full schedule.
"""
from __future__ import annotations

import math
import random
from itertools import combinations
from statistics import fmean, stdev

from .model import Distribution, State, digest, eligible, is_open, number, require, speed, timestamp

SOLVER_VERSION = "baseline-prototype-1"
MAX_PROJECTS = 12
MAX_PEOPLE = 6


def belief(state: State, project: str, quantity: str, as_of: str) -> tuple[Distribution, dict]:
    current_scope = state.projects[project]["scope_revision"]
    all_rows = [o for o in state.observations.values() if o["project"] == project and o["quantity"] == quantity and not o.get("retracted")]
    rows = [o for o in all_rows if o["scope_revision"] == current_scope]
    warnings = ["stale_observations_excluded"] if len(rows) != len(all_rows) else []
    detail = {"quantity": f"{quantity}:{project}", "scope_revision": current_scope, "warnings": warnings}
    if not rows:
        # Priors are illustrative, explicit, and make the result tentative.
        prior = {"p10": 1, "p50": 4, "p90": 16} if quantity == "effort" else {"p10": .25, "p50": 1, "p90": 4}
        return Distribution.read(prior), {**detail, "method": "prior", "observations": [], "warnings": warnings + ["prior_used"]}
    ordered = sorted(rows, key=lambda o: (timestamp(o["ts"]), o["event_id"]))
    actual = [o for o in ordered if o["source"] == "actual"]
    remaining = [o for o in ordered if o.get("basis") == "remaining"]
    if actual or remaining:
        chosen = (actual or remaining)[-1]
        offset = chosen.get("spent", 0) if chosen.get("basis") == "remaining" else 0
        distribution = Distribution.read(chosen["estimate"], offset=offset)
        return distribution, {**detail, "method": "actual" if actual else "remaining_checkin", "observations": [chosen["event_id"]], "offset": offset}
    # One current estimate per estimator. Distinct agents must have distinct identities.
    latest = {o["by"]: o for o in ordered}
    rows = [latest[person] for person in sorted(latest)]
    distributions = [Distribution.read(o["estimate"]) for o in rows]
    if all(d.point == 0 for d in distributions):
        return Distribution(point=0), {**detail, "method": "zero", "observations": [o["event_id"] for o in rows]}
    require(all(d.point != 0 for d in distributions), "Pooling zero and positive value estimates needs a mixture model; this prototype cannot do it.")
    weights = []
    for row in rows:
        age = (timestamp(as_of) - timestamp(row["ts"])).total_seconds() / 86400
        require(age >= 0, "Evaluation time precedes an observation.")
        weights.append((.25 if row["source"] == "agent" else 1) * 2 ** (-age / 60))
    require(sum(weights) > 0, "All observation weights underflowed; refresh the estimates.")
    weights = [w / sum(weights) for w in weights]
    mus = [math.log(d.point) if d.point is not None else d.mu for d in distributions]
    mu = sum(w * m for w, m in zip(weights, mus))
    variance = sum(w * (d.sigma ** 2 + (m - mu) ** 2) for w, m, d in zip(weights, mus, distributions))
    return Distribution(mu, math.sqrt(variance)), {
        **detail, "method": "log_pool", "observations": [o["event_id"] for o in rows],
        "agent_only": all(o["source"] == "agent" for o in rows),
    }


def closed_set_densities(state: State, projects: list[str], effort: dict[str, float], value: dict[str, float]) -> tuple[dict[str, float], dict[str, list[str]]]:
    remaining = set(projects)
    densities, groups = {}, {}
    while remaining:
        best, best_ratio = (), -1.0
        ordered = sorted(remaining)
        for size in range(1, len(ordered) + 1):
            for subset in combinations(ordered, size):
                members = set(subset)
                if any(dst in members and src in remaining and src not in members for src, dst in state.edges):
                    continue
                ratio = sum(value[j] for j in subset) / sum(effort[j] for j in subset)
                if ratio > best_ratio + 1e-12 or (abs(ratio - best_ratio) <= 1e-12 and subset < best):
                    best, best_ratio = subset, ratio
        require(bool(best), "No valid closed set; check dependencies.")
        for project in best:
            densities[project], groups[project] = best_ratio, list(best)
        remaining.difference_update(best)
    return densities, groups


def match(state: State, people: list[str], ready: list[str], priorities: dict[str, float]) -> dict[str, str]:
    best_score, best = 0.0, {}

    def visit(index: int, remaining: list[str], current: dict[str, str], score: float) -> None:
        nonlocal best_score, best
        if index == len(people):
            if score > best_score + 1e-12 or (score > 0 and abs(score - best_score) <= 1e-12 and tuple(sorted(current.items())) < tuple(sorted(best.items()))):
                best_score, best = score, dict(current)
            return
        person = people[index]
        visit(index + 1, remaining, current, score)
        for project in remaining:
            if eligible(state, person, project) and priorities[project] > 0:
                current[person] = project
                visit(index + 1, [p for p in remaining if p != project], current, score + priorities[project] * speed(state, person, project))
                del current[person]

    visit(0, ready, {}, 0)
    return best


def simulate(state: State, projects: list[str], durations: dict[str, float], values: dict[str, float], priorities: dict[str, float], horizon: float, rho: float) -> dict:
    completed = {j for j, w in state.work.items() if w["status"] == "shipped"}
    pending = set(projects)
    running: dict[str, tuple[str, float]] = {}
    reservations = {p: j for p, j in state.commitments.items() if j in pending}
    for j, w in state.work.items():
        if w["status"] == "in_progress" and j in pending:
            person = w["person"]
            require(person not in reservations or reservations[person] == j, "Active work conflicts with a commitment.")
            require(j not in reservations.values() or reservations.get(person) == j, "Active work conflicts with another person's commitment.")
            reservations[person] = j
    clock, objective = 0.0, 0.0
    now, finishes, starts = {}, {}, {}
    while clock < horizon:
        ready = sorted(j for j in pending if all(src in completed for src, dst in state.edges if dst == j))
        free = sorted(p for p in state.people if p not in running)
        assignments = {}
        for person in free:
            project = reservations.get(person)
            if project in ready and eligible(state, person, project):
                assignments[person] = project
        optional_people = [p for p in free if p not in reservations]
        optional_projects = [j for j in ready if j not in reservations.values()]
        assignments.update(match(state, optional_people, optional_projects, priorities))
        for person, project in sorted(assignments.items()):
            running[person] = (project, clock + durations[project] / speed(state, person, project))
            starts[project] = clock
            pending.remove(project)
        if clock == 0:
            now = dict(assignments)
        if not running:
            break
        clock = min(finish for _, finish in running.values())
        if clock > horizon:
            break
        for person, (project, finish) in list(running.items()):
            if abs(finish - clock) > 1e-12:
                continue
            completed.add(project)
            finishes[project] = clock
            del running[person]
            reservations.pop(person, None)
            reward = horizon - clock if rho == 0 else (math.exp(-rho * clock) - math.exp(-rho * horizon)) / rho
            objective += values[project] * reward
    return {"now": now, "finishes": finishes, "starts": starts, "objective": objective}


def empirical_quantile(values: list[float], p: float, total: int) -> float | None:
    index = math.ceil(p * total) - 1
    return sorted(values)[index] if index < len(values) else None


def solve(state: State, *, as_of: str, seed: int = 7, scenarios: int = 128, horizon_weeks: float = 52, discount_rate_annual: float = .25) -> dict:
    timestamp(as_of)
    require(state.latest_event_at is None or timestamp(state.latest_event_at) <= timestamp(as_of), "Evaluation time precedes an event.")
    require(not state.anomalies, "Replay has anomalies; resolve them before planning.", "replay_conflict")
    require(isinstance(seed, int) and not isinstance(seed, bool), "Seed must be an integer.")
    require(isinstance(scenarios, int) and not isinstance(scenarios, bool) and 2 <= scenarios <= 10000, "Scenarios must be an integer between 2 and 10000.")
    horizon = number(horizon_weeks)
    require(horizon > 0, "Horizon must be positive.")
    rho = number(discount_rate_annual) / 52
    projects = sorted(j for j in state.projects if is_open(state, j))
    require(len(projects) <= MAX_PROJECTS and len(state.people) <= MAX_PEOPLE, f"Prototype is limited to {MAX_PROJECTS} open projects and {MAX_PEOPLE} people.")
    efforts, values, details, warnings = {}, {}, {}, []
    for j in projects:
        efforts[j], effort_info = belief(state, j, "effort", as_of)
        values[j], value_info = belief(state, j, "value_rate", as_of)
        details[j] = {"effort": effort_info, "value_rate": value_info}
        warnings.extend({"code": code, "quantity": info["quantity"]} for info in details[j].values() for code in info["warnings"])
        if any(info.get("agent_only") for info in details[j].values()):
            warnings.append({"code": "agent_only_evidence", "project": j})
    spent = {j: state.work.get(j, {}).get("spent", 0) for j in projects}
    medians = {j: efforts[j].remaining(spent[j], .5) for j in projects}
    value_medians = {j: values[j].quantile(.5) for j in projects}
    density, groups = closed_set_densities(state, projects, medians, value_medians)
    baseline = simulate(state, projects, medians, value_medians, density, horizon, rho)
    draws = []
    for index in range(scenarios):
        # Separate stable streams prevent unrelated projects from shifting existing draws.
        effort_draws, value_draws = {}, {}
        for j in projects:
            rng = random.Random(digest([seed, index, j]))
            effort_draws[j] = efforts[j].remaining(spent[j], max(1e-15, rng.random()))
            value_draws[j] = values[j].quantile(max(1e-15, rng.random()))
        draws.append(simulate(state, projects, effort_draws, value_draws, density, horizon, rho))
    forecasts = {}
    for j in projects:
        finishes = [d["finishes"][j] for d in draws if j in d["finishes"]]
        forecasts[j] = {
            "p50_ship_weeks": empirical_quantile(finishes, .5, scenarios),
            "p90_ship_weeks": empirical_quantile(finishes, .9, scenarios),
            "probability_shipped": len(finishes) / scenarios,
        }
        if not finishes:
            warnings.append({"code": "not_scheduled_within_horizon", "project": j})
    params = {"as_of": as_of, "seed": seed, "scenarios": scenarios, "horizon_weeks": horizon, "discount_rate_annual": discount_rate_annual}
    objectives = [d["objective"] for d in draws]
    result = {
        "solver_version": SOLVER_VERSION, "state_hash": state.planning_hash(),
        "inputs_hash": digest({"state": state.planning_data(), "params": params, "solver_version": SOLVER_VERSION}),
        "params": params, "now": baseline["now"],
        "queue": [{"project": j, "density": density[j], "closed_set": groups[j], "remaining_effort_p50": medians[j], "value_rate_p50": value_medians[j], "evidence": details[j]} for j in sorted(projects, key=lambda j: (-density[j], j))],
        "forecast": forecasts, "objective": fmean(objectives), "objective_se": stdev(objectives) / math.sqrt(scenarios),
        "tentative": bool(warnings), "warnings": warnings,
        "limitations": ["Fixed baseline policy; no policy search or value-of-information calculation.", "One person per project, hard dependencies only, no automatic preemption.", "No calibration; closed-set priorities use medians, not an optimal discounted schedule.", "Ship quantiles are unconditional; null means the percentile exceeds the modeled horizon."],
    }
    result["id"] = digest(result)[:24]
    return result
