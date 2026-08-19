import tempfile
import threading
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


def test_engine_drains_after_synthesis_error(qtbot, monkeypatch):
    """合成失败后：error 触发，且 EndOfMedia 时推进章节而非永久卡死。"""

    async def failing_synthesize(sentence, voice, rate, out_path):
        raise RuntimeError("网络不可用")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", failing_synthesize)

    engine = TtsEngine()
    chapters = [
        {"title": "第一章", "content": "甲。"},
        {"title": "第二章", "content": "乙。"},
    ]
    errors: list[str] = []
    engine.error.connect(errors.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    # 第一句合成失败 → error 触发，且错误路径也发出 all_done（_worker_done 置位）
    qtbot.waitUntil(lambda: len(errors) >= 1, timeout=5000)
    qtbot.waitUntil(lambda: engine._worker_done, timeout=5000)
    assert errors[0] == "网络不可用"
    assert engine.current_chapter_index() == 0
    # 模拟本句播放结束：worker 已 done 且无可播句 → 应推进章节而非卡死
    engine._on_media_status(QMediaPlayer.MediaStatus.EndOfMedia)
    qtbot.waitUntil(lambda: engine.current_chapter_index() == 1, timeout=5000)
    engine.stop()


def test_stop_disconnects_stale_worker(qtbot, monkeypatch):
    """worker 卡在网络调用中无法及时退出时，stop() 必须断开其信号，防止僵尸线程
    迟到的信号污染后续会话（含手动补发信号的确定性验证）。"""

    entered = threading.Event()
    release = threading.Event()

    async def blocking_synthesize(sentence, voice, rate, out_path):
        entered.set()
        release.wait(10)  # 模拟卡在网络调用中，直到测试放行
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", blocking_synthesize)

    engine = TtsEngine()
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    worker = engine._worker
    assert entered.wait(5)  # 确认 worker 已进入阻塞的合成调用
    errors: list[str] = []
    engine.error.connect(errors.append)

    engine.stop()  # wait(1500) 超时 → 走断开信号分支
    assert not engine.has_session()
    engine.stop()  # 幂等：重复调用安全
    assert not engine.has_session()

    # 放行僵尸线程并等待其结束，避免 QThread 析构时仍在运行
    release.set()
    worker.wait(5000)

    # 若信号未断开，同线程手动 emit 会直接驱动引擎状态；已断开则无任何影响
    worker.all_done.emit(1)
    worker.sentence_ready.emit(0, "stale.mp3")
    worker.error_occurred.emit("boom")
    assert engine._worker_done is False
    assert engine._ready == {}
    assert engine._next_index == 0
    assert errors == []
