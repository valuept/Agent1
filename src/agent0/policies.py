"""Policy guardrails and the tools they guard.

`PolicyEngine` holds the rules (preserved from the original Agent0).
`PolicyHook` enforces them on every tool command via `before_tool_run`;
a violation raises `PolicyViolation`, aborting the operation before it runs.
`LocalCommandTool` is the one built-in capability, always hook-routed.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

DEFAULT_BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+\/f\b",
    r"\bformat\s+[a-z]:\b",
    r"\bgit\s+reset\s+--hard\b",
]


class PolicyViolation(PermissionError):
    """Raised when a policy blocks an operation."""


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


@dataclass(slots=True)
class PolicyEngine:
    blocked_command_patterns: list[str] = field(
        default_factory=lambda: list(DEFAULT_BLOCKED_COMMAND_PATTERNS)
    )

    def evaluate_command(self, command: str) -> PolicyDecision:
        for pattern in self.blocked_command_patterns:
            if re.search(pattern, command, flags=re.IGNORECASE):
                return PolicyDecision(allowed=False, reason=f"Blocked by policy pattern: {pattern}")
        return PolicyDecision(allowed=True)

    def validate_patterns(self) -> list[str]:
        """Return error strings for any pattern that does not compile."""
        errors = []
        for pattern in self.blocked_command_patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"Invalid policy pattern {pattern!r}: {exc}")
        return errors


class PolicyHook:
    """Hook adapter: enforces the policy engine on tool commands."""

    def __init__(self, engine: PolicyEngine | None = None) -> None:
        self.engine = engine or PolicyEngine()

    def before_tool_run(self, tool: str, command: str, run_id: str = "", **_: Any) -> None:
        decision = self.engine.evaluate_command(command)
        if not decision.allowed:
            raise PolicyViolation(f"Tool '{tool}' command blocked: {decision.reason}")


@dataclass(slots=True)
class ToolResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str


class LocalCommandTool:
    """`hook_manager` is any object with .call(event, **kwargs) — kept duck-typed
    so this module has no framework imports."""

    name = "local_command"

    def __init__(self, hook_manager: Any = None, timeout_seconds: int = 120) -> None:
        self.hook_manager = hook_manager
        self.timeout_seconds = timeout_seconds

    def _call(self, event: str, **kwargs: Any) -> None:
        if self.hook_manager is not None:
            self.hook_manager.call(event, **kwargs)

    def run(self, command: str, run_id: str = "") -> ToolResult:
        self._call("before_tool_run", tool=self.name, command=command, run_id=run_id)
        started_at = datetime.now(UTC).isoformat()
        completed = subprocess.run(
            shlex.split(command, posix=False),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            shell=False,
            check=False,
        )
        result = ToolResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
        )
        self._call("after_tool_run", tool=self.name, command=command, run_id=run_id, result=result)
        return result
