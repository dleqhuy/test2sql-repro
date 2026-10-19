"""Build command previews only. Staging and inference belong to later phases."""

import re
from datetime import datetime, timezone

from .config import ConfigError

METHODS = ("few-shot", "mac-sql", "dail-sql")


def plan(config, method, split="dev", limit=None, run_id=None):
    if split != "dev":
        raise ConfigError("Only Spider dev is supported by the audited contracts")
    if limit is not None and limit < 1:
        raise ConfigError("--limit must be positive")
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", run_id):
        raise ConfigError(
            "--run-id must be 1–100 letters, digits, dots, underscores or hyphens"
        )
    run = config.output / "runs" / run_id
    if run.exists():
        raise ConfigError("Run directory already exists; choose a new --run-id")
    # Staging and caches must never write into an upstream checkout or dataset.
    protected = [
        config.spider,
        config.suites,
        *(m["repository"] for m in config.methods.values()),
    ]
    resolved_run = run.resolve()
    if any(
        resolved_run == p.resolve() or p.resolve() in resolved_run.parents
        for p in protected
    ):
        raise ConfigError("Output directory overlaps a source checkout or dataset")
    stages = []

    def stage(name, script, args, cwd, output):
        runtime = config.methods[name]
        script_path = runtime["repository"] / script if name != "dail-sql" else script
        stages.append(
            {
                "method": name,
                "argv": [str(runtime["python"]), str(script_path), *map(str, args)],
                "cwd": str(cwd),
                "output": str(output),
            }
        )

    for name in METHODS if method == "all" else (method,):
        if name == "few-shot":
            output = run / "raw/few-shot.sql"
            stage(
                name,
                "DIN-SQL.py",
                ["--dataset", str(run / "input/few-shot") + "/", "--output", output],
                run,
                output,
            )
        elif name == "mac-sql":
            output = run / "raw/mac/results.jsonl"
            stage(
                name,
                "run.py",
                [
                    "--dataset_name",
                    "spider",
                    "--dataset_mode",
                    "dev",
                    "--input_file",
                    run / "input/mac-subset.json",
                    "--db_path",
                    run / "input/database",
                    "--tables_json_path",
                    config.spider / "tables.json",
                    "--output_file",
                    output,
                    "--log_file",
                    run / "logs/mac/agent.log",
                    "--start_pos",
                    "0",
                ],
                run,
                output,
            )
        elif name == "dail-sql":
            work = run / "work/dail"
            stage(
                name,
                "data_preprocess.py",
                ["--data_type", "spider", "--data_dir", "./dataset/spider"],
                work,
                work / "dataset/spider",
            )
            model_file = (
                config.env.get("LLM_MODEL", "<LLM_MODEL>")
                .replace("/", "_")
                .replace("\\", "_")
            )
            pre_sql = None
            for selector in ("EUCDISQUESTIONMASK", "EUCDISMASKPRESKLSIMTHR"):
                question = (
                    "./dataset/process/SPIDER-TEST_SQL_9-SHOT_"
                    + selector
                    + "_QA-EXAMPLE_CTX-200_ANS-4096"
                )
                args = [
                    "--data_type",
                    "spider",
                    "--split",
                    "test",
                    "--tokenizer",
                    "gpt-3.5-turbo",
                    "--max_seq_len",
                    "4096",
                    "--prompt_repr",
                    "SQL",
                    "--k_shot",
                    "9",
                    "--example_type",
                    "QA",
                    "--selector_type",
                    selector,
                ]
                if pre_sql:
                    args += ["--pre_test_result", pre_sql]
                stage(
                    name,
                    "generate_question.py",
                    args,
                    work,
                    work / question / "questions.json",
                )
                pre_sql = question + f"/RESULTS_MODEL-{model_file}.txt"
                stage(
                    name,
                    "ask_llm.py",
                    ["--question", question, "--n", "1", "--batch_size", "1"],
                    work,
                    work / pre_sql,
                )
        else:
            raise ConfigError(f"Unknown method: {name}")
    return {
        "dry_run": True,
        "run_id": run_id,
        "split": split,
        "limit": limit,
        "source": str(config.spider / "dev.json"),
        "run_directory": str(run),
        "staging": "Planned only: shared ordered subset, full tables.json; MAC local IDs and copied databases; DAIL isolated source links, full train data and regenerated schema-linking. No files created.",
        "environment": {
            "LLM_BASE_URL": config.env.get("LLM_BASE_URL", "<missing>"),
            "LLM_MODEL": config.env.get("LLM_MODEL", "<missing>"),
            "LLM_API_KEY": "<redacted>"
            if config.env.get("LLM_API_KEY")
            else "<missing>",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HF_HOME": str(run / "cache/huggingface"),
            "TORCH_HOME": str(run / "cache/torch"),
        },
        "stages": stages,
    }
