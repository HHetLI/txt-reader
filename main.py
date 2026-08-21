import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import apply_theme


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("小说阅读听书")
    apply_theme(app)  # 深色主题先于窗口应用
    window = MainWindow()
    window.show()
    # 后台预加载 IndexTTS 模型：加载 80-260s，启动即加载，播放时免等待
    window.preload_backend()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
