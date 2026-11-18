from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import NormalDist
from typing import Any


class LaylineError(ValueError):
    def __init__(self, code: str, message: str, *, fix: str | None = None):
        super().__init__(message)
        self.code, self.fix = code, fix


def require(condition: bool, message: str, code: str = "validation_error") -> None:
    if not condition:
        raise LaylineError(code, message)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Timestamps must include a timezone.")
    return parsed


def number(value: Any, *, minimum: float = 0) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), "Expected a number.")
    require(math.isfinite(value) and value >= minimum, f"Expected a finite number >= {minimum}.")
    return float(value)


@dataclass(frozen=True)
class Distribution:
    """Point or lognormal, optionally shifted by effort already spent."""

    mu: float = 0
    sigma: float = 0
    point: float | None = None
    offset: float = 0

    @classmethod
    def read(cls, data: dict, *, positive: bool = False, offset: float = 0) -> Distribution:
        if "point" in data:
            require(not any(k in data for k in ("p10", "p50", "p90")), "Use a point or three quantiles, not both.")
            point = number(data["point"])
            require(not positive or point > 0, "Effort must be positive.")
            return cls(point=point, offset=offset)
        low, middle, high = (number(data[k]) for k in ("p10", "p50", "p90"))
        require(0 < low <= middle <= high, "Require 0 < p10 <= p50 <= p90.")
        return cls(math.log(middle), (math.log(high) - math.log(low)) / (2 * NormalDist().inv_cdf(.9)), offset=offset)

    def quantile(self, probability: float) -> float:
        if self.point is not None:
            return self.offset + self.point
        return self.offset + math.exp(self.mu + self.sigma * NormalDist().inv_cdf(probability))

    def remaining(self, spent: float, probability: float) -> float:
        """Quantile of total - spent, conditional on total > spent."""
        if self.point is not None or self.sigma == 0:
            result = self.quantile(.5) - spent
            require(result > 0, "Unfinished work has exhausted a point effort estimate; record a remaining-effort check-in.")
            return result
        threshold = spent - self.offset
        cdf = 0 if threshold <= 0 else NormalDist().cdf((math.log(threshold) - self.mu) / self.sigma)
        require(cdf < 1 - 1e-12, "Effort is too far beyond this estimate; record a remaining-effort check-in.")
        p = min(1 - 1e-15, cdf + (1 - cdf) * probability)
        return self.quantile(p) - spent


@dataclass
class State:
    people: dict[str, dict] = field(default_factory=dict)
    projects: dict[str, dict] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    observations: dict[str, dict] = field(default_factory=dict)
    questions: dict[str, dict] = field(default_factory=dict)
    responses: dict[str, dict] = field(default_factory=dict)
    commitments: dict[str, str] = field(default_factory=dict)
    work: dict[str, dict] = field(default_factory=dict)
    accepted: dict | None = None
    latest_event_at: str | None = None
    anomalies: list[dict] = field(default_factory=list)

    def planning_data(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k not in {"questions", "responses", "accepted", "anomalies", "latest_event_at"}}

    def planning_hash(self) -> str:
        return digest(self.planning_data())


def eligible(state: State, person: str, project: str) -> bool:
    p, j = state.people[person], state.projects[project]
    return p["availability"] > 0 and all(p["skills"].get(skill, 0) > 0 for skill in j["skills"])


def speed(state: State, person: str, project: str) -> float:
    p, j = state.people[person], state.projects[project]
    return p["availability"] * min((p["skills"].get(skill, 0) for skill in j["skills"]), default=1)


def is_open(state: State, project: str) -> bool:
    return state.work.get(project, {}).get("status") not in {"shipped", "abandoned", "descoped"}
