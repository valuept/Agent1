from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AgentConfig:
    model_name: str = "gpt-5.3-codex"
    max_iterations: int = 12
    strict_mode: bool = True
    memory_path: Path = Path(".agent1") / "memory.jsonl"
    command_timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            model_name=os.getenv("AGENT1_MODEL", "gpt-5.3-codex"),
            max_iterations=int(os.getenv("AGENT1_MAX_ITERATIONS", "12")),
            strict_mode=os.getenv("AGENT1_STRICT_MODE", "true").lower() == "true",
            memory_path=Path(os.getenv("AGENT1_MEMORY_PATH", ".agent1\\memory.jsonl")),
            command_timeout_seconds=int(os.getenv("AGENT1_COMMAND_TIMEOUT", "120")),
        )
