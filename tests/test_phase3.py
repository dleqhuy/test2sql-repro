"""Mapping/provenance regression tests plus a live pinned-evaluator smoke test."""

import copy
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from test2sql.artifacts import file_record, read_json, sha256, write_json
from test2sql.config import Config, ConfigError, mapping
from test2sql.datasets.archives import SOURCES, install_archive
from test2sql.datasets.spider import load_run, prepare
from test2sql.evaluation.runner import (
    EvaluationError,
    database_files,
    evaluate,
    parse_metrics,
    predictions,
)
from test2sql.evaluation.smoke import smoke

ROOT = Path(__file__).resolve().parents[1]
TABLE = {
    "table_names_original": ["items"],
    "table_names": ["items"],
    "column_names_original": [[-1, "*"], [0, "id"], [0, "name"]],
    "column_names": [[-1, "*"], [0, "id"], [0, "name"]],
    "column_types": ["text", "number", "text"],
    "primary_keys": [1],
    "foreign_keys": [],
}


class Phase3Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        configured = mapping(ROOT / "configs/methods.yaml")
        methods = {
            name: {key: ROOT / value for key, value in runtime.items()}
            for name, runtime in configured.items()
        }
        self.config = Config(
            self.root,
            self.root / "spider",
            self.root / "suites",
            self.root / "results",
            methods,
            {},
        )
        (self.root / "environments/evaluator").mkdir(parents=True)
        shutil.copyfile(
            ROOT / "environments/manifest.json",
            self.root / "environments/manifest.json",
        )
        shutil.copyfile(
            ROOT / "environments/evaluator/uv.lock",
            self.root / "environments/evaluator/uv.lock",
        )
        self.rows = []
        for index, database in enumerate(("college_2", "toy")):
            path = self.config.spider / "database" / database / f"{database}.sqlite"
            path.parent.mkdir(parents=True)
            with sqlite3.connect(path) as connection:
                connection.execute(
                    "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"
                )
                connection.executemany(
                    "INSERT INTO items VALUES (?, ?)", [(1, "one"), (2, "two")]
                )
            self.rows.append(
                {
                    "db_id": database,
                    "question": "How many?",
                    "question_toks": ["How", "many", "?"],
                    "query": "SELECT count(*) FROM items",
                    "sql": {},
                    "question_id": 99 + index,
                }
            )
        self.rows.append(
            {
                **self.rows[0],
                "question": "Names?",
                "query": "SELECT name FROM items ORDER BY id",
            }
        )
        self.tables = [
            {"db_id": name, **copy.deepcopy(TABLE)} for name in ("college_2", "toy")
        ]
        for name, data in {
            "dev.json": self.rows,
            "tables.json": self.tables,
            "train_spider.json": self.rows[:1],
            "train_others.json": self.rows[1:2],
        }.items():
            write_json(self.config.spider / name, data)
        (self.config.spider / "train_gold.sql").write_text(
            "SELECT count(*) FROM items\tcollege_2\nSELECT count(*) FROM items\ttoy\n"
        )

    def prepared(self, run_id="test", indices=None):
        result = prepare(self.config, indices=indices or [2, 1, 0], run_id=run_id)
        return Path(result["run_directory"])

    def snapshot(self):
        return {
            p.relative_to(self.config.spider).as_posix(): sha256(p)
            for p in self.config.spider.rglob("*")
            if p.is_file()
        }

    def test_deterministic_staging_mapping_and_source_immutability(self):
        before = self.snapshot()
        run = self.prepared()
        other = self.prepared("repeat")
        self.assertEqual(self.snapshot(), before)
        subset = read_json(run / "subset.json")
        self.assertEqual(subset, read_json(other / "subset.json"))
        self.assertEqual([e["source_index"] for e in subset["examples"]], [2, 1, 0])
        din = read_json(run / "input/few-shot/dev.json")
        mac = read_json(run / "input/mac-subset.json")
        dail = read_json(run / "work/dail/dataset/spider/dev.json")
        self.assertEqual(din, dail)
        self.assertEqual(din, [self.rows[2], self.rows[1], self.rows[0]])
        self.assertEqual([r["question_id"] for r in mac], [0, 1, 2])
        for original, row in zip(din, mac):
            self.assertEqual(
                {k: v for k, v in row.items() if k != "question_id"},
                {k: v for k, v in original.items() if k != "question_id"},
            )
        self.assertEqual(
            (run / "input/few-shot/tables.json").read_bytes(),
            (self.config.spider / "tables.json").read_bytes(),
        )
        self.assertEqual(
            (run / "work/dail/dataset/spider/train_gold.sql").read_bytes(),
            (self.config.spider / "train_gold.sql").read_bytes(),
        )
        self.assertEqual(
            len(
                read_json(run / "work/dail/dataset/spider/train_spider_and_others.json")
            ),
            2,
        )
        self.assertTrue((run / "work/dail/utils").is_symlink())
        self.assertFalse((run / "work/dail/dataset").is_symlink())
        copied = run / "input/database/toy/toy.sqlite"
        copied.write_bytes(b"changed staging copy")
        self.assertEqual(self.snapshot(), before)

    def test_selection_and_overwrite_guards(self):
        for indices in ([0, 0], [-1], [3], []):
            with self.subTest(indices=indices), self.assertRaises(ConfigError):
                prepare(self.config, indices=indices, run_id="bad")
        with self.assertRaises(ConfigError):
            prepare(self.config, limit=100, run_id="bad")
        with self.assertRaises(ConfigError):
            prepare(self.config, indices=[0], limit=1, run_id="bad")
        self.assertFalse((self.config.output / "runs/bad").exists())
        self.prepared()
        with self.assertRaises(ConfigError):
            self.prepared()

    def test_missing_method_field_does_not_stage_partial_run(self):
        del self.rows[0]["sql"]
        write_json(self.config.spider / "dev.json", self.rows)
        with self.assertRaises(ConfigError):
            self.prepared()
        self.assertFalse((self.config.output / "runs/test").exists())
        # DIN does not need the MAC-specific parsed SQL field.
        prepare(self.config, method="few-shot", limit=1, run_id="din")

    def test_bad_database_or_gold_is_rejected(self):
        path = self.config.spider / "database/toy/toy.sqlite"
        path.write_bytes(b"not sqlite")
        with self.assertRaises(ConfigError):
            self.prepared()
        self.rows[0]["query"] = "SELECT\ncount(*) FROM items"
        write_json(self.config.spider / "dev.json", self.rows)
        with self.assertRaises(ConfigError):
            prepare(self.config, method="few-shot", indices=[0], run_id="bad-gold")

    def test_subset_and_gold_tampering_is_detected(self):
        run = self.prepared()
        (run / "subset.json").write_text("{}")
        with self.assertRaises(ConfigError):
            load_run(self.config, "test")
        other = self.prepared("other")
        (other / "evaluation/gold.sql").write_text("SELECT 1\ttoy\n")
        with self.assertRaises(ConfigError):
            load_run(self.config, "other")

    def test_prediction_count_blank_and_tabs_are_rejected_before_subprocess(self):
        run = self.prepared()
        path = self.root / "pred.sql"
        for text in (
            "SELECT 1\n",
            "SELECT 1\n" * 4,
            "SELECT 1\n\nSELECT 1\n",
            "SELECT 1\ttoy\n" * 3,
        ):
            path.write_text(text)
            with patch(
                "test2sql.evaluation.runner.subprocess.Popen",
                side_effect=AssertionError("must validate first"),
            ):
                with self.assertRaises(ConfigError):
                    evaluate(self.config, "test", path)
        self.assertFalse((run / "evaluation/manual").exists())

    def test_jsonl_ids_reorder_and_bad_mapping(self):
        run = self.prepared()
        subset = read_json(run / "subset.json")
        rows = [
            {**e, "run_id": "test", "status": "success", "predicted_sql": f"SELECT {i}"}
            for i, e in enumerate(subset["examples"])
        ]
        path = self.root / "pred.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in reversed(rows)) + "\n")
        sql, mapping = predictions(path, subset, "test")
        self.assertEqual(sql, ["SELECT 0", "SELECT 1", "SELECT 2"])
        self.assertEqual(mapping, "example-id")
        for field, value in [
            ("example_id", rows[1]["example_id"]),
            ("example_id", "unknown"),
            ("db_id", "wrong"),
            ("source_index", 99),
            ("status", "error"),
            ("run_id", "wrong"),
        ]:
            broken = copy.deepcopy(rows)
            broken[0][field] = value
            path.write_text("\n".join(json.dumps(r) for r in broken) + "\n")
            with self.subTest(field=field, value=value), self.assertRaises(ConfigError):
                predictions(path, subset, "test")

    def test_missing_suite_provenance_never_falls_back_to_spider(self):
        run = self.prepared()
        with self.assertRaises(ConfigError):
            database_files(
                self.config,
                read_json(run / "manifest.json"),
                read_json(run / "subset.json"),
                "test-suite",
            )

    def make_suites(self):
        entries = {}
        for value in ("college_2", "toy"):
            directory = self.config.suites / value
            directory.mkdir(parents=True)
            for name in (f"{value}.sqlite", "variant.sqlite"):
                shutil.copyfile(
                    self.config.spider / "database" / value / f"{value}.sqlite",
                    directory / name,
                )
                entries[f"{value}/{name}"] = file_record(directory / name)
        write_json(
            self.config.suites / "provenance.json",
            {
                "kind": "test-suite",
                "source": SOURCES["test-suite"]["url"],
                "archive": {"sha256": SOURCES["test-suite"]["sha256"]},
                "files": entries,
            },
        )

    def test_suite_checksum_and_spurious_sqlite_files(self):
        self.make_suites()
        run = self.prepared()
        args = (
            self.config,
            read_json(run / "manifest.json"),
            read_json(run / "subset.json"),
            "test-suite",
        )
        database_files(*args)
        bad = self.config.suites / "toy/toy.sqlite-journal"
        bad.touch()
        with self.assertRaises(ConfigError):
            database_files(*args)
        bad.unlink()
        (self.config.suites / "toy/variant.sqlite").write_bytes(b"bad")
        with self.assertRaises(ConfigError):
            database_files(*args)

    def test_missing_variant_is_rejected_even_when_other_variants_remain(self):
        self.make_suites()
        extra = self.config.suites / "toy/extra.sqlite"
        shutil.copyfile(self.config.suites / "toy/toy.sqlite", extra)
        metadata = read_json(self.config.suites / "provenance.json")
        metadata["files"]["toy/extra.sqlite"] = file_record(extra)
        write_json(self.config.suites / "provenance.json", metadata)
        run = self.prepared()
        extra.unlink()
        with self.assertRaises(ConfigError):
            database_files(
                self.config,
                read_json(run / "manifest.json"),
                read_json(run / "subset.json"),
                "test-suite",
            )

    def test_preparation_rejects_changed_official_source(self):
        from test2sql.datasets.archives import SOURCES

        entries = {
            name: file_record(self.config.spider / name)
            for name in (
                "dev.json",
                "tables.json",
                "train_spider.json",
                "train_others.json",
                "train_gold.sql",
            )
        }
        for value in ("college_2", "toy"):
            entries[f"database/{value}/{value}.sqlite"] = file_record(
                self.config.spider / "database" / value / f"{value}.sqlite"
            )
        write_json(
            self.config.spider / "provenance.json",
            {
                "kind": "spider",
                "source": SOURCES["spider"]["url"],
                "archive": {"sha256": SOURCES["spider"]["sha256"]},
                "files": entries,
            },
        )
        self.rows[0]["question"] = "Changed question"
        write_json(self.config.spider / "dev.json", self.rows)
        with self.assertRaises(ConfigError):
            self.prepared()

    def test_parse_metrics_and_denominator(self):
        text = "debug: failed SQL\n  easy medium hard extra all\ncount 1 1 0 1 3\nexecution 1.000 0.000 0.000 1.000 0.667\nexact match 1.000 0.000 0.000 1.000 0.667\n"
        self.assertEqual(parse_metrics(text, 3)["execution"], 0.667)
        for bad in (
            text.replace("1 1 0 1 3", "1 1 0 1 2"),
            text + text,
            text.replace("exact match", "missing"),
            text.replace("0.667", "1.500"),
        ):
            with self.assertRaises(EvaluationError):
                parse_metrics(bad, 3)

    def test_timeout_and_nonzero_exit_keep_logs_without_metrics(self):
        run = self.prepared()
        path = self.root / "pred.sql"
        path.write_bytes(
            (run / "evaluation/gold.sql")
            .read_bytes()
            .replace(b"\tcollege_2", b"")
            .replace(b"\ttoy", b"")
        )
        fake = self.root / "fake-evaluator"
        fake.mkdir()
        self.config.methods["evaluator"] = {
            "repository": fake,
            "python": Path(sys.executable),
        }
        script = fake / "evaluation.py"
        for label, source, timeout, expected_timeout in [
            ("timeout", "import time\ntime.sleep(10)", 0.1, True),
            (
                "nonzero",
                'import sys\nprint("failed", file=sys.stderr)\nsys.exit(7)',
                10,
                False,
            ),
            ("incomplete", 'print("partial output only")', 10, False),
        ]:
            script.write_text(source)
            with patch("test2sql.evaluation.runner.revision", return_value="fixture"):
                report = evaluate(self.config, "test", path, label, "spider", timeout)
            self.assertEqual(report["status"], "failed")
            self.assertIsNone(report["metrics"])
            self.assertEqual(report["timed_out"], expected_timeout)
            self.assertTrue((run / f"evaluation/{label}/stdout.log").is_file())
            self.assertTrue((run / f"evaluation/{label}/stderr.log").is_file())

    def test_pinned_evaluator_live_smoke_on_synthetic_data(self):
        if not self.config.methods["evaluator"]["python"].is_file():
            self.skipTest("Run scripts/setup_environments.py --method evaluator first")
        resource = ROOT / ".venvs/evaluator/nltk_data/tokenizers/punkt_tab/english"
        if not resource.is_dir():
            self.skipTest("Install evaluator NLTK resources for the live smoke test")
        self.config.env["NLTK_DATA"] = str(ROOT / ".venvs/evaluator/nltk_data")
        self.prepared()
        before = self.snapshot()
        result = smoke(self.config, "test", "spider", 30)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(self.snapshot(), before)
        report = read_json(
            self.config.output / "runs/test/evaluation/smoke-gold/result.json"
        )
        self.assertEqual(
            report["execution_metric"], "execution_accuracy_on_original_spider"
        )
        self.assertTrue(report["source_databases_unchanged"])
        self.assertNotIn("--plug_value", report["argv"])
        self.assertIn("--keep_distinct", report["argv"])

    def zip_archive(self, files, name="fixture.zip"):
        path = self.root / name
        with zipfile.ZipFile(path, "w") as archive:
            for filename, content in files.items():
                archive.writestr(filename, content)
        return path

    def test_archive_hash_and_unsafe_paths_are_rejected(self):
        archive = self.zip_archive({"../outside.sqlite": b"bad"})
        with self.assertRaises(ConfigError):
            install_archive(archive, self.root / "installed", "test-suite", ["toy"])
        source = {**SOURCES["test-suite"], "sha256": sha256(archive)}
        with (
            patch.dict(SOURCES, {"test-suite": source}),
            self.assertRaises(ConfigError),
        ):
            install_archive(archive, self.root / "installed", "test-suite", ["toy"])
        self.assertFalse((self.root / "installed").exists())
        self.assertFalse((self.root.parent / "outside.sqlite").exists())

    def test_archive_filters_ids_records_hashes_and_cannot_overwrite(self):
        data = (self.config.spider / "database/toy/toy.sqlite").read_bytes()
        archive = self.zip_archive(
            {
                "database/toy/toy.sqlite": data,
                "database/toy/variant.sqlite": data,
                "database/unused/unused.sqlite": data,
            }
        )
        source = {**SOURCES["test-suite"], "sha256": sha256(archive)}
        target = self.root / "installed"
        with patch.dict(SOURCES, {"test-suite": source}):
            result = install_archive(archive, target, "test-suite", ["toy"])
            with self.assertRaises(ConfigError):
                install_archive(archive, target, "test-suite", ["toy"])
        self.assertEqual(set(result["files"]), {"toy/toy.sqlite", "toy/variant.sqlite"})
        self.assertEqual(
            result["files"]["toy/toy.sqlite"]["sha256"],
            sha256(target / "toy/toy.sqlite"),
        )
        self.assertFalse((target / "unused").exists())


if __name__ == "__main__":
    unittest.main()
