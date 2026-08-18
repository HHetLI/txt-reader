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
            for i, sentence in enumerate(self._sentences):
                idx = self._start_index + i
                if self._cancel:
                    break
                if not sentence.strip():
                    continue
                path = self._out_dir / f"sentence_{idx:05d}.mp3"
                try:
                    await synthesize_sentence(sentence, self._voice, self._rate, path)
                except Exception as exc:  # noqa: BLE001
                    if self._cancel:
                        break
                    self.error_occurred.emit(str(exc))
                    return
                if self._cancel:
                    break
                self.sentence_ready.emit(idx, str(path))
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
            self._worker.wait(1500)
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
        self._worker.start()
        self.playing.emit(True)

    def _restart_current_sentence(self) -> None:
        if self._worker is None:
            return
        start = max(0, self._next_index - 1)
        self._start_chapter(self._chapter_index, start_sentence=start)

    def _on_sentence_ready(self, index: int, path: str) -> None:
        self._ready[index] = path
        if index == self._next_index:
            self._play_next()

    def _on_all_done(self, total: int) -> None:
        self._worker_done = True
        # 仅当所有句子均已合成、无可播的下一句、且播放器已停（最后一句播完）时才切章
        if (self._next_index >= total
                and self._next_index not in self._ready
                and self._player.playbackState() == QMediaPlayer.PlaybackState.StoppedState):
            self._finish_chapter()

    def _on_media_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._next_index in self._ready:
                self._play_next()
            elif not self._worker_done:
                pass  # 等待 worker 合成下一句
            else:
                self._finish_chapter()

    def _play_next(self) -> None:
        if self._next_index not in self._ready:
            return
        path = self._ready.pop(self._next_index)
        self._next_index += 1
        self.sentence_started.emit(self._next_index - 1)
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
