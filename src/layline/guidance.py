"""Operator guidance shipped inside the package, independent of the checkout."""
from __future__ import annotations

from importlib.resources import files

from .model import LaylineError


def action(*args: str) -> dict:
    return {"argv": ["layline", *args], "mutates_state": False}


def skills() -> list[dict]:
    result = []
    for folder in sorted(files("layline").joinpath("skills").iterdir(), key=lambda p: p.name):
        entry = folder.joinpath("SKILL.md")
        if not folder.is_dir() or not entry.is_file():
            continue
        content = entry.read_text(encoding="utf-8")
        # Bundled frontmatter deliberately uses plain, single-line name/description.
        metadata = {}
        for line in content.split("---", 2)[1].splitlines():
            key, separator, value = line.partition(":")
            if separator:
                metadata[key.strip()] = value.strip()
        result.append({"name": folder.name, "description": metadata["description"], "read": action("skills", "show", folder.name)})
    return result


def skill(name: str) -> dict:
    catalog = {item["name"]: item for item in skills()}
    if name not in catalog:
        raise LaylineError("not_found", f"Unknown skill: {name}.", fix="layline skills list")
    return {**catalog[name], "markdown": files("layline").joinpath("skills", name, "SKILL.md").read_text(encoding="utf-8")}


def documents() -> dict[str, dict]:
    result = {}
    for path in sorted(files("layline").joinpath("docs_content").iterdir(), key=lambda p: p.name):
        if path.is_file() and path.name.endswith(".md"):
            markdown = path.read_text(encoding="utf-8")
            topic = path.name.removesuffix(".md")
            result[topic] = {"topic": topic, "title": markdown.splitlines()[0].lstrip("# "), "markdown": markdown}
    return result


def document(topic: str) -> dict:
    catalog = documents()
    if topic not in catalog:
        raise LaylineError("not_found", f"Unknown documentation topic: {topic}.", fix="layline docs list")
    return catalog[topic]


def search(query: str) -> dict:
    matches = []
    for topic, doc in documents().items():
        haystack = doc["title"] + "\n" + doc["markdown"]
        position = haystack.casefold().find(query.casefold())
        if position >= 0:
            matches.append({"topic": topic, "title": doc["title"], "excerpt": haystack[max(0, position - 80):position + 240], "read": action("docs", "show", topic)})
    return {"query": query, "matches": matches}


def guide() -> dict:
    return {
        "mode": "agent_led_planning",
        "purpose": "Build company context and evidence-backed engineer profiles, prepare an event input file, and explain a first baseline plan.",
        "how_to_use": "The calling agent asks the questions in chat and prepares files. CLI commands remain non-interactive and read-only.",
        "first_question": "Which company or team are we planning for, and which repositories or product and strategy docs should I use for context?",
        "research": "Read relevant company repositories, contributor history and company docs available to you. Draft engineer profiles with sources and distinguish observed experience from inferred skills. Confirm current roles, availability and priorities; commit counts do not measure productivity or speed. If sources are unavailable, continue with the user's account.",
        "workflow": ["company context and repository research", "engineer profiles and availability", "projects and scope", "effort and a shared value scale", "dependencies, current work and commitments", "prepare inputs and solve", "explain, correct and compare"],
        "instructions": "Read 'layline skills show plan-team', then begin the workflow with the user. Use information already supplied and ask only for missing details. Prepare the inputs and run the planner yourself; do not ask the user to write JSON or launch another agent.",
        "available_skills": skills(),
        "references": action("docs", "list"),
        "limits": "Local baseline planning only. No live surveys, automatic state writer, git synchronization, authenticated approvals, calibration, or policy search.",
    }


def render(command: str, data: dict) -> str:
    """Readable discovery output; computation and explicit --json stay structured."""
    if command == "guide":
        stages = "\n".join(f"  {i}. {stage.capitalize()}" for i, stage in enumerate(data["workflow"], 1))
        return (
            "Layline — plan your team's work\n\n"
            "Start here:\n"
            "  layline skills show plan-team\n\n"
            "If you are the agent helping the user, read that skill and follow it.\n"
            "Ask the questions in this conversation, prepare the inputs, and run\n"
            "the planner. No separate agent-launch command is needed.\n\n"
            f"First question:\n  {data['first_question']}\n\n"
            "Use details already provided; ask only for what is missing.\n\n"
            f"Build context:\n  {data['research']}\n\n"
            f"Then work through:\n{stages}\n\n"
            "References:\n"
            "  layline docs show context\n"
            "  layline docs show inputs\n"
            "  layline docs show results\n"
            "  layline docs show limits\n\n"
            "This command prints instructions; it does not wait for terminal input.\n"
            "Use --json on guidance commands when structured output is needed."
        )
    if "markdown" in data:
        markdown = data["markdown"]
        if command == "skills" and markdown.startswith("---\n"):
            markdown = markdown.split("---", 2)[2].lstrip()
        return markdown.rstrip()
    if "skills" in data:
        lines = ["Available skills", ""]
        for item in data["skills"]:
            lines.extend([f"{item['name']}: {item['description']}", f"  layline skills show {item['name']}", ""])
        return "\n".join(lines).rstrip()
    if "topics" in data:
        return "Documentation topics\n\n" + "\n".join(f"{item['topic']}: {item['title']}\n  layline docs show {item['topic']}" for item in data["topics"])
    matches = data["matches"]
    if not matches:
        return f"No documentation matches for {data['query']!r}.\nRun layline docs list to browse topics."
    return "\n\n".join(f"{item['topic']}: {item['title']}\n{item['excerpt']}\n  layline docs show {item['topic']}" for item in matches)
