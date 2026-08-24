"""应用日志：文件 + stderr 双输出。

文件日志位于项目根 logs/app.log（追加、UTF-8），供排查问题；
stderr 同步输出 INFO 及以上，命令行启动时可见。
"""

import logging
import sys
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_root_configured = False


def _setup() -> None:
    global _root_configured
    if _root_configured:
        return
    root = logging.getLogger("t2voice")
    if root.handlers:
        _root_configured = True
        return
    root.setLevel(logging.DEBUG)
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # 日志目录不可创建时仅保留 stderr
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        fh = logging.FileHandler(_LOG_DIR / "app.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    _root_configured = True


def get_logger(name: str) -> logging.Logger:
    """按模块名取 logger（如 get_logger("tts_backend")）。"""
    _setup()
    return logging.getLogger(f"t2voice.{name}")
