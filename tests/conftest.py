import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

import core.progress_store as progress_store


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture(autouse=True)
def _isolate_progress_store(monkeypatch, tmp_path):
    """进度存储重定向到测试临时目录。

    防止部分测试（如 open_file 流程）把测试书的临时路径写入真实的
    ~/.t2voice/progress.json，污染用户阅读进度数据。
    """
    monkeypatch.setattr(progress_store, "_store_path",
                        lambda: tmp_path / "progress.json")
