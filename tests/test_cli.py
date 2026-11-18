import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def run_command(*args, cwd=None):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    return subprocess.run([sys.executable, "-m", "layline", *args], cwd=cwd, env=env, text=True, capture_output=True)


def invoke(*args, cwd=None):
    result = run_command("--json", *args, cwd=cwd)
    payload = json.loads(result.stdout)
    assert result.stderr == ""
    return result, payload


def test_demo_is_json_and_does_not_write_to_callers_directory(tmp_path):
    result, data = invoke("demo", "--scenarios", "8", cwd=tmp_path)
    assert result.returncode == 0
    assert data["ok"]
    assert data["data"]["mode"] == "offline_design_replay"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("args,code", [([], 2), (["bogus"], 2), (["solve", "missing.json"], 2), (["solve", "missing.json", "--as-of", "2026-11-20T00:00:00Z"], 3), (["demo", "--scenarios", "bad"], 2), (["demo", "--scenarios", "0"], 4)])
def test_failures_have_one_json_envelope(args, code):
    result, data = invoke(*args)
    assert result.returncode == code
    assert data["ok"] is False
    assert data["error"]["code"]


def test_variants_and_schema_report_actual_capabilities():
    _, result = invoke("demo", "--list")
    assert "scope-change" in result["data"]["variants"]
    _, result = invoke("schema")
    assert "live EDSL adapter" in result["data"]["not_implemented"]


def test_conflict_demo_reports_anomaly_without_crashing():
    result, data = invoke("demo", "--variant", "concurrent-assignment", "--scenarios", "8")
    assert result.returncode == 0  # Successful replay of an intentionally conflicting scenario.
    assert data["warnings"][0]["code"] == "assignment_conflict"
    assert data["data"]["checkpoints"][-1]["plan"] is None


def test_guide_routes_to_readable_skill_outside_checkout(tmp_path):
    result, payload = invoke("guide", cwd=tmp_path)
    assert result.returncode == 0
    action = payload["next"][0]
    assert action["mutates_state"] is False
    result, skill = invoke(*action["argv"][1:], cwd=tmp_path)
    assert result.returncode == 0
    assert skill["data"]["name"] == "plan-team"
    assert skill["data"]["markdown"].startswith("---\nname: plan-team\n")
    assert list(tmp_path.iterdir()) == []


def test_all_discovered_resources_have_working_read_actions(tmp_path):
    for command, key in [("skills", "skills"), ("docs", "topics")]:
        result, payload = invoke(command, "list", cwd=tmp_path)
        assert result.returncode == 0
        assert payload["data"][key]
        for resource in payload["data"][key]:
            read_result, content = invoke(*resource["read"]["argv"][1:], cwd=tmp_path)
            assert read_result.returncode == 0
            assert content["data"]["markdown"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command,name", [("skills", "unknown"), ("skills", "../../AGENTS.md"), ("docs", "unknown"), ("docs", "/etc/passwd")])
def test_guidance_looks_up_only_bundled_catalog(command, name):
    result, payload = invoke(command, "show", name)
    assert result.returncode == 3
    assert payload["error"]["fix"] == f"layline {command} list"


def test_docs_search_is_case_insensitive_and_returns_readable_matches():
    _, lower = invoke("docs", "search", "remaining effort")
    _, upper = invoke("docs", "search", "REMAINING EFFORT")
    assert lower["data"]["matches"] == upper["data"]["matches"]
    assert lower["data"]["matches"]
    for match in lower["data"]["matches"]:
        result, _ = invoke(*match["read"]["argv"][1:])
        assert result.returncode == 0
    _, no_matches = invoke("docs", "search", "phrase-that-is-not-in-these-docs-9375")
    assert no_matches["data"]["matches"] == []


def test_documented_input_produces_a_plan(tmp_path):
    _, reference = invoke("docs", "show", "inputs", cwd=tmp_path)
    example = reference["data"]["markdown"].split("```json\n", 1)[1].split("```", 1)[0]
    path = tmp_path / "my team's inputs.json"
    path.write_text(json.dumps(json.loads(example)))
    result, payload = invoke("solve", str(path), "--as-of", "2026-11-20T18:00:00Z", "--scenarios", "8", cwd=tmp_path)
    assert result.returncode == 0
    assert payload["data"]["now"] == {"dana": "billing"}
    assert payload["data"]["tentative"] is False
    assert payload["data"]["queue"][0]["evidence"]["effort"]["observations"] == ["003"]


def test_plain_guide_is_readable_and_its_commands_work(tmp_path):
    import shlex

    result = run_command("guide", cwd=tmp_path)
    assert result.returncode == 0
    assert not result.stderr
    assert not result.stdout.startswith("{")
    commands = [line.strip() for line in result.stdout.splitlines() if line.strip().startswith("layline ")]
    assert commands
    for command in commands:
        followup = run_command(*shlex.split(command)[1:], cwd=tmp_path)
        assert followup.returncode == 0
        assert not followup.stdout.startswith("{")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command", [("guide",), ("skills", "show", "plan-team"), ("docs", "show", "inputs"), ("docs", "search", "effort")])
def test_json_flag_works_before_and_after_guidance_commands(command):
    before = run_command("--json", *command)
    after = run_command(*command, "--json")
    assert before.returncode == after.returncode == 0
    assert json.loads(before.stdout) == json.loads(after.stdout)


def test_json_flag_survives_nested_subparser_defaults():
    grouped = run_command("skills", "--json", "show", "plan-team")
    assert grouped.returncode == 0
    assert json.loads(grouped.stdout)["data"]["name"] == "plan-team"


def test_skill_prints_instructions_without_json_or_frontmatter():
    result = run_command("skills", "show", "plan-team")
    assert result.returncode == 0
    assert result.stdout.startswith("# Plan a team with Layline\n")


def test_planning_still_defaults_to_json():
    result = run_command("demo", "--list")
    assert result.returncode == 0
    assert json.loads(result.stdout)["ok"] is True
