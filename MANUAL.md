# Agent0 / Agent1 Manual

This repository contains two generations of the same idea — a foundation for
building disciplined, auditable software agents:

- **Agent0** (`Agent0/`, package `agent0` v0.1.0) — the original foundation. A
  fixed four-step planning/execution loop with a policy engine, a memory
  store, and a builder API for spinning up named variants.
- **Agent1** (`Agent1/` submodule, package `agent0` v0.2.0) — the
  next-generation "agent factory". A zero-dependency, Kedro-inspired DAG
  runtime that lets you author whole agents declaratively (TOML manifest +
  JSON contracts + Markdown skills) with no Python code, validated,
  tested and run through one shared engine.

> **Note on Agent1 checkout**: at the time of writing, `Agent1/` is a
> configured git submodule (commit `bc24739`) but `.gitmodules` is missing
> from this repository, so the submodule cannot be initialized/checked out
> in place. The verification in this manual (reading every module, running
> the full pytest suite, and exercising every CLI command) was performed
> against the identical source tree shipped in `agent0-repo.zip` at the repo
> root, whose `pyproject.toml` (`name = "agent0"`, `version = "0.2.0"`) and
> five-module layout (`core.py`, `policies.py`, `factory.py`, `cli.py`,
> `__init__.py`) match Agent1 exactly. Once `.gitmodules` is restored and the
> submodule is checked out, this content applies directly to `Agent1/`.

---

## 1. Agent0 (`Agent0/`, v0.1.0)

### 1.1 Overview

Agent0 answers a narrow question: *how do you run an LLM-driven coding agent
through a fixed, predictable control loop instead of letting it improvise its
own process?* Every task — regardless of domain — is forced through the same
four phases (analyze → design → implement → verify), each phase is gated by
a policy engine that can block dangerous shell commands, and every run is
appended to durable memory for later inspection. It is a **control-plane**,
not a reasoning engine: the actual "thinking" for each step is delegated to a
`StepHandler`, and the shipped handler (`DefaultStepHandler`) is a stub that
always reports success without doing real analysis or generation.

Design philosophy: small, strict, composable dataclasses (`slots=True`,
`from __future__ import annotations` everywhere); protocols instead of base
classes for extension points (`Planner`, `StepHandler`); no dependencies
beyond the standard library; deliberately not clever — a "boring", fully
inspectable foundation meant to be extended per-domain via `AgentBuilder`.

### 1.2 Architecture

```
TaskSpec ──▶ BaselinePlanner.create_plan() ──▶ Plan (4 fixed PlanSteps)
                                                      │
                                    for each step (up to config.max_iterations)
                                                      ▼
                                        StepExecutor.execute_step()
                                     (dispatches by step.kind to a StepHandler)
                                                      │
                                                      ▼
                                              StepResult (success/summary)
                                                      │
                              on failure: stop early ─┴─ on success: continue
                                                      │
                                                      ▼
                                MemoryStore.append_run() (JSONL, always called)
                                                      │
                                                      ▼
                                             ExecutionResult
```

Every shell command a handler might run is meant to first pass through
`PolicyEngine.evaluate_command()` (the guard is available; wiring a handler
to call it is left to the integrator — see §1.5).

| Module | Responsibility |
|---|---|
| `contracts.md`* | Shared dataclasses/protocols: `TaskSpec`, `PlanStep`, `Plan`, `StepResult`, `ExecutionResult`, `StepStatus`, and the `Planner`/`StepHandler` protocols. |
| `planner.py` | `BaselinePlanner` — always returns the same 4-step plan (`analyze-scope` → `design-approach` → `implement-solution` → `verify-outcome`), strategy `"baseline-sequenced"`. |
| `executor.py` | `StepExecutor` — dispatches each step by `kind` to a registered `StepHandler`, falling back to `DefaultStepHandler` (a stub that always succeeds with a canned summary). |
| `policies.py` | `PolicyEngine` — regex-based `blocked_command_patterns` (default: `rm -rf`, `del /f`, `format <drive>:`, `git reset --hard`); `evaluate_command()` returns a `PolicyDecision`. |
| `memory.py` | `MemoryStore` — appends one JSON line per run to `config.memory_path`; `load_recent(limit)` reads the tail back. |
| `config.py` | `AgentConfig` — `model_name`, `max_iterations`, `strict_mode`, `memory_path`, `command_timeout_seconds`; `from_env()` reads `AGENT0_*` env vars. |
| `runtime.py` | `Agent0Runtime` — wires planner + executor + policies + memory; `.default()` builds one from env config; `.run(task)` drives the loop above. |
| `builder.py` | `AgentBuilder` / `AgentBlueprint` — builds a named `Agent0Runtime` variant with its own memory file (`{name}_memory.jsonl`) and an *extended* (never replaced) policy blocklist. |
| `tools.md`* | `LocalCommandTool` / `ToolResult` — runs a shell command via `subprocess.run(shell=False)` with `shlex.split(posix=False)` (Windows-safe argument splitting) and a timeout. |
| `cli.py` | `argparse`-based `agent0 run --objective ... [--constraint ...] [--acceptance-criterion ...]`, printing the `ExecutionResult` as JSON. |

\* `contracts.md` and `tools.md` are Python source **saved with a `.md`
extension** rather than `.py` (see §1.5, Limitations — this currently breaks
imports).

### 1.3 Why it's clever

- **Protocols, not inheritance, for extension points.** `Planner` and
  `StepHandler` are `typing.Protocol`s. `StepExecutor.handlers` is a plain
  `dict[str, StepHandler]` keyed by `step.kind`, so adding a real
  "implementation" handler is `executor.handlers["implementation"] = MyHandler()`
  — no subclassing, no registry boilerplate, and static type checkers can
  still verify conformance structurally.
- **Extend, don't replace, the policy blocklist.** `AgentBuilder.build()`
  calls `policies.blocked_command_patterns.extend(...)` rather than
  overwriting the list. A domain blueprint can only make the guardrails
  stricter, never accidentally weaker — an easy mistake to make if the API
  instead took a full replacement list.
- **Append-only memory by construction.** `MemoryStore` only exposes
  `append_run()` — there is no `overwrite`/`clear` method, so the audit trail
  cannot be silently truncated from the ordinary API surface, and every run
  (success *and* failure) is recorded before the result is returned.
- **`slots=True` everywhere.** Every dataclass in the package uses
  `@dataclass(slots=True)`. Combined with `from __future__ import
  annotations`, this keeps the object graph small, prevents accidental
  attribute injection (typo'd field names fail loudly instead of silently
  creating new instance attributes), and keeps memory overhead predictable
  for a runtime meant to process many tasks.
- **Fail-early execution loop.** `Agent0Runtime.run()` stops at the first
  failed step and *still* writes to memory before returning — so a partial,
  failed run is exactly as auditable as a successful one.

### 1.4 Capabilities

- Deterministic 4-phase planning for any `TaskSpec` (objective + constraints
  + acceptance criteria + metadata).
- Pluggable per-`kind` step handlers via `StepExecutor.handlers`, with a
  guaranteed-success fallback so an unconfigured executor never crashes.
- Regex-based command policy evaluation (`PolicyEngine.evaluate_command`),
  independently unit-testable and reusable outside the runtime loop.
- Durable, append-only JSONL run history with recent-run recall
  (`MemoryStore.load_recent`).
- Named agent variants via `AgentBuilder`/`AgentBlueprint`: per-blueprint
  `max_iterations`, extended policy patterns, and isolated memory files,
  sharing one `model_name`/`strict_mode`/`command_timeout_seconds` base.
- `AgentConfig.from_env()` for zero-code configuration via `AGENT0_MODEL`,
  `AGENT0_MAX_ITERATIONS`, `AGENT0_STRICT_MODE`, `AGENT0_MEMORY_PATH`,
  `AGENT0_COMMAND_TIMEOUT`.
- A CLI (`agent0 run --objective ... `) that runs one task and prints the
  full `ExecutionResult` as JSON.
- `LocalCommandTool`: a Windows-safe (`shlex.split(posix=False)`),
  non-shell (`shell=False`) subprocess runner with a configurable timeout.

### 1.5 Limitations

- **The package does not currently import.** `contracts.md` and `tools.md`
  contain real Python source (verified by reading them — `contracts.md`
  defines `TaskSpec`, `PlanStep`, `Plan`, etc.; `tools.md` defines
  `LocalCommandTool`) but are saved with a `.md` extension instead of `.py`.
  Python's import system does not load `.md` files as modules, and no import
  hook, build step, or file-renaming shim exists anywhere in this repo to
  bridge the gap. Verified by actually installing the package
  (`pip install -e .[dev]`) and running `pytest` in a clean venv against this
  repository's current `Agent0/`:
  ```
  ModuleNotFoundError: No module named 'agent0.contracts'
  ERROR tests/test_planner.py
  ERROR tests/test_policy_engine.py
  ERROR tests/test_runtime.py
  3 errors in 0.13s
  ```
  **To make Agent0 runnable, rename `src/agent0/contracts.md` →
  `contracts.py` and `src/agent0/tools.md` → `tools.py`** (their content is
  already valid Python). This is a pre-existing repository issue, not
  something introduced by this manual; it is documented here rather than
  fixed, per the constraints of this task.
- **`DefaultStepHandler` is a stub.** It does no real analysis, design,
  implementation, or verification — it returns a canned success summary
  string for every step. There is no shipped handler that calls an LLM,
  writes code, or performs real verification; every domain integration must
  supply its own `StepHandler` implementations.
- **The policy engine is advisory, not enforced by the runtime.**
  `PolicyEngine.evaluate_command()` exists and is unit-tested, but nothing in
  `runtime.py`/`executor.py` calls it automatically before a `LocalCommandTool`
  command runs — a custom `StepHandler` must call it explicitly. (Agent1
  closes this exact gap with a hook-enforced `PolicyHook`; see §3.)
- **No DAG / parallel step execution.** The plan is a fixed, linear
  4-step sequence; there is no dependency graph, no branching, and no way to
  run independent steps concurrently.
- **No schema validation of task input or step output.** `TaskSpec` fields
  are plain strings/lists — there's no I/O contract checking comparable to
  Agent1's JSON Schema validation.
- **No shared/multi-agent memory.** Each `MemoryStore` is a single JSONL
  file scoped to one runtime instance; there is no concept of a shared
  knowledge base across agents.
- **Single-process, synchronous only.** No async execution, no distributed
  or remote execution model, no retries beyond the fixed `max_iterations`
  step cap.

### 1.6 How to use it

```powershell
cd Agent0

# 1. First, apply the required fix (see Limitations above) — without this,
#    nothing below will work:
Rename-Item src\agent0\contracts.md contracts.py
Rename-Item src\agent0\tools.md tools.py

# 2. Set up
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 3. Run the test suite
pytest -q

# 4. Run a task through the CLI
agent0 run --objective "Design a deployment pipeline for service X" `
  --constraint "Use secure defaults" `
  --acceptance-criterion "Define a deterministic process"
```

Expected CLI output shape (from `ExecutionResult`, printed as indented JSON):

```json
{
  "success": true,
  "summary": "Plan executed successfully.",
  "step_results": [
    {"step_id": "analyze-scope", "success": true, "summary": "Objective analyzed: ...", "artifacts": {}, "error": null},
    {"step_id": "design-approach", "success": true, "summary": "Technical approach designed with modular boundaries.", "artifacts": {}, "error": null},
    {"step_id": "implement-solution", "success": true, "summary": "Implementation phase completed with current configured capabilities.", "artifacts": {}, "error": null},
    {"step_id": "verify-outcome", "success": true, "summary": "Verification phase completed and outputs prepared.", "artifacts": {}, "error": null}
  ],
  "blocked_reason": null
}
```

A run also appends one line to `.agent0/memory.jsonl` (or
`AGENT0_MEMORY_PATH`), containing the full task and step results with a UTC
timestamp.

Building a specialized agent from a blueprint (Python API):

```python
from agent0.builder import AgentBlueprint, AgentBuilder

builder = AgentBuilder()
runtime = builder.build(AgentBlueprint(
    name="deploy-agent",
    domain="infrastructure",
    blocked_command_patterns=[r"\bterraform\s+destroy\b"],
    max_iterations=4,
))
# runtime.memory writes to .agent0/deploy-agent_memory.jsonl
# runtime.policies blocks rm -rf, del /f, format, git reset --hard, AND terraform destroy
```

---

## 2. Agent1 (`Agent1/` submodule, v0.2.0 — "agent factory")

### 2.1 Overview

Agent1 answers a different, broader question: *how do you let people define
new agents — as configuration, not code — while still getting a real
execution engine underneath: a validated dependency graph, enforced I/O
contracts, policy-gated tools, and an audit trail?* It is explicitly modeled
on [Kedro](https://kedro.org)'s architecture: named `Node`s wired into a
`Pipeline` (a DAG) purely by matching input/output names, a `DataCatalog` of
named datasets, layered TOML configuration, and a `HookManager` for
cross-cutting concerns (policy enforcement, logging, auditing).

Where Agent0 is a fixed 4-step loop you extend in Python, Agent1 is a
**factory**: `agent0 new` scaffolds a complete, already-passing agent
package (manifest, JSON Schema contracts, Markdown skill files, policy
config, test cases) that a domain expert can edit without writing Python at
all. The framework ships zero third-party dependencies (`dependencies = []`
in `pyproject.toml`) — everything is standard library (`tomllib`, `graphlib`,
`hashlib`, `argparse`, `dataclasses`).

### 2.2 Architecture

```
agent.toml (manifest) ──▶ load_agent() ──▶ AgentDefinition
      │  [contracts]                          │
      │  input_schema / output_schema          ├─▶ compile_definition() — fail
      │  [catalog.*]  (datasets, scope)         │    fast: builds the DAG, checks
      │  [policies]   (blocked patterns)        │    for unconsumed inputs and a
      │  [[steps]] × N (id, kind, skill,        │    "final_output" producer
      │              command, inputs, outputs)  ▼
      │                                    ManifestPlanner.create_plan()
      ▼                                          │
run_agent(definition, input_doc)                 ▼
      │ 1. validate(input_doc, input_schema)   compile_plan() ──▶ Pipeline
      │    → fail fast, no run, if invalid          (one Node per PlanStep,
      │ 2. build_session():                          wired by input/output name,
      │      HookManager + PolicyHook(engine)         graphlib.TopologicalSorter,
      │      DataCatalog.from_config(...)             cycles/dup-outputs rejected
      │      ToolStepHandler (policy-gated)            at construction)
      │ 3. AgentSession.run(task, input_doc)                │
      │      → run_pipeline(): node-by-node,                ▼
      │        before/after hooks fire,              catalog.save() per node
      │        PolicyViolation aborts the run          output; results collected
      │      → appends record to `runs` dataset
      │ 4. validate(final_output, output_schema)
      │    → fail if output doesn't conform
      ▼
ExecutionResult (success, summary, step_results, outputs, blocked_reason)
```

| Module | Responsibility |
|---|---|
| `core.py` | The engine: `TaskSpec`/`PlanStep`/`Plan`/`StepResult`/`ExecutionResult` contracts; `Node`/`Pipeline` (DAG, built via `graphlib.TopologicalSorter`, cycles/duplicate-output/self-referential nodes rejected at construction); `HookManager` (LIFO dispatch over 8 named events); `DataCatalog` + `MemoryDataset`/`JsonlDataset` (with `scope = "shared"` resolution); `load_layered_config()` (deep-merges `conf/base.toml` then `conf/local.toml`); step handlers (`DeterministicStepHandler`, `ToolStepHandler`, the `LLMStepHandler` slot); `compile_plan()`; `AgentSession` (one full run, audit record, per-step result collection). |
| `policies.py` | `PolicyEngine` (same regex rules as Agent0, plus `validate_patterns()` for compile-time checking); `PolicyViolation` (a `PermissionError` subclass); `PolicyHook.before_tool_run()` — raises `PolicyViolation` to abort the run *before* the command executes; `LocalCommandTool` (duck-typed `hook_manager`, so this module has zero framework imports). |
| `factory.py` | Embedded string templates (`agent.toml`, `conf/base.toml`, JSON Schemas, 4 skill files, governance doc, test cases, example input, README, `.gitignore`); `create_agent()`/`update_agent()`/`update_all()` (hash-tracked scaffold refresh); `load_agent()` (manifest schema validation + fail-fast DAG compile); `run_agent()` (input validate → run → output validate); a minimal JSON-Schema-subset `validate()`/`is_valid_schema()`; the test harness (`run_conformance()`, `run_cases()`, `test_agent()`/`test_all()`, `format_report()`). |
| `cli.py` | `argparse` subcommands: `new`, `validate`, `test [--all]`, `update [--all]`, `run --input`, `list`. |
| `__init__.py` | Re-exports the public API from `core`, `factory`, `policies`. |

### 2.3 Why it's clever

- **DAG cycles (and worse) are rejected at construction, not at run time.**
  `Pipeline.__init__` builds a `producers` map and a dependency graph, then
  calls `graphlib.TopologicalSorter(...).static_order()` inside a `try` that
  catches `CycleError` and re-raises as `PipelineError`. It also independently
  rejects two nodes producing the same output name and a node using the same
  name as both input and output. Verified directly:
  ```python
  Pipeline([Node(lambda x: x, "a", "b", name="n1"), Node(lambda x: x, "b", "a", name="n2")])
  # PipelineError: Pipeline contains a cycle: [...]
  ```
  This means a broken agent manifest fails at `load_agent()` time (or even
  earlier, at `agent0 validate`), never mid-run — you cannot ship an agent
  whose steps can't actually execute.
- **Hash-tracked scaffold updates that never clobber customizations.**
  `create_agent()` writes a `.agent0-scaffold.json` recording a SHA-256 hash
  per rendered file. `update_agent()` re-renders the current templates and,
  per file, compares three hashes: the *recorded* baseline hash, the
  *current on-disk* hash, and the *new template* hash. A file is only
  overwritten if its on-disk hash still equals the recorded baseline (i.e.
  the author never touched it) — anything the author edited is left alone
  and reported as `skipped_modified`, while files the author deleted are
  `restored`. This lets a framework upgrade sweep an entire fleet of agents
  (`agent0 update . --all`) safely, refreshing only what nobody customized.
  Verified by test (`test_update_applies_new_templates_only_to_unmodified_files`):
  a hand-edited `skills/normalize.md` is preserved even when the template for
  it changes, while an untouched `skills/risks.md` picks up the new content.
- **Policy enforcement is a hook the tool cannot bypass, not a check callers
  must remember to make.** In Agent0, `PolicyEngine` is a standalone utility
  a handler *may* call. In Agent1, `LocalCommandTool.run()` always calls
  `self._call("before_tool_run", ...)` before invoking `subprocess.run`, and
  `PolicyHook.before_tool_run()` raises `PolicyViolation` (a `PermissionError`
  subclass) to abort. Because this fires through the same `HookManager` used
  for the DAG, *any* command-running step — whether built-in or
  future/custom — is automatically policy-gated as long as it goes through
  `LocalCommandTool`. Verified: `tool.run("rm -rf /critical/data")` raises
  `PolicyViolation` before any subprocess is spawned.
- **Fail-fast, three-stage contract binding.** `run_agent()` validates the
  input document against `input_schema` *before* starting the pipeline
  (rejecting bad input with zero side effects), and validates
  `outputs[FINAL_OUTPUT]` against `output_schema` *after* a successful run
  (a run that "succeeds" internally but produces a non-conforming output is
  still reported as failed). This closes a common gap in agent frameworks
  where a "successful" run can silently emit garbage.
- **Shared memory as a first-class dataset scope, isolated during tests.**
  A catalog entry declared with `scope = "shared"` resolves its file path
  under `AGENT0_SHARED_ROOT` (env var wins) or `runtime.shared_root` (config),
  so multiple independent agent packages can read and write one physical
  knowledge base by declaring the same dataset name/scope — no bespoke
  cross-agent messaging needed. Crucially, the test harness (`_run_case`)
  always runs cases against a fresh `tempfile.TemporaryDirectory` for *both*
  `base_path` and `shared_path`, so `agent0 test` can never leak a test run
  into the real shared knowledge base or the real agent's own memory —
  verified directly by `test_harness_fresh_agent_passes_everything`, which
  asserts `memory/runs.jsonl` does **not** exist after testing.
- **A deliberately named, honest integration seam for LLMs.**
  `LLMStepHandler.handle()` unconditionally `raise NotImplementedError("No
  model backend is wired in yet.")` — the framework does not pretend to have
  model integration it doesn't; it names the exact class and exact method
  where that work plugs in, and ships `DeterministicStepHandler` (structured,
  traceable, no model call) as the safe, always-testable default in the
  meantime.
- **Zero third-party dependencies.** `pyproject.toml` declares
  `dependencies = []`. TOML parsing uses the stdlib `tomllib` (Python ≥
  3.11), the DAG uses stdlib `graphlib`, hashing uses stdlib `hashlib`. This
  eliminates an entire class of supply-chain and version-pinning risk for a
  framework meant to be embedded into many different agent packages.

### 2.4 Capabilities

- `agent0 new <name> --purpose "..."` scaffolds a complete, immediately
  testable and runnable 4-step agent package (manifest, two JSON Schemas,
  four skill files, layered runtime config, `.gitignore`, README, example
  input, and two test cases — one happy-path, one policy-block probe).
- `agent0 validate <agent>` — loads the manifest, validates its structure
  against an embedded JSON-Schema-subset (`MANIFEST_SCHEMA`), compiles the
  step DAG, and confirms every declared skill file exists on disk.
- `agent0 test [<agent>] [--all]` — runs "conformance" checks (manifest
  loads, schemas are well-formed, policy patterns compile, catalog config
  resolves) plus every declarative case in `tests/cases.toml`, each isolated
  in a temp directory so no test run touches real memory or shared data.
- `agent0 run <agent> --input <file>` — validates input, executes the full
  DAG through `ToolStepHandler`, validates output, appends an audit record.
- `agent0 update [<agent>] [--all]` — hash-tracked refresh of scaffold files
  from the current package templates, reporting `updated` / `restored` /
  `skipped (customized)` / `unchanged` per file.
- `agent0 list [<dir>]` — recursively discovers every `agent.toml` under a
  directory and prints name/version/path (or `(invalid)` if it fails to
  load).
- Declarative dataset wiring: `memory` (unregistered names auto-become
  in-memory), `jsonl` (append-oriented, e.g. `memory/runs.jsonl`), with
  `scope = "agent"` (default) or `scope = "shared"`.
- Steps can declare either a `skill` (a Markdown prompt file — rendered
  deterministically today, see Limitations) or a `command` (run through the
  policy-gated `LocalCommandTool`), or both are optional (falls back to the
  deterministic handler).
- Layered runtime configuration: manifest `[runtime]` < `conf/base.toml` <
  `conf/local.toml` (local wins; `local.toml` is gitignored by the
  scaffold), covering `max_iterations`, `command_timeout_seconds`, and
  `shared_root`.
- A minimal but real JSON-Schema-subset validator (`type`, `required`,
  `properties`, `enum`, `pattern`, `minimum`/`maximum`, `minItems`, `items`)
  used identically for manifest validation, input/output contract checking,
  and self-validating the schemas themselves (`is_valid_schema`).

### 2.5 Limitations

- **`LLMStepHandler` is an unimplemented slot, not a working integration.**
  Calling `.handle()` always raises `NotImplementedError("No model backend
  is wired in yet.")`. There is no Claude/OpenAI/other API call anywhere in
  the framework; every step currently executes through
  `DeterministicStepHandler` (a structured summary, no reasoning) or
  `ToolStepHandler` (runs a literal shell command). Skill files
  (`skills/*.md`) are rendered as prompts but nothing sends them to a model.
- **No distributed or parallel execution.** `run_pipeline()` executes
  `pipeline.nodes` strictly in topological order, one at a time, in a single
  process. Independent branches of the DAG (e.g. `design` and `assess-risks`
  in the scaffold, which share no data dependency) are not run concurrently.
- **The JSON-Schema-subset validator is intentionally minimal.** It supports
  `type`, `required`, `properties`, `enum`, `pattern`, `minimum`/`maximum`,
  `minItems`, and `items` — it does not implement `anyOf`/`oneOf`/`allOf`,
  `$ref`, `additionalProperties`, `patternProperties`, string
  length/format constraints, or schema composition. Anything beyond that
  subset in a real JSON Schema document will simply be ignored, not
  rejected.
- **`DataCatalog` supports exactly two dataset types**: `memory` and
  `jsonl`. There is no SQL/Parquet/blob-storage dataset, and no plugin
  mechanism for registering new types beyond editing `_DATASET_TYPES` in
  `core.py`.
- **No network I/O, HTTP tool, or web-fetch capability.** The only built-in
  tool is `LocalCommandTool` (local subprocess execution). Anything needing
  network access must be shelled out to (and is therefore both timeout- and
  policy-gated the same as any other command).
- **`update_agent()` requires a `.agent0-scaffold.json` baseline.** Agent
  packages created manually (not via `agent0 new`), or predating this
  tracking file, cannot be updated — `update_agent()` raises `ScaffoldError`
  rather than guessing at a safe merge.
- **Policy patterns are regex, not a sandbox.** `PolicyEngine` blocks
  commands matching known-dangerous regex patterns; it is a blocklist, not
  an allowlist or a sandboxed execution environment. A sufficiently
  different or obfuscated dangerous command not matching a listed pattern
  will still run.
- **No retry/backoff logic.** A failed node aborts the pipeline (via
  `on_node_error`/`on_pipeline_error` hooks and a re-raised exception) with
  no built-in retry.

### 2.6 How to use it

All commands below were actually executed against the verified Agent1
source in this environment; output is reproduced exactly (paths shortened
for readability).

```powershell
# 1. Install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q
# 20 passed in 0.65s

# 2. Scaffold a new agent
agent0 new demo-agent --purpose "Advise on change requests"
# Created agent package: demo-agent
# Next: agent0 test demo-agent

# 3. Validate the manifest + DAG
agent0 validate demo-agent
# VALID: demo-agent v0.1.0 (4 steps)

# 4. Run the conformance suite + declarative test cases
agent0 test demo-agent
```

```
Agent: demo-agent (...\demo-agent)
  Conformance:
    [PASS] manifest loads, contracts exist, DAG compiles
    [PASS] I/O schemas are well-formed
    [PASS] policy patterns compile
    [PASS] catalog config resolves
  Cases:
    [PASS] happy-path
    [PASS] policy-block
  Result: PASS
```

```powershell
# 5. Run the agent against its example input
agent0 run demo-agent --input demo-agent\tests\inputs\example.json
```

```json
{
  "success": true,
  "summary": "Plan executed successfully.",
  "step_results": [
    {"step_id": "normalize", "success": true, "summary": "[analysis] Normalize the request — completed deterministically", "error": null},
    {"step_id": "design", "success": true, "summary": "[design] Design the approach — completed deterministically", "error": null},
    {"step_id": "assess-risks", "success": true, "summary": "[analysis] Assess risks — completed deterministically", "error": null},
    {"step_id": "finalize", "success": true, "summary": "[verification] Finalize and verify — completed deterministically", "error": null}
  ],
  "outputs": {
    "final_output": {
      "step_id": "finalize",
      "kind": "verification",
      "objective": "Advise on change requests",
      "rationale": "Merge design and risks into the final, contract-conforming output.",
      "consumed": ["design", "risks"],
      "skill": "skills/finalize.md",
      "summary": "[verification] Finalize and verify — completed deterministically"
    }
  },
  "blocked_reason": null
}
```

```powershell
# 6. Refresh scaffold files after a framework upgrade (safe against customizations)
agent0 update demo-agent
# Agent: ...\demo-agent
#   0 updated, 0 restored, 0 skipped, 13 unchanged

agent0 update . --all      # sweep every agent package under a directory

# 7. Discover every agent package under a directory
agent0 list .
# demo-agent    v0.1.0    ...\demo-agent
```

---

## 3. Agent0 vs Agent1: what changed and why

| Aspect | Agent0 (v0.1.0) | Agent1 (v0.2.0) | Why it changed |
|---|---|---|---|
| Plan structure | Fixed, linear 4-step sequence, identical for every task | Author-defined DAG of steps wired by matching input/output names, validated (cycle/duplicate-output rejection) at construction | Real workflows have independent sub-tasks (e.g. design vs. risk assessment) that don't need to be serialized, and a DAG catches broken step wiring before runtime |
| How you build an agent | Write Python: implement `StepHandler`, register on `StepExecutor.handlers`, wire into `AgentBuilder` | Write no Python: `agent0 new` scaffolds a TOML manifest + JSON contracts + Markdown skills + policies + test cases | Lowers the barrier for domain experts to define agents without touching the runtime's implementation language |
| I/O contracts | None — `TaskSpec` fields are free-form strings/lists | JSON Schema-validated input and output, checked before and after every run (`run_agent`) | Prevents "successful" runs from silently producing garbage; makes contract violations a first-class, reportable failure mode |
| Policy enforcement | `PolicyEngine.evaluate_command()` exists but must be called manually by a handler | `PolicyHook.before_tool_run()` fires automatically on every `LocalCommandTool.run()` via the hook system, raising `PolicyViolation` to abort | Guarantees every tool invocation is gated, instead of depending on each handler author remembering to check |
| Framework upgrades across many agents | Not modeled — no scaffold/versioning concept | `agent0 update [--all]`, hash-tracked per file, never overwrites author-customized files | Lets a framework author ship improvements to many already-deployed agent packages without a manual, error-prone diff/merge per agent |
| Memory / knowledge sharing | One `MemoryStore` JSONL file per runtime instance; no cross-agent sharing | `DataCatalog` datasets with `scope = "shared"`, resolved under a common root so many agents read/write one knowledge base; isolated with a temp dir during tests | Enables an actual fleet of agents to build shared knowledge, while keeping test runs from ever touching real production data |
| Extensibility model | Protocol-typed `Planner`/`StepHandler`, registered by hand in Python | `Node`/`Pipeline` DAG + `HookManager` (8 named events, LIFO dispatch) + pluggable `DataCatalog` dataset types | Adds cross-cutting extension points (hooks) instead of only per-step handler swapping |
| Dependencies | Zero third-party (stdlib only) | Zero third-party (stdlib only) | Unchanged design principle — carried forward deliberately |
| Model integration | Not modeled at all | Named, honest stub (`LLMStepHandler.handle()` raises `NotImplementedError`) | Makes the "where does the LLM plug in" question explicit and testable-around, rather than silently absent |
| Validated in this repo | **No** — `contracts.md`/`tools.md` need renaming to `.py` before `import agent0` works (see §1.5) | **Yes** — 20/20 tests pass; every CLI subcommand exercised successfully | Documented plainly rather than glossed over |

**Bottom line**: Agent1 keeps Agent0's core convictions — small stdlib-only
dataclasses, policy guardrails, append-only auditability — and rebuilds the
execution model around a validated DAG plus declarative authoring, so that
building a new agent becomes a configuration exercise instead of a Python
extension exercise, while closing two real Agent0 gaps: unenforced policy
checks and the absence of any I/O contract.
