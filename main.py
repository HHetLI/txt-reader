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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
