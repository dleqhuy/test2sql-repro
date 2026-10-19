"""Validate mappings and preserve raw evaluator logs before extracting metrics."""

import math
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from ..artifacts import file_record, read_json, safe_name, sha256, write_json
from ..config import ConfigError
from ..datasets.archives import checked_provenance
from ..datasets.spider import load_run, revision, sql_line, sqlite_file


class EvaluationError(ConfigError):
    pass


def predictions(path, subset, run_id):
    path = Path(path)
    examples = subset["examples"]
    if path.suffix == ".jsonl":
        import json

        try:
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
        except (OSError, ValueError) as exc:
            raise ConfigError(
                "Invalid prediction JSONL (blank lines are not allowed)"
            ) from exc
        if len(rows) != len(examples):
            raise ConfigError(
                f"Expected {len(examples)} predictions; found {len(rows)}"
            )
        expected = {e["example_id"]: e for e in examples}
        mapped = {}
        for row in rows:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("example_id"), str)
                or row["example_id"] not in expected
            ):
                raise ConfigError("Unknown/missing prediction example_id")
            identity = row["example_id"]
            if identity in mapped:
                raise ConfigError("Duplicate prediction example_id")
            example = expected[identity]
            if (
                type(row.get("source_index")) is not int
                or row.get("db_id") != example["db_id"]
                or row.get("source_index") != example["source_index"]
            ):
                raise ConfigError("Prediction database/source_index mapping mismatch")
            if row.get("run_id") != run_id or row.get("status") != "success":
                raise ConfigError(
                    "Prediction run_id/status mismatch; failed samples cannot be omitted"
                )
            mapped[identity] = sql_line(row.get("predicted_sql"))
        return [mapped[e["example_id"]] for e in examples], "example-id"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(f"Cannot read predictions: {path}") from exc
    if len(lines) != len(examples):
        raise ConfigError(f"Expected {len(examples)} predictions; found {len(lines)}")
    return [
        sql_line(line) for line in lines
    ], "positional (caller must supply manifest order)"


def parse_metrics(stdout, expected_count):
    """Parse only the pinned five-column Spider aggregate table, not debug text."""
    lines = stdout.splitlines()
    headers = [
        i
        for i, line in enumerate(lines)
        if line.split() == ["easy", "medium", "hard", "extra", "all"]
    ]
    if len(headers) != 1:
        raise EvaluationError("Missing/ambiguous evaluator aggregate table")
    values = {}
    for line in lines[headers[0] + 1 :]:
        match = re.fullmatch(
            r"\s*(count|execution|exact match)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*",
            line,
        )
        if match:
            name = match[1]
            if name in values:
                raise EvaluationError(f"Duplicate evaluator metric: {name}")
            values[name] = match.groups()[1:]
    if set(values) != {"count", "execution", "exact match"}:
        raise EvaluationError(
            "Evaluator did not report count, execution and exact match"
        )
    try:
        counts = [int(v) for v in values["count"]]
        if counts[-1] != expected_count or sum(counts[:-1]) != expected_count:
            raise ValueError("wrong denominator")
        execution, exact = (
            float(values["execution"][-1]),
            float(values["exact match"][-1]),
        )
        if not all(
            0 <= float(v) <= 1
            for name in ("execution", "exact match")
            for v in values[name]
        ):
            raise ValueError("score outside range")
    except ValueError as exc:
        raise EvaluationError("Invalid evaluator count/score") from exc
    return {
        "count": expected_count,
        "execution": execution,
        "exact_set_match": exact,
        "precision": "Upstream stdout rounded to three decimal places",
        "hardness_counts": dict(zip(("easy", "medium", "hard", "extra"), counts[:-1])),
    }


def database_files(config, manifest, subset, mode):
    if mode not in ("test-suite", "spider"):
        raise ConfigError("Database mode must be test-suite or spider")
    source = config.suites if mode == "test-suite" else config.spider / "database"
    if (
        config.suites.resolve() == (config.spider / "database").resolve()
        or config.suites.resolve() == config.spider.resolve()
    ):
        raise ConfigError(
            "Spider and test-suite databases must use separate directories"
        )
    provenance = (
        checked_provenance(config.suites, "test-suite")
        if mode == "test-suite"
        else None
    )
    inventory = {}
    for value in sorted({e["db_id"] for e in subset["examples"]}):
        directory = source / value
        if mode == "test-suite":
            if not directory.is_dir():
                raise ConfigError(f"Missing test-suite directory: {directory}")
            candidates = sorted(p for p in directory.iterdir() if ".sqlite" in p.name)
            if len(candidates) < 2 or not (directory / f"{value}.sqlite").is_file():
                raise ConfigError(
                    f"Missing original/variant test-suite databases: {value}"
                )
            expected_names = {
                Path(name).name
                for name in provenance["files"]
                if Path(name).parent.as_posix() == value
            }
            if {p.name for p in candidates} != expected_names:
                raise ConfigError(
                    f"Incomplete or unexpected test-suite database set: {value}"
                )
        else:
            candidates = [directory / f"{value}.sqlite"]
        for path in candidates:
            if path.suffix != ".sqlite" or path.is_symlink():
                raise ConfigError(
                    f"Unexpected SQLite-like file in database directory: {path}"
                )
            sqlite_file(path)
            record = file_record(path)
            relative = f"{value}/{path.name}"
            expected = (
                provenance["files"].get(relative)
                if provenance
                else manifest["dataset"]["databases"].get(value)
            )
            if (
                not expected
                or record["sha256"] != expected["sha256"]
                or record["bytes"] != expected["bytes"]
            ):
                raise ConfigError(f"Database checksum/provenance mismatch: {relative}")
            inventory[relative] = record
    return source, inventory, provenance


def evaluate(
    config,
    run_id,
    prediction_path,
    label="manual",
    database_mode="test-suite",
    timeout=120,
):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigError("--timeout must be a finite positive number")
    safe_name(label, "--label")
    run, manifest, subset = load_run(config, run_id)
    sql, mapping = predictions(prediction_path, subset, run_id)
    original_prediction = file_record(prediction_path)
    source, inventory, provenance = database_files(
        config, manifest, subset, database_mode
    )
    runtime = config.methods["evaluator"]
    pins = read_json(config.root / "environments/manifest.json")
    commit = revision(runtime["repository"], pins["evaluator"]["revision"])
    if not runtime["python"].is_file():
        raise ConfigError(
            "Evaluator Python is missing; run scripts/setup_environments.py --method evaluator"
        )
    output = run / "evaluation" / label
    if not output.resolve().is_relative_to(run.resolve()):
        raise ConfigError("Evaluation output escapes its prepared run")
    if output.exists():
        raise ConfigError(f"Evaluation label already exists: {label}")
    output.mkdir(parents=True)
    for relative in inventory:
        dest = output / "database" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, dest)
        if file_record(dest) != inventory[relative]:
            raise ConfigError(f"Database changed while copying: {relative}")
    raw_path = output / (
        "raw-predictions.jsonl"
        if Path(prediction_path).suffix == ".jsonl"
        else "raw-predictions.sql"
    )
    shutil.copyfile(prediction_path, raw_path)
    if file_record(raw_path) != original_prediction:
        raise ConfigError("Prediction file changed during evaluation setup")
    shutil.copyfile(run / "evaluation/gold.sql", output / "gold.sql")
    shutil.copyfile(run / "input/tables.json", output / "tables.json")
    (output / "pred.sql").write_text("\n".join(sql) + "\n", encoding="utf-8")
    argv = [
        str(runtime["python"]),
        "-B",
        str(runtime["repository"] / "evaluation.py"),
        "--gold",
        str(output / "gold.sql"),
        "--pred",
        str(output / "pred.sql"),
        "--db",
        str(output / "database"),
        "--table",
        str(output / "tables.json"),
        "--etype",
        "all",
        "--keep_distinct",
    ]
    environment = {
        k: v for k, v in os.environ.items() if not k.startswith(("LLM_", "OPENAI_"))
    }
    for key in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    nltk_paths = config.env.get("NLTK_DATA", ".venvs/evaluator/nltk_data").split(
        os.pathsep
    )
    environment["NLTK_DATA"] = os.pathsep.join(
        str(config.path(path)) for path in nltk_paths if path
    )

    report = {
        "version": 1,
        "run_id": run_id,
        "label": label,
        "status": "running",
        "argv": argv,
        "cwd": str(output),
        "evaluator_revision": commit,
        "evaluator_lock_sha256": sha256(
            config.root / pins["evaluator"]["project"] / "uv.lock"
        ),
        "flags": {"etype": "all", "plug_value": False, "keep_distinct": True},
        "database_mode": database_mode,
        "execution_metric": "test_suite_accuracy"
        if database_mode == "test-suite"
        else "execution_accuracy_on_original_spider",
        "database_source": str(source),
        "dataset_provenance": manifest["dataset"]["provenance"],
        "nltk_data_paths": environment["NLTK_DATA"].split(os.pathsep),
        "database_archive": provenance["archive"] if provenance else None,
        "database_files": inventory,
        "prediction_source": {
            "path": str(prediction_path),
            **original_prediction,
            "mapping": mapping,
        },
        "input_files": {
            name: file_record(output / name)
            for name in ("gold.sql", "pred.sql", "tables.json", raw_path.name)
        },
        "subset_sha256": manifest["subset_sha256"],
        "timeout_seconds": timeout,
        "logs": {"stdout": "stdout.log", "stderr": "stderr.log"},
        "metrics": None,
        "exit_code": None,
        "timed_out": False,
    }
    write_json(output / "result.json", report)
    started = time.monotonic()
    try:
        with (
            (output / "stdout.log").open("w", encoding="utf-8") as stdout,
            (output / "stderr.log").open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                argv,
                cwd=output,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            try:
                report["exit_code"] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                report["exit_code"] = process.returncode
                report["timed_out"] = True
        if report["timed_out"]:
            raise EvaluationError("Evaluator timed out; metrics are incomplete")
        if report["exit_code"] != 0:
            raise EvaluationError("Evaluator failed; see stderr.log and stdout.log")
        report["metrics"] = parse_metrics(
            (output / "stdout.log").read_text(encoding="utf-8"), len(sql)
        )
        report["status"] = "completed"
    except (OSError, EvaluationError) as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        report["metrics"] = None
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        try:
            unchanged = all(
                file_record(source / relative) == record
                for relative, record in inventory.items()
            )
        except OSError:
            unchanged = False
        report["source_databases_unchanged"] = unchanged
        if not unchanged:
            report.update(
                status="failed",
                metrics=None,
                error="Source databases changed during evaluation",
            )
        write_json(output / "result.json", report)
    return report
