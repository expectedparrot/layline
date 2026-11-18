from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

from .events import fold
from .model import LaylineError, canonical
from .planner import SOLVER_METHOD, SOLVER_VERSION, solve
from .scenarios import run_scenario
from . import guidance


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise LaylineError("usage_error", message, fix="layline --help")


def parser() -> Parser:
    p = Parser(description="Layline planning prototype. Start with 'layline guide' for agent-led setup. Commands are non-interactive and read-only.")
    p.add_argument("--json", action="store_true", help="Return JSON for guidance commands; planning commands always return JSON.")
    subs = p.add_subparsers(dest="command", required=True)
    guide = subs.add_parser("guide", help="Show the agent's path from team setup to a first plan.")
    guide.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Return structured guidance.")
    skill_commands = subs.add_parser("skills", help="Discover bundled operator skills.")
    skill_subs = skill_commands.add_subparsers(dest="skill_command", required=True)
    skill_list = skill_subs.add_parser("list", help="List skill names and when to use them.")
    skill_show = skill_subs.add_parser("show", help="Read a skill's full instructions.")
    skill_show.add_argument("name")
    docs = subs.add_parser("docs", help="Read and search bundled operator references.")
    doc_subs = docs.add_subparsers(dest="docs_command", required=True)
    doc_list = doc_subs.add_parser("list", help="List reference topics.")
    doc_show = doc_subs.add_parser("show", help="Read a reference topic.")
    doc_show.add_argument("topic")
    doc_search = doc_subs.add_parser("search", help="Search reference text.")
    doc_search.add_argument("query")
    for sub in (skill_commands, skill_list, skill_show, docs, doc_list, doc_show, doc_search):
        sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Return structured guidance.")
    demo = subs.add_parser("demo", help="Replay the bundled three-person, eight-project example.")
    demo.add_argument("--variant", default="main")
    demo.add_argument("--list", action="store_true", help="List available variants.")
    replay = subs.add_parser("replay", help="Replay an authored scenario JSON file.")
    replay.add_argument("path", type=Path)
    replay.add_argument("--variant", default="main")
    solving = subs.add_parser("solve", help="Fold a JSON event array and produce a baseline plan.")
    solving.add_argument("path", type=Path)
    solving.add_argument("--as-of", required=True)
    solving.add_argument("--horizon-weeks", type=float, default=52)
    for sub in (demo, replay, solving):
        sub.add_argument("--scenarios", type=int, default=64)
        sub.add_argument("--seed", type=int, default=7)
        sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    subs.add_parser("schema", help="Describe the prototype's implemented interfaces and boundaries.")
    return p


def read(path: Path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise LaylineError("not_found", f"File not found: {path}") from exc


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        next_steps = []
        if args.command == "guide":
            data = guidance.guide()
            next_steps = [guidance.action("skills", "show", "plan-team")]
        elif args.command == "skills":
            data = {"skills": guidance.skills()} if args.skill_command == "list" else guidance.skill(args.name)
        elif args.command == "docs":
            if args.docs_command == "list":
                data = {"topics": [{"topic": name, "title": doc["title"], "read": guidance.action("docs", "show", name)} for name, doc in guidance.documents().items()]}
            elif args.docs_command == "show":
                data = guidance.document(args.topic)
            else:
                data = guidance.search(args.query)
        elif args.command == "schema":
            data = {"schema_version": 1, "mode": "prototype", "implemented": ["guide", "skills list", "skills show", "docs list", "docs show", "docs search", "demo", "replay", "solve", "schema"], "scenario": {"required": ["schema_version", "name", "initial_events", "steps"], "optional": ["variants", "horizon_weeks"]}, "event": {"required": ["v", "id", "ts", "actor", "type", "subject", "data"]}, "not_implemented": ["durable writes", "git sync", "authenticated approvals", "survey delivery", "automatic question selection", "calibration", "policy search", "live EDSL adapter"]}
            data["solver"] = {"version": SOLVER_VERSION, **SOLVER_METHOD, "people_limit": None, "open_project_limit": None}
        elif args.command in {"demo", "replay"}:
            document = json.loads(files("layline").joinpath("examples/team.json").read_text()) if args.command == "demo" else read(args.path)
            if getattr(args, "list", False):
                data = {"variants": ["main", *sorted(document.get("variants", {}))]}
            else:
                data = run_scenario(document, variant=args.variant, scenarios=args.scenarios, seed=args.seed)
        else:
            from .model import require, timestamp
            events = read(args.path)
            require(isinstance(events, list), "solve expects a JSON array of events.")
            state = fold(events)
            if state.anomalies:
                raise LaylineError("replay_conflict", canonical(state.anomalies))
            require(all(timestamp(e["ts"]) <= timestamp(args.as_of) for e in events), "Evaluation time precedes an event.")
            data = solve(state, as_of=args.as_of, scenarios=args.scenarios, seed=args.seed, horizon_weeks=args.horizon_weeks)
        warnings = data.get("warnings", [])
        if "checkpoints" in data:
            warnings = [{"checkpoint": c["name"], **a} for c in data["checkpoints"] for a in c["anomalies"]]
        if args.command in {"guide", "skills", "docs"} and not args.json:
            print(guidance.render(args.command, data))
        else:
            print(canonical({"ok": True, "data": data, "warnings": warnings, "next": next_steps}))
        return 0
    except LaylineError as exc:
        print(canonical({"ok": False, "error": {"code": exc.code, "message": str(exc), "fix": exc.fix}}))
        return {"usage_error": 2, "not_found": 3, "approval_required": 5}.get(exc.code, 4)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, OverflowError) as exc:
        print(canonical({"ok": False, "error": {"code": "invalid_input", "message": str(exc), "fix": "Check the scenario/event JSON and required fields."}}))
        return 4
    except Exception as exc:
        print(canonical({"ok": False, "error": {"code": "unexpected_failure", "message": str(exc), "fix": "Report this failure with the input fixture."}}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
