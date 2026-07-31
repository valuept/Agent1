from pathlib import Path

import pytest

from agent0.config import AgentConfig
from agent0.policies import PolicyEngine, PolicyViolation
from agent0.runtime import Agent0Runtime
from agent0.tools import LocalCommandTool


def test_tool_blocks_dangerous_command_before_execution() -> None:
    tool = LocalCommandTool()
    with pytest.raises(PolicyViolation):
        tool.run("git reset --hard HEAD")


def test_tool_is_guarded_by_default() -> None:
    # An unconfigured tool must still enforce the baseline blocklist.
    assert LocalCommandTool().policies.blocked_command_patterns


def test_tool_runs_allowed_command() -> None:
    # NOTE: shlex.split(posix=False) preserves quote characters, so avoid
    # quoted arguments here - see the manual's Limitations section.
    tool = LocalCommandTool(timeout_seconds=30)
    result = tool.run("python --version")

    assert result.exit_code == 0
    assert "Python" in result.stdout


def test_tool_honours_custom_policy_patterns() -> None:
    engine = PolicyEngine()
    engine.blocked_command_patterns.append(r"\bterraform\s+destroy\b")
    tool = LocalCommandTool(policies=engine)

    with pytest.raises(PolicyViolation):
        tool.run("terraform destroy -auto-approve")


def test_runtime_create_tool_wires_config_and_policies(tmp_path: Path) -> None:
    config = AgentConfig(memory_path=tmp_path / "memory.jsonl", command_timeout_seconds=7)
    runtime = Agent0Runtime.default(config=config)
    tool = runtime.create_tool()

    assert tool.timeout_seconds == 7
    assert tool.policies is runtime.policies


def test_tool_returns_timeout_result_instead_of_raising() -> None:
    # A hung child (here, the interactive REPL) must become a recorded failure,
    # not an exception that aborts the run before anything is written to memory.
    tool = LocalCommandTool(timeout_seconds=2)
    result = tool.run("python -X ignored")

    assert result.exit_code == 124
    assert "timed out" in result.stderr


def test_tool_returns_not_found_result_instead_of_raising() -> None:
    tool = LocalCommandTool(timeout_seconds=10)
    result = tool.run("definitely-not-a-real-binary-xyz")

    assert result.exit_code == 127
    assert result.stderr


def test_enforce_command_allows_safe_command() -> None:
    PolicyEngine().enforce_command("pytest -q")
