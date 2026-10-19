"""Download/install official Spider and test-suite archives (large, ignored data)."""

import argparse
import subprocess

from test2sql.artifacts import read_json
from test2sql.config import ConfigError, load_config
from test2sql.datasets.archives import SOURCES, install_archive, verify_install


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--kind", choices=["all", *SOURCES], default="all")
    parser.add_argument(
        "--download", action="store_true", help="Fetch missing archives using curl"
    )
    parser.add_argument(
        "--archive-dir", help="Local ZIP directory; default data/downloads"
    )
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        directory = config.path(args.archive_dir or "data/downloads")
        for kind in SOURCES if args.kind == "all" else (args.kind,):
            destination = config.spider if kind == "spider" else config.suites
            if destination.exists():
                verify_install(destination, kind)
                print(
                    f"{kind}: existing checksums verified at {destination}; not overwritten"
                )
                continue
            archive = directory / SOURCES[kind]["archive"]
            if not archive.is_file() and args.download:
                directory.mkdir(parents=True, exist_ok=True)
                partial = archive.with_suffix(".zip.part")
                subprocess.run(
                    [
                        "curl",
                        "--location",
                        "--fail",
                        "--retry",
                        "2",
                        "--connect-timeout",
                        "30",
                        "--max-time",
                        "1800",
                        SOURCES[kind]["download"],
                        "--output",
                        str(partial),
                    ],
                    check=True,
                )
                partial.rename(archive)
            if not archive.is_file():
                raise ConfigError(
                    f"Missing archive: {archive}; supply --download or copy the official ZIP here"
                )
            ids = None
            if kind == "test-suite":
                ids = {row["db_id"] for row in read_json(config.spider / "dev.json")}
            result = install_archive(archive, destination, kind, ids)
            print(f"{kind}: installed {len(result['files'])} files in {destination}")
    except (ConfigError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Data setup failed: {exc}\n")


if __name__ == "__main__":
    main()
