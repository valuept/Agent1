from __future__ import annotations

from dataclasses import dataclass, field

from .config import AgentConfig
from .executor import StepExecutor
from .memory import MemoryStore
from .planner import BaselinePlanner
from .policies import PolicyEngine
from .runtime import Agent1Runtime


@dataclass(slots=True)
class AgentBlueprint:
    name: str
    domain: str
    constraints: list[str] = field(default_factory=list)
    blocked_command_patterns: list[str] = field(default_factory=list)
    max_iterations: int | None = None


class AgentBuilder:
    def __init__(self, base_config: AgentConfig | None = None) -> None:
        self.base_config = base_config or AgentConfig.from_env()

    def build(self, blueprint: AgentBlueprint) -> Agent1Runtime:
        config = AgentConfig(
            model_name=self.base_config.model_name,
            max_iterations=blueprint.max_iterations or self.base_config.max_iterations,
            strict_mode=self.base_config.strict_mode,
            memory_path=self.base_config.memory_path.parent / f"{blueprint.name}_memory.jsonl",
            command_timeout_seconds=self.base_config.command_timeout_seconds,
        )
        policies = PolicyEngine()
        if blueprint.blocked_command_patterns:
            policies.blocked_command_patterns.extend(blueprint.blocked_command_patterns)
        return Agent1Runtime(
            config=config,
            planner=BaselinePlanner(),
            executor=StepExecutor(),
            policies=policies,
            memory=MemoryStore(config.memory_path),
        )
