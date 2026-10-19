"""Small shared helpers for checksummed local artifacts."""

import hashlib
import json
import re
from pathlib import Path

from .config import ConfigError


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Missing or invalid JSON: {path}") from exc


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def safe_name(value, label="name"):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value
    ):
        raise ConfigError(
            f"{label} must be 1–100 letters, digits, dots, underscores or hyphens"
        )
    return value


def db_id(value):
    return safe_name(value, "db_id")


def file_record(path):
    path = Path(path)
    return {"sha256": sha256(path), "bytes": path.stat().st_size}
