"""生成应用图标 resources/icon.png（书 + 播放三角，256x256）。

运行：uv run python scripts/generate_icon.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QLinearGradient,
                           QPainter, QPen, QPixmap, QPolygonF)

OUT = Path(__file__).resolve().parent.parent / "resources" / "icon.png"


def draw() -> None:
    size = 256
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 圆角渐变背景
    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QColor("#5f89ff"))
    grad.setColorAt(1.0, QColor("#2b4fbf"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, size, size), 52, 52)

    # 打开的书：左右两页
    p.setBrush(QBrush(QColor("#ffffff")))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(38, 62, 84, 126), 12, 12)   # 左页
    p.drawRoundedRect(QRectF(134, 62, 84, 126), 12, 12)  # 右页
    # 书脊
    p.setPen(QPen(QColor("#c8d2e2"), 5))
    p.drawLine(126, 68, 126, 182)

    # 播放三角（金色，跨在书脊上，寓意听书）
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor("#f0b93f")))
    p.drawPolygon(QPolygonF([
        QPointF(64, 108),
        QPointF(188, 108),
        QPointF(126, 172),
    ]))

    p.end()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pm.save(str(OUT), "PNG")
    print(f"已生成: {OUT}")


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    draw()
