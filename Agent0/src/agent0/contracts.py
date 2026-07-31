from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskValidationError(ValueError):
    """Raised when a TaskSpec fails validation under strict mode."""


@dataclass(slots=True)
class TaskSpec:
    objective: str
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """Check the task is well-formed. Raises TaskValidationError.

        Called by Agent0Runtime.run() when config.strict_mode is True.
        """
        if not self.objective or not self.objective.strip():
            raise TaskValidationError("objective must be a non-empty string")
        for label, values in (
            ("constraints", self.constraints),
            ("acceptance_criteria", self.acceptance_criteria),
        ):
            for index, value in enumerate(values):
                if not isinstance(value, str) or not value.strip():
                    raise TaskValidationError(
                        f"{label}[{index}] must be a non-empty string (got {value!r})"
                    )


@dataclass(slots=True)
class PlanStep:
    id: str
    title: str
    kind: str
    rationale: str
    status: StepStatus = StepStatus.PENDING
    notes: str = ""


@dataclass(slots=True)
class Plan:
    task: TaskSpec
    steps: list[PlanStep]
    strategy: str


@dataclass(slots=True)
class StepResult:
    step_id: str
    success: bool
    summary: str
    artifacts: dict[str, str] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    summary: str
    step_results: list[StepResult]
    blocked_reason: str | None = None


class Planner(Protocol):
    def create_plan(self, task: TaskSpec) -> Plan:
        ...


class StepHandler(Protocol):
    def handle(self, task: TaskSpec, step: PlanStep) -> StepResult:
        ...
