# Agent0

Declarative agent framework. Agents are authored as a TOML manifest, JSON Schema contracts and Markdown skill files, then compiled into a validated DAG and executed by a shared runtime. No Python required to build an agent.

Zero third-party dependencies. Python >= 3.11.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q

agent0 new demo-agent --purpose "Advise on change requests"
agent0 test demo-agent
agent0 run demo-agent --input demo-agent\tests\inputs\example.json
```

See [MANUAL.md](MANUAL.md) for the full command and manifest reference.

## Layout

```
src/agent0/core.py       runtime: contracts, DAG, hooks, catalog, config, step handlers
src/agent0/policies.py   policy engine and the policy-gated local command tool
src/agent0/factory.py    scaffold templates, create/update/load/run, schema validation, tests
src/agent0/cli.py        new | validate | test | update | run | list
tests/                   framework test suite
CAA/                     Change Advisor Agent (PowerShell, separate project)
```

## Notes

- `LLMStepHandler` is an unimplemented slot; no model is contacted. Steps execute deterministically or as policy-gated shell commands.
- Execution is single-process and sequential; independent DAG branches do not run in parallel.
- JSON Schema support is a documented subset. See MANUAL.md.
