import json
import os
from pathlib import Path


def _store_path() -> Path:
    return Path.home() / ".t2voice" / "progress.json"


def load_progress() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_progress(book_path: str, chapter: int, scroll: int) -> None:
    data = load_progress()
    data[book_path] = {"chapter": chapter, "scroll": scroll}
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
