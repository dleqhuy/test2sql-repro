"""Deterministic Spider subsets and isolated method inputs."""

import copy
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..artifacts import db_id, file_record, read_json, sha256, write_json
from ..config import ConfigError
from ..runner import METHODS, plan
from .archives import checked_provenance

DAIL_SOURCE = (
    "data_preprocess.py",
    "generate_question.py",
    "ask_llm.py",
    "prompt",
    "utils",
    "llm",
)


def sql_line(sql):
    # Refuse ambiguous line-oriented artifacts rather than rewriting literals/comments.
    if not isinstance(sql, str) or not sql.strip() or any(c in sql for c in "\r\n\t"):
        raise ConfigError("SQL must be one nonempty line with no tabs")
    return sql.strip()


def records(path, fields):
    rows = read_json(path)
    if not isinstance(rows, list) or not rows:
        raise ConfigError(f"Expected nonempty Spider records: {path}")
    for row in rows:
        if not isinstance(row, dict) or not fields <= row.keys():
            raise ConfigError(
                f"Missing required Spider fields in {path}: {sorted(fields)}"
            )
        db_id(row["db_id"])
    return rows


def sqlite_file(path):
    if not path.is_file():
        raise ConfigError(f"Missing database: {path}")
    with path.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise ConfigError(f"Invalid SQLite header: {path}")


def revision(repo, expected=None):
    try:
        if not (repo / ".git").exists():
            raise ValueError("not a checkout")
        commit = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ConfigError(f"Cannot inspect pinned checkout: {repo}") from exc
    if dirty or (expected and commit != expected):
        raise ConfigError(f"Checkout is modified or at the wrong revision: {repo}")
    return commit


def provenance(root):
    path = root / "provenance.json"
    if not path.is_file():
        return {"kind": "local-unverified", "root": str(root)}
    return {
        "root": str(root),
        "manifest": str(path),
        **file_record(path),
        "kind": read_json(path).get("kind", "local-unverified"),
    }


def prepare(config, method="all", split="dev", limit=None, indices=None, run_id=None):
    preview = plan(config, method, split, limit, run_id)
    final = Path(preview["run_directory"])
    selected_methods = list(METHODS) if method == "all" else [method]
    required = {"db_id", "question", "query"}
    if "mac-sql" in selected_methods:
        required.add("sql")
    if "dail-sql" in selected_methods:
        required.add("question_toks")
    if (
        config.suites.resolve() == (config.spider / "database").resolve()
        or config.suites.resolve() == config.spider.resolve()
    ):
        raise ConfigError(
            "Spider and test-suite databases must use separate directories"
        )
    source = config.spider / "dev.json"
    rows = records(source, required)
    selection = "explicit-indices" if indices is not None else "source-order"
    if indices is not None:
        if limit is not None or not indices or len(set(indices)) != len(indices):
            raise ConfigError("Use either --indices (unique, nonempty) or --limit")
        if any(type(i) is not int or i < 0 or i >= len(rows) for i in indices):
            raise ConfigError("Subset index is outside the Spider dev split")
    else:
        if limit is not None and limit > len(rows):
            raise ConfigError("--limit exceeds the split size")
        indices = list(range(len(rows) if limit is None else limit))
    subset_rows = [copy.deepcopy(rows[i]) for i in indices]
    tables = records(
        config.spider / "tables.json",
        {"db_id", "table_names_original", "column_names_original", "foreign_keys"},
    )
    schemas = {row["db_id"]: row for row in tables}
    if len(schemas) != len(tables):
        raise ConfigError("Duplicate db_id in tables.json")
    wanted = {row["db_id"] for row in subset_rows}
    if not wanted <= schemas.keys():
        raise ConfigError("Subset has db_id missing from tables.json")
    if "few-shot" in selected_methods and "college_2" not in schemas:
        raise ConfigError("DIN requires full tables.json including college_2")
    gold_lines = [f"{sql_line(row['query'])}\t{row['db_id']}" for row in subset_rows]
    files = {name: config.spider / name for name in ("dev.json", "tables.json")}
    if "dail-sql" in selected_methods:
        for name in ("train_spider.json", "train_others.json"):
            records(
                config.spider / name, {"db_id", "question", "query", "question_toks"}
            )
            files[name] = config.spider / name
        if not (config.spider / "train_gold.sql").is_file():
            raise ConfigError(
                "DAIL requires the official train_gold.sql from the Spider archive"
            )
        files["train_gold.sql"] = config.spider / "train_gold.sql"
        wanted = set(schemas)
    databases = {
        value: config.spider / "database" / value / f"{value}.sqlite"
        for value in wanted
    }
    for database in databases.values():
        sqlite_file(database)
    sources = {name: file_record(path) for name, path in files.items()}
    database_records = {value: file_record(path) for value, path in databases.items()}
    if (config.spider / "provenance.json").is_file():
        installed = checked_provenance(config.spider, "spider")
        checked = {
            **sources,
            **{
                f"database/{value}/{value}.sqlite": record
                for value, record in database_records.items()
            },
        }
        for relative, actual in checked.items():
            expected = installed["files"].get(relative)
            if not expected or any(
                actual[key] != expected.get(key) for key in ("sha256", "bytes")
            ):
                raise ConfigError(
                    f"Spider source checksum/provenance mismatch: {relative}"
                )
    pins = read_json(config.root / "environments/manifest.json")
    commits = {
        name: revision(config.methods[name]["repository"], pins[name]["revision"])
        for name in selected_methods
    }
    if "dail-sql" in selected_methods:
        for name in DAIL_SOURCE:
            if not (config.methods["dail-sql"]["repository"] / name).exists():
                raise ConfigError(f"Missing DAIL source: {name}")
    subset = {
        "version": 1,
        "split": split,
        "source": {"path": str(source), **sources["dev.json"]},
        "selection": selection,
        "examples": [
            {
                "example_id": f"spider-{split}-{index:04d}",
                "source_index": index,
                "db_id": rows[index]["db_id"],
            }
            for index in indices
        ],
    }
    final.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=final.parent) as temporary:
        run = Path(temporary) / "payload"
        run.mkdir()
        for name in ("input", "raw", "predictions", "logs", "evaluation", "work"):
            (run / name).mkdir()
        write_json(run / "subset.json", subset)
        shutil.copyfile(config.spider / "tables.json", run / "input/tables.json")
        (run / "evaluation/gold.sql").write_text(
            "\n".join(gold_lines) + "\n", encoding="utf-8"
        )
        if "few-shot" in selected_methods:
            write_json(run / "input/few-shot/dev.json", subset_rows)
            shutil.copyfile(
                config.spider / "tables.json", run / "input/few-shot/tables.json"
            )
        if "mac-sql" in selected_methods:
            mac = copy.deepcopy(subset_rows)
            for index, row in enumerate(mac):
                row["question_id"] = index
            write_json(run / "input/mac-subset.json", mac)
            for value in {row["db_id"] for row in subset_rows}:
                dest = run / "input/database" / value / f"{value}.sqlite"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(databases[value], dest)
            (run / "raw/mac").mkdir()
            (run / "logs/mac").mkdir()
        if "dail-sql" in selected_methods:
            work = run / "work/dail"
            work.mkdir(parents=True)
            for name in DAIL_SOURCE:
                (work / name).symlink_to(
                    config.methods["dail-sql"]["repository"] / name,
                    target_is_directory=(
                        config.methods["dail-sql"]["repository"] / name
                    ).is_dir(),
                )
            for name in ("dataset/process", "third_party"):
                (work / name).mkdir(parents=True)
            data = work / "dataset/spider"
            write_json(data / "dev.json", subset_rows)
            for name in ("tables.json", "train_spider.json", "train_others.json"):
                shutil.copyfile(files[name], data / name)
            (data / "dev_gold.sql").write_text(
                "\n".join(gold_lines) + "\n", encoding="utf-8"
            )
            train = read_json(files["train_spider.json"]) + read_json(
                files["train_others.json"]
            )
            write_json(data / "train_spider_and_others.json", train)
            shutil.copyfile(files["train_gold.sql"], data / "train_gold.sql")
            for value, source_db in databases.items():
                dest = data / "database" / value / f"{value}.sqlite"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_db, dest)
        # Exclude linked source trees; hash only copied, run-owned artifacts.
        staged = {}
        for path in run.rglob("*"):
            if path.is_file() and not path.is_symlink():
                staged[path.relative_to(run).as_posix()] = file_record(path)
        if sources != {
            name: file_record(path) for name, path in files.items()
        } or database_records != {
            value: file_record(path) for value, path in databases.items()
        }:
            raise ConfigError("Source dataset changed during staging")
        manifest = {
            "version": 1,
            "run_id": preview["run_id"],
            "status": "prepared",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "split": split,
            "requested_count": len(indices),
            "methods": selected_methods,
            "submodule_commits": commits,
            "dataset": {
                "root": str(config.spider),
                "provenance": provenance(config.spider),
                "files": sources,
                "databases": database_records,
            },
            "subset_sha256": sha256(run / "subset.json"),
            "artifacts": staged,
            "evaluation_policy": {
                "etype": "all",
                "plug_value": False,
                "keep_distinct": True,
                "exact_match_note": "Upstream exact set match ignores values and DISTINCT; execution retains both.",
            },
        }
        write_json(run / "manifest.json", manifest)
        run.rename(final)
    return {
        "run_id": preview["run_id"],
        "run_directory": str(final),
        "count": len(indices),
        "example_ids": [e["example_id"] for e in subset["examples"]],
        "methods": selected_methods,
        "status": "prepared",
    }


def load_run(config, run_id):
    from ..artifacts import safe_name

    run = config.output / "runs" / safe_name(run_id, "--run-id")
    if any(
        run.resolve().is_relative_to(path.resolve())
        for path in (
            config.spider,
            config.suites,
            *(m["repository"] for m in config.methods.values()),
        )
    ):
        raise ConfigError("Run directory overlaps source data or a pinned checkout")
    manifest, subset = read_json(run / "manifest.json"), read_json(run / "subset.json")
    if (
        not isinstance(manifest, dict)
        or not isinstance(subset, dict)
        or not isinstance(manifest.get("artifacts"), dict)
        or subset.get("split") != "dev"
    ):
        raise ConfigError("Malformed run manifest/subset")
    if manifest.get("run_id") != run_id or manifest.get("subset_sha256") != sha256(
        run / "subset.json"
    ):
        raise ConfigError("Run identity/subset checksum mismatch")
    examples = subset.get("examples", [])
    if (
        not isinstance(examples, list)
        or not examples
        or len(examples) != manifest.get("requested_count")
    ):
        raise ConfigError("Subset count mismatch")
    if not all(
        isinstance(e, dict)
        and {"example_id", "source_index", "db_id"} <= e.keys()
        and isinstance(e["example_id"], str)
        and type(e["source_index"]) is int
        and e["source_index"] >= 0
        for e in examples
    ):
        raise ConfigError("Subset count mismatch")
    ids = [e["example_id"] for e in examples]
    indices = [e["source_index"] for e in examples]
    if len(set(ids)) != len(ids) or len(set(indices)) != len(indices):
        raise ConfigError("Duplicate subset example IDs or source indices")
    for example in examples:
        db_id(example["db_id"])
        if (
            example["example_id"]
            != f"spider-{subset['split']}-{example['source_index']:04d}"
        ):
            raise ConfigError("Subset example ID/source index mismatch")
    for name in ("evaluation/gold.sql", "input/tables.json"):
        if file_record(run / name) != manifest["artifacts"].get(name):
            raise ConfigError(f"Prepared artifact checksum mismatch: {name}")
    lines = (run / "evaluation/gold.sql").read_text(encoding="utf-8").splitlines()
    if len(lines) != len(examples):
        raise ConfigError("Gold count mismatch")
    for line, example in zip(lines, examples):
        parts = line.split("\t")
        if len(parts) != 2 or parts[1] != example["db_id"]:
            raise ConfigError("Gold/subset database mapping mismatch")
        sql_line(parts[0])
    return run, manifest, subset
