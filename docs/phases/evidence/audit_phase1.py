"""Offline source/CLI audit; never calls an LLM or loads the user's .env.

Usage: python3 docs/phases/evidence/audit_phase1.py /tmp/test2sql-phase1-audit
The checkouts must be at the revisions recorded below. Output is JSON on stdout.
CLI parser probes execute only argparse statements extracted from the source;
they do not establish that the full entry points or inference work.
"""

import argparse
import ast
import hashlib
import json
import os
import platform
import subprocess
import sys
import warnings
from pathlib import Path

REVISIONS = {
    "few-shot": "fe9d2ea39711dafaba7e0f0621513b9ab9646187",
    "MAC-SQL": "f8ca56f20192fe85b65a2542f917f820910e80d6",
    "DAIL-SQL": "7df99e15d8916a35711ff13735fd5ee01262c10e",
    "test-suite-sql-eval": "e97acc546ecbee8fa27fa8dbf025ef61493a876c",
}
HELP = {
    "few-shot": ["DIN-SQL.py"],
    "MAC-SQL": ["run.py"],
    "DAIL-SQL": ["data_preprocess.py", "generate_question.py", "ask_llm.py"],
    "test-suite-sql-eval": ["evaluation.py"],
}
PROBES = {
    "MAC-SQL": {
        "run.py": "--dataset_name spider --dataset_mode dev --input_file /run/subset.json --db_path /data/database --tables_json_path /data/tables.json --output_file /run/raw/mac.jsonl --log_file /run/logs/mac.log"
    },
    "DAIL-SQL": {
        "data_preprocess.py": "--data_type spider --data_dir /run/dataset/spider",
        "generate_question.py": "--data_type spider --split test --tokenizer gpt-3.5-turbo --max_seq_len 4096 --prompt_repr SQL --k_shot 9 --example_type QA --selector_type EUCDISMASKPRESKLSIMTHR --pre_test_result /run/pre.txt",
        "ask_llm.py": "--question /run/prompts --n 1 --batch_size 1 --start_index 0 --end_index 3",
    },
    "test-suite-sql-eval": {
        "evaluation.py": "--gold /run/gold.sql --pred /run/pred.sql --db /data/test-suite --table /data/tables.json --etype all --keep_distinct"
    },
}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def parser_probe(root, filename, argv):
    tree = ast.parse((root / filename).read_text())
    main = next(
        n
        for n in tree.body
        if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)
    )
    nodes = []
    for node in main.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "args" for t in node.targets
        ):
            break
        nodes.append(node)
    scope = {"argparse": argparse, "os": os}
    if root.name == "DAIL-SQL":
        enum_tree = ast.parse((root / "utils/enums.py").read_text())
        exec(compile(enum_tree, "utils/enums.py", "exec"), scope)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), scope)
    # Explicit fake key/model prevents inherited secrets in parser defaults.
    parsed = vars(scope["parser"].parse_args(argv.split()))
    parsed.pop("openai_api_key", None)
    return {"argv": argv.split(), "parsed": parsed}


def main():
    base = Path(sys.argv[1]).resolve()
    report = {
        "date": "2026-10-19",
        "python": platform.python_version(),
        "scope": "Static AST audit, isolated parser probes, and full --help attempts only; no inference or dataset evaluation.",
        "repositories": {},
    }
    # Do not pass credentials, proxy settings, PYTHONPATH, or any .env to children.
    env = {
        "PATH": os.defpath,
        "PYTHONDONTWRITEBYTECODE": "1",
        "LLM_API_KEY": "audit-placeholder",
        "LLM_MODEL": "audit-model",
        "LLM_BASE_URL": "http://127.0.0.1:1/v1",
    }
    os.environ["LLM_API_KEY"] = "audit-placeholder"
    os.environ["LLM_MODEL"] = "audit-model"
    for name, revision in REVISIONS.items():
        root = base / name
        assert git(root, "rev-parse", "HEAD") == revision, name
        assert not git(root, "status", "--porcelain", "--untracked-files=all"), name
        files = git(root, "ls-files").splitlines()
        record = {
            "commit": revision,
            "branch": git(root, "branch", "--show-current"),
            "remote": git(root, "remote", "get-url", "origin"),
            "python_sources": {},
            "requirements_sha256": None,
            "help_attempts": {},
            "parser_probes": {},
        }
        for filename in files:
            path = root / filename
            if filename.endswith(".py"):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ast.parse(path.read_text(), filename=filename)
                record["python_sources"][filename] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
            if filename == "requirements.txt":
                record["requirements_sha256"] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        for filename in HELP[name]:
            result = subprocess.run(
                [sys.executable, "-B", filename, "--help"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                timeout=15,
            )
            record["help_attempts"][filename] = {
                "command": ["python3", "-B", filename, "--help"],
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        for filename, argv in PROBES.get(name, {}).items():
            record["parser_probes"][filename] = parser_probe(root, filename, argv)
        record["working_tree_after"] = git(
            root, "status", "--porcelain", "--untracked-files=all"
        )
        assert not record["working_tree_after"], name
        report["repositories"][name] = record
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
