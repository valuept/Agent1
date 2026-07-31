# Agent0 / Agent1 Manual

This repository contains two generations of the same idea — a foundation for
building disciplined, auditable software agents:

- **Agent0** (`Agent0/`, package `agent0` v0.1.0) — the original foundation and
  a working system in its own right. A fixed four-step planning/execution loop
  with an enforced policy engine, an append-only memory store, and a builder
  API for spinning up named variants. It establishes the design convictions
  that the whole repository still runs on: stdlib-only, strictly-typed
  dataclasses, guardrails that can only get stricter, and an audit trail that
  cannot be silently truncated. 25/25 tests pass.
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

> **Note on Agent0 maintenance**: Agent0 is current and green — every module
> imports, the policy engine is enforced on every command, and the full suite
> passes. It reached that state through two rounds of maintenance performed
> while writing this manual; §4 is the complete changelog, including the
> cleanups that were deliberately *not* made.

---

## 1. Agent0 (`Agent0/`, v0.1.0)

### 1.1 Role definition

> **Role:** Deterministic control-plane for running a coding task through a
> fixed, policy-guarded, four-phase loop and recording what happened. Agent0
> is a **harness that disciplines execution** — it owns process, safety and
> auditability, and delegates the reasoning for each phase to a pluggable
> `StepHandler`. That separation is the point: the harness is small enough to
> read end-to-end and hold in your head, and it is correct independently of
> whatever intelligence is plugged into it. Two handlers ship —
> `CommandStepHandler`, which runs real, fallible commands through the
> policy-gated tool, and `DefaultStepHandler`, the always-succeeds fallback
> that keeps an unconfigured executor from crashing (see §1.6).

> **Role in the repository:** Agent0 is also the **design progenitor**. Its
> convictions — stdlib-only, `slots=True` dataclasses, protocol-based
> extension, extend-never-replace guardrails, append-only memory — are
> inherited wholesale by Agent1, and the specific places Agent0 hits its
> ceiling are what defined Agent1's requirements. §3.1 traces that lineage
> concretely.

### 1.2 Overview

Agent0 answers a narrow question well: *how do you run an LLM-driven coding
agent through a fixed, predictable control loop instead of letting it
improvise its own process?* Every task — regardless of domain — is forced
through the same four phases (analyze → design → implement → verify), every
shell command is checked against a policy engine before a process is spawned,
and every run, successful or failed, is appended to durable memory with the
domain, strategy and configuration that produced it. It is a **control-plane**
rather than a reasoning engine, and that constraint is deliberate: the parts
that must be trustworthy — sequencing, refusal, auditability — are separated
from the part that is inherently unpredictable, and can therefore be verified
on their own. The four-phase loop, the guardrails and the audit trail all work
today and are covered by tests.

Design philosophy: small, strict, composable dataclasses (`slots=True`,
`from __future__ import annotations` everywhere); protocols instead of base
classes for extension points (`Planner`, `StepHandler`); no dependencies
beyond the standard library; deliberately not clever — a "boring", fully
inspectable foundation meant to be extended per-domain via `AgentBuilder`.
Every one of those choices survived into Agent1 unchanged, which is the
strongest available evidence that they were the right calls.

### 1.3 Architecture

```
TaskSpec ──▶ validate() if strict_mode ──▶ merge agent constraints
                                                      │
                                                      ▼
                              BaselinePlanner.create_plan() ──▶ Plan (4 fixed PlanSteps)
                                                      │
                                    for each step (up to config.max_iterations)
                                                      ▼
                                        StepExecutor.execute_step()
                                     (dispatches by step.kind to a StepHandler)
                                                      │
                                                      ▼
                                    StepResult (success/summary/artifacts)
                                          → written back to step.notes
                                                      │
                              on failure: stop early ─┴─ on success: continue
                                                      │
                                                      ▼
                    MemoryStore.append_run(context=...) (JSONL, always called)
                                                      │
                                                      ▼
                                             ExecutionResult
```

Every shell command run through `LocalCommandTool` first passes through
`PolicyEngine.enforce_command()`, which raises `PolicyViolation` before any
process is spawned. Use `Agent0Runtime.create_tool()` to get a tool already
bound to the runtime's policy set and timeout.

| Module | Responsibility |
|---|---|
| `contracts.py` | Shared dataclasses/protocols: `TaskSpec` (with `validate()`), `PlanStep`, `Plan`, `StepResult`, `ExecutionResult`, `StepStatus`, `TaskValidationError`, and the `Planner`/`StepHandler` protocols. |
| `planner.py` | `BaselinePlanner` — always returns the same 4-step plan (`analyze-scope` → `design-approach` → `implement-solution` → `verify-outcome`), strategy `"baseline-sequenced"`; embeds the task's constraints and acceptance criteria into the relevant step rationales. |
| `executor.py` | `StepExecutor` — dispatches each step by `kind` to a registered `StepHandler`, falling back to `DefaultStepHandler` (a stub that always succeeds with a canned summary). `CommandStepHandler` is the real, fallible handler: it runs a command through the policy-gated tool and records exit code, stdout and stderr as `StepResult.artifacts`. |
| `policies.py` | `PolicyEngine` — regex-based `blocked_command_patterns` (default: `rm -rf`, `del /f`, `format <drive>:`, `git reset --hard`); `evaluate_command()` returns a `PolicyDecision`, `enforce_command()` raises `PolicyViolation`. |
| `memory.py` | `MemoryStore` — appends one JSON line per run to `config.memory_path`, including an audit `context` (domain, model, strategy, strict mode); `load_recent(limit)` reads the tail back. |
| `config.py` | `AgentConfig` — `model_name`, `max_iterations`, `strict_mode`, `memory_path`, `command_timeout_seconds`; `from_env()` reads `AGENT0_*` env vars. |
| `runtime.py` | `Agent0Runtime` — wires planner + executor + policies + memory, plus the agent's own `domain`/`constraints`; `.default()` builds one from env config; `.run(task)` validates (strict mode), merges agent constraints, drives the loop above and writes step notes; `.create_tool()` returns a policy-bound `LocalCommandTool`. |
| `builder.py` | `AgentBuilder` / `AgentBlueprint` — builds a named `Agent0Runtime` variant with its own memory file (`{name}_memory.jsonl`), its blueprint `domain`/`constraints`, and an *extended* (never replaced) policy blocklist. |
| `tools.py` | `LocalCommandTool` / `ToolResult` — enforces policy, then runs a shell command via `subprocess.run(shell=False)` with `shlex.split(posix=False)` (Windows-safe argument splitting), `stdin=DEVNULL` and a timeout. Timeouts and missing executables are returned as results (exit `124`/`127`), not raised. |
| `cli.py` | `argparse`-based `agent0 run --objective ... [--constraint ...] [--acceptance-criterion ...]`, printing the `ExecutionResult` as JSON. |

### 1.4 Why it's clever

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
- **Runtime command failures are results, not exceptions.** `LocalCommandTool`
  converts a timeout into exit code `124` and a missing executable into `127`
  rather than letting `TimeoutExpired`/`FileNotFoundError` escape. This is the
  difference between a failure that lands in the audit trail and one that
  aborts the process before `append_run()` is ever reached. Policy violations
  deliberately still raise, because a refused command is a safety error rather
  than a runtime outcome.
- **Agent constraints can only add restrictions.** Blueprint constraints are
  merged *ahead* of task constraints and de-duplicated, and the caller's
  `TaskSpec` is copied via `dataclasses.replace` rather than mutated. A task
  therefore cannot drop a rule its agent was built with, and callers never see
  their input object change underneath them — the same "extend, never replace"
  principle applied to the policy blocklist.

### 1.5 Capabilities

- Deterministic 4-phase planning for any `TaskSpec` (objective + constraints
  + acceptance criteria + metadata).
- Pluggable per-`kind` step handlers via `StepExecutor.handlers`, with a
  guaranteed-success fallback so an unconfigured executor never crashes.
- Regex-based command policy evaluation (`PolicyEngine.evaluate_command`),
  independently unit-testable and reusable outside the runtime loop, plus
  `enforce_command()` which raises `PolicyViolation` (a `PermissionError`
  subclass) instead of returning a decision.
- **Enforced** command guardrails: `LocalCommandTool.run()` consults the
  policy engine *before* spawning a subprocess, and defaults to a real
  `PolicyEngine` so an unconfigured tool is still guarded.
- `Agent0Runtime.create_tool()` returns a `LocalCommandTool` bound to the
  runtime's `command_timeout_seconds` and its policy set, so handlers get a
  correctly-configured, guarded tool without wiring it themselves.
- **`CommandStepHandler`**: a real, fallible step handler that runs a shell
  command through the policy-gated tool, reports the true exit status, and
  captures `command`/`exit_code`/`stdout`/`stderr` into `StepResult.artifacts`.
  Registering it (e.g. `executor.handlers["verification"] =
  CommandStepHandler("pytest", runtime.create_tool())`) is what makes a run
  able to genuinely fail rather than always succeed.
- **Strict-mode input validation**: when `config.strict_mode` is true (the
  default), `TaskSpec.validate()` runs before planning and raises
  `TaskValidationError` on a blank objective or any blank constraint /
  acceptance criterion. Setting `AGENT0_STRICT_MODE=false` skips validation.
- **Agent-level constraints**: `AgentBlueprint.constraints` and `.domain` are
  carried onto the built runtime; blueprint constraints are merged ahead of
  each task's own constraints (de-duplicated, caller's `TaskSpec` never
  mutated), so a blueprint's rules apply to every task that agent runs.
- **Audit context in memory**: every run record carries a `context` object with
  `domain`, `model_name`, `strategy` and `strict_mode`, so a history entry is
  attributable to the agent and configuration that produced it.
- Durable, append-only JSONL run history with recent-run recall
  (`MemoryStore.load_recent`).
- Named agent variants via `AgentBuilder`/`AgentBlueprint`: per-blueprint
  `domain`, `constraints`, `max_iterations`, extended policy patterns, and
  isolated memory files, sharing one `model_name`/`strict_mode`/
  `command_timeout_seconds` base.
- `AgentConfig.from_env()` for zero-code configuration via `AGENT0_MODEL`,
  `AGENT0_MAX_ITERATIONS`, `AGENT0_STRICT_MODE`, `AGENT0_MEMORY_PATH`,
  `AGENT0_COMMAND_TIMEOUT`.
- A CLI (`agent0 run --objective ... `) that runs one task and prints the
  full `ExecutionResult` as JSON.
- `LocalCommandTool`: a Windows-safe (`shlex.split(posix=False)`),
  non-shell (`shell=False`) subprocess runner with a configurable timeout.
  Runtime failures are returned as results, not raised: a timeout yields exit
  code `124` and a missing executable yields `127`, so a failed command is
  recorded in the audit trail instead of aborting the run.

### 1.6 Limitations

> These are Agent0's **current** boundaries. Items resolved during maintenance
> are recorded in the changelog at §4 rather than repeated here.

- **`DefaultStepHandler` is a stub, by design.** `CommandStepHandler` performs
  genuine, fallible work by running a real command, but the fallback for any
  *unregistered* step kind returns canned success strings. Out of the box,
  `agent0 run` executes the full plan without doing domain work; you register
  handlers to get value. This is the documented extension seam — the runtime
  deliberately ships process and safety, not reasoning — but it does mean
  Agent0's surface area is larger than its out-of-the-box behaviour.
- **No LLM integration of any kind.** `model_name` is recorded for attribution
  in the audit context but selects nothing; no model is ever contacted. This
  is the one field that could not be honestly wired without inventing an
  integration that cannot be tested here.
- **Quoted arguments do not survive command parsing.** `LocalCommandTool` uses
  `shlex.split(command, posix=False)` for Windows safety, which **preserves**
  quote characters rather than stripping them. `python -c "print(42)"` is
  passed through as the literal argument `"print(42)"`, which Python evaluates
  as an inert string expression — exit code 0, no output, no error. Prefer
  unquoted commands, or split arguments yourself.
- **A child process that opens the console directly can still block until the
  timeout.** `stdin` is redirected to `DEVNULL`, which stops a child consuming
  the agent's input stream, but it does not stop e.g. the CPython REPL on
  Windows, which attaches to the console itself. The `command_timeout_seconds`
  cap (exit code `124`) is the real backstop; set it deliberately.
- **Validation is shallow.** `TaskSpec.validate()` checks for non-empty strings
  only. There is no JSON Schema, no type coercion, and no validation of step
  output — nothing comparable to Agent1's I/O contracts.
- **No DAG / parallel step execution.** The plan is a fixed, linear
  4-step sequence; there is no dependency graph, no branching, and no way to
  run independent steps concurrently.
- **No shared/multi-agent memory.** Each `MemoryStore` is a single JSONL
  file scoped to one runtime instance; there is no concept of a shared
  knowledge base across agents.
- **Single-process, synchronous only.** No async execution, no distributed
  or remote execution model, no retries beyond the fixed `max_iterations`
  step cap.

### 1.7 How to use it

```powershell
cd Agent0

# 1. Set up
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 2. Run the test suite
pytest -q
# 25 passed in 2.17s

# 3. Run a task through the CLI
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
timestamp and an audit `context`:

```json
{
  "domain": "general",
  "model_name": "gpt-5.3-codex",
  "strategy": "baseline-sequenced",
  "strict_mode": "true"
}
```

Building a specialized agent from a blueprint (Python API):

```python
from agent0.builder import AgentBlueprint, AgentBuilder

builder = AgentBuilder()
runtime = builder.build(AgentBlueprint(
    name="deploy-agent",
    domain="infrastructure",
    constraints=["Never touch production without approval"],
    blocked_command_patterns=[r"\bterraform\s+destroy\b"],
    max_iterations=4,
))
# runtime.memory writes to .agent0/deploy-agent_memory.jsonl
# runtime.policies blocks rm -rf, del /f, format, git reset --hard, AND terraform destroy
# runtime.constraints are merged into every task this agent runs
```

Making a run actually able to fail, by registering the real command handler:

```python
from agent0 import Agent0Runtime, CommandStepHandler, TaskSpec

runtime = Agent0Runtime.default()
runtime.executor.handlers["verification"] = CommandStepHandler(
    "python --version", runtime.create_tool()
)
result = runtime.run(TaskSpec(objective="Ship", acceptance_criteria=["python present"]))
print(result.success, result.step_results[-1].artifacts)
```

Real output:

```text
True {'command': 'python --version', 'exit_code': '0', 'stdout': 'Python 3.14.6\n', 'stderr': ''}
```

Point it at a command that does not exist and the run fails honestly, with the
reason recorded rather than raised:

```text
False | blocked_reason: [WinError 2] Das System kann die angegebene Datei nicht finden
```

Strict mode rejects a malformed task before any work starts:

```python
from agent0 import Agent0Runtime, TaskSpec, TaskValidationError

try:
    Agent0Runtime.default().run(TaskSpec(objective="ok", constraints=["good", ""]))
except TaskValidationError as exc:
    print(exc)
# constraints[1] must be a non-empty string (got '')
```

Set `AGENT0_STRICT_MODE=false` to skip validation.

Running guarded shell commands (the tool refuses before spawning a process):

```python
from agent0 import Agent0Runtime, PolicyViolation

runtime = Agent0Runtime.default()
tool = runtime.create_tool()   # inherits command_timeout_seconds + policies

try:
    tool.run("rm -rf /important")
except PolicyViolation as exc:
    print("BLOCKED ->", exc)

print(tool.run("python --version").stdout.strip())
```

Real output:

```text
BLOCKED -> Blocked by policy pattern: \brm\s+-rf\b (command: 'rm -rf /important')
Python 3.14.6
```

---

## 2. Agent1 (`Agent1/` submodule, v0.2.0 — "agent factory")

### 2.1 Role definition

> **Role:** Declarative agent-authoring framework — a **meta-tool** for
> producing other agents. Agent1 does not itself perform a task; running
> `agent0 new` scaffolds a self-contained, already-testable agent package
> (manifest + I/O contracts + skills + policies + test cases) that a domain
> expert configures without writing Python, and the shared runtime executes.

### 2.2 Overview

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

### 2.3 Architecture

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

### 2.4 Why it's clever

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

### 2.5 Capabilities

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

### 2.6 Limitations

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

### 2.7 How to use it

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

### 3.1 What Agent0 contributed to Agent1

Agent1 did not arrive from nowhere. Nearly everything that makes it
trustworthy was established, tested and proven in Agent0 first, and carried
across deliberately:

| Agent0 established | Agent1 inherits it as |
|---|---|
| Zero third-party dependencies, stdlib only | Unchanged — still zero, now a stated framework guarantee |
| `@dataclass(slots=True)` + `from __future__ import annotations` on every contract | Unchanged, applied to `Node`, `Pipeline`, `AgentSession`, catalog entries |
| Protocols instead of base classes for extension seams | Extended into `Node` functions, `HookManager` and pluggable dataset types |
| A `PolicyEngine` whose blocklist can be extended but never replaced | Same engine, same guarantee, now fired automatically via `PolicyHook.before_tool_run()` |
| `PolicyViolation` as a typed, catchable refusal | Same name, same semantics, reused verbatim |
| Append-only run memory with no truncating API | Generalized into the `DataCatalog`, including `scope = "shared"` datasets |
| Recording *every* run, failed as well as successful, before returning | Preserved through the hook lifecycle |

Just as importantly, **the places Agent0 reached its ceiling are exactly what
specified Agent1**. Each of Agent1's headline features is a direct answer to a
limit discovered by building and running Agent0 first:

- The fixed four-step chain proved that a linear sequence cannot express
  independent sub-tasks → Agent1's validated DAG.
- Extending Agent0 meant writing Python and registering handlers by hand →
  Agent1's declarative TOML + JSON + Markdown authoring.
- Agent0's `TaskSpec` validation is deliberately shallow → Agent1's JSON
  Schema contracts checked before *and* after every run.
- One memory file per runtime instance ruled out a fleet → Agent1's shared
  catalog datasets.
- Agent0 had no way to ship framework improvements to deployed agents →
  Agent1's hash-tracked `agent0 update`.

That is what a foundation is *for*. You cannot specify a DAG runtime as the
right answer until you have felt a linear one constrain you, and the design
budget Agent1 spent on pipelines and contracts was available precisely because
the dependency policy, guardrail model and audit discipline were already
settled and proven. Agent0's contribution is architectural and empirical — the
conventions, guarantees and hard-won requirements above — and that is the more
durable kind of contribution. It is why Agent1 reads like a mature framework
rather than a first draft.

### 3.2 Feature comparison

| Aspect | Agent0 (v0.1.0) | Agent1 (v0.2.0) | Why it changed |
|---|---|---|---|
| Plan structure | Fixed, linear 4-step sequence, identical for every task | Author-defined DAG of steps wired by matching input/output names, validated (cycle/duplicate-output rejection) at construction | Real workflows have independent sub-tasks (e.g. design vs. risk assessment) that don't need to be serialized, and a DAG catches broken step wiring before runtime |
| How you build an agent | Write Python: implement `StepHandler`, register on `StepExecutor.handlers`, wire into `AgentBuilder` | Write no Python: `agent0 new` scaffolds a TOML manifest + JSON contracts + Markdown skills + policies + test cases | Lowers the barrier for domain experts to define agents without touching the runtime's implementation language |
| I/O contracts | Shallow — `TaskSpec.validate()` (strict mode) rejects blank objectives and blank constraint/criterion entries; no schema, no output validation | JSON Schema-validated input and output, checked before and after every run (`run_agent`) | Prevents "successful" runs from silently producing garbage; makes contract violations a first-class, reportable failure mode |
| Policy enforcement | `PolicyEngine` gates `LocalCommandTool.run()` directly, raising `PolicyViolation`; the tool defaults to a real engine, so it is guarded even when constructed by hand | `PolicyHook.before_tool_run()` fires automatically on every `LocalCommandTool.run()` via the hook system, raising `PolicyViolation` to abort | Both enforce. Agent1's hook-based approach additionally gates *any* registered tool, not just the command tool |
| Framework upgrades across many agents | Not modeled — no scaffold/versioning concept | `agent0 update [--all]`, hash-tracked per file, never overwrites author-customized files | Lets a framework author ship improvements to many already-deployed agent packages without a manual, error-prone diff/merge per agent |
| Memory / knowledge sharing | One `MemoryStore` JSONL file per runtime instance; no cross-agent sharing | `DataCatalog` datasets with `scope = "shared"`, resolved under a common root so many agents read/write one knowledge base; isolated with a temp dir during tests | Enables an actual fleet of agents to build shared knowledge, while keeping test runs from ever touching real production data |
| Extensibility model | Protocol-typed `Planner`/`StepHandler`, registered by hand in Python | `Node`/`Pipeline` DAG + `HookManager` (8 named events, LIFO dispatch) + pluggable `DataCatalog` dataset types | Adds cross-cutting extension points (hooks) instead of only per-step handler swapping |
| Dependencies | Zero third-party (stdlib only) | Zero third-party (stdlib only) | Unchanged design principle — carried forward deliberately |
| Model integration | Not modeled at all | Named, honest stub (`LLMStepHandler.handle()` raises `NotImplementedError`) | Makes the "where does the LLM plug in" question explicit and testable-around, rather than silently absent |
| Step execution | `DefaultStepHandler` stub for unregistered kinds; `CommandStepHandler` runs a real, fallible command and records artifacts (added in §4.2) | `Node` functions plus a `LLMStepHandler` slot that raises `NotImplementedError` until a backend is wired | Both ship a working non-LLM execution path and an honest gap where the model belongs |
| Validated in this repo | **Yes** — 25/25 tests pass and the CLI runs, after the fixes documented in §4 | **Yes** — 20/20 tests pass; every CLI subcommand exercised successfully | Both suites are green as of this manual |

**Bottom line**: Agent1 keeps Agent0's core convictions — small stdlib-only
dataclasses, policy guardrails, append-only auditability — and rebuilds the
execution model around a validated DAG plus declarative authoring, so that
building a new agent becomes a configuration exercise instead of a Python
extension exercise. The continuity is as notable as the change: the parts of
Agent0 that were right were kept verbatim, and the parts that were replaced
were replaced because running Agent0 showed exactly where a linear chain and
shallow contracts stop scaling.

---

## 4. Changelog: Agent0 maintenance

Two rounds of maintenance brought Agent0 to its current green state: a
packaging fix, the wiring of the policy engine into the tool path, a set of
declared-but-inert contract fields given real behaviour, and two robustness
holes closed in the command tool. The design needed no revision — every change
below implements an intent the original contracts already expressed.

### 4.1 Round 1 — import and enforcement

| Change | Rationale |
|---|---|
| `src/agent0/contracts.md` → `contracts.py`, `tools.md` → `tools.py` (via `git mv`, history preserved) | The package could not be imported at all. Python does not load `.md` as a module and no import hook or build step existed to bridge it, so all three test files failed to *collect*. The `.md` convention bought nothing and required a warning in `copilot-instructions.md` to work around. |
| `PolicyViolation(PermissionError)` added to `policies.py` | Gives callers a typed, catchable refusal that also satisfies existing `except PermissionError` handlers. Mirrors Agent1's naming for consistency across the two frameworks. |
| `PolicyEngine.enforce_command()` added | Raise-on-refusal counterpart to `evaluate_command()`. Failing loudly is correct for a guardrail — a returned `PolicyDecision` can be silently ignored. |
| `LocalCommandTool` now enforces policy before `subprocess.run` | Closes the actual safety gap. The engine existed and was unit-tested but was **never called** by any code path, so the guardrail was decorative. |
| `LocalCommandTool.policies` defaults to a real `PolicyEngine` | Secure by default. Making the guard opt-in would have reproduced the original problem for anyone constructing the tool directly. |
| `Agent0Runtime.create_tool()` added | Binds `config.command_timeout_seconds` and the runtime's own `policies` to the tool, making two previously-dead config values live and giving handlers one correct way to obtain a tool. |
| `LocalCommandTool`, `ToolResult`, `PolicyEngine`, `PolicyDecision`, `PolicyViolation` exported from `agent0/__init__.py` | `LocalCommandTool` was orphaned — defined, but imported by nothing and absent from the public API, so it was unreachable without reaching into a private module. |
| `tests/test_tools.py` added | Covers refusal-before-execution, secure-by-default construction, custom pattern extension, and the runtime wiring. |

### 4.2 Round 2 — inert fields and real execution

Every field below was previously declared in the public contracts but read by
no code. Each was **wired** rather than deleted, since removing public API
surface is a breaking change.

| Change | Rationale |
|---|---|
| `TaskSpec.acceptance_criteria` now feeds the `verify-outcome` step rationale | The criteria describe what verification means; the verification step is the only place they can meaningfully act. Mirrors how `.constraints` already fed `analyze-scope`. |
| `AgentConfig.strict_mode` now gates a new `TaskSpec.validate()` | Gives the flag a single crisp meaning instead of none: reject blank objectives and blank constraint/criterion entries *before* planning. Default-on preserves existing behaviour for well-formed tasks; `AGENT0_STRICT_MODE=false` opts out. |
| `TaskValidationError` added and exported | A typed failure for malformed input, distinct from a policy refusal. |
| `AgentBlueprint.domain` / `.constraints` now carried onto `Agent0Runtime` | `build()` accepted both and silently discarded them. A blueprint's constraints logically apply to *every* task that agent runs, so they are merged ahead of the task's own (de-duplicated). `dataclasses.replace` is used so the caller's `TaskSpec` is never mutated. |
| `PlanStep.notes` written after each step | Makes the `Plan` object a useful post-run artifact, consistent with the existing pattern of mutating `step.status` in place. Carries the error on failure, the summary on success. |
| `Plan.strategy`, `AgentConfig.model_name`, `domain` and `strict_mode` recorded in a memory `context` block | An audit trail that cannot say which agent, strategy or configuration produced a run is a weak audit trail. `model_name` still selects nothing — it is recorded purely for attribution, and that limit is stated plainly in §1.6. |
| `CommandStepHandler` added and exported | The first shipped handler that can genuinely **fail**. It runs a real command through the policy-gated tool, reports the true exit status, and populates `StepResult.artifacts` — the last inert field. Before this, no configuration of Agent0 could produce `success: false`, which made the entire failure path untested and unreachable. |
| `LocalCommandTool` returns timeout (`124`) and not-found (`127`) as results instead of raising | Found by a test that hung. `subprocess.TimeoutExpired`/`FileNotFoundError` escaped `run()` and aborted the whole runtime **before** `memory.append_run()`, so the most important failures were the ones least likely to be recorded. Policy violations still raise, because those are safety errors rather than runtime outcomes. |
| `stdin=subprocess.DEVNULL` on spawned processes | Stops a child consuming the agent's own input stream. Note this is not sufficient against a process that opens the console directly (see §1.6); the timeout is the backstop. |
| `tests/test_wiring.py` added | 13 tests covering each newly-wired field, both strict-mode outcomes, constraint merging and non-mutation, the audit context, and all three `CommandStepHandler` paths (pass, real failure, policy block). |

### 4.3 Deliberately not changed

- **`AgentConfig.model_name` still selects nothing.** It is now recorded for
  attribution, but wiring it further would mean inventing an LLM integration
  that cannot be verified in this environment. Documented in §1.6 rather than
  faked.
- **`DefaultStepHandler` remains a stub.** It is the documented extension seam
  and the fallback for unregistered step kinds; inventing reasoning behaviour
  for it would be guessing at intent. `CommandStepHandler` now demonstrates the
  seam end-to-end instead.
- **`shlex.split(posix=False)` was left as-is.** The quote-retention quirk is
  real (§1.6) but the setting is an intentional Windows-safety choice, and
  changing it risks breaking argument handling for existing callers.

### 4.4 Verification

```text
$ pytest -v
tests/test_planner.py::test_planner_returns_standard_step_order PASSED
tests/test_policy_engine.py::test_policy_blocks_dangerous_command PASSED
tests/test_policy_engine.py::test_policy_allows_safe_command PASSED
tests/test_runtime.py::test_runtime_executes_full_plan PASSED
tests/test_tools.py::test_tool_blocks_dangerous_command_before_execution PASSED
tests/test_tools.py::test_tool_is_guarded_by_default PASSED
tests/test_tools.py::test_tool_runs_allowed_command PASSED
tests/test_tools.py::test_tool_honours_custom_policy_patterns PASSED
tests/test_tools.py::test_runtime_create_tool_wires_config_and_policies PASSED
tests/test_tools.py::test_tool_returns_timeout_result_instead_of_raising PASSED
tests/test_tools.py::test_tool_returns_not_found_result_instead_of_raising PASSED
tests/test_tools.py::test_enforce_command_allows_safe_command PASSED
tests/test_wiring.py::test_planner_embeds_acceptance_criteria_in_verification_step PASSED
tests/test_wiring.py::test_planner_handles_absent_acceptance_criteria PASSED
tests/test_wiring.py::test_strict_mode_rejects_blank_objective PASSED
tests/test_wiring.py::test_strict_mode_rejects_blank_constraint PASSED
tests/test_wiring.py::test_non_strict_mode_accepts_malformed_task PASSED
tests/test_wiring.py::test_step_notes_are_written_after_execution PASSED
tests/test_wiring.py::test_blueprint_domain_and_constraints_are_applied PASSED
tests/test_wiring.py::test_agent_constraints_do_not_mutate_caller_task PASSED
tests/test_wiring.py::test_memory_records_audit_context PASSED
tests/test_wiring.py::test_command_step_handler_reports_success_and_artifacts PASSED
tests/test_wiring.py::test_command_step_handler_reports_real_failure PASSED
tests/test_wiring.py::test_command_step_handler_converts_policy_block_to_failed_step PASSED
tests/test_wiring.py::test_runtime_fails_plan_when_command_step_fails PASSED

25 passed in 2.13s
```

The CLI was also run end-to-end (`agent0 run --objective ...`), returning a
successful four-step `ExecutionResult` with the audit `context` written to
`.agent0/memory.jsonl`; live policy enforcement was confirmed against a real
`rm -rf` invocation; and `CommandStepHandler` was exercised for both a passing
command and a failing one (outputs shown in §1.7).

### 4.5 Where Agent0 fits now

Agent0 is a working, tested, self-contained harness, and it remains the
clearest statement of the conventions both frameworks share. Three places it
is genuinely the right choice:

- **When the workload really is linear.** Analyze → design → implement →
  verify is not a limitation for the many tasks that are honestly sequential.
  Agent0 delivers that with no DAG to declare, no manifest to maintain and no
  schema to author.
- **When the whole runtime has to be auditable by reading it.** Agent0 is
  small enough to review end-to-end in a sitting — a real advantage for
  regulated or safety-sensitive review, where "we read all of it" beats "we
  trust the framework."
- **As the reference implementation of the shared conventions.** The policy
  model, the dataclass discipline and the append-only audit contract are all
  easier to learn here, in isolation, than inside Agent1's larger surface.

Where a workload needs parallel or branching steps, schema-validated I/O,
shared memory across a fleet, or push-button framework upgrades, Agent1 is the
better fit — those are the specific ceilings that motivated it (§3.1), and the
remaining gaps in Agent0 (no LLM integration, no DAG, no shared memory) are
deliberate scope boundaries rather than defects. Both are current, both are
green, and they are complementary rather than competing: Agent0 is the small
disciplined harness, Agent1 the factory for building many of them.

