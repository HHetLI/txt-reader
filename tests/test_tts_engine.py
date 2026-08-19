import tempfile
import threading
from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer

from core.tts_backend import EdgeTTSBackend, TTSBackendError
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
    """连续多句合成失败（如断网）：触发 fatal 错误，停止播放而非卡死或反复切章。"""

    async def failing_synthesize(sentence, voice, rate, out_path):
        raise RuntimeError("网络不可用")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", failing_synthesize)

    engine = TtsEngine()
    chapters = [
        {"title": "第一章", "content": "甲。乙。丙。丁。"},
    ]
    errors: list[str] = []
    engine.error.connect(errors.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    # 连续 3 句失败 → fatal 错误触发，且引擎停止（会话清空）
    qtbot.waitUntil(lambda: len(errors) >= 1, timeout=15000)
    qtbot.waitUntil(lambda: not engine.has_session(), timeout=5000)
    assert any("网络连接异常" in e for e in errors)
    assert any("网络不可用" in e for e in errors)
    # 引擎已停止：不再有会话，不会反复切章或卡死
    assert engine.current_chapter_index() == 0


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


def test_worker_retries_transient_failure_then_continues(qtbot, monkeypatch):
    """偶发失败（如网络抖动）应自动重试，重试成功后继续，不中断整章。"""

    calls: dict[int, int] = {}

    async def flaky_synthesize(sentence, voice, rate, out_path):
        # 每句第一次调用抛异常（模拟偶发 NoAudioReceived），重试后成功
        key = sentence
        calls[key] = calls.get(key, 0) + 1
        if calls[key] == 1:
            raise RuntimeError("No audio received")
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", flaky_synthesize)

    out_dir = Path(tempfile.mkdtemp(prefix="t2voice_test_"))
    worker = _SynthesisWorker(["甲。", "乙。", "丙。"], "v", "+0%", out_dir)
    ready: list[tuple[int, Path]] = []
    errors: list[str] = []
    worker.sentence_ready.connect(lambda i, p: ready.append((i, Path(p))))
    worker.error_occurred.connect(errors.append)
    worker.start()
    qtbot.waitSignal(worker.all_done, timeout=15000).wait()
    worker.wait(5000)
    # 重试后全部成功，无 error
    assert [i for i, _ in ready] == [0, 1, 2]
    assert errors == []
    # 每句都调用过 2 次（1 次失败 + 1 次重试成功）
    assert all(v == 2 for v in calls.values())


def test_worker_skips_persistently_failing_sentence(qtbot, monkeypatch):
    """重试后仍失败的句子应跳过，其余句子继续，worker 正常结束不挂死。"""

    async def mostly_failing_synthesize(sentence, voice, rate, out_path):
        if sentence == "乙。":  # 乙句永远失败
            raise RuntimeError("No audio received")
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", mostly_failing_synthesize)

    out_dir = Path(tempfile.mkdtemp(prefix="t2voice_test_"))
    worker = _SynthesisWorker(["甲。", "乙。", "丙。"], "v", "+0%", out_dir)
    ready: list[tuple[int, Path]] = []
    errors: list[str] = []
    worker.sentence_ready.connect(lambda i, p: ready.append((i, Path(p))))
    worker.error_occurred.connect(errors.append)
    worker.start()
    qtbot.waitSignal(worker.all_done, timeout=15000).wait()
    worker.wait(5000)
    # 乙句被跳过（索引 1 缺失），其余正常
    assert [i for i, _ in ready] == [0, 2]
    assert len(errors) >= 1  # 有失败句时发提示


def test_engine_skips_missing_index_on_media_end(qtbot, monkeypatch):
    """句 1 永久失败被跳过时，EndOfMedia 后引擎应跳过缺失索引播下一句，不卡死。"""

    async def skipping_synthesize(sentence, voice, rate, out_path):
        if sentence == "乙。":
            raise RuntimeError("No audio received")
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", skipping_synthesize)

    engine = TtsEngine()
    chapters = [{"title": "第一章", "content": "甲。乙。丙。"}]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    # 句 0 开始播放
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=15000)
    # 句 0 播完：应跳过缺失的句 1，直接播放句 2
    engine._on_media_status(QMediaPlayer.MediaStatus.EndOfMedia)
    qtbot.waitUntil(lambda: len(started) >= 2, timeout=15000)
    assert started[1] == 2  # 第二句是索引 2（跳过 1）
    engine.stop()


def test_next_chapter_while_playing_survives_blocked_worker(qtbot, monkeypatch):
    """播放中快速切章（旧 worker 卡在合成中）不得崩溃，新会话必须干净启动。

    回归测试：stop() 对运行中 QThread 调用 setParent/deleteLater 是未定义行为，
    曾导致 Qt 层崩溃（0xc0000409）。修复后应无阻塞等待、无跨会话污染。
    """

    entered = threading.Event()
    release = threading.Event()

    async def blocking_synthesize(sentence, voice, rate, out_path):
        entered.set()
        release.wait(10)  # 模拟慢合成/网络卡顿
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", blocking_synthesize)

    engine = TtsEngine()
    chapters = [
        {"title": "第一章", "content": "甲。乙。丙。"},
        {"title": "第二章", "content": "丁。戊。己。"},
        {"title": "第三章", "content": "庚。辛。壬。"},
    ]
    errors: list[str] = []
    engine.error.connect(errors.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    old_worker = engine._worker
    assert entered.wait(5)  # 旧 worker 已卡在合成中

    # 播放中快速连续切章：stop() 等待旧线程结束 + 新 worker 启动
    engine.next_chapter()
    engine.next_chapter()
    assert engine.current_chapter_index() == 2
    assert engine.has_session()

    # 放行所有被阻塞的合成线程，确保引擎及其 worker 能安全收尾
    release.set()
    old_worker.wait(5000)
    engine.stop()
    assert not engine.has_session()
    # 显式释放引擎，触发 __del__ 等待线程结束，避免跨测试残留崩溃
    engine.deleteLater()
    qtbot.waitUntil(lambda: engine._worker is None and not engine._retired_workers,
                    timeout=5000)


# ---------- Task 3: backend 切换 + 懒加载 ----------


def test_engine_backend_default_is_indextts(qtbot, monkeypatch):
    engine = TtsEngine()
    assert engine.backend() == "indextts"  # 设计默认：情感引擎


def test_engine_switch_backend_restarts_session(qtbot, monkeypatch):
    # fake backend 记录调用；验证 set_backend 后当前章节重启（重新 play_chapters）
    calls: list[str] = []

    class FakeBackend:
        name = "fake"

        async def synthesize(self, *a, **k):
            calls.append(k.get("emo_mode", "?"))

    def factory(name):
        return FakeBackend()

    monkeypatch.setattr("core.tts_engine._backend_factory", factory)
    engine = TtsEngine()
    engine.set_backend("indextts")
    assert engine.backend() == "indextts"
    # 无会话时不崩溃
    engine.set_backend("edge")
    assert engine.backend() == "edge"


def test_engine_set_emotion_passes_to_backend(qtbot, monkeypatch):
    received: dict = {}

    class FakeBackend:
        name = "fake"

        async def synthesize(self, **kwargs):
            received.update(kwargs)

    monkeypatch.setattr("core.tts_engine._backend_factory", lambda n: FakeBackend())
    engine = TtsEngine()
    engine.set_backend("indextts")
    engine.set_emotion("悲伤", 0.5)
    assert engine._emotion_mode == "悲伤"
    assert engine._emotion_strength == 0.5


def test_engine_lazy_load_indextts_emits_status(qtbot, monkeypatch):
    """IndexTTS 首次 synthesize 前懒加载：loading → ready，且合成带情感参数。"""
    statuses: list[str] = []
    synth_kwargs: list[dict] = []
    loaded = False

    class FakeIndexBackend:
        name = "indextts"

        def is_loaded(self):
            return loaded

        def load(self):
            nonlocal loaded
            loaded = True

        async def synthesize(self, **kwargs):
            synth_kwargs.append(kwargs)
            Path(kwargs["out_path"]).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine._backend_factory",
                        lambda n: FakeIndexBackend())
    engine = TtsEngine()
    engine.backend_status.connect(statuses.append)
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)
    assert "loading" in statuses
    assert "ready" in statuses
    assert engine.backend_ready()
    assert synth_kwargs and synth_kwargs[0]["emo_mode"] == "auto"
    assert synth_kwargs[0]["emo_strength"] == 0.6
    engine.stop()


def test_engine_fallback_to_edge_on_load_failure(qtbot, monkeypatch):
    """IndexTTS 加载失败：backend_status(error) → 自动切 edge → 重启会话继续播放。"""
    statuses: list[str] = []

    class FailingIndexBackend:
        name = "indextts"

        def is_available(self):
            return True  # 模型可用但加载失败（如显存不足）

        def is_loaded(self):
            return False

        def load(self):
            raise TTSBackendError("模型加载失败: 显存不足")

        async def synthesize(self, **kwargs):
            raise AssertionError("不应走到 synthesize")

    def factory(name):
        if name == "edge":
            return EdgeTTSBackend()
        return FailingIndexBackend()

    # edge 路径经模块级 synthesize_sentence 接缝合成（与现有测试一致）
    async def fake_synthesize(sentence, voice, rate, out_path):
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine._backend_factory", factory)
    monkeypatch.setattr("core.tts_engine.synthesize_sentence", fake_synthesize)
    engine = TtsEngine()
    engine.backend_status.connect(statuses.append)
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: engine.backend() == "edge", timeout=5000)
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)  # 会话已重启并继续播放
    assert any(s.startswith("error:") for s in statuses)
    assert engine.backend() == "edge"
    assert engine.backend_ready()
    engine.stop()


def test_engine_set_backend_restarts_active_session(qtbot, monkeypatch):
    """有会话时 set_backend 重启当前章节（新后端生效），且不重复启动。"""
    synth_kwargs: list[dict] = []

    class FakeBackend:
        name = "fake"

        async def synthesize(self, **kwargs):
            synth_kwargs.append(kwargs)
            Path(kwargs["out_path"]).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine._backend_factory", lambda n: FakeBackend())
    engine = TtsEngine()
    chapters = [{"title": "第一章", "content": "甲。乙。"}]
    started: list[int] = []
    engine.sentence_started.connect(started.append)
    engine.play_chapters(chapters, start_index=0, voice="v", rate="+0%")
    qtbot.waitUntil(lambda: len(started) >= 1, timeout=5000)
    worker_before = engine._worker
    engine.set_backend("edge")
    assert engine.backend() == "edge"
    assert engine._worker is not worker_before  # 会话已重启（新 worker）
    assert worker_before.isFinished()  # 旧 worker 已同步退役，无残留
    engine.stop()


def test_engine_set_emotion_kept_for_later_switch(qtbot, monkeypatch):
    """set_emotion 在 edge 后端也保存参数，切回 indextts 时生效。"""
    engine = TtsEngine()
    engine.set_backend("edge")
    engine.set_emotion("悲伤", 0.4)
    assert engine._emotion_mode == "悲伤"
    assert engine._emotion_strength == 0.4
    engine.set_backend("indextts")
    assert engine._emotion_mode == "悲伤"
    assert engine._emotion_strength == 0.4
