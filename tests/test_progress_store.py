import json
import pytest
from core import progress_store


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setattr(progress_store, "_store_path", lambda: tmp_path / "progress.json")
    yield


def test_load_empty_when_missing():
    assert progress_store.load_progress() == {}


def test_save_and_load_roundtrip():
    progress_store.save_progress("/x/a.txt", 3, 120)
    data = progress_store.load_progress()
    assert data["/x/a.txt"] == {"chapter": 3, "scroll": 120}


def test_save_overwrites_same_book():
    progress_store.save_progress("/x/a.txt", 1, 10)
    progress_store.save_progress("/x/a.txt", 2, 20)
    data = progress_store.load_progress()
    assert data["/x/a.txt"] == {"chapter": 2, "scroll": 20}


def test_save_keeps_other_books():
    progress_store.save_progress("/x/a.txt", 1, 10)
    progress_store.save_progress("/x/b.txt", 5, 50)
    data = progress_store.load_progress()
    assert set(data) == {"/x/a.txt", "/x/b.txt"}


def test_corrupted_json_returns_empty(tmp_path):
    (tmp_path / "progress.json").write_text("{not json", encoding="utf-8")
    assert progress_store.load_progress() == {}
