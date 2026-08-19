import asyncio
import tempfile
from pathlib import Path

import edge_tts
from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from core.sentence_splitter import split_sentences


async def synthesize_sentence(sentence: str, voice: str, rate: str, out_path: Path) -> None:
    """合成单句为 mp3 文件。独立函数便于测试替换。"""
    communicate = edge_tts.Communicate(sentence, voice, rate=rate)
    await communicate.save(str(out_path))


class _SynthesisWorker(QThread):
    sentence_ready = Signal(int, str)
    all_done = Signal(int)  # 参数：总句数（start_index + len）
    error_occurred = Signal(str)
    fatal_error = Signal(str)  # 网络/服务持续失败（连续多句失败），应停止播放

    #: 单句合成失败时的重试次数（edge-tts 在线服务偶发失败，如 NoAudioReceived）
    MAX_RETRIES = 2
    #: 重试前的退避秒数
    RETRY_DELAY = 0.8
    #: 连续失败达到该阈值即判定网络断开（停止播放，避免每章反复弹错）
    FATAL_FAILURE_THRESHOLD = 3

    def __init__(self, sentences: list[str], voice: str, rate: str,
                 out_dir: Path, start_index: int = 0, parent=None):
        super().__init__(parent)
        self._sentences = sentences
        self._voice = voice
        self._rate = rate
        self._out_dir = out_dir
        self._start_index = start_index
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        async def synth_all() -> None:
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
                        await synthesize_sentence(sentence, self._voice, self._rate, path)
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


class TtsEngine(QObject):
    playing = Signal(bool)
    sentence_started = Signal(int)
    chapter_finished = Signal()
    error = Signal(str)

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

        self._chapters: list[dict] = []
        self._chapter_index = 0
        self._out_dir: Path | None = None

        self._voice = "zh-CN-XiaoxiaoNeural"
        self._rate = "+0%"

    # ---------- 对外 API ----------

    def play_chapters(self, chapters: list[dict], start_index: int = 0,
                      voice: str | None = None, rate: str | None = None) -> None:
        self.stop()
        if not chapters:
            return
        self._chapters = chapters
        self._chapter_index = max(0, min(start_index, len(chapters) - 1))
        if voice:
            self._voice = voice
        if rate:
            self._rate = rate
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
            self._worker.cancel()
            if not self._worker.wait(1500):
                # 合成线程可能卡在网络调用中未及时退出：断开其信号，防止
                # 迟到的信号污染下一次播放会话
                self._worker.sentence_ready.disconnect(self._on_sentence_ready)
                self._worker.all_done.disconnect(self._on_all_done)
                self._worker.error_occurred.disconnect(self.error)
                # 线程仍在运行：解除父子关系，等线程结束后再销毁，避免析构崩溃
                self._worker.setParent(None)
                self._worker.finished.connect(self._worker.deleteLater)
            self._worker = None
        self._ready.clear()
        self._next_index = 0
        self._worker_done = False
        self._cleanup_temp()
        self.playing.emit(False)

    def next_chapter(self) -> None:
        if self._chapter_index + 1 < len(self._chapters):
            self._start_chapter(self._chapter_index + 1)

    def prev_chapter(self) -> None:
        if self._chapter_index - 1 >= 0:
            self._start_chapter(self._chapter_index - 1)

    def set_voice(self, voice: str) -> None:
        self._voice = voice
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

    # ---------- 内部 ----------

    def _start_chapter(self, index: int, start_sentence: int = 0) -> None:
        self.stop()
        self._chapter_index = index
        chapter = self._chapters[index]
        sentences = split_sentences(chapter["content"])
        if start_sentence >= len(sentences):
            start_sentence = max(0, len(sentences) - 1)
        remainder = sentences[start_sentence:]
        self._out_dir = Path(tempfile.mkdtemp(prefix="t2voice_"))
        self._ready = {}
        self._next_index = start_sentence
        self._worker_done = False
        self._worker = _SynthesisWorker(
            remainder, self._voice, self._rate, self._out_dir,
            start_index=start_sentence, parent=self,
        )
        self._worker.sentence_ready.connect(self._on_sentence_ready)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.error_occurred.connect(self.error)
        self._worker.fatal_error.connect(self._on_fatal_error)
        self._worker.start()
        self.playing.emit(True)

    def _restart_current_sentence(self) -> None:
        if self._worker is None:
            return
        start = max(0, self._next_index - 1)
        self._start_chapter(self._chapter_index, start_sentence=start)

    def _on_sentence_ready(self, index: int, path: str) -> None:
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

    def _on_all_done(self, total: int) -> None:
        self._worker_done = True
        # 所有可播句均已播完（无可播就绪句）且播放器已停时才切章
        if (self._next_ready_index() is None
                and self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState):
            self._finish_chapter()

    def _on_fatal_error(self, message: str) -> None:
        """网络/服务持续失败：停止当前播放会话，避免每章反复重试弹错。"""
        self.stop()
        self.error.emit(message)

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
