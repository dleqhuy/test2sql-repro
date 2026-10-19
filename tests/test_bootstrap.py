"""Bootstrap regression tests run with the standard-library test runner."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from test2sql.cli import main
from test2sql.config import ConfigError, load_config
from test2sql.doctor import diagnose
from test2sql.runner import plan

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "configs").mkdir()
        (self.root / "environments").mkdir()
        self.config_path = self.root / "configs/default.yaml"
        self.config_path.write_text("root: ..\n")
        self.manifest = json.loads((ROOT / "environments/manifest.json").read_text())
        methods = {}
        for name, entry in self.manifest.items():
            repo = self.root / "external" / name
            repo.mkdir(parents=True)
            (repo / ".git").write_text("synthetic test checkout")
            for filename in (
                "DIN-SQL.py",
                "run.py",
                "data_preprocess.py",
                "generate_question.py",
                "ask_llm.py",
                "evaluation.py",
            ):
                (repo / filename).write_text('raise AssertionError("Do not execute")')
            methods[name] = {"repository": str(repo), "python": sys.executable}
            entry["python"] = f"{sys.version_info.major}.{sys.version_info.minor}"
            project = self.root / entry["project"]
            project.mkdir(parents=True)
            (project / "uv.lock").write_text(
                '[[package]]\nname="test-root"\nsource={virtual="."}\n'
            )
        (self.root / "environments/manifest.json").write_text(json.dumps(self.manifest))
        (self.root / "configs/methods.yaml").write_text(yaml.safe_dump(methods))
        self.environment = patch.dict(
            os.environ,
            {
                "LLM_BASE_URL": "https://user:password@example.test/v1?token=private#secret",
                "LLM_API_KEY": "test-key-private",
                "LLM_MODEL": "cx/model",
            },
            clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def config(self):
        return load_config(self.config_path)

    def invoke(self, *args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = main(["--config", str(self.config_path), *args])
        return status, stream.getvalue()

    def test_environment_overrides_dotenv_and_paths_use_root(self):
        (self.root / ".env").write_text(
            "LLM_MODEL=dotenv-model\nOUTPUT_DIR=local-results\nLLM_API_KEY=dotenv-key\n"
        )
        config = self.config()
        self.assertEqual(config.env["LLM_MODEL"], "cx/model")
        self.assertEqual(config.output, self.root / "local-results")
        self.assertNotIn("OUTPUT_DIR", os.environ)

    def test_python_symlink_keeps_virtual_environment_path(self):
        executable = self.root / "venv/bin/python"
        executable.parent.mkdir(parents=True)
        executable.symlink_to(sys.executable)
        methods_path = self.root / "configs/methods.yaml"
        methods = yaml.safe_load(methods_path.read_text())
        methods["few-shot"]["python"] = str(executable)
        methods_path.write_text(yaml.safe_dump(methods))
        self.assertEqual(self.config().methods["few-shot"]["python"], executable)

    def test_dry_run_has_no_subprocess_or_files(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        with patch(
            "subprocess.run", side_effect=AssertionError("No subprocess in dry-run")
        ):
            status, output = self.invoke(
                "run",
                "--method",
                "all",
                "--limit",
                "3",
                "--run-id",
                "preview",
                "--dry-run",
                "--json",
            )
        self.assertEqual(status, 0)
        result = json.loads(output)
        self.assertEqual(len(result["stages"]), 7)
        self.assertEqual(result["limit"], 3)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.assertNotIn("password", output)
        self.assertNotIn("token=private", output)
        self.assertNotIn("test-key-private", output)
        self.assertNotIn("#secret", output)
        self.assertEqual(
            result["environment"]["LLM_BASE_URL"], "https://example.test/v1"
        )

    def test_commands_follow_contracts(self):
        stages = plan(self.config(), "all", limit=3, run_id="preview")["stages"]
        self.assertTrue(stages[0]["argv"][3].endswith("/"))
        self.assertIn("--start_pos", stages[1]["argv"])
        self.assertNotIn("--without_selector", stages[1]["argv"])
        dail = stages[2:]
        self.assertEqual(dail[1]["argv"][dail[1]["argv"].index("--split") + 1], "test")
        self.assertIn(dail[2]["output"].split("/work/dail/")[1], dail[3]["argv"][-1])
        for ask in (dail[2], dail[4]):
            self.assertEqual(ask["argv"][-4:], ["--n", "1", "--batch_size", "1"])
            self.assertNotIn("--model", ask["argv"])
            self.assertNotIn("--api_key", ask["argv"])
            self.assertIn("RESULTS_MODEL-cx_model.txt", ask["output"])

    def test_reject_execution_bad_limit_and_run_id(self):
        self.assertEqual(self.invoke("run")[0], 2)
        self.assertEqual(self.invoke("run", "--dry-run", "--limit", "0")[0], 2)
        self.assertEqual(self.invoke("run", "--dry-run", "--run-id", "../escape")[0], 2)
        existing = self.root / "results/runs/existing"
        existing.mkdir(parents=True)
        with self.assertRaises(ConfigError):
            plan(self.config(), "few-shot", run_id="existing")

    def test_reject_output_inside_dataset(self):
        with patch.dict(os.environ, {"OUTPUT_DIR": "data/spider/results"}):
            with self.assertRaises(ConfigError):
                plan(self.config(), "all")

    def test_missing_or_malformed_configuration(self):
        self.config_path.write_text("root: [wrong]\n")
        self.assertEqual(self.invoke("doctor")[0], 2)
        self.config_path.write_text("invalid: [yaml\n")
        self.assertEqual(self.invoke("doctor")[0], 2)

    def test_redacts_escaped_key_in_json(self):
        with patch.dict(
            os.environ,
            {"LLM_API_KEY": 'key"with\\escapes', "LLM_MODEL": 'key"with\\escapes'},
        ):
            status, output = self.invoke("run", "--dry-run", "--json")
        self.assertEqual(status, 0)
        self.assertNotIn("escapes", output)
        json.loads(output)

    def make_dataset(self):
        spider = self.root / "data/spider"
        spider.mkdir(parents=True)
        (spider / "dev.json").write_text(
            json.dumps(
                [{"db_id": "college_2", "question": "count", "query": "SELECT 1"}]
            )
        )
        (spider / "tables.json").write_text(json.dumps([{"db_id": "college_2"}]))
        for filename in ("train_spider.json", "train_others.json"):
            (spider / filename).write_text("[]")
        for root in (spider / "database", self.root / "data/test-suite-databases"):
            db = root / "college_2/college_2.sqlite"
            db.parent.mkdir(parents=True)
            db.touch()

    def git_probe(self, argv, cwd=None):
        if argv[0] == "git":
            name = Path(argv[2]).name
            return self.manifest[name]["revision"] if "rev-parse" in argv else ""
        raise AssertionError("Unexpected command")

    def test_doctor_valid_and_missing_prerequisites(self):
        self.make_dataset()
        from test2sql.doctor import command

        def probe(argv, cwd=None):
            return self.git_probe(argv, cwd) if argv[0] == "git" else command(argv, cwd)

        with patch("test2sql.doctor.command", side_effect=probe):
            status, output = self.invoke("doctor", "--json")
            self.assertEqual(status, 0, output)
            checks = json.loads(output)["checks"]
            self.assertTrue(any(c["status"] == "warning" for c in checks))
            (self.root / "data/spider/dev.json").write_text("{}")
            status, output = self.invoke("doctor", "--method", "few-shot", "--json")
            self.assertEqual(status, 1)
            self.assertIn("Missing/invalid Spider JSON", output)

    def test_doctor_handles_missing_python_repo_and_secrets(self):
        config = self.config()
        config.methods["few-shot"]["python"] = self.root / "absent-python"
        config.methods["few-shot"]["repository"] = self.root / "absent-repo"
        checks = diagnose(config, "few-shot")
        self.assertTrue(
            any(
                c["name"] == "few-shot repository" and c["status"] == "error"
                for c in checks
            )
        )
        self.assertTrue(
            any(
                c["name"] == "few-shot environment" and c["status"] == "error"
                for c in checks
            )
        )
        self.assertNotIn("test-key-private", json.dumps(checks))

    def test_doctor_dependency_and_revision_mismatch(self):
        self.make_dataset()
        path = self.root / self.manifest["few-shot"]["project"] / "uv.lock"
        path.write_text(
            '[[package]]\nname="test-root"\nsource={virtual="."}\ndependencies=[{name="missing-test-package"}]\n[[package]]\nname="missing-test-package"\nversion="1.0"\nsource={registry="https://example.test"}\n'
        )
        from test2sql.doctor import command

        def probe(argv, cwd=None):
            if argv[0] == "git":
                return "wrong-revision" if "rev-parse" in argv else " M run.py"
            return command(argv, cwd)

        with patch("test2sql.doctor.command", side_effect=probe):
            checks = diagnose(self.config(), "few-shot")
        failed = {c["name"] for c in checks if c["status"] == "error"}
        self.assertTrue(
            {"few-shot revision", "few-shot checkout", "few-shot dependencies"}
            <= failed
        )

    def test_lock_markers_and_extras_select_runtime_packages(self):
        from test2sql.doctor import required_packages

        lock = {
            "package": [
                {
                    "name": "root",
                    "source": {"virtual": "."},
                    "dependencies": [{"name": "core", "extra": ["http"]}],
                },
                {
                    "name": "core",
                    "version": "1",
                    "source": {"registry": "test"},
                    "dependencies": [
                        {"name": "windows", "marker": "sys_platform == 'win32'"}
                    ],
                    "optional-dependencies": {"http": [{"name": "http"}]},
                },
                {"name": "http", "version": "1", "source": {"registry": "test"}},
                {"name": "windows", "version": "1", "source": {"registry": "test"}},
                {"name": "build-only", "version": "1", "source": {"registry": "test"}},
            ]
        }
        for platform, expected in (
            ("darwin", {"core", "http"}),
            ("win32", {"core", "http", "windows"}),
        ):
            self.assertEqual(
                {
                    p["name"]
                    for p in required_packages(lock, {"sys_platform": platform})
                },
                expected,
            )

    def test_doctor_timeout_becomes_actionable_error(self):
        with patch(
            "test2sql.doctor.command",
            side_effect=subprocess.TimeoutExpired("probe", 30),
        ):
            checks = diagnose(self.config(), "few-shot")
        self.assertTrue(
            any(
                c["name"] == "few-shot environment" and c["status"] == "error"
                for c in checks
            )
        )


if __name__ == "__main__":
    unittest.main()
