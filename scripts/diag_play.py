"""诊断：用 QMediaPlayer 播放一个已合成的 mp3，监控状态与错误。"""
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

player = QMediaPlayer()
audio = QAudioOutput()
player.setAudioOutput(audio)
audio.setVolume(1.0)

player.errorOccurred.connect(
    lambda err, msg: print(f"[ERROR] {err} {msg}"))
player.mediaStatusChanged.connect(
    lambda s: print(f"[mediaStatus] {s}"))
player.playbackStateChanged.connect(
    lambda s: print(f"[playbackState] {s}"))
player.positionChanged.connect(
    lambda pos: pos % 1000 < 100 and print(f"[position] {pos}ms"))

mp3 = sys.argv[1] if len(sys.argv) > 1 else None
if not mp3:
    print("用法: python scripts/diag_play.py <mp3路径>")
    sys.exit(1)

print(f"播放: {mp3}")
player.setSource(QUrl.fromLocalFile(mp3))
player.play()

def stop():
    print("[diag] 5 秒到，退出")
    app.quit()

QTimer.singleShot(5000, stop)
app.exec()
