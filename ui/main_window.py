from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QFileDialog, QMainWindow, QMessageBox,
                               QSplitter, QVBoxLayout, QWidget)

from core.chapter_splitter import split_chapters
from core.encoding import read_text_file
from core.progress_store import load_progress, save_progress
from core.tts_engine import TtsEngine
from ui.chapter_panel import ChapterPanel
from ui.player_bar import PlayerBar
from ui.reader_view import ReaderView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小说阅读听书")
        self.resize(1000, 700)

        self._engine = TtsEngine(self)
        self._chapters: list[dict] = []
        self._book_path: str | None = None

        self._chapter_panel = ChapterPanel()
        self._reader = ReaderView()
        self._player_bar = PlayerBar()

        splitter = QSplitter()
        splitter.addWidget(self._chapter_panel)
        splitter.addWidget(self._reader)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 780])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        layout.addWidget(self._player_bar)
        self.setCentralWidget(central)

        self._build_menu()
        self._connect_signals()

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("文件")
        open_action = file_menu.addAction("打开...")
        open_action.triggered.connect(self.open_file)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("退出")
        quit_action.triggered.connect(self.close)

        settings_menu = menu.addMenu("设置")
        settings_menu.addAction("字号 +").triggered.connect(
            lambda: self._reader.set_font_size(self._reader._font_size + 1))
        settings_menu.addAction("字号 -").triggered.connect(
            lambda: self._reader.set_font_size(max(8, self._reader._font_size - 1)))
        settings_menu.addSeparator()
        settings_menu.addAction("行距 +").triggered.connect(
            lambda: self._reader.set_line_spacing(round(self._reader._line_spacing + 0.2, 1)))
        settings_menu.addAction("行距 -").triggered.connect(
            lambda: self._reader.set_line_spacing(max(1.0, round(self._reader._line_spacing - 0.2, 1))))

    def _connect_signals(self) -> None:
        self._chapter_panel.chapter_selected.connect(self._on_chapter_selected)
        self._player_bar.play_toggled.connect(self._on_play_toggled)
        self._player_bar.prev_requested.connect(self._on_prev)
        self._player_bar.next_requested.connect(self._on_next)
        self._player_bar.stop_requested.connect(self._on_stop)
        self._player_bar.voice_changed.connect(self._on_voice_changed)
        self._player_bar.rate_changed.connect(self._on_rate_changed)
        self._engine.playing.connect(self._player_bar.set_playing)
        self._engine.chapter_finished.connect(self._on_chapter_finished)
        self._engine.error.connect(
            lambda msg: QMessageBox.warning(self, "听书出错", msg))

    # ---------- 文件 ----------

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开小说", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if not path:
            return
        try:
            text = read_text_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", f"无法读取文件：\n{exc}")
            return
        self._chapters = split_chapters(text)
        self._book_path = str(Path(path).resolve())
        self._chapter_panel.set_chapters([c["title"] for c in self._chapters])
        progress = load_progress().get(self._book_path, {})
        index = progress.get("chapter", 0)
        self._chapter_panel.select_chapter(index)
        self._show_chapter(index)
        self._reader.restore_scroll(progress.get("scroll", 0))
        name = Path(path).name
        self._player_bar.set_status(f"已打开：{name}（{len(self._chapters)} 章）")

    def _show_chapter(self, index: int) -> None:
        chapter = self._chapters[index]
        self._reader.show_chapter(chapter["title"], chapter["content"])
        self._save_progress()

    def _save_progress(self) -> None:
        if self._book_path:
            save_progress(self._book_path,
                          self._chapter_panel.current_index(),
                          self._reader.scroll_value())

    # ---------- 播放 ----------

    def _on_chapter_selected(self, index: int) -> None:
        self._show_chapter(index)
        self._player_bar.set_status(f"当前章节：{self._chapters[index]['title']}")

    def _on_play_toggled(self) -> None:
        if not self._chapters:
            QMessageBox.information(self, "提示", "请先打开一本小说")
            return
        # 已存在会话（播放中或暂停中）→ 切换播放/暂停；否则从当前章节开始播
        if self._engine.has_session():
            self._engine.toggle_play()
            return
        index = self._chapter_panel.current_index()
        if index < 0:
            index = 0
        self._engine.play_chapters(
            self._chapters, start_index=index,
            voice=self._player_bar.voice(), rate=self._player_bar.rate())
        self._player_bar.set_status(f"正在朗读：{self._chapters[index]['title']}")

    def _on_prev(self) -> None:
        if not self._chapters:
            return
        index = self._chapter_panel.current_index()
        if index <= 0:
            return
        new_index = index - 1
        self._chapter_panel.select_chapter(new_index)
        self._show_chapter(new_index)
        if self._engine.is_playing():
            self._engine.prev_chapter()

    def _on_next(self) -> None:
        if not self._chapters:
            return
        index = self._chapter_panel.current_index()
        if index < 0 or index >= len(self._chapters) - 1:
            return
        new_index = index + 1
        self._chapter_panel.select_chapter(new_index)
        self._show_chapter(new_index)
        if self._engine.is_playing():
            self._engine.next_chapter()

    def _on_stop(self) -> None:
        self._engine.stop()
        self._player_bar.set_status("已停止")

    def _on_voice_changed(self, voice: str) -> None:
        if self._engine.is_playing():
            self._engine.set_voice(voice)

    def _on_rate_changed(self, rate: str) -> None:
        if self._engine.is_playing():
            self._engine.set_rate(rate)

    def _on_chapter_finished(self) -> None:
        idx = self._engine.current_chapter_index()
        if self._chapters and idx < len(self._chapters):
            self._chapter_panel.select_chapter(idx)
            self._show_chapter(idx)
            if idx + 1 < len(self._chapters):
                self._player_bar.set_status(f"正在朗读：{self._chapters[idx]['title']}")
            else:
                self._player_bar.set_status("全部朗读完毕")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._engine.stop()
        self._save_progress()
        super().closeEvent(event)
