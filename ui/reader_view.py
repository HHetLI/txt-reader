import html

from PySide6.QtGui import QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import QTextBrowser


class ReaderView(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self._font_size = 16
        self._line_spacing = 1.6
        self._apply_style()
        self.setPlaceholderText("打开一个 txt 小说文件开始阅读")

    def _apply_style(self) -> None:
        font = self.font()
        font.setPointSize(self._font_size)
        self.setFont(font)
        self.document().setDefaultStyleSheet(
            f"body {{ font-size: {self._font_size}pt; }}"
        )

    def show_chapter(self, title: str, content: str) -> None:
        body = html.escape(content).replace("\n", "<br>")
        self.setHtml(f"<h1>{html.escape(title)}</h1><br>{body}")
        self._apply_line_spacing()
        self.verticalScrollBar().setValue(0)

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
