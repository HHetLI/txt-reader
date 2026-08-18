from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QPushButton,
                               QVBoxLayout, QWidget)


class ChapterPanel(QWidget):
    chapter_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        top = QHBoxLayout()
        self._toggle_btn = QPushButton("📕")
        self._toggle_btn.setToolTip("折叠/展开章节列表")
        self._toggle_btn.setFixedWidth(32)
        self._toggle_btn.clicked.connect(self.toggle_visible)
        top.addWidget(self._toggle_btn)
        top.addStretch()
        layout.addLayout(top)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._emit_selected)
        layout.addWidget(self._list)

    def _emit_selected(self, row: int) -> None:
        if row >= 0:
            self.chapter_selected.emit(row)

    def set_chapters(self, titles: list[str]) -> None:
        self._list.clear()
        self._list.addItems(titles)

    def select_chapter(self, index: int) -> None:
        self._list.setCurrentRow(index)

    def current_index(self) -> int:
        return self._list.currentRow()

    def toggle_visible(self) -> None:
        self._visible = not self._visible
        self._list.setVisible(self._visible)
        self._toggle_btn.setText("📖" if not self._visible else "📕")
