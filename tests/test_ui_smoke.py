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
