"""JSON command surface for Aura's append-only M0 control plane."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from forge import aura_runtime


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aura")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Git repository root")
    parser.add_argument("--state-root", type=Path, help="external user-local Aura state directory")
    commands = parser.add_subparsers(dest="command", required=True)

    def add_state_root(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--state-root", type=Path, default=argparse.SUPPRESS)

    init = commands.add_parser("init", help="record a bounded task in the Aura ledger")
    init.add_argument("repository", nargs="?", type=Path)
    init.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    init.add_argument("--objective")
    init.add_argument("--allow", action="append", dest="allowed_paths")
    add_state_root(init)
    build = commands.add_parser("build", help="request a governed builder run")
    build.add_argument("objective")
    build.add_argument("--allow", action="append", required=True, dest="allowed_paths")
    build.add_argument("--budget-attempts", type=int, required=True)
    build.add_argument("--authorization-id", required=True)
    build.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    add_state_root(build)
    state = commands.add_parser("status", help="list durable task state")
    state.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    add_state_root(state)
    inspect = commands.add_parser("inspect", help="inspect a durable task")
    inspect.add_argument("task_id")
    inspect.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    add_state_root(inspect)
    pause = commands.add_parser("pause", help="pause a task before dispatch")
    pause.add_argument("task_id")
    pause.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    add_state_root(pause)
    resume = commands.add_parser("resume", help="resume a paused task")
    resume.add_argument("task_id")
    resume.add_argument("--repo", type=Path, default=argparse.SUPPRESS)
    add_state_root(resume)
    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "state_root", None):
        os.environ["AURA_STATE_HOME"] = str(args.state_root.resolve())
    repo = getattr(args, "repo", Path.cwd()).resolve()
    if args.command == "init":
        repo = (args.repository or repo).resolve()
        initialized = aura_runtime.init_repository(repo)
        if args.objective:
            if not args.allowed_paths:
                raise aura_runtime.RuntimeErrorDetail(
                    "INVALID_REQUEST", "--allow is required when init creates a task"
                )
            initialized["task"] = aura_runtime.init_task(
                repo, objective=args.objective, allowed_paths=args.allowed_paths
            )
        return initialized
    if args.command == "build":
        return aura_runtime.request_build(
            repo,
            objective=args.objective,
            allowed_paths=args.allowed_paths,
            budget_attempts=args.budget_attempts,
            authorization_id=args.authorization_id,
        )
    if args.command == "status":
        return aura_runtime.status(repo)
    if args.command == "inspect":
        return aura_runtime.inspect(repo, args.task_id)
    if args.command == "pause":
        return aura_runtime.pause(repo, args.task_id)
    if args.command == "resume":
        return aura_runtime.resume(repo, args.task_id)
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    try:
        result = dispatch(_parser().parse_args(argv))
        print(json.dumps(result, sort_keys=True))
        return 0
    except aura_runtime.RuntimeErrorDetail as exc:
        print(
            json.dumps({"status": "BLOCKED", "code": exc.code, "message": str(exc)}, sort_keys=True)
        )
        return 2
    except Exception as exc:  # CLI boundary keeps machine-readable failures stable.
        print(
            json.dumps(
                {"status": "UNKNOWN", "code": "UNEXPECTED", "message": str(exc)}, sort_keys=True
            )
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())
