"""Create isolated method environments without touching upstream checkouts."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "environments/manifest.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=["all", *manifest], default="all")
    parser.add_argument(
        "--lock",
        action="store_true",
        help="Resolve/update lockfiles instead of installing",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview uv sync without installing"
    )
    args = parser.parse_args()
    if args.lock and args.dry_run:
        parser.error("--lock and --dry-run cannot be combined")
    uv = shutil.which("uv")
    if not uv:
        parser.error(
            "uv is required: https://docs.astral.sh/uv/getting-started/installation/"
        )
    selected = (
        manifest if args.method == "all" else {args.method: manifest[args.method]}
    )
    failures = []
    for name, config in selected.items():
        project = ROOT / config["project"]
        environment = ROOT / config["environment"]
        if not args.lock and not (project / "uv.lock").is_file():
            print(
                f"{name}: missing uv.lock; run --method {name} --lock first", flush=True
            )
            failures.append(name)
            continue
        # Always target a fixed, separate environment, even if the caller has
        # another venv activated or UV_PROJECT_ENVIRONMENT exported.
        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        env["UV_PROJECT_ENVIRONMENT"] = str(environment)
        command = [uv, "lock" if args.lock else "sync", "--project", str(project)]
        command.extend(["--python", config["python"], "--managed-python"])
        if not args.lock:
            command.extend(["--locked", "--no-dev"])
        if args.dry_run:
            command.append("--dry-run")
        print(f"{name}: Python {config['python']} -> {environment}", flush=True)
        result = subprocess.run(command, cwd=ROOT, env=env)
        if result.returncode:
            failures.append(name)
    if failures:
        parser.exit(1, "Failed environments: " + ", ".join(failures) + "\n")


if __name__ == "__main__":
    main()
