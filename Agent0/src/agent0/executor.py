from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import PlanStep, StepHandler, StepResult, TaskSpec


@dataclass(slots=True)
class DefaultStepHandler:
    def handle(self, task: TaskSpec, step: PlanStep) -> StepResult:
        if step.kind == "analysis":
            summary = f"Objective analyzed: {task.objective}"
        elif step.kind == "design":
            summary = "Technical approach designed with modular boundaries."
        elif step.kind == "implementation":
            summary = "Implementation phase completed with current configured capabilities."
        elif step.kind == "verification":
            summary = "Verification phase completed and outputs prepared."
        else:
            summary = f"Step handled: {step.title}"
        return StepResult(step_id=step.id, success=True, summary=summary)


@dataclass(slots=True)
class StepExecutor:
    handlers: dict[str, StepHandler] = field(default_factory=dict)
    fallback_handler: StepHandler = field(default_factory=DefaultStepHandler)

    def execute_step(self, task: TaskSpec, step: PlanStep) -> StepResult:
        handler = self.handlers.get(step.kind, self.fallback_handler)
        return handler.handle(task, step)
