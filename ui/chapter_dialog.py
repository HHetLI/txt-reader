from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLineEdit,
                               QListWidget, QVBoxLayout)


class ChapterDialog(QDialog):
    """章节选择对话框：搜索过滤 + 列表定位，适合上千章的书籍。

    用法：dialog.exec() 后若 result() == Accepted，selected_index 为所选章节
    （-1 表示未选择）。
    """

    def __init__(self, titles: list[str], current: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择章节")
        self.setModal(True)
        self.resize(400, 560)
        self._titles = titles
        self.selected_index = -1

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self._search = QLineEdit()
        self._search.setObjectName("chapterSearch")
        self._search.setPlaceholderText("输入关键词过滤章节…")
        self._search.textChanged.connect(self._filter)
        self._search.returnPressed.connect(self._accept_current)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setObjectName("chapterList")
        self._list.setUniformItemSizes(True)
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list.itemDoubleClicked.connect(self._accept_item)
        layout.addWidget(self._list, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("跳转")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        buttons.accepted.connect(self._accept_current)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate(current)

    # ---------- 内部 ----------

    def _populate(self, current: int) -> None:
        self._list.addItems(self._titles)
        if self._titles:
            row = max(0, min(current, len(self._titles) - 1))
            self._list.setCurrentRow(row)
            self._list.scrollToItem(self._list.currentItem())
        self._search.setFocus()

    def _filter(self, text: str) -> None:
        """关键词过滤：隐藏不匹配行；当前行被隐藏时跳到首个可见行。"""
        keyword = text.strip().lower()
        first_visible = -1
        current = self._list.currentRow()
        current_visible = False
        for row in range(self._list.count()):
            item = self._list.item(row)
            match = not keyword or keyword in item.text().lower()
            item.setHidden(not match)
            if match:
                if first_visible < 0:
                    first_visible = row
                if row == current:
                    current_visible = True
        if not current_visible and first_visible >= 0:
            self._list.setCurrentRow(first_visible)

    def _accept_item(self, item) -> None:
        self.selected_index = self._list.row(item)
        self.accept()

    def _accept_current(self) -> None:
        if self._list.currentRow() >= 0:
            self.selected_index = self._list.currentRow()
            self.accept()
