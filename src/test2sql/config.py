"""Load explicit project paths and environment without exposing credentials."""

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml
from dotenv import dotenv_values


class ConfigError(ValueError):
    pass


def mapping(path):
    try:
        value = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Cannot read configuration: {path}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"Expected a mapping: {path}")
    return value


def project_root():
    for parent in (Path.cwd(), *Path.cwd().parents):
        if (parent / "environments/manifest.json").is_file():
            return parent
    raise ConfigError("Run inside the repository or supply --config PATH")


@dataclass
class Config:
    root: Path
    spider: Path
    suites: Path
    output: Path
    methods: dict
    env: dict

    def path(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ConfigError("Configured paths must be nonempty strings")
        return Path(os.path.abspath(self.root / Path(value).expanduser()))

    def safe(self, value):
        """Redact the full configured URL and key in every displayed string."""
        value = str(value)
        base = self.env.get("LLM_BASE_URL", "")
        if base:
            try:
                url = urlsplit(base)
                host = url.hostname or ""
                if url.port:
                    host += f":{url.port}"
                if ":" in (url.hostname or ""):
                    host = f"[{url.hostname}]" + (f":{url.port}" if url.port else "")
                cleaned = urlunsplit((url.scheme, host, url.path, "", ""))
            except ValueError:
                cleaned = "<redacted-url>"
            value = value.replace(base, cleaned)
            value = value.replace(json.dumps(base)[1:-1], json.dumps(cleaned)[1:-1])
        key = self.env.get("LLM_API_KEY", "")
        if key:
            variants = {key, key.replace("/", "_").replace("\\", "_")}
            for secret in sorted(variants, key=len, reverse=True):
                for representation in (
                    json.dumps(secret)[1:-1],
                    shlex.quote(secret),
                    secret,
                ):
                    value = value.replace(representation, "<redacted>")
        return value


def load_config(filename=None):
    path = (
        Path(filename).resolve()
        if filename
        else project_root() / "configs/default.yaml"
    )
    raw = mapping(path)
    root_value = raw.get("root", "..")
    if not isinstance(root_value, str):
        raise ConfigError("root must be a path string")
    root = (path.parent / root_value).resolve()
    # No interpolation: a value containing ${...} must never substitute a secret
    # into another setting that might subsequently be logged.
    env = {
        k: v
        for k, v in dotenv_values(root / ".env", interpolate=False).items()
        if v is not None
    }
    env.update(os.environ)
    config = Config(root, root, root, root, {}, env)
    config.spider = config.path(
        env.get("SPIDER_DATA_DIR", raw.get("spider_data_dir", "data/spider"))
    )
    config.suites = config.path(
        env.get(
            "TEST_SUITE_DB_DIR",
            raw.get("test_suite_db_dir", "data/test-suite-databases"),
        )
    )
    config.output = config.path(env.get("OUTPUT_DIR", raw.get("output_dir", "results")))
    config.methods = mapping(
        config.path(raw.get("methods_file", "configs/methods.yaml"))
    )
    for name in ("few-shot", "mac-sql", "dail-sql", "evaluator"):
        method = config.methods.get(name)
        if (
            not isinstance(method, dict)
            or not {"repository", "python"} <= method.keys()
        ):
            raise ConfigError(f"Missing repository/python configuration for {name}")
        method["repository"] = config.path(method["repository"])
        method["python"] = config.path(method["python"])
    if env.get("EVALUATOR_DIR"):
        config.methods["evaluator"]["repository"] = config.path(env["EVALUATOR_DIR"])
    return config
