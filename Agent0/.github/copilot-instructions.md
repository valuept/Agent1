# Agent0 Copilot Instructions

## Commands

```powershell
pip install -e .[dev]          # install with dev deps
pytest                         # full test suite
pytest tests/test_runtime.py   # single test file
agent0 run --objective "..."   # CLI entrypoint
```

## Architecture

`TaskSpec` → `BaselinePlanner` → `Plan` (4 fixed steps) → `StepExecutor` → `ExecutionResult`, persisted to `MemoryStore`.

Fixed step sequence (ids): `analyze-scope` → `design-approach` → `implement-solution` → `verify-outcome`, each with a `kind` (`analysis`, `design`, `implementation`, `verification`).

`Agent0Runtime.default()` wires all components; `AgentBuilder.build(blueprint)` creates named variants with per-agent memory files and extended policy blocklists.

`PolicyEngine.blocked_command_patterns` is a list of regex strings; extend it (don't replace it) when adding domain-specific safety rules.

## Key conventions

- All dataclasses use `slots=True`; no `__dict__`, no monkey-patching.
- Config is read from env vars (`AGENT0_MODEL`, `AGENT0_MAX_ITERATIONS`, `AGENT0_STRICT_MODE`, `AGENT0_MEMORY_PATH`, `AGENT0_COMMAND_TIMEOUT`); `AgentConfig.from_env()` is the canonical factory.
- Memory is append-only JSONL at `.agent0/memory.jsonl` (or blueprint-named sibling). Never truncate; read via `MemoryStore.load_recent(limit)`.
- Custom step logic: implement `StepHandler` protocol (`handle(task, step) -> StepResult`) and register on `StepExecutor.handlers[kind]`. The fallback (`DefaultStepHandler`) always succeeds — add real handlers before shipping domain logic.
- `LocalCommandTool` uses `shlex.split(posix=False)` (Windows-safe) and never shells out with `shell=True`.
- `from __future__ import annotations` is in every module; keep it that way.
- Python ≥ 3.11 required.
