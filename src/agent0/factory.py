"""The agent factory: scaffold, update, load and run declarative agent packages.

`create_agent` renders a complete, immediately-testable agent package.
`update_agent` refreshes scaffold-owned files from the current templates,
overwriting only files still matching the hash recorded at generation —
customized files are never clobbered. `load_agent`/`run_agent` execute a
package with contract validation and policy enforcement.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import tomllib
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from string import Template
from typing import Any

from .core import (
    FINAL_OUTPUT,
    TASK_INPUT,
    AgentConfig,
    AgentSession,
    DataCatalog,
    DatasetError,
    ExecutionResult,
    HookManager,
    Pipeline,
    PipelineError,
    Plan,
    PlanStep,
    TaskSpec,
    ToolStepHandler,
    compile_plan,
    load_layered_config,
)
from .policies import PolicyEngine, PolicyHook

MANIFEST_FILE = "agent.toml"
SCAFFOLD_STATE_FILE = ".agent0-scaffold.json"
_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ScaffoldError(ValueError):
    """Raised when an agent package cannot be generated or updated."""


class AgentLoadError(ValueError):
    """Raised when an agent package is invalid."""


# --------------------------------------------------------------------------- templates

_AGENT_TOML = """\
# Agent manifest — authored declaratively, executed by the shared Agent0 runtime.
# Edit steps, skills, contracts and policies freely; run `agent0 test .` after.

name = "$name"
version = "0.1.0"
purpose = "$purpose"

[contracts]
input_schema = "contracts/input.schema.json"
output_schema = "contracts/output.schema.json"

# Datasets: run history and anything you want persisted. Unlisted names
# automatically become in-memory datasets. Datasets with scope = "shared"
# resolve under the shared root (AGENT0_SHARED_ROOT or runtime.shared_root
# in conf) — every agent declaring them reads and writes the same file.
[catalog.runs]
type = "jsonl"
filepath = "memory/runs.jsonl"

[policies]
# Extends the framework defaults (rm -rf, format, hard reset, ...).
blocked_command_patterns = []

[[steps]]
id = "normalize"
title = "Normalize the request"
kind = "analysis"
rationale = "Turn the raw request into a structured statement of scope."
skill = "skills/normalize.md"
inputs = ["task_input"]
outputs = ["normalized"]

[[steps]]
id = "design"
title = "Design the approach"
kind = "design"
rationale = "Decide how to fulfil the normalized request."
skill = "skills/design.md"
inputs = ["normalized"]
outputs = ["design"]

[[steps]]
id = "assess-risks"
title = "Assess risks"
kind = "analysis"
rationale = "Identify risks independently of the design track."
skill = "skills/risks.md"
inputs = ["normalized"]
outputs = ["risks"]

[[steps]]
id = "finalize"
title = "Finalize and verify"
kind = "verification"
rationale = "Merge design and risks into the final, contract-conforming output."
skill = "skills/finalize.md"
inputs = ["design", "risks"]
outputs = ["final_output"]
"""

_CONF_BASE = """\
# Committed tunables for $name; override per environment in conf/local.toml
# (gitignored). Precedence: manifest < base.toml < local.toml.

[runtime]
max_iterations = 12
command_timeout_seconds = 120
"""

_INPUT_SCHEMA = """\
{
  "type": "object",
  "required": ["request"],
  "properties": {
    "request": { "type": "string" },
    "priority": { "type": "string", "enum": ["low", "medium", "high"] },
    "constraints": { "type": "array", "items": { "type": "string" } }
  }
}
"""

_OUTPUT_SCHEMA = """\
{
  "type": "object",
  "required": ["step_id", "kind", "summary"],
  "properties": {
    "step_id": { "type": "string" },
    "kind": { "type": "string" },
    "summary": { "type": "string" },
    "objective": { "type": "string" },
    "rationale": { "type": "string" },
    "consumed": { "type": "array", "items": { "type": "string" } },
    "skill": { "type": ["string", "null"] }
  }
}
"""

_SKILL = """\
# SKILL: $id

## Purpose
$purpose_line

## Input
$input_line

## Process
1. $step_one
2. $step_two

## Quality gates
- No invented facts: every statement traces back to the inputs.
- Unknowns are listed as open questions, never guessed.
"""

_SKILLS = {
    "normalize": {
        "purpose_line": "Turn the raw request into a structured, unambiguous statement of scope.",
        "input_line": "- The validated input document (`task_input`).",
        "step_one": "Restate the request; list what is in and out of scope.",
        "step_two": "Derive acceptance criteria from the request and constraints.",
    },
    "design": {
        "purpose_line": "Decide how to fulfil the normalized request.",
        "input_line": "- `normalized`: the structured scope statement.",
        "step_one": "Choose an approach and justify it against the acceptance criteria.",
        "step_two": "Break the approach into concrete, ordered work items.",
    },
    "risks": {
        "purpose_line": "Identify risks in the normalized request, independent of the design.",
        "input_line": "- `normalized`: the structured scope statement.",
        "step_one": "List risks with probability and impact (score 1-9).",
        "step_two": "Propose a mitigation for every risk scoring 4 or higher.",
    },
    "finalize": {
        "purpose_line": "Merge design and risks into the final, contract-conforming output.",
        "input_line": "- `design` and `risks` from the parallel tracks.",
        "step_one": "Verify the design addresses every acceptance criterion.",
        "step_two": "Produce the final document in the output contract's shape.",
    },
}

_GOVERNANCE = """\
# Governance — $name

- Purpose: $purpose
- Blocked operations: see [policies] in agent.toml (extends framework defaults).
- Output contract: contracts/output.schema.json is binding; non-conforming runs fail.
- Run history: every run is appended to memory/runs.jsonl for audit.
"""

_CASES = """\
# Test cases for $name — run with `agent0 test <agent-path>`.

[cases.happy-path]
input = "inputs/example.json"

[cases.happy-path.expect]
status = "success"
output_valid = true

[cases.happy-path.expect.fields]
step_id = "finalize"
kind = "verification"

# Negative case: injects an extra step attempting a dangerous command and
# asserts the agent's policy configuration blocks it.
[cases.policy-block]
input = "inputs/example.json"
probe_command = "rm -rf /"

[cases.policy-block.expect]
status = "blocked"
"""

_EXAMPLE_INPUT = """\
{
  "request": "Example request for $name — replace with a realistic scenario.",
  "priority": "medium",
  "constraints": ["Must complete within the current sprint"]
}
"""

_README = """\
# $name

$purpose

Declarative agent generated by `agent0 new` — no Python required. The shared
Agent0 runtime compiles agent.toml into a validated DAG and runs it with
policy hooks, binding I/O contracts, and an auditable run history.

```powershell
agent0 test .                              # conformance suite + test cases
agent0 run . --input tests/inputs/example.json
agent0 update .                            # refresh scaffold files after a framework upgrade
```
"""

_GITIGNORE = """\
conf/local.toml
memory/runs.jsonl
"""


def render_files(name: str, purpose: str) -> dict[str, str]:
    """Render all scaffold files; returns {relative path: content}."""
    subs = {"name": name, "purpose": purpose}
    files = {
        "agent.toml": Template(_AGENT_TOML).substitute(subs),
        "conf/base.toml": Template(_CONF_BASE).substitute(subs),
        "contracts/input.schema.json": _INPUT_SCHEMA,
        "contracts/output.schema.json": _OUTPUT_SCHEMA,
        "memory/00-governance.md": Template(_GOVERNANCE).substitute(subs),
        "tests/cases.toml": Template(_CASES).substitute(subs),
        "tests/inputs/example.json": Template(_EXAMPLE_INPUT).substitute(subs),
        "README.md": Template(_README).substitute(subs),
        ".gitignore": _GITIGNORE,
    }
    for skill_id, skill_subs in _SKILLS.items():
        files[f"skills/{skill_id}.md"] = Template(_SKILL).substitute(id=skill_id, **skill_subs)
    return files


# --------------------------------------------------------------------------- scaffold & update

@dataclass(slots=True)
class UpdateReport:
    agent_path: Path
    updated: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    skipped_modified: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _write_state(root: Path, file_hashes: dict[str, str]) -> None:
    try:
        version = metadata.version("agent0")
    except metadata.PackageNotFoundError:
        version = "unknown"
    state = {"agent0_version": version, "files": file_hashes}
    (root / SCAFFOLD_STATE_FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")


def create_agent(name: str, target_dir: str | Path = ".", purpose: str | None = None) -> Path:
    """Generate a new declarative agent package; returns its root directory."""
    if not _NAME_PATTERN.match(name):
        raise ScaffoldError(f"Invalid agent name {name!r}: use lowercase letters, digits and hyphens")
    root = Path(target_dir) / name
    if root.exists():
        raise ScaffoldError(f"Target directory already exists: {root}")
    rendered = render_files(name, purpose or f"Declarative agent '{name}' built with Agent0.")
    hashes = {}
    for rel_path, content in rendered.items():
        destination = root / rel_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        hashes[rel_path] = _hash_text(content)
    _write_state(root, hashes)
    return root


def update_agent(agent_path: str | Path) -> UpdateReport:
    """Refresh scaffold-owned files; never overwrite files the author changed."""
    root = Path(agent_path).resolve()
    if not (root / MANIFEST_FILE).exists():
        raise ScaffoldError(f"Not an agent package (no {MANIFEST_FILE}): {root}")
    state_path = root / SCAFFOLD_STATE_FILE
    if not state_path.exists():
        raise ScaffoldError(
            f"No {SCAFFOLD_STATE_FILE} in {root} — this package predates update support "
            "or was created manually, so there is no safe baseline to update against."
        )
    try:
        recorded: dict[str, str] = json.loads(state_path.read_text(encoding="utf-8"))["files"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise ScaffoldError(f"Corrupt {SCAFFOLD_STATE_FILE} in {root}: {exc}") from exc
    with (root / MANIFEST_FILE).open("rb") as handle:
        manifest = tomllib.load(handle)
    name = manifest.get("name", root.name)
    purpose = manifest.get("purpose", f"Declarative agent '{name}' built with Agent0.")

    report = UpdateReport(agent_path=root)
    new_hashes: dict[str, str] = {}
    for rel_path, content in render_files(name, purpose).items():
        target = root / rel_path
        old_hash = recorded.get(rel_path)
        new_hash = _hash_text(content)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            report.restored.append(rel_path)
            new_hashes[rel_path] = new_hash
            continue
        current_hash = _hash_text(target.read_text(encoding="utf-8"))
        if current_hash == new_hash:
            report.unchanged.append(rel_path)
            new_hashes[rel_path] = new_hash
        elif old_hash is not None and current_hash == old_hash:
            target.write_text(content, encoding="utf-8")
            report.updated.append(rel_path)
            new_hashes[rel_path] = new_hash
        else:
            # Customized by the author (or unknown baseline): never clobber.
            report.skipped_modified.append(rel_path)
            new_hashes[rel_path] = old_hash if old_hash is not None else current_hash
    _write_state(root, new_hashes)
    return report


def update_all(directory: str | Path) -> list[UpdateReport]:
    """Update every agent package under a directory."""
    return [
        update_agent(manifest.parent)
        for manifest in sorted(Path(directory).resolve().rglob(MANIFEST_FILE))
        if (manifest.parent / SCAFFOLD_STATE_FILE).exists()
    ]


def discover_agents(directory: str | Path) -> list[Path]:
    """Find every agent package (folder containing agent.toml) under a directory."""
    return sorted(p.parent for p in Path(directory).resolve().rglob(MANIFEST_FILE))


# --------------------------------------------------------------------------- loader

MANIFEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["name", "version", "purpose", "contracts", "steps"],
    "properties": {
        "name": {"type": "string", "pattern": r"^[a-z0-9][a-z0-9-]*$"},
        "version": {"type": "string"},
        "purpose": {"type": "string"},
        "runtime": {"type": "object"},
        "contracts": {
            "type": "object",
            "required": ["input_schema", "output_schema"],
            "properties": {
                "input_schema": {"type": "string"},
                "output_schema": {"type": "string"},
            },
        },
        "catalog": {"type": "object"},
        "policies": {
            "type": "object",
            "properties": {
                "blocked_command_patterns": {"type": "array", "items": {"type": "string"}}
            },
        },
        "steps": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "title", "kind", "outputs"],
                "properties": {
                    "id": {"type": "string", "pattern": r"^[\w-]+$"},
                    "title": {"type": "string"},
                    "kind": {"type": "string"},
                    "rationale": {"type": "string"},
                    "skill": {"type": "string"},
                    "command": {"type": "string"},
                    "inputs": {"type": "array", "items": {"type": "string"}},
                    "outputs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


@dataclass(slots=True)
class AgentDefinition:
    root: Path
    name: str
    version: str
    purpose: str
    config: AgentConfig
    steps: list[PlanStep]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    catalog_config: dict[str, dict[str, Any]] = field(default_factory=dict)
    blocked_command_patterns: list[str] = field(default_factory=list)


class ManifestPlanner:
    """Planner that replays the manifest's steps (plus optional extra steps)."""

    def __init__(self, definition: AgentDefinition, extra_steps: list[PlanStep] | None = None) -> None:
        self.definition = definition
        self.extra_steps = extra_steps or []

    def create_plan(self, task: TaskSpec) -> Plan:
        return Plan(
            task=task,
            steps=list(self.definition.steps) + self.extra_steps,
            strategy=f"manifest:{self.definition.name}",
        )


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise AgentLoadError(f"{label} not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentLoadError(f"{label} is not valid JSON: {path}: {exc}") from exc


def load_agent(agent_path: str | Path) -> AgentDefinition:
    root = Path(agent_path).resolve()
    manifest_path = root / MANIFEST_FILE
    if not manifest_path.exists():
        raise AgentLoadError(f"No {MANIFEST_FILE} found in {root}")
    try:
        with manifest_path.open("rb") as handle:
            manifest = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise AgentLoadError(f"{manifest_path} is not valid TOML: {exc}") from exc
    errors = validate(manifest, MANIFEST_SCHEMA)
    if errors:
        raise AgentLoadError("Invalid manifest:\n" + "\n".join(errors))

    steps = []
    for raw in manifest["steps"]:
        step = PlanStep(
            id=raw["id"],
            title=raw["title"],
            kind=raw["kind"],
            rationale=raw.get("rationale", raw["title"]),
            inputs=list(raw.get("inputs", [])),
            outputs=list(raw.get("outputs", [])),
            skill=raw.get("skill"),
            command=raw.get("command"),
        )
        if step.skill and not (root / step.skill).exists():
            raise AgentLoadError(f"Step '{step.id}': skill file not found: {root / step.skill}")
        steps.append(step)

    # Precedence: manifest defaults < conf/base.toml < conf/local.toml
    runtime = {**manifest.get("runtime", {}), **load_layered_config(root / "conf").get("runtime", {})}
    definition = AgentDefinition(
        root=root,
        name=manifest["name"],
        version=manifest["version"],
        purpose=manifest["purpose"],
        config=AgentConfig.from_mapping(runtime),
        steps=steps,
        input_schema=_read_json(root / manifest["contracts"]["input_schema"], "Input schema"),
        output_schema=_read_json(root / manifest["contracts"]["output_schema"], "Output schema"),
        catalog_config=manifest.get("catalog", {}),
        blocked_command_patterns=list(manifest.get("policies", {}).get("blocked_command_patterns", [])),
    )
    compile_definition(definition)  # fail fast on DAG errors
    return definition


def compile_definition(definition: AgentDefinition) -> Pipeline:
    """Compile the manifest steps into a pipeline and check its shape."""
    plan = ManifestPlanner(definition).create_plan(TaskSpec(objective=definition.purpose))
    try:
        pipe = compile_plan(plan, ToolStepHandler())
    except PipelineError as exc:
        raise AgentLoadError(f"Manifest steps do not form a valid pipeline: {exc}") from exc
    unknown = definition and (pipe.free_inputs - {TASK_INPUT})
    if unknown:
        raise AgentLoadError(f"Steps consume inputs nothing produces: {sorted(unknown)}")
    if FINAL_OUTPUT not in pipe.outputs:
        raise AgentLoadError(f"No step produces '{FINAL_OUTPUT}' — the pipeline has no final result")
    return pipe


def build_session(
    definition: AgentDefinition,
    extra_steps: list[PlanStep] | None = None,
    base_path: Path | None = None,
    shared_path: Path | None = None,
) -> AgentSession:
    """Wire a session for this agent: catalog, policy hooks, handler, planner."""
    hook_manager = HookManager()
    engine = PolicyEngine()
    engine.blocked_command_patterns.extend(definition.blocked_command_patterns)
    hook_manager.register(PolicyHook(engine))
    if shared_path is None:
        # Env var wins over manifest/conf so operators can redirect the fleet.
        shared_root = os.getenv("AGENT0_SHARED_ROOT") or definition.config.shared_root
        shared_path = Path(shared_root) if shared_root else None
    catalog = DataCatalog.from_config(
        definition.catalog_config, base_path or definition.root, shared_path=shared_path
    )
    handler = ToolStepHandler(hook_manager, definition.config.command_timeout_seconds)
    return AgentSession(
        planner=ManifestPlanner(definition, extra_steps),
        handler=handler,
        hook_manager=hook_manager,
        catalog=catalog,
        config=definition.config,
    )


def run_agent(
    definition: AgentDefinition,
    input_doc: Any,
    extra_steps: list[PlanStep] | None = None,
    base_path: Path | None = None,
    shared_path: Path | None = None,
) -> ExecutionResult:
    """Validate input, run the agent, validate output. The full contract loop."""
    input_errors = validate(input_doc, definition.input_schema)
    if input_errors:
        return ExecutionResult(
            success=False,
            summary="Input rejected: does not conform to the input contract.",
            step_results=[],
            blocked_reason="input contract violation:\n" + "\n".join(input_errors),
        )
    session = build_session(definition, extra_steps, base_path, shared_path)
    task = TaskSpec(objective=definition.purpose, metadata={"agent": definition.name})
    result = session.run(task, task_input=input_doc)
    if result.success and FINAL_OUTPUT in result.outputs:
        output_errors = validate(result.outputs[FINAL_OUTPUT], definition.output_schema)
        if output_errors:
            return ExecutionResult(
                success=False,
                summary="Run completed but output violates the output contract.",
                step_results=result.step_results,
                outputs=result.outputs,
                blocked_reason="output contract violation:\n" + "\n".join(output_errors),
            )
    return result


# --------------------------------------------------------------------------- validation

_JSON_TYPES = {
    "object": dict, "array": list, "string": str, "integer": int,
    "number": (int, float), "boolean": bool, "null": type(None),
}


def _check_type(instance: Any, expected: str) -> bool:
    python_type = _JSON_TYPES.get(expected)
    if python_type is None:
        return True
    if expected in ("integer", "number") and isinstance(instance, bool):
        return False
    return isinstance(instance, python_type)


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Minimal JSON-Schema-subset validator; empty list means valid."""
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_check_type(instance, t) for t in allowed):
            errors.append(f"{path}: expected type {expected_type}, got {type(instance).__name__}")
            return errors
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in enum {schema['enum']}")
    if isinstance(instance, str) and "pattern" in schema and not re.search(schema["pattern"], instance):
        errors.append(f"{path}: string does not match pattern {schema['pattern']!r}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is less than minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is greater than maximum {schema['maximum']}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property '{key}'")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{path}.{key}"))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: has {len(instance)} items, minimum is {schema['minItems']}")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{index}]"))
    return errors


def is_valid_schema(schema: Any, path: str = "$") -> list[str]:
    """Structural sanity check of a schema document itself."""
    errors: list[str] = []
    if not isinstance(schema, dict):
        return [f"{path}: schema must be an object, got {type(schema).__name__}"]
    expected_type = schema.get("type")
    if expected_type is not None:
        for t in (expected_type if isinstance(expected_type, list) else [expected_type]):
            if t not in _JSON_TYPES:
                errors.append(f"{path}: unknown type {t!r}")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            errors.append(f"{path}: invalid pattern: {exc}")
    for key, subschema in schema.get("properties", {}).items():
        errors.extend(is_valid_schema(subschema, f"{path}.{key}"))
    if isinstance(schema.get("items"), dict):
        errors.extend(is_valid_schema(schema["items"], f"{path}.items"))
    return errors


# --------------------------------------------------------------------------- test harness

CASES_FILE = "tests/cases.toml"


@dataclass(slots=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(slots=True)
class CaseResult:
    name: str
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentTestReport:
    agent_path: Path
    agent_name: str
    conformance: list[CheckResult] = field(default_factory=list)
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.conformance) and all(c.passed for c in self.cases)


def run_conformance(agent_path: str | Path) -> tuple[AgentDefinition | None, list[CheckResult]]:
    """Universal checks any agent package must pass; no test authoring needed."""
    checks: list[CheckResult] = []
    try:
        definition = load_agent(agent_path)
        checks.append(CheckResult("manifest loads, contracts exist, DAG compiles", True))
    except AgentLoadError as exc:
        checks.append(CheckResult("manifest loads, contracts exist, DAG compiles", False, str(exc)))
        return None, checks
    schema_errors = is_valid_schema(definition.input_schema) + is_valid_schema(definition.output_schema)
    checks.append(CheckResult("I/O schemas are well-formed", not schema_errors, "; ".join(schema_errors)))
    engine = PolicyEngine()
    engine.blocked_command_patterns.extend(definition.blocked_command_patterns)
    pattern_errors = engine.validate_patterns()
    checks.append(CheckResult("policy patterns compile", not pattern_errors, "; ".join(pattern_errors)))
    try:
        DataCatalog.from_config(definition.catalog_config, definition.root, shared_path=definition.root)
        checks.append(CheckResult("catalog config resolves", True))
    except DatasetError as exc:
        checks.append(CheckResult("catalog config resolves", False, str(exc)))
    return definition, checks


def _dot_get(document: Any, path: str) -> Any:
    for part in path.split("."):
        if isinstance(document, dict) and part in document:
            document = document[part]
        else:
            return None
    return document


def _run_case(definition: AgentDefinition, name: str, case: dict[str, Any]) -> CaseResult:
    input_path = definition.root / "tests" / case.get("input", "")
    if not input_path.exists():
        return CaseResult(name, False, [f"input file not found: {input_path}"])
    try:
        input_doc = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CaseResult(name, False, [f"input file is not valid JSON: {exc}"])

    extra_steps = None
    if case.get("probe_command"):
        extra_steps = [
            PlanStep(
                id="policy-probe",
                title="Policy probe (injected by the test harness)",
                kind="command",
                rationale="Verifies the agent's policy configuration blocks this command.",
                inputs=[FINAL_OUTPUT],
                outputs=["probe_result"],
                command=case["probe_command"],
            )
        ]

    # Isolated catalog: file datasets (agent-scoped AND shared) write into a
    # temp dir, never into real agent memory or the real shared root.
    with tempfile.TemporaryDirectory(prefix="agent0-test-") as tmp:
        result = run_agent(
            definition, input_doc, extra_steps=extra_steps,
            base_path=Path(tmp), shared_path=Path(tmp) / "shared",
        )

    failures: list[str] = []
    expect = case.get("expect", {})
    expected_status = expect.get("status", "success")
    actual_status = "blocked" if result.blocked_reason else ("success" if result.success else "failed")
    if actual_status != expected_status:
        detail = result.blocked_reason or result.summary
        failures.append(f"expected status '{expected_status}', got '{actual_status}' ({detail})")
    final = result.outputs.get(FINAL_OUTPUT)
    if expect.get("output_valid") and actual_status == "success":
        errors = validate(final, definition.output_schema)
        if errors:
            failures.append("output does not conform to output schema: " + "; ".join(errors))
    for path, expected_value in expect.get("fields", {}).items():
        actual_value = _dot_get(final, path)
        if actual_value != expected_value:
            failures.append(f"field '{path}': expected {expected_value!r}, got {actual_value!r}")
    return CaseResult(name, not failures, failures)


def run_cases(definition: AgentDefinition) -> list[CaseResult]:
    cases_path = definition.root / CASES_FILE
    if not cases_path.exists():
        return [CaseResult("cases.toml", False, [f"no {CASES_FILE} found — agent has no test cases"])]
    try:
        with cases_path.open("rb") as handle:
            cases = tomllib.load(handle).get("cases", {})
    except tomllib.TOMLDecodeError as exc:
        return [CaseResult("cases.toml", False, [f"invalid TOML: {exc}"])]
    if not cases:
        return [CaseResult("cases.toml", False, ["no [cases.<name>] entries defined"])]
    return [_run_case(definition, name, case) for name, case in cases.items()]


def test_agent(agent_path: str | Path) -> AgentTestReport:
    """Conformance suite + declarative test cases for one agent package."""
    path = Path(agent_path).resolve()
    definition, conformance = run_conformance(path)
    report = AgentTestReport(
        agent_path=path,
        agent_name=definition.name if definition else path.name,
        conformance=conformance,
    )
    if definition is not None:
        report.cases = run_cases(definition)
    return report


def test_all(directory: str | Path) -> list[AgentTestReport]:
    return [test_agent(path) for path in discover_agents(directory)]


def format_report(report: AgentTestReport) -> str:
    lines = [f"Agent: {report.agent_name} ({report.agent_path})", "  Conformance:"]
    for check in report.conformance:
        mark = "PASS" if check.passed else "FAIL"
        lines.append(f"    [{mark}] {check.name}" + (f" — {check.detail}" if check.detail else ""))
    if report.cases:
        lines.append("  Cases:")
        for case in report.cases:
            lines.append(f"    [{'PASS' if case.passed else 'FAIL'}] {case.name}")
            lines.extend(f"           - {failure}" for failure in case.failures)
    lines.append(f"  Result: {'PASS' if report.passed else 'FAIL'}")
    return "\n".join(lines)
