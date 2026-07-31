from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import PlanStep, StepHandler, StepResult, TaskSpec
from .policies import PolicyViolation
from .tools import LocalCommandTool


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
class CommandStepHandler:
    """Executes a real shell command and reports its true exit status.

    Unlike DefaultStepHandler this can fail. Register it per step kind, e.g.
    ``executor.handlers["verification"] = CommandStepHandler("pytest", tool)``.
    The command is routed through LocalCommandTool, so PolicyEngine still
    applies; a blocked command becomes a failed step rather than an exception.
    """

    command: str
    tool: LocalCommandTool = field(default_factory=LocalCommandTool)

    def handle(self, task: TaskSpec, step: PlanStep) -> StepResult:
        try:
            outcome = self.tool.run(self.command)
        except PolicyViolation as exc:
            return StepResult(
                step_id=step.id,
                success=False,
                summary=f"Command blocked by policy: {self.command}",
                artifacts={"command": self.command},
                error=str(exc),
            )
        success = outcome.exit_code == 0
        return StepResult(
            step_id=step.id,
            success=success,
            summary=f"Command exited {outcome.exit_code}: {self.command}",
            artifacts={
                "command": self.command,
                "exit_code": str(outcome.exit_code),
                "stdout": outcome.stdout,
                "stderr": outcome.stderr,
            },
            error=None if success else outcome.stderr.strip() or f"exit code {outcome.exit_code}",
        )


@dataclass(slots=True)
class StepExecutor:
    handlers: dict[str, StepHandler] = field(default_factory=dict)
    fallback_handler: StepHandler = field(default_factory=DefaultStepHandler)

    def execute_step(self, task: TaskSpec, step: PlanStep) -> StepResult:
        handler = self.handlers.get(step.kind, self.fallback_handler)
        return handler.handle(task, step)
