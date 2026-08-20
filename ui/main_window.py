from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import (QCloseEvent, QIcon, QKeySequence, QShortcut)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox,
                               QDialog, QFileDialog, QLineEdit, QMainWindow,
                               QMenu, QMessageBox, QSystemTrayIcon, QVBoxLayout,
                               QWidget)

from core.chapter_splitter import split_chapters
from core.encoding import read_text_file
from core.progress_store import load_progress, save_progress
from core.settings_store import (load_settings, recent_books, save_settings,
                                 update_recent_book)
from core.tts_engine import TtsEngine
from ui.chapter_dialog import ChapterDialog
from ui.player_bar import PlayerBar
from ui.reader_view import ReaderView
from ui.search_bar import SearchBar
from ui.theme import apply_theme, theme_label, theme_names

_ICON_PATH = Path(__file__).resolve().parent.parent / "resources" / "icon.png"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小说阅读听书")
        self.resize(1000, 700)

        self._app_icon = (QIcon(str(_ICON_PATH))
                          if _ICON_PATH.exists() else QIcon())
        self.setWindowIcon(self._app_icon)

        settings = load_settings()
        self._theme = settings.get("theme", "deep")

        self._engine = TtsEngine(self)
        self._chapters: list[dict] = []
        self._current_chapter = -1  # 当前阅读章节索引
        self._book_path: str | None = None

        self._reader = ReaderView()
        self._search_bar = SearchBar()
        self._search_bar.hide()
        self._player_bar = PlayerBar()

        # 单栏布局：正文占满主区域，底部播放栏；搜索工具条在正文上方
        central = QWidget()
        central.setObjectName("centralRoot")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._search_bar)
        layout.addWidget(self._reader, 1)
        layout.addWidget(self._player_bar)
        self.setCentralWidget(central)

        self._build_menu()
        self._setup_shortcuts()
        self._connect_signals()
        self._apply_theme(self._theme, persist=False)
        self._restore_window_state(settings)
        self._setup_tray()
        self._refresh_recent_menu()

    # ---------- 菜单 ----------

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("文件")
        open_action = file_menu.addAction("打开...")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("最近打开")
        file_menu.addSeparator()
        quit_action = file_menu.addAction("退出")
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self._quit_app)

        # 播放控制（快捷键同款，便于键盘用户）
        play_menu = menu.addMenu("播放")
        play_menu.addAction("播放/暂停\tSpace").triggered.connect(
            self._on_play_toggled)
        play_menu.addAction("停止\tCtrl+S").triggered.connect(self._on_stop)
        play_menu.addSeparator()
        play_menu.addAction("上一章\tCtrl+PageUp").triggered.connect(
            self._on_prev)
        play_menu.addAction("下一章\tCtrl+PageDown").triggered.connect(
            self._on_next)

        # 章节选择收敛到菜单栏：跳转对话框 + 快速前后翻章
        chapter_menu = menu.addMenu("章节")
        jump_action = chapter_menu.addAction("跳转到章节…")
        jump_action.setShortcut("Ctrl+G")
        jump_action.triggered.connect(self._open_chapter_dialog)
        chapter_menu.addSeparator()
        prev_action = chapter_menu.addAction("上一章")
        prev_action.setShortcut("Ctrl+PageUp")
        prev_action.triggered.connect(self._on_prev)
        next_action = chapter_menu.addAction("下一章")
        next_action.setShortcut("Ctrl+PageDown")
        next_action.triggered.connect(self._on_next)

        settings_menu = menu.addMenu("设置")
        theme_menu = settings_menu.addMenu("主题")
        self._theme_actions: list = []
        for name in theme_names():
            act = theme_menu.addAction(theme_label(name))
            act.setCheckable(True)
            act.setData(name)
            act.triggered.connect(
                lambda checked=False, n=name: self._apply_theme(n))
            self._theme_actions.append(act)
        settings_menu.addSeparator()
        settings_menu.addAction("字号 +\tCtrl+=").triggered.connect(
            lambda: self._zoom_font(1))
        settings_menu.addAction("字号 -\tCtrl+-").triggered.connect(
            lambda: self._zoom_font(-1))
        settings_menu.addAction("复位字号\tCtrl+0").triggered.connect(
            self._reset_font)
        settings_menu.addSeparator()
        settings_menu.addAction("行距 +\tCtrl+Shift+=").triggered.connect(
            lambda: self._reader.set_line_spacing(round(self._reader._line_spacing + 0.2, 1)))
        settings_menu.addAction("行距 -\tCtrl+Shift+-").triggered.connect(
            lambda: self._reader.set_line_spacing(max(1.0, round(self._reader._line_spacing - 0.2, 1))))
        settings_menu.addSeparator()
        settings_menu.addAction("在正文中搜索\tCtrl+F").triggered.connect(self._open_search)
        settings_menu.addAction("全屏\tF11").triggered.connect(self._toggle_fullscreen)

    def _refresh_recent_menu(self) -> None:
        """刷新『最近打开』子菜单。"""
        self._recent_menu.clear()
        books = recent_books()
        if not books:
            none_act = self._recent_menu.addAction("（无）")
            none_act.setEnabled(False)
            return
        for path in books:
            act = self._recent_menu.addAction(Path(path).name)
            act.setToolTip(path)
            act.triggered.connect(
                lambda checked=False, p=path: self._load_book(p))

    # ---------- 快捷键 ----------

    def _setup_shortcuts(self) -> None:
        """全局快捷键：播放控制 / 搜索 / 字号 / 全屏。"""
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._on_space_shortcut)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_stop)
        QShortcut(QKeySequence.StandardKey.Find, self, self._open_search)
        QShortcut(QKeySequence(Qt.Key.Key_F3), self, self._on_find_next)
        # Esc 关闭搜索：输入框和正文区聚焦时均生效
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self._search_bar,
                  self._close_search)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self._reader,
                  self._close_search)
        QShortcut(QKeySequence.StandardKey.ZoomIn, self,
                  lambda: self._zoom_font(1))
        QShortcut(QKeySequence.StandardKey.ZoomOut, self,
                  lambda: self._zoom_font(-1))
        QShortcut(QKeySequence("Ctrl+0"), self, self._reset_font)
        QShortcut(QKeySequence("Ctrl+Shift+="), self,
                  lambda: self._reader.set_line_spacing(round(self._reader._line_spacing + 0.2, 1)))
        QShortcut(QKeySequence("Ctrl+Shift+-"), self,
                  lambda: self._reader.set_line_spacing(max(1.0, round(self._reader._line_spacing - 0.2, 1))))
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self._toggle_fullscreen)

    def _on_space_shortcut(self) -> None:
        """空格：播放/暂停。输入控件聚焦时放行（避免吃空格/误触按钮）。"""
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QComboBox, QAbstractButton)):
            return
        self._on_play_toggled()

    def _zoom_font(self, delta: int) -> None:
        self._reader.set_font_size(max(8, self._reader._font_size + delta))

    def _reset_font(self) -> None:
        self._reader.set_font_size(16)

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ---------- 主题 / 窗口状态 ----------

    def _apply_theme(self, name: str, persist: bool = True) -> None:
        """切换阅读主题：应用 QSS + 阅读器配色；持久化。"""
        self._theme = name
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, name)
        self._reader.set_theme(name)
        for act in self._theme_actions:
            act.setChecked(act.data() == name)
        if persist:
            save_settings(theme=name)

    def _restore_window_state(self, settings: dict) -> None:
        """恢复上次窗口大小/位置（settings 存储 hex 几何）。"""
        from PySide6.QtCore import QByteArray
        geo = settings.get("window_geometry")
        if geo:
            self.restoreGeometry(QByteArray.fromHex(bytes.fromhex(geo)))
        state = settings.get("window_state")
        if state:
            self.restoreState(QByteArray.fromHex(bytes.fromhex(state)))

    def _save_window_state(self) -> None:
        """保存窗口几何状态（hex 编码，JSON 可存）。"""
        geo = self.saveGeometry()
        state = self.saveState()
        save_settings(
            window_geometry=bytes(geo.toHex()).decode() if geo else None,
            window_state=bytes(state.toHex()).decode() if state else None,
        )

    # ---------- 系统托盘 ----------

    def _setup_tray(self) -> None:
        """系统托盘：关窗最小化到托盘，托盘菜单控制播放/退出。"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = None
            return
        self._tray = QSystemTrayIcon(self._app_icon, self)
        menu = QMenu(self)
        menu.setObjectName("trayMenu")
        menu.addAction("显示主窗口").triggered.connect(self._show_main)
        menu.addSeparator()
        menu.addAction("播放/暂停").triggered.connect(self._on_play_toggled)
        menu.addAction("上一章").triggered.connect(self._on_prev)
        menu.addAction("下一章").triggered.connect(self._on_next)
        menu.addAction("停止").triggered.connect(self._on_stop)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.setToolTip("小说阅读听书")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_main()

    def _show_main(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app(self) -> None:
        """真正退出：保存进度与窗口状态，隐藏托盘。"""
        self._engine.stop()
        self._save_progress()
        self._save_window_state()
        if self._tray is not None:
            self._tray.hide()
        QApplication.quit()

    # ---------- 信号连接 ----------

    def _connect_signals(self) -> None:
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
        self._engine.sentence_started.connect(self._on_sentence_started)
        self._engine.error.connect(
            lambda msg: QMessageBox.warning(self, "听书出错", msg))

        # 正文搜索：工具条 → 阅读器
        self._search_bar.search_text.connect(self._on_search_text)
        self._search_bar.find_next_requested.connect(self._on_find_next)
        self._search_bar.find_prev_requested.connect(self._on_find_prev)
        self._search_bar.closed.connect(self._close_search)

        # 章末导航：上一章 / 下一章
        self._reader.prev_requested.connect(self._on_prev)
        self._reader.next_requested.connect(self._on_next)

    # ---------- 文件 ----------

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开小说", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if path:
            self._load_book(path)

    def _load_book(self, path: str) -> None:
        try:
            text = read_text_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "打开失败", f"无法读取文件：\n{exc}")
            return
        self._chapters = split_chapters(text)
        # 切换书本时停止旧播放会话，防止 A 书的引擎状态泄漏到 B 书
        self._engine.stop()
        self._book_path = str(Path(path).resolve())
        progress = load_progress().get(self._book_path, {})
        index = progress.get("chapter", 0)
        index = max(0, min(index, len(self._chapters) - 1))
        self._show_chapter(index)
        self._reader.restore_scroll(progress.get("scroll", 0))
        self._save_progress()  # 恢复滚动后重存进度，避免把 scroll=0 覆盖回存档
        update_recent_book(self._book_path)
        self._refresh_recent_menu()
        name = Path(path).name
        self._player_bar.set_status(f"已打开：{name}（{len(self._chapters)} 章）")
        self._player_bar.set_sentence_progress(0, 0)

    def _show_chapter(self, index: int) -> None:
        chapter = self._chapters[index]
        self._current_chapter = index
        self._reader.show_chapter(chapter["title"], chapter["content"])
        # 换章后保留搜索词并重算：输入框有词则在新章重新高亮，无词则清空
        self._on_search_text(self._search_bar.current_text())
        self._save_progress()

    def _save_progress(self) -> None:
        if self._book_path:
            save_progress(self._book_path,
                          self._current_chapter,
                          self._reader.scroll_value())

    # ---------- 章节菜单 ----------

    def _open_chapter_dialog(self) -> None:
        if not self._chapters:
            QMessageBox.information(self, "提示", "请先打开一本小说")
            return
        dialog = ChapterDialog(
            [c["title"] for c in self._chapters],
            current=self._current_chapter, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_index >= 0:
            self._show_chapter(dialog.selected_index)
            title = self._chapters[dialog.selected_index]["title"]
            self._player_bar.set_status(f"当前章节：{title}")

    # ---------- 正文搜索 ----------

    def _open_search(self) -> None:
        """Ctrl+F：显示搜索工具条并聚焦输入框。"""
        self._search_bar.show()
        self._search_bar.focus_input()
        # 已有搜索词时同步一次计数（例如换章后重算过）
        self._on_search_text(self._search_bar.current_text())

    def _close_search(self) -> None:
        """Esc/✕：清除高亮、隐藏工具条、焦点还给正文。"""
        self._reader.clear_search()
        self._search_bar.hide()
        self._reader.setFocus()

    def _on_search_text(self, text: str) -> None:
        count = self._reader.search(text)
        cur = self._reader.current_match()
        self._search_bar.set_result(cur, count)

    def _on_find_next(self) -> None:
        if self._reader.find_next(False):
            self._search_bar.set_result(self._reader.current_match(),
                                        self._reader.match_count())

    def _on_find_prev(self) -> None:
        if self._reader.find_next(True):
            self._search_bar.set_result(self._reader.current_match(),
                                        self._reader.match_count())

    # ---------- 播放 ----------

    def _on_play_toggled(self) -> None:
        if not self._chapters:
            QMessageBox.information(self, "提示", "请先打开一本小说")
            return
        # 已存在会话（播放中或暂停中）→ 切换播放/暂停；否则从当前章节开始播
        if self._engine.has_session():
            self._engine.toggle_play()
            return
        index = self._current_chapter
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
        # 有会话（播放/暂停）时，引擎章节索引是唯一事实来源：界面可能已被
        # 用户跳到与听书位置不一致的章节，必须按引擎索引切章，防止视图与音频错位
        if self._engine.has_session():
            idx = self._engine.current_chapter_index()
            if idx > 0:
                self._show_chapter(idx - 1)
                self._engine.prev_chapter()
            return
        index = self._current_chapter
        if index <= 0:
            return
        self._show_chapter(index - 1)

    def _on_next(self) -> None:
        if not self._chapters:
            return
        if self._engine.has_session():
            idx = self._engine.current_chapter_index()
            if idx < len(self._chapters) - 1:
                self._show_chapter(idx + 1)
                self._engine.next_chapter()
            return
        index = self._current_chapter
        if index < 0 or index >= len(self._chapters) - 1:
            return
        self._show_chapter(index + 1)

    def _on_stop(self) -> None:
        self._engine.stop()
        self._player_bar.set_status("已停止")
        self._player_bar.set_sentence_progress(0, 0)

    def _on_voice_changed(self, voice: str) -> None:
        # 无条件透传：引擎 set_voice 内部按后端映射（edge→voice，
        # indextts→参考音频音色），无会话时安全返回
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
                "正在加载情感引擎（首次约 2-4 分钟）…")
        elif text == "ready":
            self._player_bar.set_backend_status("情感引擎就绪")
        elif text.startswith("error:"):
            self._player_bar.set_backend_status(text[len("error:"):])
        else:
            self._player_bar.set_backend_status(text)

    def _on_chapter_finished(self) -> None:
        idx = self._engine.current_chapter_index()
        if self._chapters and idx < len(self._chapters):
            self._show_chapter(idx)
            if idx + 1 < len(self._chapters):
                self._player_bar.set_status(f"正在朗读：{self._chapters[idx]['title']}")
            else:
                self._player_bar.set_status("全部朗读完毕")
                self._player_bar.set_sentence_progress(0, 0)

    def _on_sentence_started(self, idx: int) -> None:
        """播放句子 → 高亮正文中对应句子（跟读）+ 显示句级进度。

        仅当视图章节与引擎播放章节一致时高亮：用户播放中跳到别的章节
        （菜单跳转）时视图与听书位置不一致，跳过避免错位。
        """
        if not self._chapters:
            return
        if self._engine.current_chapter_index() != self._current_chapter:
            return
        rng = self._engine.sentence_range(idx)
        if rng:
            self._reader.highlight_sentence_range(*rng)
        total = self._engine.sentence_count()
        if total > 0:
            self._player_bar.set_sentence_progress(idx + 1, total)

    # ---------- 退出 ----------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._engine.stop()
        self._save_progress()
        if self._tray is not None:
            # 关窗 → 最小化到托盘：听书后台继续
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "小说阅读听书", "已最小化到系统托盘，听书继续播放。",
                QSystemTrayIcon.MessageIcon.Information, 2000)
        else:
            self._save_window_state()
            super().closeEvent(event)
