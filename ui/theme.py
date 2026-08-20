"""深色护眼主题（暗色背景 + 柔和文字，适合长时间阅读/夜间）。"""

# ---- 配色 ----
BG_MAIN = "#1b1e26"        # 主窗口背景
BG_PANEL = "#22262f"        # 面板/列表背景
BG_READER = "#1e222b"       # 正文阅读区
BG_INPUT = "#262b35"        # 下拉框/输入控件
BG_HOVER = "#2c3240"        # 悬停
BG_SELECT = "#3d4a63"       # 选中
ACCENT = "#4f7cff"          # 强调色（播放/激活）
TEXT_MAIN = "#d5dae3"       # 主文字
TEXT_MUTED = "#8b93a3"      # 次要文字
BORDER = "#2e3440"          # 边框
MENU_BG = "#1e2129"         # 菜单栏背景
SENTENCE_HL = "#8a7a42"     # 播放句子跟读高亮（暗金）


def build_qss() -> str:
    """返回应用级深色主题样式表。"""
    return f"""
/* ===== 主窗口 ===== */
QMainWindow, QWidget#centralRoot {{
    background-color: {BG_MAIN};
    color: {TEXT_MAIN};
}}

/* ===== 菜单栏 ===== */
QMenuBar {{
    background-color: {MENU_BG};
    color: {TEXT_MAIN};
    border-bottom: 1px solid {BORDER};
    padding: 2px 4px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 3px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {BG_HOVER};
}}
QMenu {{
    background-color: {BG_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 4px 24px 4px 12px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {BG_SELECT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* ===== 章节选择对话框 ===== */
QDialog {{
    background-color: {BG_MAIN};
    color: {TEXT_MAIN};
}}
QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 12px;
    selection-background-color: {BG_SELECT};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QListWidget {{
    background-color: {BG_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 5px;
    outline: none;
    font-size: 12px;
}}
QListWidget::item {{
    padding: 3px 8px;
    border-radius: 3px;
    margin: 0 3px;
}}
QListWidget::item:hover {{
    background-color: {BG_HOVER};
}}
QListWidget::item:selected {{
    background-color: {BG_SELECT};
    color: #e8ecf5;
}}

/* ===== 按钮 ===== */
QPushButton {{
    background-color: {BG_INPUT};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: #3a4152;
}}
QPushButton:pressed {{
    background-color: {BG_SELECT};
}}
QPushButton:disabled {{
    color: {TEXT_MUTED};
    background-color: {BG_PANEL};
}}
QPushButton#playBtn {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #ffffff;
    font-size: 13px;
}}
QPushButton#playBtn:hover {{
    background-color: #5f89ff;
}}
/* ===== 正文搜索工具条 ===== */
QWidget#searchBar {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}
QLabel#searchCount {{
    color: {TEXT_MUTED};
    min-width: 48px;
}}
QPushButton#searchNav, QPushButton#searchClose {{
    padding: 2px;
    font-size: 12px;
}}

/* ===== 下拉框 ===== */
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 12px;
    min-height: 18px;
}}
QComboBox:hover {{
    border-color: #3a4152;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_MUTED};
    margin-right: 4px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER};
    selection-background-color: {BG_SELECT};
    outline: none;
}}

/* ===== 标签 ===== */
QLabel {{
    color: {TEXT_MAIN};
    font-size: 12px;
}}
QLabel#statusLabel {{
    color: {TEXT_MUTED};
}}

/* ===== 正文阅读区 ===== */
QTextBrowser {{
    background-color: {BG_READER};
    color: {TEXT_MAIN};
    border: none;
    font-size: 16px;
    selection-background-color: {BG_SELECT};
}}
QTextBrowser QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QTextBrowser QScrollBar::handle:vertical {{
    background: #333a47;
    border-radius: 4px;
    min-height: 24px;
}}
QTextBrowser QScrollBar::handle:vertical:hover {{
    background: #3d4657;
}}
QTextBrowser QScrollBar::add-line:vertical,
QTextBrowser QScrollBar::sub-line:vertical {{
    height: 0;
}}
QTextBrowser QScrollBar::add-page:vertical,
QTextBrowser QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ===== 通用滚动条 ===== */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #333a47;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3d4657;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""


def apply_theme(app) -> None:
    """将深色主题应用到整个应用。"""
    app.setStyleSheet(build_qss())
