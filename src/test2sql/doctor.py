"""Read-only diagnostics; never import method entry points or contact providers."""

import json
import os
import subprocess
from urllib.parse import urlsplit

import tomli
from packaging.markers import Marker

from .runner import METHODS

ENTRY_POINTS = {
    "few-shot": ["DIN-SQL.py"],
    "mac-sql": ["run.py"],
    "dail-sql": ["data_preprocess.py", "generate_question.py", "ask_llm.py"],
    "evaluator": ["evaluation.py"],
}


def command(argv, cwd=None):
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, timeout=30, check=True
    ).stdout


def required_packages(lock, marker_env):
    """Walk runtime dependencies; uv locks also contain other platforms/builds."""
    packages = {p["name"]: p for p in lock["package"]}
    roots = [p for p in packages.values() if "virtual" in p.get("source", {})]
    if len(roots) != 1:
        raise ValueError("Expected one environment project in uv.lock")
    pending = [(roots[0]["name"], ())]
    visited, required = set(), {}
    while pending:
        name, extras = pending.pop()
        if (name, extras) in visited:
            continue
        visited.add((name, extras))
        package = packages[name]
        if "registry" in package.get("source", {}):
            required[name] = package
        dependencies = list(package.get("dependencies", []))
        for extra in extras:
            dependencies.extend(package.get("optional-dependencies", {}).get(extra, []))
        for dependency in dependencies:
            if "marker" not in dependency or Marker(dependency["marker"]).evaluate(
                marker_env
            ):
                pending.append((dependency["name"], tuple(dependency.get("extra", []))))
    return required.values()


def diagnose(config, method="all"):
    checks = []

    def add(name, ok, detail, warning=False):
        checks.append(
            {
                "name": name,
                "status": "ok" if ok else "warning" if warning else "error",
                "detail": str(detail),
            }
        )

    for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        add(
            key,
            bool(config.env.get(key, "").strip()),
            "configured"
            if config.env.get(key, "").strip()
            else f"Set {key} in environment or .env",
        )
    try:
        url = urlsplit(config.env.get("LLM_BASE_URL", ""))
        valid = url.scheme in ("http", "https") and bool(url.hostname) and url.port != 0
    except ValueError:
        valid = False
    add("LLM URL", valid, "HTTP(S) URL required; no network request performed")
    try:
        manifest = json.loads((config.root / "environments/manifest.json").read_text())
    except (OSError, ValueError):
        add(
            "environment manifest",
            False,
            "Missing or invalid environments/manifest.json",
        )
        return checks
    selected = [*METHODS, "evaluator"] if method == "all" else [method]
    for name in selected:
        runtime = config.methods[name]
        repo, python = runtime["repository"], runtime["python"]
        try:
            if not (repo / ".git").exists():
                raise ValueError("checkout not initialized")
            revision = command(["git", "-C", str(repo), "rev-parse", "HEAD"]).strip()
            add(
                f"{name} revision",
                revision == manifest[name]["revision"],
                f"{revision}; expected {manifest[name]['revision']}",
            )
            dirty = command(["git", "-C", str(repo), "status", "--porcelain"]).strip()
            add(
                f"{name} checkout",
                not dirty,
                "clean"
                if not dirty
                else "Local changes present; restore the pinned checkout before benchmarking",
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            add(
                f"{name} repository",
                False,
                f"Initialize {repo}: git submodule update --init --recursive",
            )
        for entry in ENTRY_POINTS[name]:
            add(f"{name} {entry}", (repo / entry).is_file(), repo / entry)
        try:
            if not python.is_file() or not os.access(python, os.X_OK):
                raise ValueError("missing executable")
            # -I isolates PYTHONPATH/user site; -B avoids writing bytecode. Metadata
            # inspection does not import torch/NLTK or any method code.
            probe = """
import sys, os, platform, json, importlib.metadata as m
marker = {
    "implementation_name": sys.implementation.name,
    "implementation_version": platform.python_version(),
    "os_name": os.name,
    "platform_machine": platform.machine(),
    "platform_release": platform.release(),
    "platform_system": platform.system(),
    "platform_version": platform.version(),
    "python_full_version": platform.python_version(),
    "platform_python_implementation": platform.python_implementation(),
    "python_version": '.'.join(map(str, sys.version_info[:2])),
    "sys_platform": sys.platform,
    "extra": "",
}
print(json.dumps({"python": marker["python_version"], "markers": marker,
    "packages": {d.metadata['Name'].lower().replace('_','-'): d.version for d in m.distributions()}}))
"""
            installed = json.loads(command([str(python), "-I", "-B", "-c", probe]))
            add(
                f"{name} Python",
                installed["python"] == manifest[name]["python"],
                f"{python}: {installed['python']}; expected {manifest[name]['python']}",
            )
            lockpath = config.root / manifest[name]["project"] / "uv.lock"
            with lockpath.open("rb") as stream:
                lock = tomli.load(stream)
            mismatch = []
            for package in required_packages(lock, installed["markers"]):
                if "registry" in package.get("source", {}):
                    actual = installed["packages"].get(
                        package["name"].lower().replace("_", "-")
                    )
                    if actual != package["version"]:
                        mismatch.append(
                            f"{package['name']} expected {package['version']}, found {actual or 'missing'}"
                        )
            add(
                f"{name} dependencies",
                not mismatch,
                "; ".join(mismatch)
                if mismatch
                else "Runtime package versions match uv.lock for this platform (metadata check)",
            )
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            add(
                f"{name} environment",
                False,
                f"Cannot inspect Python/lockfile; run scripts/setup_environments.py --method {name}",
            )
    examples, tables = None, None
    for filename in ("dev.json", "tables.json"):
        path = config.spider / filename
        try:
            value = json.loads(path.read_text())
            if (
                not isinstance(value, list)
                or not value
                or not all(isinstance(row, dict) for row in value)
            ):
                raise ValueError("expected nonempty records")
            if filename == "dev.json":
                if not all(
                    all(key in row for key in ("db_id", "question", "query"))
                    and isinstance(row["db_id"], str)
                    for row in value
                ):
                    raise ValueError("missing Spider fields")
                examples = value
            else:
                if not all(isinstance(row.get("db_id"), str) for row in value):
                    raise ValueError("missing db_id")
                tables = value
            add(filename, True, f"{path}: {len(value)} records")
        except (OSError, ValueError):
            add(filename, False, f"Missing/invalid Spider JSON: {path}")
    if examples and tables:
        ids = {row["db_id"] for row in examples}
        schema_ids = {row["db_id"] for row in tables}
        add(
            "Spider schemas",
            ids <= schema_ids,
            "All dev DBs require entries in tables.json",
        )
        if method in ("all", "few-shot"):
            add(
                "DIN prompt schema",
                "college_2" in schema_ids,
                "Full tables.json must include college_2",
            )
        for label, root in (
            ("Spider databases", config.spider / "database"),
            ("Test-suite databases", config.suites),
        ):
            missing = [
                db for db in sorted(ids) if not (root / db / f"{db}.sqlite").is_file()
            ]
            add(
                label,
                not missing,
                f"{root}; missing DBs: {', '.join(missing)}" if missing else root,
            )
    else:
        for label, root in (
            ("Spider databases", config.spider / "database"),
            ("Test-suite databases", config.suites),
        ):
            add(
                label,
                root.is_dir() and any(root.glob("*/*.sqlite")),
                f"{root}; install separately (Phase 3)",
            )
    add(
        "Test-suite provenance",
        False,
        "File presence does not verify suite provenance or metric correctness; run check-evaluator on a prepared subset",
        warning=True,
    )
    if method in ("all", "dail-sql"):
        for filename in ("train_spider.json", "train_others.json"):
            add(
                f"DAIL {filename}",
                (config.spider / filename).is_file(),
                config.spider / filename,
            )
        add(
            "DAIL resources",
            False,
            "Java/CoreNLP 2018-10-05, GloVe, embedding weights and NLTK data require separate setup; see environments/README.md. Not verified by metadata checks.",
            warning=True,
        )
    add(
        "runtime scope",
        False,
        "No inference, preprocessing, resource downloads or evaluator execution performed",
        warning=True,
    )
    return checks
