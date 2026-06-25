from pathlib import Path

from agent0.config import AgentConfig
from agent0.contracts import TaskSpec
from agent0.runtime import Agent0Runtime


def test_runtime_executes_full_plan(tmp_path: Path) -> None:
    config = AgentConfig(memory_path=tmp_path / "memory.jsonl")
    runtime = Agent0Runtime.default(config=config)
    result = runtime.run(
        TaskSpec(
            objective="Create baseline standards for deployment automation",
            constraints=["Use secure defaults"],
            acceptance_criteria=["Define deterministic process"],
        )
    )

    assert result.success is True
    assert len(result.step_results) == 4
    assert config.memory_path.exists()
