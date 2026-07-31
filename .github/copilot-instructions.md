# Copilot Instructions

This repository contains two agent frameworks and their tooling:

- **Agent0** (`Agent0/`) — Python-based agent foundation (installable package)
- **Change Advisor Agent / CAA** (`Change Advisor Agent/`, `CAA/`) — PowerShell-orchestrated SAP advisory agents

---

## Agent0 — Python Package

### Commands

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]           # installs pytest

# Run a task
agent0 run --objective "..." --constraint "..." --acceptance-criterion "..."

# Tests
pytest                          # all tests
pytest tests/test_runtime.py    # single file
```

### Architecture

`Agent0Runtime` wires together five components — call `Agent0Runtime.default()` to get one with env-based config:

```
TaskSpec → BaselinePlanner.create_plan() → Plan (4 fixed steps)
         → StepExecutor.execute_step()   (per step, up to config.max_iterations)
         → PolicyEngine.evaluate_command() (guards each shell command)
         → MemoryStore.append_run()      (JSONL at config.memory_path)
         → ExecutionResult
```

Fixed step sequence (ids): `analyze-scope` → `design-approach` → `implement-solution` → `verify-outcome`, each with a `kind` (`analysis`, `design`, `implementation`, `verification`).

- **`builder.py`** — `AgentBuilder.build(AgentBlueprint)` creates a fully wired `Agent0Runtime` for a named domain; extend `blocked_command_patterns` (don't replace) per blueprint.
- **`policies.py`** — `PolicyEngine` blocks commands via regex patterns; default list covers `rm -rf`, `del /f`, `format`, `git reset --hard`. `evaluate_command()` returns a `PolicyDecision`; `enforce_command()` raises `PolicyViolation`.
- Config via env vars: `AGENT0_MODEL`, `AGENT0_MAX_ITERATIONS`, `AGENT0_STRICT_MODE`, `AGENT0_MEMORY_PATH`, `AGENT0_COMMAND_TIMEOUT` — `AgentConfig.from_env()` is the canonical factory.

### Key conventions

- All modules use `from __future__ import annotations` and `@dataclass(slots=True)`. No `__dict__`, no monkey-patching.
- Memory is append-only JSONL at `.agent0/memory.jsonl` (blueprint-named sibling for variants). Never truncate; read via `MemoryStore.load_recent(limit)`.
- Custom step logic: implement `StepHandler` protocol (`handle(task, step) -> StepResult`) and register on `StepExecutor.handlers[kind]`. `DefaultStepHandler` always succeeds — add real handlers before shipping domain logic.
- `LocalCommandTool` uses `shlex.split(posix=False)` (Windows-safe) and never shells out with `shell=True`. It enforces `PolicyEngine` before spawning a process and defaults to a real engine, so it is guarded even when constructed directly; prefer `Agent0Runtime.create_tool()` to inherit the runtime's policies and timeout.
- Tests use `tmp_path` fixture for memory isolation; no mocking frameworks.
- Python ≥ 3.11 required.

---

## Change Advisor Agent (CAA / Change Advisor Agent)

Two versions share the same pattern; **CAA** (v2.0.0) is the current one.

### Run

```powershell
# CAA (v2.0.0) — fully automated evaluator-optimizer
cd CAA
.\run-agent.ps1 -InputFile "tests/example-input.json" -OutputDir "test-output"

# Change Advisor Agent (v1.0.0) — bundle-then-paste workflow
cd "Change Advisor Agent"
.\run-agent.ps1 -InputPath .\examples\sample-input.json -AgentRoot . -MemoryRoot .\memory -BundleOutPath .\artifacts\context-bundle.txt
# Then paste context-bundle.txt into Copilot Desktop
```

### Architecture (CAA v2.0.0)

Pipeline pattern: **evaluator-optimizer** (max 2 passes).

```
Input JSON
  → pre-hooks: pre-validate-input.ps1, pre-pii-guard.ps1
  → Pass 1: requirement-normalizer → gap-question-generator → impact-analyzer
            → compliance-checker → testcase-designer → handover-writer
  → Quality gates (schema_compliance blocks; others trigger Pass 2):
      evidence_only | schema_compliance | explicit_unknowns | risk_transparency
  → Pass 2 (if any gate failed): deepens risk/compliance/test-coverage
  → post-hook: post-validate-output.ps1
  → Output: <change_id>-advisory.json + <change_id>-advisory.md
```

### Key conventions

- **Skills** are plain `.txt` prompt files in `skills/`; `config.yaml` maps `id → file`.
- **Memory** folders are numerically ordered (`00-`, `10-`, `20-`…); lower numbers = higher priority context. `60-cases/` and `70-retrospectives/` are write targets.
- **Schemas** (`schemas/input.schema.json`, `schemas/output.schema.json`) are the contracts — hooks validate against them, not ad-hoc logic.
- Optional skills (`grill-me`, `leanix-export-preparation`) activate via `input_field` checks defined in `config.yaml`; add new optional modules there, not in the script.
- `[HUMAN DECISION REQUIRED]` markers in output indicate interactive decision points.
- Output filenames follow `<change_id>-advisory.{json,md}`.
