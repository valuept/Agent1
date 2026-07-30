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


@dataclass(slots=True)
class TaskSpec:
    objective: str
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


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
