from __future__ import annotations

from .contracts import Plan, PlanStep, TaskSpec


class BaselinePlanner:
    def create_plan(self, task: TaskSpec) -> Plan:
        constraints_note = " | ".join(task.constraints) if task.constraints else "No explicit constraints."
        steps = [
            PlanStep(
                id="analyze-scope",
                title="Analyze scope and constraints",
                kind="analysis",
                rationale=f"Understand objective boundaries. Constraints: {constraints_note}",
            ),
            PlanStep(
                id="design-approach",
                title="Design technical approach",
                kind="design",
                rationale="Choose architecture, interfaces, and sequencing before implementation.",
            ),
            PlanStep(
                id="implement-solution",
                title="Implement solution",
                kind="implementation",
                rationale="Produce the requested artifact(s) with deterministic behavior.",
            ),
            PlanStep(
                id="verify-outcome",
                title="Verify outcome",
                kind="verification",
                rationale="Confirm acceptance criteria and quality expectations are met.",
            ),
        ]
        return Plan(task=task, steps=steps, strategy="baseline-sequenced")
