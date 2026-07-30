# Agent1

Agent1 is a production-oriented foundation for building specialized software agents that can operate in demanding engineering environments.

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
agent1 run --objective "Design a deployment pipeline for service X"
pytest
```

## Core architecture

- `agent1.contracts` - shared dataclasses and protocols
- `agent1.planner` - base planning strategy
- `agent1.executor` - step execution orchestration
- `agent1.policies` - policy engine and safety checks
- `agent1.memory` - persisted run memory store
- `agent1.runtime` - main Agent1 runtime loop
- `agent1.builder` - factory for creating specialized agents
- `agent1.tools` - tool interface and local command execution

This foundation is intentionally strict and extensible so downstream agents can add domain-specific reasoning without rewriting control-plane fundamentals.
