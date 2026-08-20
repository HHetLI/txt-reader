def test_import_core_packages():
    import core  # noqa: F401
    import ui  # noqa: F401


from ui.reader_view import ReaderView


def test_reader_view_shows_chapter(qapp):
    view = ReaderView()
    view.show_chapter("第一章", "第一行\n第二行")
    html = view.toHtml()
    assert "第一章" in html
    assert "第一行" in html
    assert "第二行" in html


def test_reader_view_font_size_changes(qapp):
    view = ReaderView()
    view.set_font_size(24)
    assert view._font_size == 24


def test_reader_view_escapes_html_content(qapp):
    """HTML 特殊字符（如 <未完待续>、<BR>）必须原样保留，不能当标签吞掉。"""
    view = ReaderView()
    view.show_chapter("第一章", "正文<未完待续> 与 <BR> 标签")
    text = view.toPlainText()
    assert "<未完待续>" in text
    assert "<BR>" in text


def test_reader_view_line_spacing_sets_block_height(qapp):
    """行距必须真正落到 QTextBlockFormat 的 lineHeight 上（CSS 在 Qt rich text 中无效）。"""
    from PySide6.QtGui import QTextBlockFormat

    view = ReaderView()
    view.show_chapter("标题", "第一行\n第二行")
    view.set_line_spacing(2.0)
    block = view.document().begin()
    fmt = block.blockFormat()
    assert fmt.lineHeight() == 200.0
    assert fmt.lineHeightType() == QTextBlockFormat.ProportionalHeight.value


from ui.chapter_panel import ChapterPanel


def test_chapter_panel_set_and_select(qapp):
    panel = ChapterPanel()
    panel.set_chapters(["第一章", "第二章", "第三章"])
    panel.select_chapter(1)
    assert panel.current_index() == 1


def test_chapter_panel_signal(qapp):
    from PySide6.QtTest import QSignalSpy
    panel = ChapterPanel()
    spy = QSignalSpy(panel.chapter_selected)
    panel.set_chapters(["a", "b"])
    panel._list.setCurrentRow(1)
    assert spy.count() == 1
    assert spy.at(0)[0] == 1


def test_chapter_panel_select_chapter_silent(qapp):
    from PySide6.QtTest import QSignalSpy
    panel = ChapterPanel()
    spy = QSignalSpy(panel.chapter_selected)
    panel.set_chapters(["a", "b", "c"])
    panel.select_chapter(1)
    assert spy.count() == 0
    panel._list.setCurrentRow(2)
    assert spy.count() == 1
    assert spy.at(0)[0] == 2


from ui.player_bar import PlayerBar


def test_player_bar_defaults(qapp):
    bar = PlayerBar()
    assert bar.voice() == "zh-CN-XiaoxiaoNeural"
    assert bar.rate() == "+0%"


def test_player_bar_voice_change_signal(qapp):
    from PySide6.QtTest import QSignalSpy
    bar = PlayerBar()
    spy = QSignalSpy(bar.voice_changed)
    bar._voice.setCurrentIndex(1)
    assert spy.count() == 1
    assert spy.at(0)[0] == "zh-CN-YunxiNeural"


def test_player_bar_status(qapp):
    bar = PlayerBar()
    bar.set_status("正在朗读：第一章")
    assert bar._status.text() == "正在朗读：第一章"


def test_player_bar_backend_default_indextts(qapp):
    """设计默认：引擎下拉选中 IndexTTS2.5 情感。"""
    bar = PlayerBar()
    assert bar.backend() == "indextts"
    assert bar._engine_combo.currentText() == "IndexTTS2.5 情感"


def test_player_bar_emotion_defaults(qapp):
    """情感默认：自动 + 强度 60%（0.0-1.0 浮点）。"""
    bar = PlayerBar()
    assert bar.emotion_mode() == "auto"  # 键与后端 EMO_MODE_AUTO 一致
    assert bar.emotion_strength() == 0.6
    assert bar._strength.value() == 60


def test_player_bar_backend_change_signal(qapp):
    from PySide6.QtTest import QSignalSpy
    bar = PlayerBar()
    spy = QSignalSpy(bar.backend_changed)
    bar._engine_combo.setCurrentIndex(1)  # edge-tts 快速
    assert spy.count() == 1
    assert spy.at(0)[0] == "edge"


def test_player_bar_emotion_changed_signal(qapp):
    """切换情感模式时携带 (mode, strength) 发射 emotion_changed。"""
    from PySide6.QtTest import QSignalSpy
    bar = PlayerBar()
    spy = QSignalSpy(bar.emotion_changed)
    bar._emotion.setCurrentIndex(2)  # 悲伤
    assert spy.count() == 1
    assert spy.at(0)[0] == "悲伤"
    assert spy.at(0)[1] == 0.6


def test_player_bar_strength_changed_signal(qapp):
    """强度滑条变化发射 emotion_changed（0-100 映射 0.0-1.0）。"""
    from PySide6.QtTest import QSignalSpy
    bar = PlayerBar()
    spy = QSignalSpy(bar.emotion_changed)
    bar._strength.setValue(30)
    assert spy.count() == 1
    assert spy.at(0)[1] == 0.3
    bar._strength.setValue(100)
    assert spy.count() == 2
    assert spy.at(1)[1] == 1.0


def test_player_bar_emotion_controls_toggle_with_backend(qapp):
    """情感控件随引擎联动：IndexTTS 可见可用，edge 隐藏禁用。"""
    bar = PlayerBar()
    # 默认 IndexTTS：可见可用
    assert not bar._emotion.isHidden()
    assert bar._emotion.isEnabled()
    assert not bar._strength.isHidden()
    assert bar._strength.isEnabled()
    # 切到 edge：隐藏禁用
    bar._engine_combo.setCurrentIndex(1)
    assert bar._emotion.isHidden()
    assert not bar._emotion.isEnabled()
    assert bar._strength.isHidden()
    assert not bar._strength.isEnabled()
    # 切回 IndexTTS：恢复可见可用
    bar._engine_combo.setCurrentIndex(0)
    assert not bar._emotion.isHidden()
    assert bar._emotion.isEnabled()
    assert not bar._strength.isHidden()
    assert bar._strength.isEnabled()


def test_player_bar_emotion_presets(qapp):
    """情感下拉包含全部预设（显示文本），索引 0 为自动。"""
    bar = PlayerBar()
    texts = [bar._emotion.itemText(i) for i in range(bar._emotion.count())]
    assert texts == ["自动", "平静", "悲伤", "激昂", "温柔", "恐惧", "高兴"]
    # 键与后端预设一致（自动→auto，其余中文名）
    keys = [bar._emotion.itemData(i) for i in range(bar._emotion.count())]
    assert keys == ["auto", "平静", "悲伤", "激昂", "温柔", "恐惧", "高兴"]


def test_player_bar_set_backend_status(qapp):
    """set_backend_status 在状态栏显示后端加载进度。"""
    bar = PlayerBar()
    bar.set_backend_status("加载情感引擎…")
    assert bar._status.text() == "加载情感引擎…"
    bar.set_backend_status("就绪")
    assert bar._status.text() == "就绪"


from ui.main_window import MainWindow


def test_main_window_constructs(qapp):
    win = MainWindow()
    assert win.windowTitle() == "小说阅读听书"
    assert win._reader is not None
    assert win._chapter_panel is not None
    assert win._player_bar is not None


def test_main_window_open_file_flow(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    book = tmp_path / "novel.txt"
    book.write_text("第一章 风起\n内容甲。\n第二章 云涌\n内容乙。", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book), "txt")))
    win = MainWindow()
    win.open_file()
    assert win._chapter_panel.current_index() == 0
    assert len(win._chapters) == 2
    assert win._chapter_panel._list.count() == 2
    assert "内容甲" in win._reader.toHtml()


def test_open_file_switching_book_stops_engine(qapp, tmp_path, monkeypatch):
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog

    import core.progress_store

    async def fake_synthesize(sentence, voice, rate, out_path):
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", fake_synthesize)

    book_a = tmp_path / "book_a.txt"
    book_a.write_text("第一章 风起\n内容甲。\n第二章 云涌\n内容乙。", encoding="utf-8")
    book_b = tmp_path / "book_b.txt"
    book_b.write_text("第一章 新书\n内容丙。\n第二章 新章\n内容丁。", encoding="utf-8")
    monkeypatch.setattr(core.progress_store, "_store_path",
                        lambda: tmp_path / "progress.json")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book_a), "txt")))
    win = MainWindow()
    win.open_file()
    # 开始播放 A（离线假合成，不发起真实网络调用）
    win._on_play_toggled()
    assert win._engine.has_session() is True
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book_b), "txt")))
    win.open_file()
    assert win._engine.has_session() is False
    assert win._book_path == str(book_b.resolve())


def test_open_file_clamps_out_of_range_progress(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    import core.progress_store
    import ui.main_window

    book = tmp_path / "novel.txt"
    book.write_text("第一章 风起\n内容甲。\n第二章 云涌\n内容乙。", encoding="utf-8")
    book_key = str(book.resolve())
    monkeypatch.setattr(core.progress_store, "_store_path",
                        lambda: tmp_path / "progress.json")
    monkeypatch.setattr(
        core.progress_store, "load_progress",
        lambda: {book_key: {"chapter": 999, "scroll": 0}})
    # main_window 通过 `from core.progress_store import load_progress` 在导入时
    # 绑定了自己的引用，必须同时替换，open_file 内才会读到 mock 数据
    monkeypatch.setattr(
        ui.main_window, "load_progress",
        lambda: {book_key: {"chapter": 999, "scroll": 0}})
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book), "txt")))
    win = MainWindow()
    win.open_file()  # 不应抛出 IndexError
    assert win._chapter_panel.current_index() == 1


def test_prev_next_uses_engine_index_when_session(qapp, tmp_path, monkeypatch):
    """有会话（播放/暂停）时，⏭/⏮ 必须按引擎章节索引切章：
    即使面板被用户点到其他章节，切章也必须跟随听书位置，防止视图与音频错位。"""
    from pathlib import Path

    from PySide6.QtWidgets import QFileDialog

    import core.progress_store

    async def fake_synthesize(sentence, voice, rate, out_path):
        Path(out_path).write_bytes(b"fake-mp3")

    monkeypatch.setattr("core.tts_engine.synthesize_sentence", fake_synthesize)
    book = tmp_path / "novel.txt"
    book.write_text(
        "第一章 风起\n甲。\n第二章 云涌\n乙。\n第三章 雷动\n丙。\n"
        "第四章 雨落\n丁。\n第五章 雪飞\n戊。\n第六章 霜降\n己。",
        encoding="utf-8")
    monkeypatch.setattr(core.progress_store, "_store_path",
                        lambda: tmp_path / "progress.json")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book), "txt")))
    win = MainWindow()
    win.open_file()
    win._on_play_toggled()
    assert win._engine.has_session() is True
    # 模拟：听书在第五章（索引 4），面板被点到第二章（索引 1）→ 视图与音频错位
    win._engine._chapter_index = 4
    win._chapter_panel.select_chapter(1)
    win._on_next()
    assert win._engine.current_chapter_index() == 5
    assert win._chapter_panel.current_index() == 5
    win._on_prev()
    assert win._engine.current_chapter_index() == 4
    assert win._chapter_panel.current_index() == 4
    win._engine.stop()


def test_theme_applies_without_error(qapp):
    """深色主题 QSS 可构建且应用到应用不抛异常。"""
    from ui.theme import build_qss, apply_theme
    qss = build_qss()
    assert "background-color" in qss
    assert "#1b1e26" in qss  # 深色主背景
    apply_theme(qapp)
    assert qapp.styleSheet() == qss


# ---------- Task 6: 参数透传 + 状态提示 ----------


def test_main_window_backend_changed_wires_to_engine(qapp):
    """引擎下拉切换 → backend_changed → engine.set_backend。"""
    win = MainWindow()
    assert win._engine.backend() == "indextts"  # 设计默认
    win._player_bar._engine_combo.setCurrentIndex(1)  # edge-tts 快速
    assert win._engine.backend() == "edge"
    win._player_bar._engine_combo.setCurrentIndex(0)  # 切回 IndexTTS
    assert win._engine.backend() == "indextts"


def test_main_window_emotion_changed_wires_to_engine(qapp):
    """情感模式/强度变化 → emotion_changed → engine.set_emotion。"""
    win = MainWindow()
    win._player_bar._emotion.setCurrentIndex(2)  # 悲伤
    assert win._engine._emotion_mode == "悲伤"
    assert win._engine._emotion_strength == 0.6
    win._player_bar._strength.setValue(30)
    assert win._engine._emotion_mode == "悲伤"
    assert win._engine._emotion_strength == 0.3


def test_main_window_backend_status_maps_to_status_label(qapp):
    """engine.backend_status → 状态栏文案映射（loading/ready/error:）。"""
    win = MainWindow()
    win._engine.backend_status.emit("loading")
    assert win._player_bar._status.text() == "正在加载情感引擎（首次约 2-4 分钟）…"
    win._engine.backend_status.emit("ready")
    assert win._player_bar._status.text() == "情感引擎就绪"
    win._engine.backend_status.emit("error:IndexTTS2.5 模型加载失败")
    assert win._player_bar._status.text() == "IndexTTS2.5 模型加载失败"


def test_main_window_play_passes_backend_and_emotion(qapp):
    """首次播放：play_chapters 必须携带引擎/情感控件当前值。"""
    win = MainWindow()
    win._chapters = [{"title": "第一章", "content": "甲。"}]
    win._chapter_panel.set_chapters(["第一章"])
    win._chapter_panel.select_chapter(0)
    calls: list[tuple] = []

    def spy_play(chapters, start_index=0, voice=None, rate=None,
                 backend=None, emotion_mode=None, emotion_strength=None):
        calls.append((start_index, voice, rate, backend,
                      emotion_mode, emotion_strength))

    win._engine.play_chapters = spy_play  # 记录透传参数，不真正播放
    win._player_bar._engine_combo.setCurrentIndex(1)  # edge
    win._player_bar._emotion.setCurrentIndex(2)       # 悲伤
    win._player_bar._strength.setValue(30)
    win._on_play_toggled()
    assert calls, "play_chapters 未被调用"
    _, _, _, backend, emo_mode, emo_strength = calls[-1]
    assert backend == "edge"
    assert emo_mode == "悲伤"
    assert emo_strength == 0.3


def test_reader_view_dark_style(qapp):
    """正文区深色样式：文字浅色、标题强调色。"""
    from ui.reader_view import ReaderView
    view = ReaderView()
    view.show_chapter("第一章", "正文内容")
    css = view.document().defaultStyleSheet()
    assert "#d5dae3" in css  # 浅色正文
    assert "#7fa3ff" in css  # 标题强调色
    assert view.viewportMargins().left() == 30  # 紧凑边距


def test_player_bar_voice_combo_repopulates_on_backend_switch(qapp):
    """引擎切换时声线下拉重填，保持选中声线一致。"""
    from ui.player_bar import PlayerBar
    bar = PlayerBar()
    # 默认 IndexTTS：声线为参考音色（data 为声线码）
    bar._voice.setCurrentIndex(2)  # 云健
    assert bar.voice() == "zh-CN-YunjianNeural"
    # 切到 edge：条目重填，选中保持不变
    bar._engine_combo.setCurrentIndex(bar._engine_combo.findData("edge"))
    assert bar.voice() == "zh-CN-YunjianNeural"
    # 切回 indextts：仍保持
    bar._engine_combo.setCurrentIndex(bar._engine_combo.findData("indextts"))
    assert bar.voice() == "zh-CN-YunjianNeural"
