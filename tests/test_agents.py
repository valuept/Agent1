"""Agent packages: scaffold, load, run, update, and the test harness."""

import json

import pytest

from agent0 import factory as factory_module
from agent0.factory import (
    SCAFFOLD_STATE_FILE,
    AgentLoadError,
    ScaffoldError,
    build_session,
    create_agent,
    format_report,
    load_agent,
    run_agent,
    update_agent,
    update_all,
)
from agent0.factory import test_agent as harness_test_agent
from agent0.factory import test_all as harness_test_all
from agent0.core import FINAL_OUTPUT


@pytest.fixture()
def agent_root(tmp_path):
    return create_agent("demo-agent", tmp_path, purpose="Demo agent for tests.")


def test_scaffold_validates_and_refuses_overwrite(tmp_path, agent_root):
    with pytest.raises(ScaffoldError, match="Invalid agent name"):
        create_agent("Bad Name!", tmp_path)
    with pytest.raises(ScaffoldError, match="already exists"):
        create_agent("demo-agent", tmp_path)
    definition = load_agent(agent_root)
    assert definition.name == "demo-agent" and len(definition.steps) == 4


def test_generated_agent_runs_end_to_end(agent_root):
    definition = load_agent(agent_root)
    input_doc = json.loads((agent_root / "tests/inputs/example.json").read_text(encoding="utf-8"))
    result = run_agent(definition, input_doc)
    assert result.success is True
    assert result.outputs[FINAL_OUTPUT]["step_id"] == "finalize"
    assert (agent_root / "memory" / "runs.jsonl").exists()  # audit record


def test_contract_violations_rejected(agent_root):
    definition = load_agent(agent_root)
    result = run_agent(definition, {"priority": "urgent"})
    assert result.success is False and "input contract violation" in result.blocked_reason


def test_load_rejects_missing_skill_and_broken_dag(agent_root):
    manifest = (agent_root / "agent.toml").read_text(encoding="utf-8")
    (agent_root / "agent.toml").write_text(
        manifest.replace('inputs = ["design", "risks"]', 'inputs = ["design", "phantom"]'),
        encoding="utf-8",
    )
    with pytest.raises(AgentLoadError, match="phantom"):
        load_agent(agent_root)
    (agent_root / "agent.toml").write_text(manifest, encoding="utf-8")
    (agent_root / "skills" / "normalize.md").unlink()
    with pytest.raises(AgentLoadError, match="skill file not found"):
        load_agent(agent_root)


def test_conf_layers_override_manifest(agent_root):
    (agent_root / "conf" / "local.toml").write_text("[runtime]\nmax_iterations = 2\n", encoding="utf-8")
    definition = load_agent(agent_root)
    assert definition.config.max_iterations == 2
    input_doc = json.loads((agent_root / "tests/inputs/example.json").read_text(encoding="utf-8"))
    assert run_agent(definition, input_doc).blocked_reason == "max_iterations exceeded"


def test_shared_root_env_var_wires_catalog(tmp_path, monkeypatch):
    shared = tmp_path / "org-shared"
    monkeypatch.setenv("AGENT0_SHARED_ROOT", str(shared))
    agent_root = create_agent("sharing-agent", tmp_path)
    manifest = (agent_root / "agent.toml").read_text(encoding="utf-8")
    manifest += '\n[catalog.org-knowledge]\ntype = "jsonl"\nfilepath = "knowledge.jsonl"\nscope = "shared"\n'
    (agent_root / "agent.toml").write_text(manifest, encoding="utf-8")
    session = build_session(load_agent(agent_root))
    assert str(shared) in str(session.catalog.get("org-knowledge").filepath)


def test_update_noop_skip_restore(agent_root):
    report = update_agent(agent_root)
    assert not report.updated and not report.restored and not report.skipped_modified

    (agent_root / "skills" / "design.md").write_text("customized", encoding="utf-8")
    (agent_root / "README.md").unlink()
    report = update_agent(agent_root)
    assert "skills/design.md" in report.skipped_modified
    assert "README.md" in report.restored
    assert (agent_root / "skills" / "design.md").read_text(encoding="utf-8") == "customized"


def test_update_applies_new_templates_only_to_unmodified_files(agent_root, monkeypatch):
    original = factory_module.render_files

    def newer(name, purpose):
        rendered = original(name, purpose)
        rendered["skills/risks.md"] += "\n## New framework section\n"
        rendered["skills/normalize.md"] += "\n## New framework section\n"
        return rendered

    (agent_root / "skills" / "normalize.md").write_text("customized", encoding="utf-8")
    monkeypatch.setattr(factory_module, "render_files", newer)
    report = update_agent(agent_root)
    assert "skills/risks.md" in report.updated
    assert "skills/normalize.md" in report.skipped_modified


def test_update_requires_state_and_sweeps_fleet(tmp_path, agent_root):
    (agent_root / SCAFFOLD_STATE_FILE).unlink()
    with pytest.raises(ScaffoldError, match="predates update support"):
        update_agent(agent_root)

    create_agent("agent-one", tmp_path / "fleet")
    create_agent("agent-two", tmp_path / "fleet" / "nested")
    (tmp_path / "fleet" / "agent-one" / "README.md").unlink()
    reports = update_all(tmp_path / "fleet")
    assert len(reports) == 2
    assert "README.md" in reports[0].restored


def test_harness_fresh_agent_passes_everything(agent_root):
    report = harness_test_agent(agent_root)
    assert {c.name for c in report.cases} == {"happy-path", "policy-block"}
    assert report.passed, format_report(report)
    # isolation: no run artifacts leaked into real agent memory
    assert not (agent_root / "memory" / "runs.jsonl").exists()


def test_harness_detects_broken_manifest_and_unblocked_probe(agent_root):
    cases = (agent_root / "tests" / "cases.toml").read_text(encoding="utf-8")
    (agent_root / "tests" / "cases.toml").write_text(
        cases.replace('probe_command = "rm -rf /"', 'probe_command = "python --version"'),
        encoding="utf-8",
    )
    report = harness_test_agent(agent_root)
    assert not next(c for c in report.cases if c.name == "policy-block").passed

    manifest = (agent_root / "agent.toml").read_text(encoding="utf-8")
    (agent_root / "agent.toml").write_text(
        manifest.replace('outputs = ["final_output"]', 'outputs = ["not_final"]'), encoding="utf-8"
    )
    report = harness_test_agent(agent_root)
    assert not report.passed
    assert any("final_output" in c.detail for c in report.conformance if not c.passed)


def test_harness_fleet(tmp_path):
    create_agent("agent-one", tmp_path)
    create_agent("agent-two", tmp_path / "nested")
    reports = harness_test_all(tmp_path)
    assert len(reports) == 2 and all(r.passed for r in reports)
