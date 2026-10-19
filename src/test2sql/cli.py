"""Local dataset preparation, diagnostics and evaluator command line interface."""

import argparse
import json
import shlex

from .config import ConfigError, load_config
from .datasets.spider import prepare
from .doctor import diagnose
from .evaluation.runner import evaluate
from .evaluation.smoke import smoke
from .runner import METHODS, plan


def main(argv=None):
    parser = argparse.ArgumentParser(prog="test2sql")
    parser.add_argument(
        "--config", help="Config YAML (paths relative to its root setting)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "run"):
        child = sub.add_parser(name)
        child.add_argument("--config", default=argparse.SUPPRESS)
        child.add_argument("--method", choices=["all", *METHODS], default="all")
        child.add_argument(
            "--json",
            action="store_true",
            help="Print machine-readable diagnostics/plan",
        )
        if name == "run":
            child.add_argument("--split", choices=["dev"], default="dev")
            child.add_argument("--limit", type=int)
            child.add_argument("--run-id")
            child.add_argument("--dry-run", action="store_true")
    prepare_parser = sub.add_parser(
        "prepare", help="Stage a deterministic Spider subset without inference"
    )
    prepare_parser.add_argument("--config", default=argparse.SUPPRESS)
    prepare_parser.add_argument("--method", choices=["all", *METHODS], default="all")
    prepare_parser.add_argument("--split", choices=["dev"], default="dev")
    selection = prepare_parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--limit", type=int, help="First N source records (default: 3)"
    )
    selection.add_argument(
        "--indices", type=int, nargs="+", help="Explicit ordered source indices"
    )
    prepare_parser.add_argument("--run-id")
    for name in ("evaluate", "check-evaluator"):
        child = sub.add_parser(name)
        child.add_argument("--config", default=argparse.SUPPRESS)
        child.add_argument("--run-id", required=True)
        child.add_argument(
            "--database-mode", choices=["test-suite", "spider"], default="test-suite"
        )
        child.add_argument("--timeout", type=float, default=120)
        if name == "evaluate":
            child.add_argument(
                "--predictions",
                required=True,
                help="Ordered SQL lines or normalized prediction JSONL",
            )
            child.add_argument("--label", default="manual")
    args = parser.parse_args(argv)
    config = None
    try:
        config = load_config(args.config)
        if args.command == "prepare":
            limit = (
                args.limit
                if args.limit is not None
                else (None if args.indices is not None else 3)
            )
            result = prepare(
                config, args.method, args.split, limit, args.indices, args.run_id
            )
            print(config.safe(json.dumps(result, indent=2)))
            return 0
        if args.command == "evaluate":
            result = evaluate(
                config,
                args.run_id,
                config.path(args.predictions),
                args.label,
                args.database_mode,
                args.timeout,
            )
            print(config.safe(json.dumps(result, indent=2)))
            return 0 if result["status"] == "completed" else 1
        if args.command == "check-evaluator":
            result = smoke(config, args.run_id, args.database_mode, args.timeout)
            print(config.safe(json.dumps(result, indent=2)))
            return 0 if result["status"] == "passed" else 1
        if args.command == "doctor":
            checks = diagnose(config, args.method)
            result = {
                "checks": checks,
                "ok": not any(c["status"] == "error" for c in checks),
            }
            output = (
                json.dumps(result, indent=2)
                if args.json
                else "\n".join(
                    f"[{c['status'].upper()}] {c['name']}: {c['detail']}"
                    for c in checks
                )
            )
            print(config.safe(output))
            return 0 if result["ok"] else 1
        if not args.dry_run:
            raise ConfigError(
                "Inference is not implemented yet; use run --dry-run or prepare"
            )
        result = plan(config, args.method, args.split, args.limit, args.run_id)
        if args.json:
            output = json.dumps(result, indent=2)
        else:
            lines = [
                f"Dry run: {result['run_id']} (no files created, no LLM calls)",
                f"Spider {args.split}, limit={args.limit or 'all'}: {result['source']}",
                f"Run directory: {result['run_directory']}",
                result["staging"],
                "Environment: " + json.dumps(result["environment"]),
            ]
            for step in result["stages"]:
                lines.extend(
                    [
                        f"\n[{step['method']}] cwd: {step['cwd']}",
                        "command: " + shlex.join(step["argv"]),
                        "output: " + step["output"],
                    ]
                )
            lines.append(
                "\nPreview only; use doctor to check prerequisites. Use prepare to stage inputs; inference follows in Phases 4–5."
            )
            output = "\n".join(lines)
        print(config.safe(output))
        return 0
    except (ConfigError, OSError, ValueError) as exc:
        # Configuration parse errors deliberately omit raw YAML/dotenv values.
        message = (
            str(exc)
            if isinstance(exc, ConfigError)
            else "Cannot read project inputs; check paths and configuration"
        )
        print("error: " + (config.safe(message) if config else message))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
