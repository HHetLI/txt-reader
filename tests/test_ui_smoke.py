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


# ---------- 正文搜索（Ctrl+F） ----------


def test_reader_view_search_highlights_all(qapp):
    """搜索词高亮全部匹配，当前匹配索引指向第一个。"""
    view = ReaderView()
    view.show_chapter("第一章", "甲乙丙甲丁甲")
    count = view.search("甲")
    assert count == 3
    assert view.match_count() == 3
    assert view.current_match() == 0
    assert len(view.extraSelections()) == 3


def test_reader_view_search_empty_text(qapp):
    """空搜索词：不清除旧高亮以外的状态，匹配数为 0。"""
    view = ReaderView()
    view.show_chapter("第一章", "甲乙")
    assert view.search("") == 0
    assert view.extraSelections() == []


def test_reader_view_find_next_cycles(qapp):
    """下一个/上一个循环跳转，当前匹配索引跟随。"""
    view = ReaderView()
    view.show_chapter("第一章", "甲乙丙甲乙")
    view.search("甲")
    assert view.current_match() == 0
    assert view.find_next(False) is True
    assert view.current_match() == 1
    assert view.find_next(False) is True  # 循环回第一个
    assert view.current_match() == 0
    assert view.find_next(True) is True   # 上一个 → 最后一个
    assert view.current_match() == 1


def test_reader_view_find_next_no_match(qapp):
    """无匹配时 find_next 返回 False，计数为空。"""
    view = ReaderView()
    view.show_chapter("第一章", "甲乙丙")
    view.search("不存在")
    assert view.match_count() == 0
    assert view.find_next() is False


def test_reader_view_clear_search(qapp):
    """清除搜索：匹配清空、高亮移除。"""
    view = ReaderView()
    view.show_chapter("第一章", "甲乙甲")
    view.search("甲")
    view.clear_search()
    assert view.match_count() == 0
    assert view.extraSelections() == []


def test_reader_view_search_reset_on_show_chapter(qapp):
    """换章后旧搜索高亮失效（正文已变更）。"""
    view = ReaderView()
    view.show_chapter("第一章", "甲乙甲")
    view.search("甲")
    assert view.match_count() == 2
    view.show_chapter("第二章", "丙丁")
    assert view.match_count() == 0
    assert view.extraSelections() == []


from ui.search_bar import SearchBar


def test_search_bar_result_text(qapp):
    bar = SearchBar()
    bar.set_result(0, 5)
    assert bar._count.text() == "1/5"
    bar.set_result(4, 5)
    assert bar._count.text() == "5/5"
    bar.set_result(-1, 0)
    assert bar._count.text() == "无匹配"


def test_search_bar_text_change_signal(qapp):
    from PySide6.QtTest import QSignalSpy
    bar = SearchBar()
    spy = QSignalSpy(bar.search_text)
    bar._input.setText("风起")
    assert spy.count() == 1
    assert spy.at(0)[0] == "风起"
    bar._input.setText("")
    assert spy.count() == 2
    assert spy.at(1)[0] == ""


def test_search_bar_enter_signal(qapp):
    from PySide6.QtTest import QSignalSpy
    bar = SearchBar()
    next_spy = QSignalSpy(bar.find_next_requested)
    bar._input.setText("风")
    bar._input.returnPressed.emit()
    assert next_spy.count() == 1


def test_search_bar_close_signal(qapp):
    from PySide6.QtTest import QSignalSpy
    bar = SearchBar()
    spy = QSignalSpy(bar.closed)
    bar._close_btn.click()
    assert spy.count() == 1


# ---------- 播放句子跟读高亮 ----------


def test_reader_view_highlight_sentence(qapp):
    view = ReaderView()
    view.show_chapter("第一章", "风起云涌。风起云涌。")
    assert view.highlight_sentence("风起云涌。") is True
    assert view._sentence_sel is not None
    assert view._sentence_anchor >= 0


def test_reader_view_highlight_sentence_cross_line(qapp):
    """跨行句子：\n 在渲染文档中是 U+2028，归一化后必须能匹配。"""
    view = ReaderView()
    view.show_chapter("第一章", "第一行开头\n第二行结尾。")
    assert view.highlight_sentence("第一行开头\n第二行结尾。") is True
    assert view._sentence_sel is not None


def test_reader_view_highlight_anchor_advances(qapp):
    """重复句子：从上次位置向后找，第二句定位到第二处而非开头。"""
    view = ReaderView()
    view.show_chapter("第一章", "风起。风起。")
    assert view.highlight_sentence("风起。") is True
    first_start = view._sentence_sel.cursor.selectionStart()
    assert view.highlight_sentence("风起。") is True
    second_start = view._sentence_sel.cursor.selectionStart()
    assert second_start > first_start


def test_reader_view_highlight_no_match(qapp):
    view = ReaderView()
    view.show_chapter("第一章", "甲乙丙")
    assert view.highlight_sentence("不存在的句子") is False
    assert view._sentence_sel is None


def test_reader_view_sentence_and_search_coexist(qapp):
    """跟读高亮与搜索高亮并存互不覆盖。"""
    view = ReaderView()
    view.show_chapter("第一章", "风起云涌。风起云涌。")
    view.highlight_sentence("风起云涌。")
    view.search("风起")  # 2 个搜索匹配
    # 搜索 2 个 + 句子 1 个 = 3 个 extra selections
    assert len(view.extraSelections()) == 3
    # 清搜索：句子高亮保留
    view.clear_search()
    assert view._sentence_sel is not None
    assert len(view.extraSelections()) == 1
    # 清句子高亮：全部清空
    view.clear_sentence_highlight()
    assert view.extraSelections() == []


def test_reader_view_sentence_cleared_on_show_chapter(qapp):
    """换章后跟读高亮失效（正文已变更）。"""
    view = ReaderView()
    view.show_chapter("第一章", "甲乙甲")
    view.highlight_sentence("甲乙甲")
    assert view._sentence_sel is not None
    view.show_chapter("第二章", "丙丁")
    assert view._sentence_sel is None
    assert view.extraSelections() == []


from ui.chapter_dialog import ChapterDialog


def test_chapter_dialog_populates_and_preselects(qapp):
    """对话框填充全部章节，且预选当前章节。"""
    dialog = ChapterDialog(["第一章", "第二章", "第三章"], current=1)
    assert dialog._list.count() == 3
    assert dialog._list.currentRow() == 1


def test_chapter_dialog_clamps_current(qapp):
    """越界的 current 索引被夹取到合法范围。"""
    dialog = ChapterDialog(["第一章", "第二章"], current=99)
    assert dialog._list.currentRow() == 1


def test_chapter_dialog_filter(qapp):
    """搜索过滤：只保留标题匹配的章节行。"""
    dialog = ChapterDialog(["第一章 风起", "第二章 云涌", "第三章 雷动"])
    dialog._search.setText("云涌")
    visible = [i for i in range(dialog._list.count())
               if not dialog._list.item(i).isHidden()]
    assert visible == [1]


def test_chapter_dialog_accept_current(qapp):
    """确认当前行：selected_index 记录所选章节并 accept。"""
    from PySide6.QtWidgets import QDialog
    dialog = ChapterDialog(["a", "b", "c"], current=2)
    dialog._accept_current()
    assert dialog.selected_index == 2
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_chapter_dialog_accept_item(qapp):
    """双击条目：按点击行返回所选章节。"""
    from PySide6.QtWidgets import QDialog
    dialog = ChapterDialog(["a", "b", "c"])
    dialog._accept_item(dialog._list.item(1))
    assert dialog.selected_index == 1
    assert dialog.result() == QDialog.DialogCode.Accepted


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
    assert win._player_bar is not None
    assert win._current_chapter == -1
    # 单栏布局：正文阅读器直接是中央区域的子控件（不再有章节分栏）
    assert win._reader.parent() is win.centralWidget()


def test_main_window_search_open_close(qapp):
    """Ctrl+F 打开搜索工具条，Esc 关闭并清除高亮。"""
    win = MainWindow()
    assert win._search_bar.isHidden()
    win._open_search()
    assert not win._search_bar.isHidden()
    win._close_search()
    assert win._search_bar.isHidden()


def test_main_window_search_wires_to_reader(qapp):
    """输入搜索词 → 阅读器高亮 → 计数显示。"""
    win = MainWindow()
    win._chapters = [{"title": "第一章", "content": "风起云涌。风起云涌。"}]
    win._show_chapter(0)
    win._on_search_text("风起")
    assert win._reader.match_count() == 2
    assert win._reader.current_match() == 0
    assert win._search_bar._count.text() == "1/2"
    # 下一个 → 计数 2/2
    win._on_find_next()
    assert win._search_bar._count.text() == "2/2"
    # 上一个 → 回到 1/2
    win._on_find_prev()
    assert win._search_bar._count.text() == "1/2"
    # 清空搜索词 → 高亮与计数清除
    win._on_search_text("")
    assert win._reader.match_count() == 0
    assert win._search_bar._count.text() == "无匹配"


def test_main_window_search_persists_across_chapters(qapp):
    """换章后搜索词保留并重算（输入框有词时在新章重新高亮）。"""
    win = MainWindow()
    win._chapters = [
        {"title": "第一章", "content": "风起甲"},
        {"title": "第二章", "content": "风落乙"},
    ]
    win._show_chapter(0)
    win._search_bar._input.setText("风")  # 模拟用户输入 → textChanged 信号链
    assert win._reader.match_count() == 1
    # 换章：输入框仍保留搜索词 → 新章重算高亮
    win._show_chapter(1)
    assert win._reader.match_count() == 1
    assert win._reader.current_match() == 0


def test_main_window_sentence_highlight_wires(qapp):
    """引擎句子开始信号 → 正文跟读高亮。"""
    win = MainWindow()
    win._chapters = [{"title": "第一章", "content": "风起云涌。风起云涌。"}]
    win._show_chapter(0)
    win._engine._current_sentences = ["风起云涌。", "风起云涌。"]
    win._engine.sentence_started.emit(0)
    assert win._reader._sentence_sel is not None
    first_start = win._reader._sentence_sel.cursor.selectionStart()
    # 下一句：锚点推进，定位到第二处
    win._engine.sentence_started.emit(1)
    second_start = win._reader._sentence_sel.cursor.selectionStart()
    assert second_start > first_start


def test_main_window_sentence_highlight_skips_on_mismatch(qapp):
    """视图与听书章节不一致时（用户跳章），不误高亮当前视图。"""
    win = MainWindow()
    win._chapters = [
        {"title": "第一章", "content": "甲。"},
        {"title": "第二章", "content": "乙。"},
    ]
    win._show_chapter(0)
    win._engine._current_sentences = ["乙。"]
    win._engine._chapter_index = 1  # 引擎在播第二章，视图停在第一章
    win._engine.sentence_started.emit(0)
    assert win._reader._sentence_sel is None


def test_main_window_has_chapter_menu(qapp):
    """菜单栏包含『章节』菜单（章节选择收敛到菜单栏）。"""
    win = MainWindow()
    titles = [a.text() for a in win.menuBar().actions() if a.text()]
    assert "章节" in titles


def test_main_window_chapter_menu_jump(qapp, tmp_path, monkeypatch):
    """菜单『跳转到章节』→ 对话框选定章节 → 阅读器切换。"""
    from PySide6.QtWidgets import QFileDialog

    book = tmp_path / "novel.txt"
    book.write_text("第一章 风起\n内容甲。\n第二章 云涌\n内容乙。",
                    encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book), "txt")))
    win = MainWindow()
    win.open_file()

    # 对话框预选当前章节；模拟用户确认跳转到第二章
    dialog = ChapterDialog([c["title"] for c in win._chapters],
                           current=win._current_chapter)
    dialog._list.setCurrentRow(1)
    dialog._accept_current()
    assert dialog.selected_index == 1
    # 主窗口应用对话框选择
    win._show_chapter(dialog.selected_index)
    assert win._current_chapter == 1
    assert "内容乙" in win._reader.toHtml()


def test_main_window_open_file_flow(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    book = tmp_path / "novel.txt"
    book.write_text("第一章 风起\n内容甲。\n第二章 云涌\n内容乙。", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(book), "txt")))
    win = MainWindow()
    win.open_file()
    assert win._current_chapter == 0
    assert len(win._chapters) == 2
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
    assert win._current_chapter == 1


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
    # 模拟：听书在第五章（索引 4），界面被切到第二章（索引 1）→ 视图与音频错位
    win._engine._chapter_index = 4
    win._show_chapter(1)
    win._on_next()
    assert win._engine.current_chapter_index() == 5
    assert win._current_chapter == 5
    win._on_prev()
    assert win._engine.current_chapter_index() == 4
    assert win._current_chapter == 4
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
    win._show_chapter(0)
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
