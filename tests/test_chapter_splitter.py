from core.chapter_splitter import split_chapters


def test_split_basic_chapters():
    text = "第一章 风起\n这是第一章内容。\n第二章 云涌\n这是第二章内容。"
    chapters = split_chapters(text)
    assert len(chapters) == 2
    assert chapters[0]["title"] == "第一章 风起"
    assert "第一章内容" in chapters[0]["content"]
    assert chapters[1]["title"] == "第二章 云涌"


def test_split_arabic_and_chinese_numerals():
    text = "第1章 相遇\n内容一\n第12章 离别\n内容二\n第二百五十章 重逢\n内容三"
    chapters = split_chapters(text)
    assert [c["title"] for c in chapters] == ["第1章 相遇", "第12章 离别", "第二百五十章 重逢"]


def test_split_english_chapter():
    text = "Chapter 1\nHello world.\nChapter 2\nBye world."
    chapters = split_chapters(text)
    assert [c["title"] for c in chapters] == ["Chapter 1", "Chapter 2"]


def test_split_special_titles():
    text = "楔子\n这是一个楔子。\n第一章 开始\n正文内容。\n番外 小花絮\n额外内容。"
    chapters = split_chapters(text)
    assert len(chapters) == 3
    assert chapters[0]["title"] == "楔子"
    assert "正文内容" in chapters[1]["content"]
    assert chapters[-1]["title"] == "番外 小花絮"


def test_no_chapter_headers_returns_single_chapter():
    text = "从前有座山，山里有座庙。\n庙里有个老和尚。"
    chapters = split_chapters(text)
    assert len(chapters) == 1
    assert chapters[0]["title"] == "全文"
    assert "老和尚" in chapters[0]["content"]


def test_title_with_colon_and_spaces():
    text = "第一章：相遇\n正文A\n第二章 重逢\n正文B"
    chapters = split_chapters(text)
    assert chapters[0]["title"] == "第一章：相遇"
    assert chapters[1]["title"] == "第二章 重逢"
