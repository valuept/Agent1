from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

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
    domain: str = "general"
    constraints: list[str] = field(default_factory=list)

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
        if self.config.strict_mode:
            task.validate()
        task = self._apply_agent_constraints(task)
        plan = self.planner.create_plan(task)
        step_results: list[StepResult] = []
        for step in plan.steps[: self.config.max_iterations]:
            step.status = StepStatus.RUNNING
            result = self.executor.execute_step(task, step)
            step.status = StepStatus.DONE if result.success else StepStatus.FAILED
            step.notes = result.error or result.summary
            step_results.append(result)
            if not result.success:
                self.memory.append_run(task, step_results, context=self._audit_context(plan.strategy))
                return ExecutionResult(
                    success=False,
                    summary=f"Failed at step: {step.title}",
                    step_results=step_results,
                    blocked_reason=result.error,
                )

        self.memory.append_run(task, step_results, context=self._audit_context(plan.strategy))
        return ExecutionResult(
            success=True,
            summary="Plan executed successfully.",
            step_results=step_results,
        )

    def _apply_agent_constraints(self, task: TaskSpec) -> TaskSpec:
        """Merge the agent's own constraints into the task.

        Constraints declared on a blueprint apply to every task the agent runs,
        so they are prepended here. The caller's TaskSpec is never mutated.
        """
        if not self.constraints:
            return task
        merged = list(self.constraints)
        merged.extend(c for c in task.constraints if c not in merged)
        return dataclasses.replace(task, constraints=merged)

    def _audit_context(self, strategy: str) -> dict[str, str]:
        return {
            "domain": self.domain,
            "model_name": self.config.model_name,
            "strategy": strategy,
            "strict_mode": str(self.config.strict_mode).lower(),
        }
