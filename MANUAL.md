# Agent0 User Manual

Declarative agent framework. Author agents as TOML + JSON Schema + Markdown; run them through a shared DAG runtime. Python ≥ 3.11, standard library only.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Commands

| Command | Purpose |
|---|---|
| `agent0 new <name> --purpose "..."` | Scaffold a new agent package |
| `agent0 validate <path>` | Check manifest, schemas, DAG, skill files |
| `agent0 test <path> [--all]` | Run conformance checks + `tests/cases.toml` |
| `agent0 run <path> --input <file>` | Validate input, execute DAG, validate output |
| `agent0 update <path> [--all]` | Refresh scaffold files; keeps customized ones |
| `agent0 list <dir>` | Find every agent package under a directory |

## Quick start

```powershell
agent0 new demo-agent --purpose "Advise on change requests"
agent0 validate demo-agent
agent0 test demo-agent
agent0 run demo-agent --input demo-agent\tests\inputs\example.json
```

```
Agent: demo-agent
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

## Package layout

```
demo-agent/
  agent.toml                     manifest: steps, contracts, catalog, policies
  conf/base.toml                 runtime config (conf/local.toml overrides, gitignored)
  contracts/input.schema.json    input contract
  contracts/output.schema.json   output contract
  skills/*.md                    per-step prompt files
  memory/00-governance.md        agent notes
  tests/cases.toml               declarative test cases
  tests/inputs/example.json      example input
  .agent0-scaffold.json          scaffold hashes; required by `agent0 update`
```

## Manifest

```toml
name = "demo-agent"
version = "0.1.0"
purpose = "Advise on change requests"

[contracts]
input_schema = "contracts/input.schema.json"
output_schema = "contracts/output.schema.json"

[catalog.runs]
type = "jsonl"                   # "jsonl" or "memory"; unlisted names default to memory
filepath = "memory/runs.jsonl"
# scope = "shared"               # optional; resolves under the shared root

[policies]
blocked_command_patterns = []    # extends framework defaults

[[steps]]
id = "normalize"
title = "Normalize the request"
kind = "analysis"                # free-form label; appears in step output
rationale = "Turn the raw request into a structured statement of scope."
skill = "skills/normalize.md"    # optional
# command = "pytest -q"          # optional; runs through the policy-gated tool
inputs = ["task_input"]
outputs = ["normalized"]
```

Steps are wired into a DAG by matching `outputs` to `inputs`. `task_input` is the validated input document. One step must produce `final_output`. Cycles, duplicate outputs and unconsumed inputs are rejected at load time. A step with `command` runs it through the policy-gated tool; otherwise it runs deterministically.

## Config

Layered, later wins: manifest `[runtime]` → `conf/base.toml` → `conf/local.toml`.

| Key | Meaning |
|---|---|
| `max_iterations` | Step cap per run |
| `command_timeout_seconds` | Timeout for `command` steps |
| `shared_root` | Root for `scope = "shared"` datasets (env: `AGENT0_SHARED_ROOT`) |

## Limits

- No LLM integration. `LLMStepHandler.handle()` raises `NotImplementedError`. Skill files are rendered but never sent to a model; steps run deterministically or as shell commands.
- Single process, sequential. Independent DAG branches do not run concurrently.
- JSON Schema support is a subset: `type`, `required`, `properties`, `enum`, `pattern`, `minimum`/`maximum`, `minItems`, `items`. No `$ref`, `anyOf`/`oneOf`/`allOf`, `additionalProperties`. Unsupported keywords are ignored, not rejected.
- Dataset types are `memory` and `jsonl` only.
- No network tool. Anything remote must be shelled out via `command`.
- Policies are a regex blocklist, not a sandbox.
- No retries. A failed step aborts the run.
- `agent0 update` requires `.agent0-scaffold.json`; manually created packages cannot be updated.
