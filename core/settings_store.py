"""应用级设置存储：主题、最近打开的书、窗口几何状态（~/.t2voice/settings.json）。"""

import json
import os
from pathlib import Path


def _settings_path() -> Path:
    return Path.home() / ".t2voice" / "settings.json"


_DEFAULTS: dict = {
    "theme": "deep",
    "recent_books": [],
    "window_geometry": None,
    "window_state": None,
}


def load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(_DEFAULTS)
        merged.update(data if isinstance(data, dict) else {})
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_settings(**kwargs) -> None:
    """保存设置项（原子写）。未给出的键保持原值。"""
    data = load_settings()
    data.update(kwargs)
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def update_recent_book(book_path: str, limit: int = 5) -> None:
    """把书加入最近打开列表：去重、置顶、截断。"""
    recent = load_settings().get("recent_books", [])
    recent = [p for p in recent if p != book_path]
    recent.insert(0, book_path)
    save_settings(recent_books=recent[:limit])


def recent_books() -> list[str]:
    """最近打开的书（过滤已不存在的文件）。"""
    return [p for p in load_settings().get("recent_books", []) if Path(p).exists()]
