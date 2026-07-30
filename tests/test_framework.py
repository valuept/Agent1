"""Framework: pipeline, hooks, runner, catalog, validation, policies."""

import pytest

from agent0.core import DataCatalog, DatasetError, HookManager, JsonlDataset, MemoryDataset, Node, Pipeline, PipelineError, run_pipeline
from agent0.factory import is_valid_schema, validate
from agent0.policies import LocalCommandTool, PolicyEngine, PolicyHook, PolicyViolation


def test_dag_toposort_free_inputs_and_outputs():
    p = Pipeline(
        [
            Node(lambda a, b: a + b, ["clean", "extra"], "merged", name="merge"),
            Node(lambda x: x, "raw", "clean", name="cleanse"),
            Node(lambda x: x * 2, "merged", "final", name="double"),
        ]
    )
    order = [n.name for n in p.nodes]
    assert order.index("cleanse") < order.index("merge") < order.index("double")
    assert p.free_inputs == {"raw", "extra"}
    assert p.outputs == {"final"}


def test_invalid_pipelines_rejected_at_construction():
    with pytest.raises(PipelineError, match="cycle"):
        Pipeline([Node(lambda x: x, "a", "b", name="n1"), Node(lambda x: x, "b", "a", name="n2")])
    with pytest.raises(PipelineError, match="produced by two"):
        Pipeline([Node(lambda: 1, None, "out", name="n1"), Node(lambda: 2, None, "out", name="n2")])
    with pytest.raises(PipelineError, match="input and output"):
        Node(lambda x: x, "a", "a", name="loop")


def test_run_pipeline_executes_dag_and_fails_fast_on_missing_input():
    catalog = DataCatalog()
    catalog.save("seed", 2)
    p = Pipeline(
        [
            Node(lambda s: s + 1, "seed", "a", name="inc"),
            Node(lambda s: s * 10, "seed", "b", name="mul"),
            Node(lambda a, b: a + b, ["a", "b"], "total", name="sum"),
        ]
    )
    assert run_pipeline(p, catalog, HookManager()) == {"total": 23}
    with pytest.raises(ValueError, match="absent"):
        run_pipeline(Pipeline([Node(lambda x: x, "absent", "o", name="n")]), DataCatalog(), HookManager())


def test_hooks_lifo_blocking_and_error_events():
    log = []

    class Recorder:
        def __init__(self, label):
            self.label = label

        def before_node_run(self, **_):
            log.append(self.label)

    class Blocker:
        def before_node_run(self, **_):
            raise PermissionError("blocked")

    class Watcher:
        def on_node_error(self, **_):
            log.append("node_error")

        def on_pipeline_error(self, **_):
            log.append("pipeline_error")

    p = Pipeline([Node(lambda: 1, None, "out", name="only")])
    hooks = HookManager()
    hooks.register(Recorder("first"))
    hooks.register(Recorder("second"))
    run_pipeline(p, DataCatalog(), hooks)
    assert log == ["second", "first"]

    log.clear()
    hooks = HookManager()
    hooks.register(Watcher())
    hooks.register(Blocker())
    with pytest.raises(PermissionError):
        run_pipeline(p, DataCatalog(), hooks)
    assert log == ["node_error", "pipeline_error"]
    with pytest.raises(ValueError, match="no hook events"):
        hooks.register(object())


def test_datasets_and_catalog(tmp_path):
    ds = MemoryDataset()
    with pytest.raises(DatasetError, match="empty"):
        ds.load()
    jsonl = JsonlDataset(tmp_path / "log.jsonl")
    jsonl.save({"run": 1})
    jsonl.save({"run": 2})
    assert jsonl.load() == [{"run": 1}, {"run": 2}]

    catalog = DataCatalog()
    catalog.save("intermediate", 42)  # auto-memory for unregistered names
    assert catalog.load("intermediate") == 42
    with pytest.raises(DatasetError, match="unknown type"):
        DataCatalog.from_config({"x": {"type": "parquet"}})


def test_shared_scope(tmp_path):
    shared = tmp_path / "shared"
    config = {"knowledge": {"type": "jsonl", "filepath": "knowledge.jsonl", "scope": "shared"}}
    catalog_a = DataCatalog.from_config(config, tmp_path / "a", shared_path=shared)
    catalog_b = DataCatalog.from_config(config, tmp_path / "b", shared_path=shared)
    catalog_a.save("knowledge", {"fact": "written by A"})
    assert catalog_b.load("knowledge") == [{"fact": "written by A"}]
    with pytest.raises(DatasetError, match="AGENT0_SHARED_ROOT"):
        DataCatalog.from_config(config, base_path=tmp_path)


def test_validation():
    schema = {
        "type": "object",
        "required": ["objective"],
        "properties": {
            "objective": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "high"]},
            "score": {"type": "integer", "minimum": 1, "maximum": 9},
        },
    }
    assert validate({"objective": "x", "priority": "high", "score": 5}, schema) == []
    errors = "\n".join(validate({"priority": "urgent", "score": 10}, schema))
    assert "missing required property 'objective'" in errors
    assert "not in enum" in errors
    assert "greater than maximum" in errors
    assert validate(True, {"type": "integer"}) != []
    assert is_valid_schema(schema) == []
    assert is_valid_schema({"type": "objekt"}) != []
    assert is_valid_schema({"pattern": "["}) != []


def test_policies_and_tool_gating():
    engine = PolicyEngine()
    assert engine.evaluate_command("git reset --hard HEAD").allowed is False
    assert engine.evaluate_command("pytest -q").allowed is True
    engine.blocked_command_patterns.append(r"\bcurl\b")
    assert engine.evaluate_command("curl http://x").allowed is False
    assert PolicyEngine(blocked_command_patterns=["[bad"]).validate_patterns()

    hooks = HookManager()
    hooks.register(PolicyHook())
    tool = LocalCommandTool(hook_manager=hooks)
    with pytest.raises(PolicyViolation, match="blocked"):
        tool.run("rm -rf /critical/data")
    result = tool.run("python --version")
    assert result.exit_code == 0 and "Python" in result.stdout
