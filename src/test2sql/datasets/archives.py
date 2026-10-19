"""Install official archives into separate, checksummed local directories."""

import shutil
import stat
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from ..artifacts import db_id, file_record, read_json, write_json
from ..config import ConfigError

SOURCES = {
    "spider": {
        "page": "https://yale-lily.github.io/spider",
        "url": "https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view",
        "download": "https://drive.usercontent.google.com/download?id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J&export=download&confirm=t",
        "archive": "spider_data.zip",
        "sha256": "00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b",
    },
    "test-suite": {
        "page": "https://github.com/taoyds/test-suite-sql-eval",
        "url": "https://drive.google.com/file/d/1mkCx2GOFIqNesD4y8TDAO1yX1QZORP5w/view",
        "download": "https://drive.usercontent.google.com/download?id=1mkCx2GOFIqNesD4y8TDAO1yX1QZORP5w&export=download&confirm=t",
        "archive": "testsuitedatabases.zip",
        "sha256": "9ec24ea8debc6bd04abfe137b5f1a739b5a8836f32c0464e4dfc94eb7f41da96",
    },
}


def install_archive(archive, destination, kind, database_ids=None):
    """Select known payloads; never extract archive paths directly or overwrite data."""
    archive, destination = Path(archive), Path(destination)
    if destination.exists():
        raise ConfigError(f"Data destination already exists: {destination}")
    if kind not in SOURCES:
        raise ConfigError("Unknown dataset archive kind")
    archive_record = file_record(archive)
    if archive_record["sha256"] != SOURCES[kind]["sha256"]:
        raise ConfigError("Archive SHA256 differs from the audited official download")
    ids = None if database_ids is None else {db_id(value) for value in database_ids}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".install-", dir=destination.parent
    ) as temporary:
        target = Path(temporary) / "payload"
        target.mkdir()
        members = {}
        try:
            with zipfile.ZipFile(archive) as bundle:
                for member in bundle.infolist():
                    path = PurePosixPath(member.filename)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or "\\" in member.filename
                    ):
                        raise ConfigError("Unsafe archive path")
                    if stat.S_ISLNK(member.external_attr >> 16):
                        raise ConfigError("Archive symlinks are not supported")
                    if member.is_dir() or "__MACOSX" in path.parts:
                        continue
                    name = path.name
                    relative = None
                    if kind == "spider" and name in {
                        "dev.json",
                        "tables.json",
                        "train_spider.json",
                        "train_others.json",
                        "train_gold.sql",
                        "dev_gold.sql",
                    }:
                        relative = Path(name)
                    elif (
                        name.endswith(".sqlite")
                        and len(path.parts) >= 2
                        and (kind != "spider" or "database" in path.parts)
                    ):
                        database = db_id(path.parts[-2])
                        if ids is None or database in ids:
                            relative = (
                                Path("database") / database / name
                                if kind == "spider"
                                else Path(database) / name
                            )
                    if relative is None:
                        continue
                    key = relative.as_posix()
                    if key in members:
                        raise ConfigError(f"Duplicate archive payload: {key}")
                    output = target / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, output.open("wb") as sink:
                        shutil.copyfileobj(source, sink, 1024 * 1024)
                    members[key] = {
                        "archive_member": member.filename,
                        **file_record(output),
                    }
        except (zipfile.BadZipFile, OSError) as exc:
            raise ConfigError(f"Cannot install ZIP archive: {archive}") from exc
        if kind == "spider":
            for name in (
                "dev.json",
                "tables.json",
                "train_spider.json",
                "train_others.json",
            ):
                if name not in members:
                    raise ConfigError(f"Spider archive missing {name}")
            rows = read_json(target / "dev.json")
            ids_required = {db_id(row["db_id"]) for row in rows}
            database_root = target / "database"
        else:
            ids_required = ids or {Path(name).parts[0] for name in members}
            database_root = target
        if not ids_required or any(
            not (database_root / value / f"{value}.sqlite").is_file()
            for value in ids_required
        ):
            raise ConfigError(
                "Archive does not contain all required original databases"
            )
        if kind == "test-suite" and any(
            len(list((database_root / value).glob("*.sqlite"))) < 2
            for value in ids_required
        ):
            raise ConfigError(
                "Test-suite archive must include additional database variants"
            )
        provenance = {
            "version": 1,
            "kind": kind,
            "source": SOURCES[kind]["url"],
            "source_page": SOURCES[kind]["page"],
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "archive": {"filename": archive.name, **archive_record},
            "database_ids": sorted(
                {Path(name).parts[-2] for name in members if name.endswith(".sqlite")}
            ),
            "required_database_ids": sorted(ids_required),
            "files": members,
            "checksum_note": "Locally observed SHA256; publisher does not provide an independent checksum here.",
        }
        write_json(target / "provenance.json", provenance)
        target.rename(destination)
    return provenance


def checked_provenance(root, kind):
    metadata = read_json(Path(root) / "provenance.json")
    if (
        not isinstance(metadata, dict)
        or metadata.get("kind") != kind
        or metadata.get("source") != SOURCES[kind]["url"]
        or metadata.get("archive", {}).get("sha256") != SOURCES[kind]["sha256"]
        or not isinstance(metadata.get("files"), dict)
    ):
        raise ConfigError(
            f"{kind} provenance does not identify the audited official archive"
        )
    return metadata


def verify_install(root, kind):
    root = Path(root)
    metadata = checked_provenance(root, kind)
    for relative, expected in metadata["files"].items():
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ConfigError("Unsafe provenance file path")
        actual = file_record(root / relative)
        if any(actual.get(key) != expected.get(key) for key in ("sha256", "bytes")):
            raise ConfigError(f"Installed data checksum mismatch: {relative}")
    return metadata
