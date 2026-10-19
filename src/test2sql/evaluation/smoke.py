"""Exercise the pinned evaluator with gold, semantically wrong, and invalid SQL."""

import sqlite3
import time

from ..artifacts import read_json, write_json
from ..config import ConfigError
from ..datasets.spider import load_run
from .runner import evaluate


def wrong_predictions(run, subset):
    """Construct valid SQLite queries whose result differs on the original DB."""
    schemas = {row["db_id"]: row for row in read_json(run / "input/tables.json")}
    gold = (run / "evaluation/gold.sql").read_text(encoding="utf-8").splitlines()
    output = []
    for index, example in enumerate(subset["examples"]):
        schema = schemas[example["db_id"]]
        table = schema["table_names_original"][0].replace('"', '""')
        # Arithmetic in SELECT is intentionally simple and independent of contents.
        query = f'SELECT COUNT(*) + 1000000000 FROM "{table}"'
        original = (
            run / "input/database" / example["db_id"] / f"{example['db_id']}.sqlite"
        )
        if not original.is_file():
            original = (
                run
                / "work/dail/dataset/spider/database"
                / example["db_id"]
                / f"{example['db_id']}.sqlite"
            )
        if not original.is_file():
            raise ConfigError(
                "Smoke test requires prepared MAC or DAIL database copies; use prepare --method all"
            )
        with sqlite3.connect(
            original.resolve().as_uri() + "?mode=ro", uri=True
        ) as connection:
            deadline = time.monotonic() + 5
            connection.set_progress_handler(
                lambda: int(time.monotonic() > deadline), 10000
            )
            answer = connection.execute(gold[index].split("\t")[0]).fetchall()
            if answer == connection.execute(query).fetchall():
                query = f'SELECT COUNT(*) + 1000000001 FROM "{table}"'
            if answer == connection.execute(query).fetchall():
                raise ConfigError("Cannot construct controlled incorrect prediction")
        output.append(query)
    return output


def smoke(config, run_id, database_mode="test-suite", timeout=120):
    run, manifest, subset = load_run(config, run_id)
    root = run / "evaluation/smoke-inputs"
    if root.exists():
        raise ConfigError("Smoke inputs already exist; prepare a new run to repeat")
    wrong = wrong_predictions(run, subset)
    root.mkdir()
    gold = [
        line.split("\t")[0]
        for line in (run / "evaluation/gold.sql")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    cases = {
        "gold": gold,
        "wrong": wrong,
        "invalid": ["SELECT FROM __invalid_sql__"] * len(gold),
    }
    reports = {}
    for name, lines in cases.items():
        path = root / f"{name}.sql"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        reports[name] = evaluate(
            config,
            run_id,
            path,
            label=f"smoke-{name}",
            database_mode=database_mode,
            timeout=timeout,
        )
    passed = all(report["status"] == "completed" for report in reports.values())
    if passed:
        passed = (
            reports["gold"]["metrics"]["execution"] == 1
            and reports["gold"]["metrics"]["exact_set_match"] == 1
            and reports["wrong"]["metrics"]["execution"] == 0
            and reports["invalid"]["metrics"]["execution"] == 0
            and reports["invalid"]["metrics"]["exact_set_match"] == 0
        )
    result = {
        "run_id": run_id,
        "status": "passed" if passed else "failed",
        "database_mode": database_mode,
        "count": manifest["requested_count"],
        "cases": {
            name: {
                "status": report["status"],
                "metrics": report["metrics"],
                "result": f"smoke-{name}/result.json",
            }
            for name, report in reports.items()
        },
        "note": "Harness smoke checks only; these are controlled inputs, not model benchmark results.",
    }
    write_json(run / "evaluation/smoke.json", result)
    return result
