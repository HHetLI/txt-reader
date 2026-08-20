import html

from PySide6.QtGui import QColor, QTextBlockFormat, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextBrowser, QTextEdit

from ui.theme import ACCENT, BG_SELECT, SENTENCE_HL, TEXT_MAIN


class ReaderView(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self._font_size = 16
        self._line_spacing = 1.6
        self.setFrameShape(self.Shape.NoFrame)
        self.setViewportMargins(30, 18, 30, 18)  # 左右留白，紧凑不空旷
        self._apply_style()
        self.setPlaceholderText("打开一个 txt 小说文件开始阅读")

        # ---------- 搜索状态 ----------
        self._search_text = ""
        self._matches: list[tuple[int, int]] = []  # (起始位置, 长度)
        self._current_match = -1
        self._match_fmt = QTextCharFormat()
        self._match_fmt.setBackground(QColor(BG_SELECT))
        self._current_fmt = QTextCharFormat()
        self._current_fmt.setBackground(QColor(ACCENT))
        self._current_fmt.setForeground(QColor("#ffffff"))

        # ---------- 播放句子跟读高亮 ----------
        self._sentence_sel: QTextEdit.ExtraSelection | None = None
        self._sentence_anchor = -1  # 上次句子高亮结束位置，避免重复句子定位到开头
        self._sentence_fmt = QTextCharFormat()
        self._sentence_fmt.setBackground(QColor(SENTENCE_HL))

    def _apply_style(self) -> None:
        font = self.font()
        font.setPointSize(self._font_size)
        self.setFont(font)
        # 深色主题：正文文字浅色、标题带强调色
        self.document().setDefaultStyleSheet(
            f"body {{ font-size: {self._font_size}pt; color: #d5dae3; }}"
            f"h1 {{ color: #7fa3ff; font-size: {self._font_size + 4}pt; }}"
        )

    def show_chapter(self, title: str, content: str) -> None:
        body = html.escape(content).replace("\n", "<br>")
        self.setHtml(f"<h1>{html.escape(title)}</h1><br>{body}")
        self._apply_line_spacing()
        self.verticalScrollBar().setValue(0)
        # 正文已变更：旧搜索高亮/句子高亮失效
        self._search_text = ""
        self._matches = []
        self._current_match = -1
        self._sentence_sel = None
        self._sentence_anchor = -1
        self.setExtraSelections([])

    def _apply_line_spacing(self) -> None:
        block_fmt = QTextBlockFormat()
        block_fmt.setLineHeight(self._line_spacing * 100,
                                QTextBlockFormat.ProportionalHeight.value)
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.Document)
        cursor.mergeBlockFormat(block_fmt)

    def set_font_size(self, pt: int) -> None:
        self._font_size = pt
        self._apply_style()

    def set_line_spacing(self, ratio: float) -> None:
        self._line_spacing = ratio
        self._apply_line_spacing()

    def scroll_value(self) -> int:
        return self.verticalScrollBar().value()

    def restore_scroll(self, value: int) -> None:
        self.verticalScrollBar().setValue(value)

    # ---------- 正文搜索 ----------

    def search(self, text: str) -> int:
        """设置搜索词：高亮全部匹配并跳到第一个，返回匹配数。"""
        self._search_text = text
        self._collect_matches()
        if self._matches:
            self._goto_match(0)
        else:
            self._render_selections()
        return len(self._matches)

    def find_next(self, backward: bool = False) -> bool:
        """跳到下一个/上一个匹配（循环）。无匹配返回 False。"""
        if not self._matches:
            return False
        n = len(self._matches)
        if self._current_match < 0:
            self._goto_match(n - 1 if backward else 0)
        else:
            step = -1 if backward else 1
            self._goto_match((self._current_match + step) % n)
        return True

    def clear_search(self) -> None:
        """清除搜索词与全部搜索高亮（保留播放句子高亮）。"""
        self._search_text = ""
        self._matches = []
        self._current_match = -1
        self._render_selections()

    def match_count(self) -> int:
        return len(self._matches)

    def current_match(self) -> int:
        return self._current_match

    # ---------- 播放句子跟读高亮 ----------

    def highlight_sentence(self, text: str) -> bool:
        """高亮正在播放的句子。

        从上次句子位置向后查找（句子顺序播放，避免重复文本定位到开头）；
        找不到则从头查找（换章/回绕）。正文换行符 \n 在渲染文档中是
        U+2028，需归一化后再匹配。返回是否定位成功。
        """
        if not text:
            return False
        search = text.replace("\r", "\u2028").replace("\n", "\u2028")
        doc = self.document()
        cursor = QTextCursor(doc)
        if self._sentence_anchor > 0:
            cursor.setPosition(self._sentence_anchor)
        found = doc.find(search, cursor)
        if found.isNull() and self._sentence_anchor > 0:
            found = doc.find(search)  # 从头找（换章/循环播放）
        if found.isNull():
            return False
        sel = QTextEdit.ExtraSelection()
        sel.cursor = found
        sel.format = self._sentence_fmt
        self._sentence_sel = sel
        self._sentence_anchor = found.selectionEnd()
        self._render_selections()
        return True

    def clear_sentence_highlight(self) -> None:
        """清除播放句子高亮（停止/切书时）。"""
        self._sentence_sel = None
        self._sentence_anchor = -1
        self._render_selections()

    def _collect_matches(self) -> None:
        """从文档开头收集全部匹配位置（不区分大小写，不找重叠）。"""
        self._matches = []
        self._current_match = -1
        if not self._search_text:
            self.setExtraSelections([])
            return
        doc = self.document()
        cursor = QTextCursor(doc)
        while True:
            found = doc.find(self._search_text, cursor)
            if found.isNull():
                break
            start = found.selectionStart()
            length = found.selectionEnd() - start
            if length <= 0:  # 空匹配防死循环
                break
            self._matches.append((start, length))
            cursor = QTextCursor(doc)
            cursor.setPosition(start + length)
        self._render_selections()

    def _goto_match(self, index: int) -> None:
        if not self._matches:
            self._current_match = -1
            self._render_selections()
            return
        self._current_match = index % len(self._matches)
        start, length = self._matches[self._current_match]
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self._render_selections()

    def _render_selections(self) -> None:
        """合并渲染：搜索匹配高亮 + 播放句子跟读高亮。"""
        selections = []
        for i, (start, length) in enumerate(self._matches):
            cursor = QTextCursor(self.document())
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = self._current_fmt if i == self._current_match else self._match_fmt
            selections.append(sel)
        if self._sentence_sel is not None:
            selections.append(self._sentence_sel)
        self.setExtraSelections(selections)
