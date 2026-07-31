"""The Agent0 runtime engine: contracts, DAG pipeline, hooks, catalog, session.

Nodes declare inputs/outputs by name; the pipeline matches names to build the
dependency graph and validates it (cycles, duplicate outputs) at construction
time. Named data flows through the catalog. Hooks observe and guard execution
— a hook that raises aborts the run.
"""

from __future__ import annotations

import json
import re
import tomllib
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any, Protocol

from .policies import LocalCommandTool, PolicyViolation

_NAME = re.compile(r"^[\w.-]+$")
TASK_INPUT = "task_input"
FINAL_OUTPUT = "final_output"
RUNS_DATASET = "runs"
HOOK_EVENTS = frozenset(
    {
        "before_pipeline_run",
        "after_pipeline_run",
        "on_pipeline_error",
        "before_node_run",
        "after_node_run",
        "on_node_error",
        "before_tool_run",
        "after_tool_run",
    }
)


# --------------------------------------------------------------------------- contracts

@dataclass(slots=True)
class TaskSpec:
    objective: str
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PlanStep:
    id: str
    title: str
    kind: str
    rationale: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    skill: str | None = None
    command: str | None = None


@dataclass(slots=True)
class Plan:
    task: TaskSpec
    steps: list[PlanStep]
    strategy: str


@dataclass(slots=True)
class StepResult:
    step_id: str
    success: bool
    summary: str
    error: str | None = None


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    summary: str
    step_results: list[StepResult]
    outputs: dict[str, Any] = field(default_factory=dict)
    blocked_reason: str | None = None


class Planner(Protocol):
    def create_plan(self, task: TaskSpec) -> Plan: ...


class StepHandler(Protocol):
    """Executes one plan step given its named inputs; returns the step's output value."""

    def handle(self, task: TaskSpec, step: PlanStep, inputs: dict[str, Any]) -> Any: ...


# --------------------------------------------------------------------------- pipeline

class PipelineError(ValueError):
    """Raised when a pipeline or node definition is invalid."""


def _names(value: str | Iterable[str] | None, label: str, owner: str) -> list[str]:
    names = [value] if isinstance(value, str) else list(value or [])
    for name in names:
        if not isinstance(name, str) or not _NAME.match(name):
            raise PipelineError(f"Node '{owner}': invalid {label} name {name!r}")
    if len(names) != len(set(names)):
        raise PipelineError(f"Node '{owner}': duplicate {label} names in {names}")
    return names


class Node:
    """A single unit of work: a callable with named inputs and outputs."""

    def __init__(
        self,
        func: Callable,
        inputs: str | Iterable[str] | None,
        outputs: str | Iterable[str] | None,
        *,
        name: str | None = None,
    ) -> None:
        self.name = name or getattr(func, "__name__", "node")
        if not _NAME.match(self.name):
            raise PipelineError(f"Invalid node name {self.name!r}")
        self.func = func
        self.inputs = _names(inputs, "input", self.name)
        self.outputs = _names(outputs, "output", self.name)
        if set(self.inputs) & set(self.outputs):
            raise PipelineError(f"Node '{self.name}': same name used as input and output")

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = self.func(*(inputs[name] for name in self.inputs))
        if not self.outputs:
            return {}
        if len(self.outputs) == 1:
            return {self.outputs[0]: result}
        if isinstance(result, dict):
            return {name: result[name] for name in self.outputs}
        if isinstance(result, (tuple, list)) and len(result) == len(self.outputs):
            return dict(zip(self.outputs, result))
        raise PipelineError(f"Node '{self.name}': cannot map result onto outputs {self.outputs}")


class Pipeline:
    """A validated DAG of nodes, wired by matching input/output names."""

    def __init__(self, nodes: Iterable[Node]) -> None:
        nodes = list(nodes)
        producers: dict[str, Node] = {}
        seen: set[str] = set()
        for nd in nodes:
            if nd.name in seen:
                raise PipelineError(f"Duplicate node name '{nd.name}'")
            seen.add(nd.name)
            for out in nd.outputs:
                if out in producers:
                    raise PipelineError(f"Output '{out}' produced by two nodes")
                producers[out] = nd
        dependencies = {nd: {producers[i] for i in nd.inputs if i in producers} for nd in nodes}
        try:
            self.nodes: list[Node] = list(TopologicalSorter(dependencies).static_order())
        except CycleError as exc:
            raise PipelineError(f"Pipeline contains a cycle: {exc.args[1]}") from exc
        consumed = {i for nd in nodes for i in nd.inputs}
        self.free_inputs: set[str] = consumed - set(producers)
        self.outputs: set[str] = set(producers) - consumed


# --------------------------------------------------------------------------- hooks

class HookManager:
    """Registers hook objects and dispatches events LIFO (last registered first)."""

    def __init__(self) -> None:
        self._hooks: list[object] = []

    def register(self, hook: object) -> None:
        if not any(callable(getattr(hook, event, None)) for event in HOOK_EVENTS):
            raise ValueError(f"{type(hook).__name__} implements no hook events")
        if hook not in self._hooks:
            self._hooks.append(hook)

    def unregister(self, hook: object) -> None:
        if hook in self._hooks:
            self._hooks.remove(hook)

    def call(self, event: str, **kwargs: Any) -> None:
        for hook in reversed(self._hooks):
            method = getattr(hook, event, None)
            if callable(method):
                method(**kwargs)


# --------------------------------------------------------------------------- catalog

class DatasetError(Exception):
    """Raised when a dataset load/save or catalog config fails."""


class MemoryDataset:
    _EMPTY = object()

    def __init__(self) -> None:
        self._data: Any = MemoryDataset._EMPTY

    def load(self) -> Any:
        if self._data is MemoryDataset._EMPTY:
            raise DatasetError("MemoryDataset is empty: no data has been saved")
        return self._data

    def save(self, data: Any) -> None:
        self._data = data

    def exists(self) -> bool:
        return self._data is not MemoryDataset._EMPTY


class JsonlDataset:
    """Append-oriented record log (run history, shared knowledge, cases)."""

    def __init__(self, filepath: str | Path) -> None:
        self.filepath = Path(filepath)

    def load(self) -> list[Any]:
        if not self.filepath.exists():
            return []
        lines = self.filepath.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(line) for line in lines if line]

    def save(self, data: Any) -> None:
        """Append one record (or each record of a list) as a JSON line."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        records = data if isinstance(data, list) else [data]
        with self.filepath.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def exists(self) -> bool:
        return self.filepath.exists()


_DATASET_TYPES = {"memory": MemoryDataset, "jsonl": JsonlDataset}


class DataCatalog:
    """Named datasets. Unregistered names become in-memory datasets. Entries
    with `scope = "shared"` resolve under a shared root, so multiple agents
    read and write the same datasets."""

    def __init__(self, datasets: dict[str, Any] | None = None) -> None:
        self._datasets: dict[str, Any] = dict(datasets or {})

    @classmethod
    def from_config(
        cls,
        config: dict[str, dict[str, Any]],
        base_path: Path | None = None,
        shared_path: Path | None = None,
    ) -> "DataCatalog":
        datasets: dict[str, Any] = {}
        for name, entry in config.items():
            entry = dict(entry)
            type_key = entry.pop("type", "memory")
            scope = entry.pop("scope", "agent")
            if type_key not in _DATASET_TYPES:
                raise DatasetError(f"Dataset '{name}': unknown type '{type_key}' (known: {sorted(_DATASET_TYPES)})")
            if scope not in ("agent", "shared"):
                raise DatasetError(f"Dataset '{name}': unknown scope '{scope}' (use 'agent' or 'shared')")
            root = base_path
            if scope == "shared":
                if shared_path is None:
                    raise DatasetError(
                        f"Dataset '{name}' has scope 'shared' but no shared root is configured "
                        "(set AGENT0_SHARED_ROOT or runtime.shared_root)"
                    )
                root = shared_path
            if "filepath" in entry and root is not None and not Path(entry["filepath"]).is_absolute():
                entry["filepath"] = root / entry["filepath"]
            try:
                datasets[name] = _DATASET_TYPES[type_key](**entry)
            except TypeError as exc:
                raise DatasetError(f"Dataset '{name}': invalid config: {exc}") from exc
        return cls(datasets)

    def get(self, name: str) -> Any:
        if name not in self._datasets:
            self._datasets[name] = MemoryDataset()
        return self._datasets[name]

    def load(self, name: str) -> Any:
        try:
            return self.get(name).load()
        except Exception as exc:
            raise DatasetError(f"Failed to load dataset '{name}': {exc}") from exc

    def save(self, name: str, data: Any) -> None:
        try:
            self.get(name).save(data)
        except Exception as exc:
            raise DatasetError(f"Failed to save dataset '{name}': {exc}") from exc

    def exists(self, name: str) -> bool:
        return name in self._datasets and self._datasets[name].exists()


# --------------------------------------------------------------------------- runner

def run_pipeline(pipeline: Pipeline, catalog: DataCatalog, hooks: HookManager, run_id: str = "") -> dict[str, Any]:
    """Execute the DAG in topological order against the catalog."""
    missing = {name for name in pipeline.free_inputs if not catalog.exists(name)}
    if missing:
        raise ValueError(f"Pipeline inputs not found in catalog: {sorted(missing)}")
    hooks.call("before_pipeline_run", pipeline=pipeline, catalog=catalog, run_id=run_id)
    try:
        for nd in pipeline.nodes:
            inputs = {name: catalog.load(name) for name in nd.inputs}
            try:
                hooks.call("before_node_run", node=nd, catalog=catalog, inputs=inputs, run_id=run_id)
                outputs = nd.run(inputs)
            except Exception as exc:
                hooks.call("on_node_error", error=exc, node=nd, catalog=catalog, inputs=inputs, run_id=run_id)
                raise
            hooks.call(
                "after_node_run", node=nd, catalog=catalog, inputs=inputs, outputs=outputs, run_id=run_id
            )
            for name, value in outputs.items():
                catalog.save(name, value)
    except Exception as exc:
        hooks.call("on_pipeline_error", error=exc, pipeline=pipeline, catalog=catalog, run_id=run_id)
        raise
    results = {name: catalog.load(name) for name in pipeline.outputs}
    hooks.call("after_pipeline_run", pipeline=pipeline, catalog=catalog, run_id=run_id, results=results)
    return results


# --------------------------------------------------------------------------- config

@dataclass(slots=True)
class AgentConfig:
    max_iterations: int = 12
    command_timeout_seconds: int = 120
    shared_root: str | None = None

    @classmethod
    def from_mapping(cls, runtime: dict[str, Any]) -> "AgentConfig":
        return cls(
            max_iterations=int(runtime.get("max_iterations", 12)),
            command_timeout_seconds=int(runtime.get("command_timeout_seconds", 120)),
            shared_root=runtime.get("shared_root"),
        )


def load_layered_config(conf_dir: Path) -> dict[str, Any]:
    """Deep-merge conf/base.toml with conf/local.toml (local wins)."""
    def merge(base: dict, override: dict) -> dict:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    merged: dict[str, Any] = {}
    for layer in ("base", "local"):
        path = conf_dir / f"{layer}.toml"
        if path.exists():
            with path.open("rb") as handle:
                merged = merge(merged, tomllib.load(handle))
    return merged


# --------------------------------------------------------------------------- handlers

class DeterministicStepHandler:
    """Default handler: a structured, traceable record of the step (no model call)."""

    def handle(self, task: TaskSpec, step: PlanStep, inputs: dict[str, Any]) -> Any:
        return {
            "step_id": step.id,
            "kind": step.kind,
            "objective": task.objective,
            "rationale": step.rationale,
            "consumed": sorted(inputs),
            "skill": step.skill,
            "summary": f"[{step.kind}] {step.title} — completed deterministically",
        }


class ToolStepHandler:
    """Runs steps that declare a `command` via the policy-gated tool;
    skill-only steps fall back to the deterministic handler."""

    def __init__(self, hook_manager: HookManager | None = None, timeout_seconds: int = 120) -> None:
        self.tool = LocalCommandTool(hook_manager=hook_manager, timeout_seconds=timeout_seconds)
        self._fallback = DeterministicStepHandler()

    def handle(self, task: TaskSpec, step: PlanStep, inputs: dict[str, Any]) -> Any:
        if not step.command:
            return self._fallback.handle(task, step, inputs)
        result = self.tool.run(step.command)
        return {
            "step_id": step.id,
            "kind": step.kind,
            "command": result.command,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "summary": f"[{step.kind}] {step.title} — command exited {result.exit_code}",
        }


class LLMStepHandler:
    """Declared integration slot for a model-backed handler (e.g. the Claude API)."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def handle(self, task: TaskSpec, step: PlanStep, inputs: dict[str, Any]) -> Any:
        raise NotImplementedError("No model backend is wired in yet.")


# --------------------------------------------------------------------------- session

def compile_plan(plan: Plan, handler: StepHandler) -> Pipeline:
    """Compile a Plan into an executable Pipeline, one node per step."""
    def make_func(step: PlanStep):
        def run_step(*args: Any) -> Any:
            return handler.handle(plan.task, step, dict(zip(step.inputs, args)))
        return run_step

    return Pipeline(
        Node(make_func(step), step.inputs, step.outputs, name=step.id) for step in plan.steps
    )


class _Collector:
    """Hook recording a StepResult per executed node."""

    def __init__(self) -> None:
        self.results: list[StepResult] = []

    def after_node_run(self, node: Node, outputs: dict[str, Any], **_: Any) -> None:
        summary = next(
            (str(v["summary"]) for v in outputs.values() if isinstance(v, dict) and "summary" in v),
            node.name,
        )
        self.results.append(StepResult(step_id=node.name, success=True, summary=summary))

    def on_node_error(self, error: Exception, node: Node, **_: Any) -> None:
        self.results.append(
            StepResult(step_id=node.name, success=False, summary=f"Failed: {node.name}", error=str(error))
        )


class AgentSession:
    """One run of an agent end to end: compile the plan, run it with hooks,
    record per-step results, append an audit record to the `runs` dataset."""

    def __init__(
        self,
        planner: Planner,
        handler: StepHandler,
        hook_manager: HookManager,
        catalog: DataCatalog,
        config: AgentConfig | None = None,
    ) -> None:
        self.planner = planner
        self.handler = handler
        self.hook_manager = hook_manager
        self.catalog = catalog
        self.config = config or AgentConfig()

    def run(self, task: TaskSpec, task_input: Any | None = None) -> ExecutionResult:
        run_id = uuid.uuid4().hex[:12]
        plan = self.planner.create_plan(task)
        if len(plan.steps) > self.config.max_iterations:
            return ExecutionResult(
                success=False,
                summary=f"Plan has {len(plan.steps)} steps, exceeding max_iterations={self.config.max_iterations}",
                step_results=[],
                blocked_reason="max_iterations exceeded",
            )
        pipeline = compile_plan(plan, self.handler)
        self.catalog.save(TASK_INPUT, asdict(task) if task_input is None else task_input)

        collector = _Collector()
        self.hook_manager.register(collector)
        blocked_reason = error = None
        outputs: dict[str, Any] = {}
        try:
            outputs = run_pipeline(pipeline, self.catalog, self.hook_manager, run_id)
        except PolicyViolation as exc:
            blocked_reason = str(exc)
        except Exception as exc:
            error = str(exc)
        finally:
            self.hook_manager.unregister(collector)

        if blocked_reason:
            summary = f"Run blocked by policy: {blocked_reason}"
        elif error:
            failed = next((r for r in collector.results if not r.success), None)
            summary = f"Failed at step: {failed.step_id}" if failed else f"Run failed: {error}"
        else:
            summary = "Plan executed successfully."

        execution = ExecutionResult(
            success=blocked_reason is None and error is None,
            summary=summary,
            step_results=collector.results,
            outputs=outputs,
            blocked_reason=blocked_reason,
        )
        self.catalog.save(
            RUNS_DATASET,
            {
                "run_id": run_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "task": asdict(task),
                "success": execution.success,
                "summary": execution.summary,
                "blocked_reason": execution.blocked_reason,
                "steps": [asdict(result) for result in execution.step_results],
            },
        )
        return execution
