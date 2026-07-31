"""Regression tests for contract fields that were previously declared but inert."""

import json
from pathlib import Path

import pytest

from agent0.builder import AgentBlueprint, AgentBuilder
from agent0.config import AgentConfig
from agent0.contracts import PlanStep, StepStatus, TaskSpec, TaskValidationError
from agent0.executor import CommandStepHandler
from agent0.planner import BaselinePlanner
from agent0.runtime import Agent0Runtime


def _runtime(tmp_path: Path, **config_kwargs: object) -> Agent0Runtime:
    config = AgentConfig(memory_path=tmp_path / "memory.jsonl", **config_kwargs)  # type: ignore[arg-type]
    return Agent0Runtime.default(config=config)


# --- TaskSpec.acceptance_criteria is read by the planner ---------------------


def test_planner_embeds_acceptance_criteria_in_verification_step() -> None:
    plan = BaselinePlanner().create_plan(
        TaskSpec(objective="Ship it", acceptance_criteria=["Tests pass", "Docs updated"])
    )
    verify = next(step for step in plan.steps if step.id == "verify-outcome")
    assert "Tests pass" in verify.rationale
    assert "Docs updated" in verify.rationale


def test_planner_handles_absent_acceptance_criteria() -> None:
    plan = BaselinePlanner().create_plan(TaskSpec(objective="Ship it"))
    verify = next(step for step in plan.steps if step.id == "verify-outcome")
    assert "No explicit acceptance criteria." in verify.rationale


# --- strict_mode drives TaskSpec validation ---------------------------------


def test_strict_mode_rejects_blank_objective(tmp_path: Path) -> None:
    with pytest.raises(TaskValidationError):
        _runtime(tmp_path).run(TaskSpec(objective="   "))


def test_strict_mode_rejects_blank_constraint(tmp_path: Path) -> None:
    with pytest.raises(TaskValidationError):
        _runtime(tmp_path).run(TaskSpec(objective="Ship it", constraints=["ok", ""]))


def test_non_strict_mode_accepts_malformed_task(tmp_path: Path) -> None:
    result = _runtime(tmp_path, strict_mode=False).run(TaskSpec(objective=""))
    assert result.success is True


# --- PlanStep.notes is populated during execution ---------------------------


def test_step_notes_are_written_after_execution(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    plan = runtime.planner.create_plan(TaskSpec(objective="Ship it"))
    assert all(step.notes == "" for step in plan.steps)

    runtime.planner = _FixedPlanner(plan)
    runtime.run(TaskSpec(objective="Ship it"))
    assert all(step.notes for step in plan.steps)
    assert all(step.status is StepStatus.DONE for step in plan.steps)


class _FixedPlanner:
    def __init__(self, plan: object) -> None:
        self.plan = plan

    def create_plan(self, task: TaskSpec) -> object:
        return self.plan


# --- Blueprint domain/constraints reach the runtime -------------------------


def test_blueprint_domain_and_constraints_are_applied(tmp_path: Path) -> None:
    builder = AgentBuilder(AgentConfig(memory_path=tmp_path / "memory.jsonl"))
    runtime = builder.build(
        AgentBlueprint(
            name="deployer",
            domain="deployment",
            constraints=["Never touch production without approval"],
        )
    )
    assert runtime.domain == "deployment"
    assert runtime.constraints == ["Never touch production without approval"]

    runtime.run(TaskSpec(objective="Roll out release", constraints=["Use blue/green"]))
    entry = json.loads(runtime.config.memory_path.read_text(encoding="utf-8").strip())
    # Agent-level constraints are merged ahead of task-level ones.
    assert entry["task"]["constraints"] == [
        "Never touch production without approval",
        "Use blue/green",
    ]


def test_agent_constraints_do_not_mutate_caller_task(tmp_path: Path) -> None:
    builder = AgentBuilder(AgentConfig(memory_path=tmp_path / "memory.jsonl"))
    runtime = builder.build(
        AgentBlueprint(name="deployer", domain="deployment", constraints=["Agent rule"])
    )
    task = TaskSpec(objective="Roll out release", constraints=["Task rule"])
    runtime.run(task)
    assert task.constraints == ["Task rule"]


# --- Plan.strategy / model_name / domain land in the audit trail ------------


def test_memory_records_audit_context(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.run(TaskSpec(objective="Ship it"))
    entry = runtime.memory.load_recent()[0]
    assert entry["context"]["strategy"] == "baseline-sequenced"
    assert entry["context"]["model_name"] == runtime.config.model_name
    assert entry["context"]["domain"] == "general"
    assert entry["context"]["strict_mode"] == "true"


# --- CommandStepHandler is a real, fallible handler -------------------------


def _step() -> PlanStep:
    return PlanStep(id="s", title="t", kind="verification", rationale="r")


def test_command_step_handler_reports_success_and_artifacts() -> None:
    result = CommandStepHandler("python --version").handle(TaskSpec(objective="check"), _step())
    assert result.success is True
    assert result.artifacts["exit_code"] == "0"
    assert "Python" in result.artifacts["stdout"] + result.artifacts["stderr"]


def test_command_step_handler_reports_real_failure() -> None:
    result = CommandStepHandler("definitely-not-a-real-binary-xyz").handle(
        TaskSpec(objective="check"), _step()
    )
    assert result.success is False
    assert result.artifacts["exit_code"] == "127"
    assert result.error


def test_command_step_handler_converts_policy_block_to_failed_step() -> None:
    result = CommandStepHandler("git reset --hard HEAD~5").handle(
        TaskSpec(objective="check"), _step()
    )
    assert result.success is False
    assert "policy" in result.summary.lower()
    assert "exit_code" not in result.artifacts


def test_runtime_fails_plan_when_command_step_fails(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.executor.handlers["verification"] = CommandStepHandler("git reset --hard HEAD~5")
    result = runtime.run(TaskSpec(objective="Ship it"))
    assert result.success is False
    assert result.blocked_reason
    assert len(result.step_results) == 4
