from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, Iterator


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.common.db import load_settings  # noqa: E402


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved inputs and DB target without mutating the database.",
    )
    return parser


def csv_dict_reader(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def is_blank(value: object) -> bool:
    return value is None or str(value).strip() == ""


def normalize_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "y", "yes"}


def print_summary(stats: Iterable[tuple[str, object]]) -> None:
    for key, value in stats:
        print(f"- {key}: {value}")


def print_stage_banner(script_name: str, source_name: str) -> None:
    settings = load_settings()
    print(f"[etl] {script_name}")
    print(f"- source: {source_name}")
    print(f"- target DB: {settings.jdbc_url}")
    print("- implementation owner: follow the matching current-sprint workstream")
