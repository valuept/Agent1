# Agent0

Agent0 is a production-oriented foundation for building specialized software agents that can operate in demanding engineering environments.

## What this baseline provides

- Deterministic planning contracts (`TaskSpec`, `Plan`, `PlanStep`)
- Execution runtime with pluggable step handlers
- Policy guardrails to block unsafe operations
- Memory store for run history and traceability
- Tool abstraction layer with a local command tool
- Agent builder API to create specialized agents from blueprints
- CLI entrypoint for running tasks

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
agent0 run --objective "Design a deployment pipeline for service X"
pytest
```

## Core architecture

- `agent0.contracts` - shared dataclasses and protocols
- `agent0.planner` - base planning strategy
- `agent0.executor` - step execution orchestration
- `agent0.policies` - policy engine and safety checks
- `agent0.memory` - persisted run memory store
- `agent0.runtime` - main Agent0 runtime loop
- `agent0.builder` - factory for creating specialized agents
- `agent0.tools` - tool interface and local command execution

This foundation is intentionally strict and extensible so downstream agents can add domain-specific reasoning without rewriting control-plane fundamentals.
