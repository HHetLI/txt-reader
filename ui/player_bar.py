from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                               QSlider, QWidget)

VOICES = [
    ("zh-CN-XiaoxiaoNeural", "晓晓（女）"),
    ("zh-CN-YunxiNeural", "云希（男）"),
    ("zh-CN-YunjianNeural", "云健（男）"),
    ("zh-CN-XiaoyiNeural", "晓伊（女）"),
    ("zh-CN-YunyangNeural", "云扬（男）"),
]
RATES = [f"{r:+d}%" for r in range(-10, 51, 10)]

# 引擎列表：(后端名, 显示文案)；设计默认 IndexTTS2.5 情感
ENGINES = [
    ("indextts", "IndexTTS2.5 情感"),
    ("edge", "edge-tts 快速"),
]
# 情感预设（IndexTTS 模式生效）：(键, 显示文本)；索引 0 为自动
# 键与 core/tts_backend.EMO_MODE_AUTO / EMO_VECTOR_PRESETS 一致
EMOTIONS = [
    ("auto", "自动"),
    ("平静", "平静"),
    ("悲伤", "悲伤"),
    ("激昂", "激昂"),
    ("温柔", "温柔"),
    ("恐惧", "恐惧"),
    ("高兴", "高兴"),
]
# 情感强度滑条范围：0-100，默认 60%（emotion_strength() 返回 0.0-1.0）
STRENGTH_MIN, STRENGTH_MAX, STRENGTH_DEFAULT = 0, 100, 60


class PlayerBar(QWidget):
    play_toggled = Signal()
    prev_requested = Signal()
    next_requested = Signal()
    stop_requested = Signal()
    voice_changed = Signal(str)
    rate_changed = Signal(str)
    backend_changed = Signal(str)          # 引擎切换（edge/indextts）
    emotion_changed = Signal(str, float)   # 情感模式 + 强度（0.0-1.0）

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)  # 紧凑：上下 2px
        layout.setSpacing(4)

        layout.addWidget(QLabel("引擎:"))
        self._engine_combo = QComboBox()
        self._engine_combo.setObjectName("engineCombo")
        for name, label in ENGINES:
            self._engine_combo.addItem(label, name)
        self._engine_combo.setFixedWidth(120)
        layout.addWidget(self._engine_combo)

        layout.addWidget(QLabel("声线:"))
        self._voice = QComboBox()
        for code, label in VOICES:
            self._voice.addItem(label, code)
        self._voice.setFixedWidth(110)
        self._voice.currentIndexChanged.connect(self._on_voice_changed)
        layout.addWidget(self._voice)

        layout.addWidget(QLabel("语速:"))
        self._rate = QComboBox()
        self._rate.addItems(RATES)
        self._rate.setCurrentText("+0%")
        self._rate.setFixedWidth(60)
        self._rate.currentTextChanged.connect(self.rate_changed)
        layout.addWidget(self._rate)

        layout.addWidget(QLabel("情感:"))
        self._emotion = QComboBox()
        self._emotion.setObjectName("emotionCombo")
        for key, label in EMOTIONS:
            self._emotion.addItem(label, key)
        self._emotion.setFixedWidth(80)
        self._emotion.currentTextChanged.connect(self._on_emotion_changed)
        layout.addWidget(self._emotion)

        layout.addWidget(QLabel("强度:"))
        self._strength = QSlider(Qt.Orientation.Horizontal)
        self._strength.setObjectName("strengthSlider")
        self._strength.setRange(STRENGTH_MIN, STRENGTH_MAX)
        self._strength.setValue(STRENGTH_DEFAULT)
        self._strength.setFixedWidth(90)
        self._strength.setToolTip("情感强度（IndexTTS 生效）")
        self._strength.valueChanged.connect(self._on_strength_changed)
        layout.addWidget(self._strength)

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setToolTip("上一章")
        self._prev_btn.setFixedSize(30, 24)
        self._prev_btn.clicked.connect(self.prev_requested)
        layout.addWidget(self._prev_btn)

        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("playBtn")
        self._play_btn.setToolTip("播放/暂停")
        self._play_btn.setFixedSize(36, 24)
        self._play_btn.clicked.connect(self.play_toggled)
        layout.addWidget(self._play_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setToolTip("下一章")
        self._next_btn.setFixedSize(30, 24)
        self._next_btn.clicked.connect(self.next_requested)
        layout.addWidget(self._next_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setToolTip("停止")
        self._stop_btn.setFixedSize(30, 24)
        self._stop_btn.clicked.connect(self.stop_requested)
        layout.addWidget(self._stop_btn)

        self._sentence_progress = QLabel("")
        self._sentence_progress.setObjectName("sentenceProgress")
        self._sentence_progress.setToolTip("播放进度（句）")
        layout.addWidget(self._sentence_progress)

        self._status = QLabel("未打开书籍")
        self._status.setObjectName("statusLabel")
        layout.addWidget(self._status, 1)

        # 连接放在控件初始化之后：避免构造期间的初始值触发误发射
        self._engine_combo.currentIndexChanged.connect(self._on_backend_changed)
        # 默认引擎为 IndexTTS：情感控件可见可用（edge 时隐藏禁用）
        self._apply_backend_visibility(self.backend())

    # ---------- 信号转发 ----------

    def _on_voice_changed(self) -> None:
        self.voice_changed.emit(self._voice.currentData())

    def _on_backend_changed(self) -> None:
        name = self.backend()
        self._apply_backend_visibility(name)
        self._repopulate_voice_combo(name)
        self.backend_changed.emit(name)

    def _apply_backend_visibility(self, name: str) -> None:
        """情感控件随引擎联动：IndexTTS 可见可用，edge 隐藏禁用。"""
        active = name == "indextts"
        for widget in (self._emotion, self._strength):
            widget.setVisible(active)
            widget.setEnabled(active)

    def _repopulate_voice_combo(self, name: str) -> None:
        """声线下拉自适应：edge 显示微软 5 声线；IndexTTS 显示同名参考音色。

        两种模式条目同名（晓晓/云希/...）且 data 均为声线码，切换引擎时
        保持选中项不变——引擎 set_voice 负责按后端把声线码映射到
        edge voice 或 IndexTTS 参考音频。
        """
        current = self._voice.currentData()
        self._voice.blockSignals(True)
        self._voice.clear()
        for code, label in VOICES:
            self._voice.addItem(label, code)
        if current is not None:
            idx = self._voice.findData(current)
            self._voice.setCurrentIndex(idx if idx >= 0 else 0)
        self._voice.blockSignals(False)
        # 通知引擎当前声线（引擎会按后端映射，IndexTTS 切参考音频）
        self.voice_changed.emit(self.voice())

    def _on_emotion_changed(self) -> None:
        self.emotion_changed.emit(self.emotion_mode(), self.emotion_strength())

    def _on_strength_changed(self) -> None:
        self.emotion_changed.emit(self.emotion_mode(), self.emotion_strength())

    # ---------- 查询 / 状态 ----------

    def backend(self) -> str:
        return self._engine_combo.currentData()

    def emotion_mode(self) -> str:
        return self._emotion.currentData()

    def emotion_strength(self) -> float:
        return self._strength.value() / 100.0

    def set_backend_status(self, text: str) -> None:
        self._status.setText(text)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_sentence_progress(self, current: int, total: int) -> None:
        """显示播放进度：如 3/45 句；total<=0 时清空。"""
        if total > 0 and current > 0:
            self._sentence_progress.setText(f"{current}/{total} 句")
        else:
            self._sentence_progress.setText("")

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")

    def voice(self) -> str:
        return self._voice.currentData()

    def rate(self) -> str:
        return self._rate.currentText()
