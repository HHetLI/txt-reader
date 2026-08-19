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
from ui.theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小说阅读听书")
        self.resize(1000, 700)
        apply_theme(self)  # 深色主题（QSS 作用到整个应用）

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
        splitter.setSizes([170, 830])  # 紧凑：章节列表 170px

        central = QWidget()
        central.setObjectName("centralRoot")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
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
        # Task 6：引擎/情感控件 → 引擎；引擎后端状态 → 状态栏
        self._player_bar.backend_changed.connect(self._on_backend_changed)
        self._player_bar.emotion_changed.connect(self._on_emotion_changed)
        self._engine.backend_status.connect(self._on_backend_status)
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
        # 切换书本时停止旧播放会话，防止 A 书的引擎状态泄漏到 B 书
        self._engine.stop()
        self._book_path = str(Path(path).resolve())
        self._chapter_panel.set_chapters([c["title"] for c in self._chapters])
        progress = load_progress().get(self._book_path, {})
        index = progress.get("chapter", 0)
        index = max(0, min(index, len(self._chapters) - 1))
        self._chapter_panel.select_chapter(index)
        self._show_chapter(index)
        self._reader.restore_scroll(progress.get("scroll", 0))
        self._save_progress()  # 恢复滚动后重存进度，避免把 scroll=0 覆盖回存档
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
        # 先更新状态栏再启动：play_chapters 内部可能同步发出后端回退 error 状态
        # （如 IndexTTS 不可用自动切 edge），后置 set_status 会把它覆盖掉
        self._player_bar.set_status(f"正在朗读：{self._chapters[index]['title']}")
        self._engine.play_chapters(
            self._chapters, start_index=index,
            voice=self._player_bar.voice(), rate=self._player_bar.rate(),
            backend=self._player_bar.backend(),
            emotion_mode=self._player_bar.emotion_mode(),
            emotion_strength=self._player_bar.emotion_strength())

    def _on_prev(self) -> None:
        if not self._chapters:
            return
        # 有会话（播放/暂停）时，引擎章节索引是唯一事实来源：面板可能已被
        # 用户点到与听书位置不一致的章节，必须按引擎索引切章，防止视图与音频错位
        if self._engine.has_session():
            idx = self._engine.current_chapter_index()
            if idx > 0:
                new_index = idx - 1
                self._chapter_panel.select_chapter(new_index)
                self._show_chapter(new_index)
                self._engine.prev_chapter()
            return
        index = self._chapter_panel.current_index()
        if index <= 0:
            return
        new_index = index - 1
        self._chapter_panel.select_chapter(new_index)
        self._show_chapter(new_index)

    def _on_next(self) -> None:
        if not self._chapters:
            return
        if self._engine.has_session():
            idx = self._engine.current_chapter_index()
            if idx < len(self._chapters) - 1:
                new_index = idx + 1
                self._chapter_panel.select_chapter(new_index)
                self._show_chapter(new_index)
                self._engine.next_chapter()
            return
        index = self._chapter_panel.current_index()
        if index < 0 or index >= len(self._chapters) - 1:
            return
        new_index = index + 1
        self._chapter_panel.select_chapter(new_index)
        self._show_chapter(new_index)

    def _on_stop(self) -> None:
        self._engine.stop()
        self._player_bar.set_status("已停止")

    def _on_voice_changed(self, voice: str) -> None:
        if self._engine.is_playing():
            self._engine.set_voice(voice)

    def _on_rate_changed(self, rate: str) -> None:
        if self._engine.is_playing():
            self._engine.set_rate(rate)

    # ---------- Task 6：引擎/情感 参数透传 ----------

    def _on_backend_changed(self, name: str) -> None:
        """引擎下拉切换 → 即时切换后端（有会话时引擎会重启当前章节）。"""
        self._engine.set_backend(name)

    def _on_emotion_changed(self, mode: str, strength: float) -> None:
        """情感模式/强度变化 → 保存到引擎（IndexTTS 模式生效）。"""
        self._engine.set_emotion(mode, strength)

    def _on_backend_status(self, text: str) -> None:
        """引擎后端加载状态 → 状态栏文案：loading/ready/error:..."""
        if text == "loading":
            self._player_bar.set_backend_status(
                "正在加载情感引擎（首次约 30-60 秒）…")
        elif text == "ready":
            self._player_bar.set_backend_status("情感引擎就绪")
        elif text.startswith("error:"):
            self._player_bar.set_backend_status(text[len("error:"):])
        else:
            self._player_bar.set_backend_status(text)

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
