import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

import core.progress_store as progress_store
import core.settings_store as settings_store


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture(autouse=True)
def _isolate_stores(monkeypatch, tmp_path):
    """进度/设置存储重定向到测试临时目录。

    防止测试（如 open_file 流程、主题/最近打开切换）把临时路径写入真实的
    ~/.t2voice/progress.json 与 settings.json，污染用户数据。
    """
    monkeypatch.setattr(progress_store, "_store_path",
                        lambda: tmp_path / "progress.json")
    monkeypatch.setattr(settings_store, "_settings_path",
                        lambda: tmp_path / "settings.json")
