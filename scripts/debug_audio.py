"""调试：枚举音频输出设备与 Qt 默认设备。"""
import sys

from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
devs = QMediaDevices.audioOutputs()
print("=== 音频输出设备 ===")
for d in devs:
    dflt = "默认" if d.isDefault() else "    "
    print(f"  [{dflt}] {d.description()}")
d = QMediaDevices.defaultAudioOutput()
print("=== Qt 默认输出 ===", d.description())
