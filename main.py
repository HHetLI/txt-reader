import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.logging_setup import get_logger
from ui.main_window import MainWindow
from ui.theme import apply_theme

logger = get_logger("main")


def main() -> None:
    logger.info("==== 应用启动 ====")
    logger.info("CWD: %s", Path.cwd())
    logger.info("项目根: %s", Path(__file__).resolve().parent)
    logger.info("python: %s", sys.version.split()[0])
    logger.info("INDEXTTS_REF_AUDIO: %s", os.environ.get("INDEXTTS_REF_AUDIO"))
    app = QApplication(sys.argv)
    app.setApplicationName("小说阅读听书")
    apply_theme(app)  # 深色主题先于窗口应用
    window = MainWindow()
    window.show()
    # 后台预加载 IndexTTS 模型：加载 80-260s，启动即加载，播放时免等待
    ok = window.preload_backend()
    logger.info("preload_backend 返回: %s", ok)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
