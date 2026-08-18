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
