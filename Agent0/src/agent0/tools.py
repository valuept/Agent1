from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import shlex
import subprocess

from .policies import PolicyEngine


@dataclass(slots=True)
class ToolResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str


class LocalCommandTool:
    def __init__(
        self,
        timeout_seconds: int = 120,
        policies: PolicyEngine | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        # Secure by default: an unconfigured tool still enforces the baseline
        # blocklist. Pass an explicit engine to extend or relax it.
        self.policies = policies if policies is not None else PolicyEngine()

    def run(self, command: str) -> ToolResult:
        # Enforce before anything is spawned; raises PolicyViolation on refusal.
        self.policies.enforce_command(command)
        started_at = datetime.now(UTC).isoformat()
        argv = shlex.split(command, posix=False)
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            shell=False,
            check=False,
        )
        finished_at = datetime.now(UTC).isoformat()
        return ToolResult(
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started_at,
            finished_at=finished_at,
        )
