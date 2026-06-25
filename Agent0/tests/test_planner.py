from agent0.contracts import TaskSpec
from agent0.planner import BaselinePlanner


def test_planner_returns_standard_step_order() -> None:
    planner = BaselinePlanner()
    plan = planner.create_plan(TaskSpec(objective="Build an internal deployment agent"))

    assert plan.strategy == "baseline-sequenced"
    assert [step.id for step in plan.steps] == [
        "analyze-scope",
        "design-approach",
        "implement-solution",
        "verify-outcome",
    ]
