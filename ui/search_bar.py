from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QWidget)


class SearchBar(QWidget):
    """正文搜索工具条：输入即高亮，Enter/Shift+Enter 或 ↑/↓ 跳转，Esc 关闭。"""

    search_text = Signal(str)      # 输入变化 → 重新高亮（空串=清除）
    find_next_requested = Signal()
    find_prev_requested = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._input = QLineEdit()
        self._input.setObjectName("searchInput")
        self._input.setPlaceholderText("在正文中搜索…（Enter 下一个，Shift+Enter 上一个）")
        self._input.setClearButtonEnabled(True)
        self._input.textChanged.connect(self.search_text)
        self._input.returnPressed.connect(self.find_next_requested)
        layout.addWidget(self._input, 1)

        self._count = QLabel()
        self._count.setObjectName("searchCount")
        self._count.setMinimumWidth(48)
        layout.addWidget(self._count)

        self._prev_btn = QPushButton("↑")
        self._prev_btn.setObjectName("searchNav")
        self._prev_btn.setToolTip("上一个（Shift+Enter）")
        self._prev_btn.setFixedSize(26, 24)
        self._prev_btn.clicked.connect(self.find_prev_requested)
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("↓")
        self._next_btn.setObjectName("searchNav")
        self._next_btn.setToolTip("下一个（Enter）")
        self._next_btn.setFixedSize(26, 24)
        self._next_btn.clicked.connect(self.find_next_requested)
        layout.addWidget(self._next_btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("searchClose")
        self._close_btn.setToolTip("关闭（Esc）")
        self._close_btn.setFixedSize(26, 24)
        self._close_btn.clicked.connect(self.closed)
        layout.addWidget(self._close_btn)

    # ---------- 查询 / 状态 ----------

    def current_text(self) -> str:
        return self._input.text()

    def set_result(self, current: int, total: int) -> None:
        """显示匹配计数：如 3/12；无匹配显示『无匹配』。"""
        if total <= 0:
            self._count.setText("无匹配")
        else:
            self._count.setText(f"{current + 1}/{total}")

    def focus_input(self) -> None:
        self._input.setFocus()
        self._input.selectAll()
