from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .factory import (
    AgentLoadError,
    ScaffoldError,
    UpdateReport,
    create_agent,
    discover_agents,
    format_report,
    load_agent,
    run_agent,
    test_agent,
    test_all,
    update_agent,
    update_all,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent0", description="Agent0: build, validate, test and run declarative agents"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="Scaffold a new declarative agent package")
    p.add_argument("name", help="Agent name (lowercase, digits, hyphens)")
    p.add_argument("--dir", default=".", help="Parent directory (default: current)")
    p.add_argument("--purpose", default=None, help="One-line mission statement")

    p = sub.add_parser("validate", help="Validate an agent package")
    p.add_argument("agent", help="Path to the agent package")

    p = sub.add_parser("test", help="Run the agent test harness")
    p.add_argument("agent", nargs="?", default=".", help="Path to the agent package")
    p.add_argument("--all", action="store_true", help="Test every agent under the given directory")

    p = sub.add_parser("update", help="Refresh scaffold-owned files from the current templates")
    p.add_argument("agent", nargs="?", default=".", help="Path to the agent package")
    p.add_argument("--all", action="store_true", help="Update every agent under the given directory")

    p = sub.add_parser("run", help="Run an agent against an input document")
    p.add_argument("agent", help="Path to the agent package")
    p.add_argument("--input", required=True, help="Path to the input JSON document")

    p = sub.add_parser("list", help="List agent packages under a directory")
    p.add_argument("dir", nargs="?", default=".", help="Directory to search")
    return parser


def _print_update_report(report: UpdateReport) -> None:
    print(f"Agent: {report.agent_path}")
    for label, files in [
        ("updated", report.updated),
        ("restored", report.restored),
        ("skipped (customized)", report.skipped_modified),
    ]:
        for rel_path in files:
            print(f"  [{label}] {rel_path}")
    print(
        f"  {len(report.updated)} updated, {len(report.restored)} restored, "
        f"{len(report.skipped_modified)} skipped, {len(report.unchanged)} unchanged"
    )


def main() -> None:
    args = build_parser().parse_args()
    try:
        sys.exit(_dispatch(args))
    except (ScaffoldError, AgentLoadError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "new":
        root = create_agent(args.name, args.dir, purpose=args.purpose)
        print(f"Created agent package: {root}\nNext: agent0 test {root}")
        return 0

    if args.command == "validate":
        definition = load_agent(args.agent)
        print(f"VALID: {definition.name} v{definition.version} ({len(definition.steps)} steps)")
        return 0

    if args.command == "test":
        reports = test_all(args.agent) if args.all else [test_agent(args.agent)]
        if not reports:
            print(f"No agent packages found under {Path(args.agent).resolve()}", file=sys.stderr)
            return 1
        for report in reports:
            print(format_report(report))
        failed = sum(1 for r in reports if not r.passed)
        if args.all:
            print(f"{len(reports)} agent(s) tested, {failed} failed")
        return 1 if failed else 0

    if args.command == "update":
        reports = update_all(args.agent) if args.all else [update_agent(args.agent)]
        if not reports:
            print(f"No updatable agent packages under {Path(args.agent).resolve()}", file=sys.stderr)
            return 1
        for report in reports:
            _print_update_report(report)
        return 0

    if args.command == "run":
        definition = load_agent(args.agent)
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"error: input file not found: {input_path}", file=sys.stderr)
            return 1
        result = run_agent(definition, json.loads(input_path.read_text(encoding="utf-8")))
        print(json.dumps(asdict(result), indent=2, default=str))
        return 0 if result.success else 1

    # list
    agents = discover_agents(args.dir)
    if not agents:
        print(f"No agent packages found under {Path(args.dir).resolve()}")
        return 0
    for path in agents:
        try:
            definition = load_agent(path)
            print(f"{definition.name}\tv{definition.version}\t{path}")
        except AgentLoadError:
            print(f"{path.name}\t(invalid)\t{path}")
    return 0


if __name__ == "__main__":
    main()
