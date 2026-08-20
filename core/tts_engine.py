import asyncio
import tempfile
from pathlib import Path

import edge_tts
from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from core.sentence_splitter import split_sentences
from core.tts_backend import (EdgeTTSBackend, IndexTTSBackend, TTSBackendError,
                              sentence_limit_for_backend)


async def synthesize_sentence(sentence: str, voice: str, rate: str, out_path: Path) -> None:
    """合成单句为 mp3 文件。独立函数便于测试替换。"""
    communicate = edge_tts.Communicate(sentence, voice, rate=rate)
    await communicate.save(str(out_path))


#: edge-tts 声线代码 → IndexTTS 参考音频文件名（在 models/indextts/ref_audio/ 下）
_VOICE_TO_REF_AUDIO = {
    "zh-CN-XiaoxiaoNeural": "xiaoxiao.wav",
    "zh-CN-YunxiNeural": "yunxi.wav",
    "zh-CN-YunjianNeural": "yunjian.wav",
    "zh-CN-XiaoyiNeural": "xiaoyi.wav",
    "zh-CN-YunyangNeural": "yunyang.wav",
}


def _resolve_ref_audio_for_voice(voice: str) -> Path | None:
    """edge 声线代码 → IndexTTS 参考音频路径；无对应素材返回 None。"""
    fname = _VOICE_TO_REF_AUDIO.get(voice)
    if fname is None:
        return None
    p = Path("models/indextts/ref_audio") / fname
    if p.is_file():
        return p
    # 备选：index-tts 克隆仓库旁的素材（部署环境可能不同）
    alt = Path(r"E:/WorkSpace/index-tts/examples/ref_audio") / fname
    return alt if alt.is_file() else None


def _backend_factory(name: str):
    """按名称创建后端实例。模块级函数便于测试 monkeypatch。"""
    if name == "edge":
        return EdgeTTSBackend()
    return IndexTTSBackend()


class _SynthesisWorker(QThread):
    sentence_ready = Signal(int, str)
    all_done = Signal(int)  # 参数：总句数（start_index + len）
    error_occurred = Signal(str)
    fatal_error = Signal(str)  # 网络/服务持续失败（连续多句失败），应停止播放
    backend_status = Signal(str)  # 后端加载状态：loading / ready / error:...

    #: 单句合成失败时的重试次数（edge-tts 在线服务偶发失败，如 NoAudioReceived）
    MAX_RETRIES = 2
    #: 重试前的退避秒数
    RETRY_DELAY = 0.8
    #: 连续失败达到该阈值即判定网络断开（停止播放，避免每章反复弹错）
    FATAL_FAILURE_THRESHOLD = 3

    def __init__(self, sentences: list[str], voice: str, rate: str,
                 out_dir: Path, start_index: int = 0, parent=None,
                 backend=None, emo_mode: str = "auto",
                 emo_strength: float = 0.6):
        super().__init__(parent)
        self._sentences = sentences
        self._voice = voice
        self._rate = rate
        self._out_dir = out_dir
        self._start_index = start_index
        self._backend = backend
        self._emo_mode = emo_mode
        self._emo_strength = emo_strength
        self._cancel = False
        #: 当前是否处于懒加载中（供 __del__ 判断退役 worker 的加载滞留窗口）
        self._loading = False

    def cancel(self) -> None:
        self._cancel = True
        # 通知后端取消加载：worker 可能正处于懒加载（模型构造约 2-4 分钟，
        # 实测 264s），cancel_load 置位后 load() 在检查点快速抛错，退役线程尽快结束，
        # 缩小 QThread 仍在运行时引擎被 GC 的崩溃窗口
        cancel_load = getattr(self._backend, "cancel_load", None)
        if cancel_load is not None:
            cancel_load()

    def run(self) -> None:
        async def synth_all() -> None:
            # 懒加载：IndexTTS 首次合成前在 worker 线程内加载模型，
            # 加载前/后上报状态；失败则上报 error，由引擎回退 edge 并重启会话
            backend = self._backend
            if backend is not None and backend.name != "edge":
                load = getattr(backend, "load", None)
                is_loaded = getattr(backend, "is_loaded", None)
                if load is not None and is_loaded is not None and not is_loaded():
                    self.backend_status.emit("loading")
                    self._loading = True
                    try:
                        load()
                    except Exception as exc:  # noqa: BLE001
                        self.backend_status.emit(f"error:{exc}")
                        return
                    finally:
                        self._loading = False
                    self.backend_status.emit("ready")
            failed_count = 0
            consecutive_failures = 0
            for i, sentence in enumerate(self._sentences):
                idx = self._start_index + i
                if self._cancel:
                    break
                if not sentence.strip():
                    continue
                path = self._out_dir / f"sentence_{idx:05d}.mp3"
                ok = False
                last_error: Exception | None = None
                # 重试机制：edge-tts 在线服务偶发失败（NoAudioReceived 等），
                # 失败后重试 MAX_RETRIES 次，避免单次网络抖动中断整章听书
                for attempt in range(self.MAX_RETRIES + 1):
                    if self._cancel:
                        break
                    try:
                        await self._synthesize_one(sentence, path)
                        ok = True
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(self.RETRY_DELAY)
                if self._cancel:
                    break
                if ok:
                    consecutive_failures = 0
                    self.sentence_ready.emit(idx, str(path))
                else:
                    # 重试后仍失败：跳过该句继续，不中断整章
                    failed_count += 1
                    consecutive_failures += 1
                    # 本地情感引擎（IndexTTS）合成失败（OOM/模型故障）：重试已耗尽，
                    # 本地故障不随重试恢复，交由引擎切 edge 并重启会话保持播放连续
                    if (self._backend is not None and self._backend.name != "edge"
                            and isinstance(last_error, TTSBackendError)):
                        self.backend_status.emit(f"error:{last_error}")
                        self.all_done.emit(self._start_index + len(self._sentences))
                        return
                    if consecutive_failures >= self.FATAL_FAILURE_THRESHOLD:
                        # 连续多句失败说明网络/服务不可用：停止整章，避免每章反复重试
                        self.fatal_error.emit(
                            f"网络连接异常，朗读已停止（{last_error}）")
                        self.all_done.emit(self._start_index + len(self._sentences))
                        return
            if failed_count > 0:
                self.error_occurred.emit(
                    f"本章有 {failed_count} 句合成失败，已跳过继续播放")
            self.all_done.emit(self._start_index + len(self._sentences))

        asyncio.run(synth_all())

    async def _synthesize_one(self, sentence: str, path: Path) -> None:
        """按后端路由合成：edge 走 (rate, voice)，其余（indextts）走情感参数。"""
        backend = self._backend
        if backend is None or backend.name == "edge":
            await synthesize_sentence(sentence, self._voice, self._rate, path)
        else:
            await backend.synthesize(
                text=sentence, emo_mode=self._emo_mode,
                emo_strength=self._emo_strength, out_path=path)


class TtsEngine(QObject):
    playing = Signal(bool)
    sentence_started = Signal(int)
    chapter_finished = Signal()
    error = Signal(str)
    backend_status = Signal(str)  # "loading" / "ready" / "error:..."

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(1.0)
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_media_status)

        self._worker: _SynthesisWorker | None = None
        self._ready: dict[int, str] = {}
        self._next_index = 0
        self._worker_done = False
        # 退役 worker：仍在运行（网络合成中）的旧线程保留引用直到自然结束，
        # 防止被 GC 回收时 QThread 仍在运行而崩溃（Qt 未定义行为）。
        self._retired_workers: list[_SynthesisWorker] = []
        # 代际令牌：每次启动新会话递增；旧代际 worker 的迟到信号因令牌不匹配被丢弃
        self._generation = 0

        self._chapters: list[dict] = []
        self._chapter_index = 0
        self._out_dir: Path | None = None
        # 当前章节切分结果：供 UI 跟读高亮定位（sentence_started 的索引直接索引）
        self._current_sentences: list[str] = []

        self._voice = "zh-CN-XiaoxiaoNeural"
        self._rate = "+0%"

        # ---- Task 3：后端切换 + 情感参数 ----
        self._backend_name = "indextts"  # 设计默认：情感引擎
        self._emotion_mode = "auto"
        self._emotion_strength = 0.6
        self._backend_status = "idle"
        self._backend = _backend_factory(self._backend_name)
        # 播放中修改情感的防抖重启定时器（0.5s，滑条连续触发时合并为一次）
        self._emotion_debounce: QTimer | None = None

    def __del__(self) -> None:
        """析构保护：确保所有 worker 线程已结束再释放对象。

        QThread 对象被 GC 回收时若线程仍在运行会崩溃（0xc0000409）。
        正常路径由 stop() 的 wait 保证；此处兜底覆盖未调用 stop 直接
        丢弃引擎的场景（如异常退出），循环等待直到线程结束。
        """
        try:
            # 加载中的 worker（模型构造约 2-4 分钟，实测 264s，含 QwenEmotion，为单体
            # 调用）无法被 cancel 中途打断，cancel_load 只在 load() 检查点生效；此处把
            # 加载中的等待上限放宽到覆盖一次构造时长（≥264s，取 320s 余量），避免
            # 线程未结束时 GC 释放 QThread 崩溃（0xc0000409，__del__ 守卫针对该场景）。
            deadline = 15.0
            import time as _time
            start = _time.monotonic()
            if any(not w.isFinished() and getattr(w, "_loading", False)
                   for w in list(self._retired_workers)) or (
                       self._worker is not None
                       and not self._worker.isFinished()
                       and getattr(self._worker, "_loading", False)):
                deadline = 320.0
            while _time.monotonic() - start < deadline:
                alive = False
                for w in list(self._retired_workers):
                    if not w.isFinished():
                        w.wait(500)
                        if not w.isFinished():
                            alive = True
                if self._worker is not None and not self._worker.isFinished():
                    self._worker.wait(500)
                    if not self._worker.isFinished():
                        alive = True
                if not alive:
                    break
        except Exception:
            pass

    # ---------- 对外 API ----------

    def play_chapters(self, chapters: list[dict], start_index: int = 0,
                      voice: str | None = None, rate: str | None = None,
                      backend: str | None = None,
                      emotion_mode: str | None = None,
                      emotion_strength: float | None = None) -> None:
        self.stop()
        if not chapters:
            return
        self._chapters = chapters
        self._chapter_index = max(0, min(start_index, len(chapters) - 1))
        if voice:
            self._voice = voice
        if rate:
            self._rate = rate
        # Task 6：播放时透传 UI 控件值（引擎/情感参数立即生效，供后续会话使用）
        if backend:
            self.set_backend(backend)
        if emotion_mode is not None:
            self._emotion_mode = emotion_mode
        if emotion_strength is not None:
            self._emotion_strength = emotion_strength
        self._start_chapter(self._chapter_index)

    def toggle_play(self) -> None:
        if self._worker is None:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self.playing.emit(False)
        else:
            self._player.play()
            self.playing.emit(True)

    def stop(self) -> None:
        self._player.stop()
        if self._worker is not None:
            self._retire_worker(self._worker)
            self._worker = None
        self._ready.clear()
        self._next_index = 0
        self._worker_done = False
        self._cleanup_temp()
        self.playing.emit(False)

    def _retire_worker(self, worker: _SynthesisWorker) -> None:
        """退役一个 worker：断开信号、请求取消、同步等待线程结束。

        这是线程安全的唯一路径：QThread 对象在被 GC 回收时若线程仍在
        运行（run() 中访问 self._sentences/_out_dir），shiboken 销毁 C++
        对象会导致崩溃（0xc0000409，实测复现）。断开信号防污染、cancel
        请求终止、wait 同步等待线程真正结束后才允许引用被释放。
        """
        try:
            # 信号连接使用 lambda（绑定代际令牌），需用无参 disconnect 断开全部连接
            worker.sentence_ready.disconnect()
            worker.all_done.disconnect()
            worker.error_occurred.disconnect()
            worker.fatal_error.disconnect()
            worker.backend_status.disconnect()
        except (RuntimeError, TypeError):
            pass
        worker.cancel()
        # 同步等待线程结束（合成是网络 IO，cancel 在句间检查，单句 <1s，
        # 3s 上限足够；若极端超时，保留引用到线程自然结束，绝不放行 GC）
        if not worker.wait(3000):
            self._retired_workers.append(worker)
            worker.finished.connect(
                lambda w=worker: self._drop_retired_worker(w))

    def _drop_retired_worker(self, worker: _SynthesisWorker) -> None:
        """退役线程结束：从保留列表移除，允许 Qt 安全回收该线程对象。

        线程已在 _retire_worker 中 wait 结束；此处移除引用（finished 信号
        可能因事件循环退出未及时到达，故清理同时依赖引用列表生命周期）。
        """
        try:
            self._retired_workers.remove(worker)
        except ValueError:
            pass

    def next_chapter(self) -> None:
        if self._chapter_index + 1 < len(self._chapters):
            self._start_chapter(self._chapter_index + 1)

    def prev_chapter(self) -> None:
        if self._chapter_index - 1 >= 0:
            self._start_chapter(self._chapter_index - 1)

    def set_voice(self, voice: str) -> None:
        """切换声线：edge 后端直接设 voice；IndexTTS 后端映射到参考音频（音色）。"""
        self._voice = voice
        if self._backend is not None and self._backend.name == "indextts":
            ref = _resolve_ref_audio_for_voice(voice)
            if ref is not None:
                try:
                    self._backend.set_reference_audio(ref)
                except Exception:  # noqa: BLE001
                    pass  # 参考音频缺失时保持默认音色，不阻断
        self._restart_current_sentence()

    def set_rate(self, rate: str) -> None:
        self._rate = rate
        self._restart_current_sentence()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def has_session(self) -> bool:
        """是否存在未停止的播放会话（播放中或暂停中）。"""
        return self._worker is not None

    def current_chapter_index(self) -> int:
        return self._chapter_index

    def sentence_text(self, index: int) -> str | None:
        """当前章节第 index 句的文本（UI 跟读高亮定位用）。

        sentence_started 的索引是相对当前章节的绝对句索引，直接索引
        _current_sentences 即可；越界或未切句时返回 None。
        """
        if 0 <= index < len(self._current_sentences):
            return self._current_sentences[index]
        return None

    # ---- Task 3：后端切换 + 情感 ----

    def set_backend(self, name: str) -> None:
        """切换后端（edge/indextts）；有会话则从当前句重启，不回到章首。未知名称忽略。"""
        if name not in ("edge", "indextts"):
            return
        if name == self._backend_name:
            return
        self._backend_name = name
        self._backend = _backend_factory(name)
        if self.has_session():
            self._start_chapter(self._chapter_index,
                                start_sentence=max(0, self._next_index - 1))

    def backend(self) -> str:
        return self._backend_name

    def set_emotion(self, mode: str, strength: float) -> None:
        """设置情感参数（IndexTTS 模式生效）；edge 模式也保存，供后续切换使用。

        播放中且后端为 IndexTTS 时：0.5s 防抖后从当前句重启会话，情感立即生效
        （滑条连续触发时合并为一次重启）。edge 后端忽略情感，不触发重启。
        """
        self._emotion_mode = mode
        self._emotion_strength = strength
        if self._backend_name == "indextts" and self.has_session():
            self._arm_emotion_restart()

    def _arm_emotion_restart(self) -> None:
        """防抖重启：取消之前挂起的重启，500ms 后从当前句重启会话。"""
        if self._emotion_debounce is None:
            self._emotion_debounce = QTimer(self)
            self._emotion_debounce.setSingleShot(True)
            self._emotion_debounce.timeout.connect(self._on_emotion_restart)
        self._emotion_debounce.start(500)

    def _on_emotion_restart(self) -> None:
        """防抖到期：仍处于 IndexTTS 会话才重启（stop 后到期的迟到重启须忽略）。"""
        if self._backend_name == "indextts" and self.has_session():
            self._restart_current_sentence()

    def backend_ready(self) -> bool:
        """IndexTTS 后端已加载（edge 视为始终就绪，供 UI 显示状态）。"""
        if self._backend_name == "indextts":
            return bool(getattr(self._backend, "is_loaded", lambda: False)())
        return True

    # ---------- 内部 ----------

    def _start_chapter(self, index: int, start_sentence: int = 0) -> None:
        self.stop()
        self._chapter_index = index
        # IndexTTS 模型不可用（未安装/缺权重）时同步回退 edge，
        # 避免 worker 启动后 load 失败再走异步重启（阻塞式测试依赖同步路径）
        if self._backend_name == "indextts":
            is_available = getattr(self._backend, "is_available", None)
            if is_available is None:
                available = True
            else:
                try:
                    available = bool(is_available())
                except Exception:  # noqa: BLE001
                    available = False
            if not available:
                self._backend_status = "error:IndexTTS2.5 模型未安装，已自动回退 edge-tts"
                self.backend_status.emit(self._backend_status)
                self._backend_name = "edge"
                self._backend = _backend_factory("edge")
        chapter = self._chapters[index]
        limit = sentence_limit_for_backend(self._backend_name)
        sentences = split_sentences(chapter["content"], max_len=limit)
        self._current_sentences = sentences
        if start_sentence >= len(sentences):
            start_sentence = max(0, len(sentences) - 1)
        remainder = sentences[start_sentence:]
        self._out_dir = Path(tempfile.mkdtemp(prefix="t2voice_"))
        self._ready = {}
        self._next_index = start_sentence
        self._worker_done = False
        self._generation += 1
        generation = self._generation
        self._worker = _SynthesisWorker(
            remainder, self._voice, self._rate, self._out_dir,
            start_index=start_sentence, parent=self,
            backend=self._backend, emo_mode=self._emotion_mode,
            emo_strength=self._emotion_strength,
        )
        # 代际令牌：迟到的旧代际信号（如已退役 worker 的排队消息）因令牌不匹配被丢弃
        self._worker.sentence_ready.connect(
            lambda i, p, g=generation: self._on_sentence_ready(i, p, g))
        self._worker.all_done.connect(
            lambda total, g=generation: self._on_all_done(total, g))
        self._worker.error_occurred.connect(
            lambda msg, g=generation: self._on_error(msg, g))
        self._worker.fatal_error.connect(
            lambda msg, g=generation: self._on_fatal_error(msg, g))
        self._worker.backend_status.connect(
            lambda text, g=generation: self._on_worker_backend_status(text, g))
        self._worker.start()
        self.playing.emit(True)

    def _restart_current_sentence(self) -> None:
        if self._worker is None:
            return
        start = max(0, self._next_index - 1)
        self._start_chapter(self._chapter_index, start_sentence=start)

    def _on_sentence_ready(self, index: int, path: str, generation: int) -> None:
        if generation != self._generation:
            return  # 旧代际 worker 的迟到信号，丢弃
        self._ready[index] = path
        # 若当前未在播放且未处于暂停（含播放器空闲/刚启动），立即播下一个就绪句；
        # 暂停中保持暂停，等用户恢复
        if (self._player.playbackState() != QMediaPlayer.PlaybackState.PausedState
                and not self._player.isPlaying()
                and self._next_ready_index() is not None):
            self._play_next()

    def _next_ready_index(self) -> int | None:
        """返回 >= _next_index 的最小已就绪句索引；无则返回 None（支持跳过失败句）。"""
        for k in sorted(self._ready):
            if k >= self._next_index:
                return k
        return None

    def _on_all_done(self, total: int, generation: int) -> None:
        if generation != self._generation:
            return  # 旧代际 worker 的迟到信号，丢弃
        self._worker_done = True
        # 所有可播句均已播完（无可播就绪句）且播放器已停时才切章
        if (self._next_ready_index() is None
                and self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState):
            self._finish_chapter()

    def _on_error(self, message: str, generation: int) -> None:
        if generation != self._generation:
            return
        self.error.emit(message)

    def _on_fatal_error(self, message: str, generation: int) -> None:
        """网络/服务持续失败：停止当前播放会话，避免每章反复重试弹错。"""
        if generation != self._generation:
            return
        self.stop()
        self.error.emit(message)

    def _on_worker_backend_status(self, text: str, generation: int) -> None:
        """转发 worker 的后端加载/合成状态；引擎后端（IndexTTS）失败时回退 edge。

        回退仅在仍有播放会话时执行（保持播放连续）；已停止（无会话）时不改变后端
        配置——迟到信号不得幽灵切换后端。回退后从当前句重启，不丢失播放进度。
        """
        if generation != self._generation:
            return
        if text.startswith("error:"):
            self.backend_status.emit(text)
            if not self.has_session():
                return
            # IndexTTS 懒加载/合成失败（OOM、模型故障等）：切 edge 并重启会话
            reason = text[len("error:"):]
            self._backend_name = "edge"
            self._backend = _backend_factory("edge")
            self._backend_status = f"error:{reason}，已切换至 edge-tts"
            self.backend_status.emit(self._backend_status)
            self.error.emit(f"情感引擎合成失败（{reason}），已切换至 edge-tts")
            self._start_chapter(self._chapter_index,
                                start_sentence=max(0, self._next_index - 1))
        else:
            self._backend_status = text
            self.backend_status.emit(text)

    def _on_media_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._next_ready_index() is not None:
                self._play_next()
            elif not self._worker_done:
                pass  # 等待 worker 合成下一句
            else:
                self._finish_chapter()

    def _play_next(self) -> None:
        idx = self._next_ready_index()
        if idx is None:
            return
        path = self._ready.pop(idx)
        self._next_index = idx + 1
        self.sentence_started.emit(idx)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def _finish_chapter(self) -> None:
        if self._chapter_index + 1 < len(self._chapters):
            self._start_chapter(self._chapter_index + 1)
        else:
            self.playing.emit(False)
        self.chapter_finished.emit()

    def _cleanup_temp(self) -> None:
        if self._out_dir is not None and self._out_dir.exists():
            for f in self._out_dir.iterdir():
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                self._out_dir.rmdir()
            except OSError:
                pass
        self._out_dir = None
