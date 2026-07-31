from __future__ import annotations

from dataclasses import dataclass

from .config import AgentConfig
from .contracts import ExecutionResult, StepResult, StepStatus, TaskSpec
from .executor import StepExecutor
from .memory import MemoryStore
from .planner import BaselinePlanner
from .policies import PolicyEngine
from .tools import LocalCommandTool


@dataclass(slots=True)
class Agent0Runtime:
    config: AgentConfig
    planner: BaselinePlanner
    executor: StepExecutor
    policies: PolicyEngine
    memory: MemoryStore

    @classmethod
    def default(cls, config: AgentConfig | None = None) -> "Agent0Runtime":
        effective_config = config or AgentConfig.from_env()
        return cls(
            config=effective_config,
            planner=BaselinePlanner(),
            executor=StepExecutor(),
            policies=PolicyEngine(),
            memory=MemoryStore(effective_config.memory_path),
        )

    def create_tool(self) -> LocalCommandTool:
        """Build a command tool bound to this runtime's timeout and policies.

        Step handlers should obtain their tool from here rather than
        constructing one directly, so the runtime's policy set is always the
        one enforced.
        """
        return LocalCommandTool(
            timeout_seconds=self.config.command_timeout_seconds,
            policies=self.policies,
        )

    def run(self, task: TaskSpec) -> ExecutionResult:
        plan = self.planner.create_plan(task)
        step_results: list[StepResult] = []
        for step in plan.steps[: self.config.max_iterations]:
            step.status = StepStatus.RUNNING
            result = self.executor.execute_step(task, step)
            step.status = StepStatus.DONE if result.success else StepStatus.FAILED
            step_results.append(result)
            if not result.success:
                self.memory.append_run(task, step_results)
                return ExecutionResult(
                    success=False,
                    summary=f"Failed at step: {step.title}",
                    step_results=step_results,
                    blocked_reason=result.error,
                )

        self.memory.append_run(task, step_results)
        return ExecutionResult(
            success=True,
            summary="Plan executed successfully.",
            step_results=step_results,
        )
