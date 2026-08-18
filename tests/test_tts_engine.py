import tempfile
from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from core.tts_engine import TtsEngine, _SynthesisWorker


@pytest.fixture
def fake_synth(monkeypatch):
    """用写假 mp3 的合成函数替换真实 edge-tts，保证离线可测。"""

    async def fake_synthesize(sentence, voice, rate, out_path):
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", fake_synthesize)


def test_worker_synthesizes_in_order(qtbot, fake_synth):
    out_dir = Path(tempfile.mkdtemp(prefix="t2voice_test_"))
    worker = _SynthesisWorker(["甲。", "乙。", "丙。"], "v", "+0%", out_dir)
    ready: list[tuple[int, Path]] = []
    worker.sentence_ready.connect(lambda i, p: ready.append((i, Path(p))))
    worker.start()
    qtbot.waitSignal(worker.all_done, timeout=5000).wait()
    worker.wait(5000)  # 确保线程完全结束，避免析构时仍在运行
    assert [i for i, _ in ready] == [0, 1, 2]
    assert all(p.exists() for _, p in ready)


def test_worker_respects_cancel(qtbot, fake_synth):
    out_dir = Path(tempfile.mkdtemp(prefix="t2voice_test_"))
    worker = _SynthesisWorker(["甲。", "乙。", "丙。"], "v", "+0%", out_dir)
    worker.start()
    worker.cancel()
    qtbot.waitSignal(worker.all_done, timeout=5000).wait()
    worker.wait(5000)  # 确保线程完全结束，避免析构时仍在运行


def test_engine_plays_next_sentence_after_media_end(qtbot, fake_synth):
    """模拟播放结束信号，验证引擎顺序播放下一句（不依赖真实音频设备）。"""
    engine = TtsEngine()
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)  # 第一句已开始
    engine._on_media_status(QMediaPlayer.MediaStatus.EndOfMedia)
    qtbot.waitUntil(lambda: len(started) >= 2, timeout=5000)  # 第二句开始
    assert started[:2] == [0, 1]
    engine.stop()


def test_engine_auto_advances_chapter(qtbot, fake_synth):
    """第一章最后一句播完后自动切到第二章。"""
    engine = TtsEngine()
    chapters = [
        {"title": "第一章", "content": "甲。"},
        {"title": "第二章", "content": "乙。"},
    ]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)
    engine._on_media_status(QMediaPlayer.MediaStatus.EndOfMedia)  # 第一章播完
    qtbot.waitUntil(lambda: engine.current_chapter_index() == 1, timeout=5000)
    qtbot.waitUntil(lambda: len(started) >= 2, timeout=5000)  # 第二章第一句开始
    assert engine.current_chapter_index() == 1
    assert started[:2] == [0, 0]
    engine.stop()


def test_engine_stop_clears_session(qtbot, fake_synth):
    engine = TtsEngine()
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: engine.has_session(), timeout=5000)
    engine.stop()
    assert not engine.has_session()
