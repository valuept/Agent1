from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


@dataclass(slots=True)
class PolicyEngine:
    blocked_command_patterns: list[str] = field(
        default_factory=lambda: [
            r"\brm\s+-rf\b",
            r"\bdel\s+\/f\b",
            r"\bformat\s+[a-z]:\b",
            r"\bgit\s+reset\s+--hard\b",
        ]
    )

    def evaluate_command(self, command: str) -> PolicyDecision:
        for pattern in self.blocked_command_patterns:
            if re.search(pattern, command, flags=re.IGNORECASE):
                return PolicyDecision(allowed=False, reason=f"Blocked by policy pattern: {pattern}")
        return PolicyDecision(allowed=True)
