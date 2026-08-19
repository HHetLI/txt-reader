from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                               QWidget)

VOICES = [
    ("zh-CN-XiaoxiaoNeural", "晓晓（女）"),
    ("zh-CN-YunxiNeural", "云希（男）"),
    ("zh-CN-YunjianNeural", "云健（男）"),
    ("zh-CN-XiaoyiNeural", "晓伊（女）"),
    ("zh-CN-YunyangNeural", "云扬（男）"),
]
RATES = [f"{r:+d}%" for r in range(-10, 51, 10)]


class PlayerBar(QWidget):
    play_toggled = Signal()
    prev_requested = Signal()
    next_requested = Signal()
    stop_requested = Signal()
    voice_changed = Signal(str)
    rate_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        layout.addWidget(QLabel("声线:"))
        self._voice = QComboBox()
        for code, label in VOICES:
            self._voice.addItem(label, code)
        self._voice.currentIndexChanged.connect(self._on_voice_changed)
        layout.addWidget(self._voice)

        layout.addWidget(QLabel("语速:"))
        self._rate = QComboBox()
        self._rate.addItems(RATES)
        self._rate.setCurrentText("+0%")
        self._rate.currentTextChanged.connect(self.rate_changed)
        layout.addWidget(self._rate)

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setToolTip("上一章")
        self._prev_btn.clicked.connect(self.prev_requested)
        layout.addWidget(self._prev_btn)

        self._play_btn = QPushButton("▶")
        self._play_btn.setToolTip("播放/暂停")
        self._play_btn.clicked.connect(self.play_toggled)
        layout.addWidget(self._play_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setToolTip("下一章")
        self._next_btn.clicked.connect(self.next_requested)
        layout.addWidget(self._next_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setToolTip("停止")
        self._stop_btn.clicked.connect(self.stop_requested)
        layout.addWidget(self._stop_btn)

        self._status = QLabel("未打开书籍")
        layout.addWidget(self._status, 1)

    def _on_voice_changed(self) -> None:
        self.voice_changed.emit(self._voice.currentData())

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")

    def voice(self) -> str:
        return self._voice.currentData()

    def rate(self) -> str:
        return self._rate.currentText()
