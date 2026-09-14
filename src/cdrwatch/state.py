"""Snapshot and meta persistence under the state directory."""

import dataclasses
import json
from pathlib import Path

from cdrwatch.models import SourceMeta

META_FILE = "meta.json"


def load_snapshot(state_dir: Path, source_id: str) -> str | None:
    path = Path(state_dir) / f"{source_id}.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def save_snapshot(state_dir: Path, source_id: str, text: str) -> None:
    path = Path(state_dir) / f"{source_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def load_meta(state_dir: Path) -> dict[str, SourceMeta]:
    path = Path(state_dir) / META_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {source_id: SourceMeta(**fields) for source_id, fields in data.items()}


def save_meta(state_dir: Path, meta: dict[str, SourceMeta]) -> None:
    path = Path(state_dir) / META_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {source_id: dataclasses.asdict(m) for source_id, m in meta.items()}
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
