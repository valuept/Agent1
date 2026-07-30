# Agent1

Agent1 is an **agent factory**: a zero-dependency Python framework (stdlib
only, Python ≥ 3.11) that scaffolds, validates, tests and runs declaratively-
defined agents. Architecture follows [Kedro](https://kedro.org)'s patterns —
DAG pipelines wired by name, a data catalog, layered config, lifecycle hooks.

Agents are authored without Python: `agent0 new` generates a complete,
immediately-testable **agent package** (TOML manifest, JSON I/O contracts,
skill files, policies, test cases) that the shared runtime executes.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest

agent0 new my-agent --purpose "Advise on change requests"
agent0 test my-agent          # conformance suite + scaffolded test cases
agent0 run my-agent --input my-agent/tests/inputs/example.json
agent0 update . --all         # fleet-refresh scaffold files from templates
agent0 list .
```

## Modules (5 files)

| Module | Responsibility |
|---|---|
| `core.py` | The runtime engine: contracts, DAG pipeline (cycles rejected at construction), hooks, catalog (incl. `scope = "shared"`), config layering, step handlers incl. the `LLMStepHandler` slot, `AgentSession` |
| `policies.py` | `PolicyEngine` rules (original Agent0 architecture) enforced via `before_tool_run`, plus the policy-gated `LocalCommandTool` |
| `factory.py` | Embedded templates, `create/update/load/run` agent packages, schema validation, and the test harness (conformance + cases) |
| `cli.py` | `new / validate / test / update / run / list` |
| `__init__.py` | Public API |

## Guarantees

- **Fail fast**: broken manifests, DAG cycles and missing files rejected at load time.
- **Contracts bind**: input validated before every run, output after; violations fail the run.
- **Policies enforce**: every tool command passes the policy hook, which can abort it.
- **Auditable**: every run appends a structured record to the agent's `runs` dataset.
- **Fleet updates**: framework behavior ships via the package; scaffold files refresh
  with `agent0 update` (hash-tracked — customized files are never overwritten).
- **Shared memory**: `scope = "shared"` datasets resolve under `AGENT0_SHARED_ROOT`,
  so all agents read/write the same knowledge base; tests never touch it.
- **LLM slot**: `runtime.LLMStepHandler` marks where a Claude-backed handler plugs in;
  until then skill steps render deterministically and stay testable.
