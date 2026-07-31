from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .contracts import StepResult, TaskSpec


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_run(
        self,
        task: TaskSpec,
        step_results: list[StepResult],
        context: dict[str, str] | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "context": context or {},
            "task": asdict(task),
            "steps": [asdict(step) for step in step_results],
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def load_recent(self, limit: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return []
        selected = lines[-limit:]
        return [json.loads(line) for line in selected]
