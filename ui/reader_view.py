import html

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QTextBlockFormat, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextBrowser, QTextEdit

from ui.theme import DEFAULT_THEME, THEMES


class ReaderView(QTextBrowser):
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self._font_size = 16
        self._line_spacing = 1.6
        self.setFrameShape(self.Shape.NoFrame)
        self.setViewportMargins(30, 18, 30, 18)  # 左右留白，紧凑不空旷
        self._theme = DEFAULT_THEME
        self._text_color = THEMES[DEFAULT_THEME]["reader_text"]
        self._title_color = THEMES[DEFAULT_THEME]["reader_title"]
        self.setPlaceholderText("打开一个 txt 小说文件开始阅读")

        # 正文渲染映射：渲染文档与 content 字符 1:1（\n → 段落边界 U+2029）
        self._body_start = 0  # 正文首字符的文档位置
        self._body_len = 0    # 正文渲染长度（= len(content)）

        # ---------- 搜索状态 ----------
        self._search_text = ""
        self._matches: list[tuple[int, int]] = []  # (起始位置, 长度)
        self._current_match = -1
        self._match_fmt = QTextCharFormat()
        self._current_fmt = QTextCharFormat()
        self._current_fmt.setForeground(QColor("#ffffff"))

        # ---------- 播放句子跟读高亮 ----------
        self._sentence_sel: QTextEdit.ExtraSelection | None = None
        self._sentence_fmt = QTextCharFormat()

        self._apply_theme_colors()
        self._apply_style()
        self.anchorClicked.connect(self._on_anchor)

    def _apply_theme_colors(self) -> None:
        """按当前主题设置正文/标题/高亮配色。"""
        colors = THEMES.get(self._theme, THEMES[DEFAULT_THEME])
        self._text_color = colors["reader_text"]
        self._title_color = colors["reader_title"]
        self._match_fmt.setBackground(QColor(colors["bg_select"]))
        self._current_fmt.setBackground(QColor(colors["accent"]))
        self._sentence_fmt.setBackground(QColor(colors["sentence_hl"]))
        self._render_selections()

    def set_theme(self, theme_name: str) -> None:
        """阅读主题切换：更新正文/标题/高亮配色。"""
        self._theme = theme_name
        self._apply_theme_colors()
        self._apply_style()

    def _apply_style(self) -> None:
        font = self.font()
        font.setPointSize(self._font_size)
        self.setFont(font)
        # 主题配色：正文文字浅色、标题带强调色
        self.document().setDefaultStyleSheet(
            f"body {{ font-size: {self._font_size}pt; color: {self._text_color}; }}"
            f"h1 {{ color: {self._title_color}; font-size: {self._font_size + 4}pt; }}"
        )

    def show_chapter(self, title: str, content: str) -> None:
        # 每行一个 <p> 段落：\n → 段落边界，与 content 字符 1:1 映射
        paras = "".join(f"<p>{html.escape(line)}</p>" for line in content.split("\n"))
        self.setHtml(f"<h1>{html.escape(title)}</h1>{paras}")
        doc = self.document()
        block1 = doc.findBlockByNumber(1)
        self._body_start = (block1.position()
                            if block1.isValid() else doc.characterCount() - 1)
        self._body_len = len(content)
        self._apply_paragraph_style()
        self._append_nav()
        self.verticalScrollBar().setValue(0)
        # 正文已变更：旧搜索高亮/句子高亮失效
        self._search_text = ""
        self._matches = []
        self._current_match = -1
        self._sentence_sel = None
        self.setExtraSelections([])

    def _apply_paragraph_style(self) -> None:
        """中文排版：正文每段首行缩进 2 字符 + 段间距 + 行距（标题/章末导航不处理）。"""
        indent = float(self._font_size * 2)
        end_pos = self._body_start + self._body_len
        doc = self.document()
        cursor = QTextCursor(doc)
        block = doc.begin().next()  # 跳过标题 block
        while block.isValid() and block.position() < end_pos:
            fmt = QTextBlockFormat()
            fmt.setTextIndent(indent)
            fmt.setTopMargin(self._font_size * 0.4)
            fmt.setBottomMargin(self._font_size * 0.4)
            fmt.setLineHeight(self._line_spacing * 100,
                              QTextBlockFormat.ProportionalHeight.value)
            cursor.setPosition(block.position())
            cursor.setBlockFormat(fmt)
            block = block.next()

    def _append_nav(self) -> None:
        """章末导航：上一章 / 下一章（anchorClicked 处理）。"""
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(
            '<p style="text-align:center; margin-top:24px; color:#8b93a3;">'
            '<a href="prev">← 上一章</a>　|　'
            '<a href="next">下一章 →</a></p>')

    def _on_anchor(self, url) -> None:
        href = url.toString() if hasattr(url, "toString") else str(url)
        if href == "prev":
            self.prev_requested.emit()
        elif href == "next":
            self.next_requested.emit()

    def set_font_size(self, pt: int) -> None:
        self._font_size = pt
        self._apply_style()
        self._apply_paragraph_style()

    def set_line_spacing(self, ratio: float) -> None:
        self._line_spacing = ratio
        self._apply_paragraph_style()

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

    def highlight_sentence_range(self, start: int, end: int) -> bool:
        """高亮正文中 [start, end) 字符偏移对应的句子（相对 content）。"""
        if end <= start or start < 0:
            return False
        lo = self._body_start + start
        hi = self._body_start + end
        doc_len = self.document().characterCount()
        if lo < 0 or hi > doc_len:
            return False
        cursor = QTextCursor(self.document())
        cursor.setPosition(lo)
        cursor.setPosition(hi, QTextCursor.MoveMode.KeepAnchor)
        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        sel.format = self._sentence_fmt
        self._sentence_sel = sel
        self._render_selections()
        return True

    def clear_sentence_highlight(self) -> None:
        """清除播放句子高亮（停止/切书时）。"""
        self._sentence_sel = None
        self._render_selections()

    # ---------- 内部 ----------

    def _collect_matches(self) -> None:
        """从文档开头收集全部匹配位置（不区分大小写，不找重叠）。"""
        self._matches = []
        self._current_match = -1
        if not self._search_text:
            self._render_selections()
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
