"""Minimal Phase 2 command line interface."""

import argparse
import json
import shlex

from .config import ConfigError, load_config
from .doctor import diagnose
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
    args = parser.parse_args(argv)
    config = None
    try:
        config = load_config(args.config)
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
                "Inference is not implemented in Phase 2; use run --dry-run"
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
                "\nPreview only; use doctor to check prerequisites. Staging and execution follow in Phases 3–5."
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
