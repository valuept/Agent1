from __future__ import annotations

from dataclasses import dataclass, field
import re


class PolicyViolation(PermissionError):
    """Raised when a command is refused by the policy engine.

    Subclasses PermissionError so callers that already handle OS-level
    permission failures treat a policy refusal the same way.
    """


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

    def enforce_command(self, command: str) -> None:
        decision = self.evaluate_command(command)
        if not decision.allowed:
            raise PolicyViolation(f"{decision.reason} (command: {command!r})")
