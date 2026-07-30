from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import shlex
import subprocess


@dataclass(slots=True)
class ToolResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str


class LocalCommandTool:
    def __init__(self, timeout_seconds: int = 120) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, command: str) -> ToolResult:
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
