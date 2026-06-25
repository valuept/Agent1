from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .contracts import TaskSpec
from .runtime import Agent0Runtime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent0", description="Agent0 runtime CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run_parser = subcommands.add_parser("run", help="Execute a task with Agent0")
    run_parser.add_argument("--objective", required=True, help="Task objective")
    run_parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Task constraint (repeatable)",
    )
    run_parser.add_argument(
        "--acceptance-criterion",
        action="append",
        default=[],
        help="Acceptance criterion (repeatable)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        runtime = Agent0Runtime.default()
        task = TaskSpec(
            objective=args.objective,
            constraints=args.constraint,
            acceptance_criteria=args.acceptance_criterion,
        )
        result = runtime.run(task)
        print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
