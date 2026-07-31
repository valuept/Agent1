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
        # Policy violations raise because they are a safety error, not a runtime
        # outcome. Runtime failures below are returned as results instead, so an
        # unattended run records them in memory rather than crashing.
        self.policies.enforce_command(command)
        started_at = datetime.now(UTC).isoformat()
        argv = shlex.split(command, posix=False)
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
                # Never inherit the parent's stdin: a child must not be able to
                # consume the agent's own input stream. Note this cannot stop a
                # process that opens the console directly (e.g. the CPython
                # REPL on Windows) - the timeout is the backstop for those.
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            return self._result(
                command,
                # 124 is the conventional timeout exit code (GNU coreutils).
                exit_code=124,
                stdout=_as_text(exc.stdout),
                stderr=f"Command timed out after {self.timeout_seconds}s.",
                started_at=started_at,
            )
        except (FileNotFoundError, NotADirectoryError) as exc:
            return self._result(
                command,
                # 127 is the conventional "command not found" exit code.
                exit_code=127,
                stdout="",
                stderr=str(exc),
                started_at=started_at,
            )
        return self._result(
            command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started_at,
        )

    @staticmethod
    def _result(
        command: str, *, exit_code: int, stdout: str, stderr: str, started_at: str
    ) -> ToolResult:
        return ToolResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
        )


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
