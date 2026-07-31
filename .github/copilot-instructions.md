# Copilot Instructions

This repository contains two projects:

- **Agent0** (`src/agent0/`, package `agent0` v0.2.0) — declarative agent framework (installable Python package)
- **Change Advisor Agent / CAA** (`CAA/`) — PowerShell-orchestrated SAP advisory agents

---

## Agent0 — Python Package

### Commands

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

pytest -q                         # all tests
pytest tests/test_framework.py    # single file

agent0 new <name> --purpose "..."
agent0 validate <path>
agent0 test <path> [--all]
agent0 run <path> --input <file>
agent0 update <path> [--all]
agent0 list <dir>
```

### Architecture

Agents are declared, not coded. A package is a directory containing `agent.toml`, JSON Schema contracts, Markdown skills, config and test cases.

```
agent.toml → load_agent() → AgentDefinition → compile_plan() → Pipeline (DAG)
                                                                    ↓
run_agent(): validate input → AgentSession.run() → validate output → ExecutionResult
```

| Module | Responsibility |
|---|---|
| `core.py` | Contracts (`TaskSpec`, `PlanStep`, `Plan`, `StepResult`, `ExecutionResult`); `Node`/`Pipeline` DAG built with `graphlib.TopologicalSorter`; `HookManager` (8 events, LIFO); `DataCatalog` with `MemoryDataset`/`JsonlDataset`; `load_layered_config()`; step handlers; `AgentSession` |
| `policies.py` | `PolicyEngine`, `PolicyViolation` (a `PermissionError`), `PolicyHook.before_tool_run()`, `LocalCommandTool`. No framework imports — `hook_manager` is duck-typed |
| `factory.py` | Embedded scaffold templates; `create_agent()`/`update_agent()`/`update_all()`; `load_agent()`; `run_agent()`; JSON-Schema-subset `validate()`; test harness |
| `cli.py` | `argparse` subcommands |
| `__init__.py` | Public API re-exports |

### Key conventions

- All modules use `from __future__ import annotations` and `@dataclass(slots=True)`.
- Zero third-party dependencies. Standard library only — keep it that way.
- The DAG is validated at construction: cycles, duplicate outputs and self-referential nodes are rejected in `Pipeline.__init__`, not at run time.
- Steps wire by name: a step's `inputs` must match some other step's `outputs`, or `task_input`. One step must produce `final_output`.
- `agent0 update` is hash-tracked via `.agent0-scaffold.json` and never overwrites a file the author has customized. Preserve that guarantee.
- Policy patterns extend the framework defaults; never replace them.
- Tests isolate the catalog in a temp directory so no run touches real memory or shared data.
- `LLMStepHandler` is a deliberate stub raising `NotImplementedError`. Do not fake a model integration.
- Python >= 3.11 required.

---

## Change Advisor Agent (CAA)

```powershell
cd CAA
.\run-agent.ps1 -InputFile "tests/example-input.json" -OutputDir "test-output"
```

Evaluator-optimizer pipeline, max 2 passes, with pre/post hooks and quality gates.

### Key conventions

- **Skills** are plain `.txt` prompt files in `skills/`; `config.yaml` maps `id → file`.
- **Memory** folders are numerically ordered (`00-`, `10-`, `20-`…); lower numbers = higher priority. `60-cases/` and `70-retrospectives/` are write targets.
- **Schemas** (`schemas/input.schema.json`, `schemas/output.schema.json`) are the contracts — hooks validate against them, not ad-hoc logic.
- Optional skills activate via `input_field` checks in `config.yaml`; add new optional modules there, not in the script.
- `[HUMAN DECISION REQUIRED]` markers indicate interactive decision points.
- Output filenames follow `<change_id>-advisory.{json,md}`.
