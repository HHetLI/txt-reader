"""阅读主题（深色 / 护眼绿 / 浅色），QSS 按主题参数化构建。"""

# ---- 主题配色定义 ----
# 每主题含：QSS 色板 + 正文/标题/高亮色（ReaderView 用）
THEMES: dict[str, dict] = {
    "deep": {
        "label": "深色",
        "bg_main": "#1b1e26",     # 主窗口背景
        "bg_panel": "#22262f",    # 面板/列表背景
        "bg_reader": "#1e222b",   # 正文阅读区
        "bg_input": "#262b35",    # 下拉框/输入控件
        "bg_hover": "#2c3240",    # 悬停
        "bg_select": "#3d4a63",   # 选中
        "accent": "#4f7cff",      # 强调色（播放/激活）
        "text_main": "#d5dae3",   # 主文字
        "text_muted": "#8b93a3",  # 次要文字
        "border": "#2e3440",      # 边框
        "menu_bg": "#1e2129",     # 菜单栏背景
        "sentence_hl": "#8a7a42",  # 播放句子跟读高亮（暗金）
        "reader_text": "#d5dae3",
        "reader_title": "#7fa3ff",
    },
    "green": {
        "label": "护眼绿",
        "bg_main": "#1c2620",
        "bg_panel": "#222e27",
        "bg_reader": "#1e2a22",
        "bg_input": "#27352c",
        "bg_hover": "#2d3d32",
        "bg_select": "#3d5a46",
        "accent": "#5fb78a",
        "text_main": "#c8d6c0",
        "text_muted": "#8aa08f",
        "border": "#2e3a32",
        "menu_bg": "#1f2a24",
        "sentence_hl": "#6e8a52",
        "reader_text": "#c8d6c0",
        "reader_title": "#7fd4a8",
    },
    "light": {
        "label": "浅色",
        "bg_main": "#f5f5f3",
        "bg_panel": "#ececea",
        "bg_reader": "#ffffff",
        "bg_input": "#e9e9e6",
        "bg_hover": "#e1e1dc",
        "bg_select": "#c9d6f0",
        "accent": "#3a6de0",
        "text_main": "#2a2f3a",
        "text_muted": "#8a8f99",
        "border": "#d8d8d3",
        "menu_bg": "#f0f0ee",
        "sentence_hl": "#d9c86a",
        "reader_text": "#2a2f3a",
        "reader_title": "#3a6de0",
    },
}

DEFAULT_THEME = "deep"


def theme_names() -> list[str]:
    return list(THEMES)


def theme_label(name: str) -> str:
    return THEMES.get(name, THEMES[DEFAULT_THEME])["label"]


def build_qss(theme: str = DEFAULT_THEME) -> str:
    """按主题构建应用级样式表。"""
    c = THEMES.get(theme, THEMES[DEFAULT_THEME])
    return f"""
/* ===== 主窗口 ===== */
QMainWindow, QWidget#centralRoot {{
    background-color: {c['bg_main']};
    color: {c['text_main']};
}}

/* ===== 菜单栏 ===== */
QMenuBar {{
    background-color: {c['menu_bg']};
    color: {c['text_main']};
    border-bottom: 1px solid {c['border']};
    padding: 2px 4px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 3px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {c['bg_hover']};
}}
QMenu {{
    background-color: {c['bg_panel']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    padding: 4px;
}}
QMenu::item {{
    padding: 4px 24px 4px 12px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {c['bg_select']};
}}
QMenu::item:disabled {{
    color: {c['text_muted']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 4px 8px;
}}

/* ===== 章节选择对话框 ===== */
QDialog {{
    background-color: {c['bg_main']};
    color: {c['text_main']};
}}
QLineEdit {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 12px;
    selection-background-color: {c['bg_select']};
}}
QLineEdit:focus {{
    border-color: {c['accent']};
}}
QListWidget {{
    background-color: {c['bg_panel']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
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
    background-color: {c['bg_hover']};
}}
QListWidget::item:selected {{
    background-color: {c['bg_select']};
}}

/* ===== 按钮 ===== */
QPushButton {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 3px 8px;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['border']};
}}
QPushButton:pressed {{
    background-color: {c['bg_select']};
}}
QPushButton:disabled {{
    color: {c['text_muted']};
    background-color: {c['bg_panel']};
}}
QPushButton#playBtn {{
    background-color: {c['accent']};
    border-color: {c['accent']};
    color: #ffffff;
    font-size: 13px;
}}
QPushButton#playBtn:hover {{
    background-color: {c['accent']};
}}

/* ===== 下拉框 ===== */
QComboBox {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 12px;
    min-height: 18px;
}}
QComboBox:hover {{
    border-color: {c['border']};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c['text_muted']};
    margin-right: 4px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_panel']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    selection-background-color: {c['bg_select']};
    outline: none;
}}

/* ===== 标签 ===== */
QLabel {{
    color: {c['text_main']};
    font-size: 12px;
}}
QLabel#statusLabel {{
    color: {c['text_muted']};
}}
QLabel#sentenceProgress {{
    color: {c['text_muted']};
    min-width: 56px;
}}

/* ===== 正文搜索工具条 ===== */
QWidget#searchBar {{
    background-color: {c['bg_panel']};
    border-bottom: 1px solid {c['border']};
}}
QLabel#searchCount {{
    color: {c['text_muted']};
    min-width: 48px;
}}
QPushButton#searchNav, QPushButton#searchClose {{
    padding: 2px;
    font-size: 12px;
}}

/* ===== 正文阅读区 ===== */
QTextBrowser {{
    background-color: {c['bg_reader']};
    color: {c['text_main']};
    border: none;
    font-size: 16px;
    selection-background-color: {c['bg_select']};
}}
QTextBrowser QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QTextBrowser QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 4px;
    min-height: 24px;
}}
QTextBrowser QScrollBar::handle:vertical:hover {{
    background: {c['bg_select']};
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
    background: {c['border']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['bg_select']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ===== 系统托盘菜单 ===== */
QMenu#trayMenu {{
    background-color: {c['bg_panel']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
}}
"""


def apply_theme(app, theme: str = DEFAULT_THEME) -> None:
    """将指定主题应用到整个应用。"""
    app.setStyleSheet(build_qss(theme))
