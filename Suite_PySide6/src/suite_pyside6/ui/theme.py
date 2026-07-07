from __future__ import annotations

from PySide6.QtCore import QSettings


BRAND_BLUE = "#064493"
BRAND_RED = "#d71920"
BRAND_RED_DARK = "#a91117"
SUCCESS = "#0f7a3b"
WARNING = "#9a5b00"


LIGHT = {
    "blue_dark": "#082a5a",
    "blue_soft": "#eef5ff",
    "ink": "#111827",
    "surface": "#ffffff",
    "background": "#f4f7fb",
    "muted": "#5f6f85",
    "border": "#d3ddea",
    "panel": "#f7f9fc",
    "field": "#fcfdff",
    "header": "#edf2f8",
    "tooltip": "#111827",
    "shadow": "#0b264d",
}

DARK = {
    "blue_dark": "#c7dcf8",
    "blue_soft": "#17304f",
    "ink": "#edf2f7",
    "surface": "#1e232b",
    "background": "#121418",
    "muted": "#a7b0bf",
    "border": "#38414d",
    "panel": "#171b21",
    "field": "#10141a",
    "header": "#252b34",
    "tooltip": "#f7fbff",
    "shadow": "#000000",
}


def current_theme_mode() -> str:
    value = QSettings("RodriguezFinura", "SuitePySide6").value("theme", "light")
    return "dark" if value == "dark" else "light"


def set_theme_mode(mode: str) -> None:
    QSettings("RodriguezFinura", "SuitePySide6").setValue("theme", "dark" if mode == "dark" else "light")


def is_dark_mode() -> bool:
    return current_theme_mode() == "dark"


def base_qss() -> str:
    palette = DARK if is_dark_mode() else LIGHT
    BRAND_BLUE_DARK = palette["blue_dark"]
    BRAND_BLUE_SOFT = palette["blue_soft"]
    INK = palette["ink"]
    SURFACE = palette["surface"]
    BACKGROUND = palette["background"]
    MUTED = palette["muted"]
    BORDER = palette["border"]
    PANEL = palette["panel"]
    FIELD = palette["field"]
    HEADER = palette["header"]
    TOOLTIP = palette["tooltip"]
    TOOLTIP_TEXT = "#ffffff" if not is_dark_mode() else "#0b111c"
    FOCUS = "#7fb7f2" if is_dark_mode() else "#1f6feb"
    CARD_HOVER = "#252b33" if is_dark_mode() else "#fcfdff"
    BUTTON_BG = "#242a33" if is_dark_mode() else "#ffffff"
    BUTTON_HOVER = "#2d3540" if is_dark_mode() else "#f5f9ff"
    PRIMARY_HOVER = "#0a5bb5" if is_dark_mode() else BRAND_BLUE_DARK
    CHECKED_TEXT = "#d8e9ff" if is_dark_mode() else BRAND_BLUE
    TABLE_ALT = "#151a21" if is_dark_mode() else "#f7f9fc"
    DANGER_BG = "#351f23" if is_dark_mode() else "#fff8f8"
    DANGER_HOVER = "#42242a" if is_dark_mode() else "#fff0f1"
    DISABLED_BG = "#202935" if is_dark_mode() else "#edf1f6"
    DISABLED_TEXT = "#8b96a6" if is_dark_mode() else "#94a0b2"
    SOFT_BORDER = "#465569" if is_dark_mode() else "#dbe4ef"
    CHIP_BG = "#1d3049" if is_dark_mode() else "#f1f6ff"
    SUCCESS_BG = "#173421" if is_dark_mode() else "#f2fbf6"
    SUCCESS_BORDER = "#3f7d57" if is_dark_mode() else "#c9e7d3"
    WARNING_BG = "#3a2f1a" if is_dark_mode() else "#fff8e7"
    WARNING_BORDER = "#8d6d26" if is_dark_mode() else "#ead49a"
    SUCCESS_FG = "#8ee3b0" if is_dark_mode() else SUCCESS
    WARNING_FG = "#f4cf72" if is_dark_mode() else WARNING
    SUCCESS_BADGE_TEXT = "#111827" if is_dark_mode() else "#ffffff"
    WARNING_BADGE_TEXT = "#111827" if is_dark_mode() else "#ffffff"
    ERROR_BG = "#3f2024" if is_dark_mode() else "#fff0f1"
    ERROR_BORDER = "#9a4850" if is_dark_mode() else "#efb8bd"
    SCROLL_BG = "#161d27" if is_dark_mode() else "#edf2f8"
    SCROLL_HANDLE = "#657384" if is_dark_mode() else "#9fb0c9"
    return f"""
    QWidget {{
        background: {BACKGROUND};
        color: {INK};
        font-family: Segoe UI, Arial, sans-serif;
        font-size: 9.5pt;
    }}
    QMainWindow {{
        background: {BACKGROUND};
    }}
    QFrame#ContentShell {{
        background: transparent;
    }}
    QWidget#SuiteShell {{
        background: {BACKGROUND};
    }}
    QWidget#MainWorkspace {{
        background: {BACKGROUND};
    }}
    QFrame#NavRail {{
        background: {SURFACE};
        border-right: 1px solid {BORDER};
    }}
    QFrame#NavBrand {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QLabel#NavTitle {{
        color: {BRAND_BLUE_DARK};
        background: transparent;
        font-size: 12pt;
        font-weight: 800;
    }}
    QLabel#NavSubtitle, QLabel#NavFooter {{
        color: {MUTED};
        background: transparent;
        font-weight: 650;
    }}
    QLabel#NavFooter {{
        border-top: 1px solid {BORDER};
        padding-top: 10px;
    }}
    QFrame#Sidebar {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px;
    }}
    QFrame#Header {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-top: 4px solid {BRAND_BLUE};
        border-bottom: 2px solid {BRAND_RED};
        border-radius: 8px;
        padding: 12px;
    }}
    QFrame#BrandPanel {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
    QFrame#ProductStrip {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
    QFrame#FieldStrip {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
    QLabel#WindowTitle {{
        font-size: 19pt;
        font-weight: 750;
        color: {BRAND_BLUE_DARK};
        background: transparent;
        padding-top: 2px;
    }}
    QLabel#WindowSubtitle, QLabel#StatusLabel, QLabel#AppDescription, QLabel#ShortcutLabel {{
        color: {MUTED};
    }}
    QLabel#WindowSubtitle {{
        background: transparent;
        font-size: 10pt;
        padding-bottom: 2px;
    }}
    QLabel#SectionLabel, QLabel#ResultLabel {{
        font-weight: 700;
        letter-spacing: 0;
    }}
    QLabel#SectionLabel, QLabel#AppTitle, QLabel#AppDescription, QLabel#MetricLabel, QLabel#MetricValue {{
        background: transparent;
    }}
    QLabel#ResultLabel {{
        background: {SURFACE};
        border: 1px solid {SOFT_BORDER};
        border-left: 4px solid {BRAND_BLUE};
        border-radius: 7px;
        padding: 9px 11px;
        color: {INK};
    }}
    QLabel#StepBar {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-left: 4px solid {BRAND_BLUE};
        border-radius: 6px;
        padding: 9px 12px;
        color: {BRAND_BLUE_DARK};
        font-weight: 650;
    }}
    QLabel#MetricValue {{
        font-size: 18pt;
        font-weight: 750;
        color: {BRAND_BLUE_DARK};
        background: transparent;
    }}
    QLabel#MetricLabel {{
        color: {MUTED};
        font-weight: 650;
        background: transparent;
    }}
    QLabel#AppIcon {{
        min-width: 40px;
        max-width: 40px;
        min-height: 40px;
        max-height: 40px;
        border-radius: 7px;
        background: {PANEL};
        border: 1px solid {BORDER};
        color: {BRAND_BLUE_DARK};
        font-size: 13pt;
        font-weight: 800;
    }}
    QLabel#StatusLabel {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-left: 4px solid {BRAND_BLUE};
        border-radius: 6px;
        padding: 8px 10px;
    }}
    QLineEdit, QComboBox {{
        min-width: 140px;
        min-height: 34px;
        background: {SURFACE};
        color: {INK};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 0 10px;
    }}
    QComboBox {{
        min-width: 104px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 2px solid {FOCUS};
        background: {FIELD};
    }}
    QPlainTextEdit, QTableWidget {{
        color: {INK};
        background: {FIELD};
        alternate-background-color: {TABLE_ALT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        selection-background-color: {BRAND_BLUE};
        selection-color: white;
        font-family: Consolas, Segoe UI, monospace;
        padding: 6px;
    }}
    QPlainTextEdit[emptyState="true"] {{
        background: {PANEL};
        border: 1px dashed {BORDER};
        color: {MUTED};
        font-weight: 600;
        padding: 10px;
    }}
    QPlainTextEdit:focus, QTableWidget:focus {{
        border: 2px solid {FOCUS};
    }}
    QTableWidget::item {{
        padding: 6px;
        border-bottom: 1px solid {BORDER};
    }}
    QTableWidget::item:selected {{
        background: {BRAND_BLUE};
        color: white;
    }}
    QHeaderView::section {{
        background: {HEADER};
        color: {BRAND_BLUE_DARK};
        border: 0;
        border-bottom: 1px solid {BORDER};
        padding: 8px;
        font-weight: 650;
    }}
    QScrollArea {{
        border: 0;
        background: transparent;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollArea#WindowScroll, QScrollArea#ToolbarScroll {{
        border: 0;
        background: transparent;
    }}
    QWidget#WindowScrollContent {{
        background: transparent;
    }}
    QScrollArea#ToolbarScroll QScrollBar:horizontal {{
        background: {SCROLL_BG};
        height: 9px;
        margin: 0;
        border-radius: 4px;
    }}
    QScrollArea#ToolbarScroll QScrollBar::handle:horizontal {{
        background: {SCROLL_HANDLE};
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollArea#ToolbarScroll QScrollBar::handle:horizontal:hover {{
        background: {BRAND_BLUE};
    }}
    QScrollArea#ToolbarScroll QScrollBar::add-line:horizontal,
    QScrollArea#ToolbarScroll QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QFrame#AppCard {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QFrame#AppCard:hover {{
        border-color: {BRAND_BLUE};
        background: {CARD_HOVER};
    }}
    QFrame#Toolbar {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 7px;
    }}
    QFrame#Toolbar QPushButton {{
        min-width: 58px;
        padding-left: 8px;
        padding-right: 8px;
    }}
    QFrame#Toolbar QLineEdit {{
        min-width: 118px;
    }}
    QLabel#GroupLabel {{
        color: {MUTED};
        background: transparent;
        font-size: 8.6pt;
        font-weight: 750;
        padding: 0 4px;
    }}
    QLineEdit#CompactField, QComboBox#CompactField {{
        min-width: 72px;
        max-width: 110px;
    }}
    QFrame#MailPanel, QFrame#FormPanel {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
    QFrame#CollapsiblePanel {{
        background: transparent;
        border: 0;
    }}
    QToolButton#CollapsibleHeader {{
        background: {PANEL};
        color: {BRAND_BLUE_DARK};
        border: 1px solid {BORDER};
        border-radius: 7px;
        min-height: 32px;
        padding: 6px 10px;
        font-weight: 750;
    }}
    QToolButton#CollapsibleHeader:hover {{
        background: {BUTTON_HOVER};
        border-color: {BRAND_BLUE};
    }}
    QTabWidget#WorkTabs::pane {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        top: -1px;
    }}
    QTabWidget#WorkTabs QTabBar::tab {{
        background: {PANEL};
        color: {INK};
        border: 1px solid {BORDER};
        border-bottom-color: {BORDER};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 7px 12px;
        margin-right: 4px;
        font-weight: 650;
    }}
    QTabWidget#WorkTabs QTabBar::tab:selected {{
        background: {SURFACE};
        color: {BRAND_BLUE_DARK};
        border-bottom-color: {SURFACE};
    }}
    QTabWidget#WorkTabs QTabBar::tab:hover {{
        background: {BUTTON_HOVER};
        border-color: {BRAND_BLUE};
    }}
    QFrame#MetricCard {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 10px;
    }}
    QFrame#MetricCard[accent="red"] {{
        border-top: 3px solid {BRAND_RED};
    }}
    QFrame#MetricCard[accent="blue"] {{
        border-top: 3px solid {BRAND_BLUE};
    }}
    QFrame#MetricCard[accent="green"] {{
        border-top: 3px solid {SUCCESS};
    }}
    QLabel#AppTitle {{
        font-size: 12pt;
        font-weight: 750;
        color: {BRAND_BLUE_DARK};
        background: transparent;
    }}
    QLabel#CategoryTag {{
        background: {CHIP_BG};
        border: 1px solid {BORDER};
        border-radius: 5px;
        padding: 3px 7px;
        color: {BRAND_BLUE_DARK};
        font-weight: 650;
    }}
    QLabel#MigrationTag {{
        background: {SUCCESS_BG};
        border: 1px solid {SUCCESS_BORDER};
        border-radius: 5px;
        padding: 3px 7px;
        color: {SUCCESS_FG};
        font-weight: 650;
    }}
    QLabel#AppMeta {{
        color: {MUTED};
        background: transparent;
        font-size: 9pt;
        font-weight: 600;
    }}
    QLabel#EmptyLabel {{
        color: {MUTED};
        background: {SURFACE};
        border: 1px dashed {BORDER};
        border-radius: 8px;
        padding: 28px;
        font-size: 12pt;
        font-weight: 650;
    }}
    QFrame#AppBrandBar {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-top: 4px solid {BRAND_BLUE};
        border-bottom: 2px solid {BRAND_RED};
        border-radius: 8px;
        padding: 6px;
    }}
    QLabel#BrandCaption {{
        color: {BRAND_BLUE_DARK};
        background: transparent;
        font-size: 10.5pt;
        font-weight: 750;
    }}
    QLabel#BrandLogo {{
        background: transparent;
    }}
    QFrame#Stepper {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 8px;
    }}
    QLabel#StepBadge {{
        min-width: 24px;
        max-width: 24px;
        min-height: 24px;
        max-height: 24px;
        border-radius: 12px;
        background: {BORDER};
        color: white;
        font-weight: 800;
    }}
    QLabel#StepBadge[stepState="active"] {{
        background: {BRAND_BLUE};
        color: white;
    }}
    QLabel#StepBadge[stepState="complete"] {{
        background: {SUCCESS_FG};
        color: {SUCCESS_BADGE_TEXT};
    }}
    QLabel#StepBadge[stepState="warning"] {{
        background: {WARNING_FG};
        color: {WARNING_BADGE_TEXT};
    }}
    QLabel#StepBadge[stepState="pending"] {{
        background: {BORDER};
        color: {MUTED};
    }}
    QLabel#StepText {{
        color: {INK};
        background: transparent;
        font-weight: 650;
        padding-right: 2px;
    }}
    QLabel#StepConnector {{
        color: {MUTED};
        background: transparent;
        font-weight: 700;
        padding: 0 2px;
    }}
    QFrame#ContextPanel {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 6px;
    }}
    QFrame#ContextItem {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 7px;
        min-height: 34px;
        padding: 1px;
    }}
    QLabel#ContextLabel {{
        color: {MUTED};
        background: transparent;
        font-size: 8.8pt;
        font-weight: 700;
    }}
    QLabel#ContextStateValue, QLabel#ContextNextValue, QLabel#ContextAlertsValue {{
        color: {INK};
        background: transparent;
        font-weight: 750;
    }}
    QLabel#InlineBanner {{
        background: {CHIP_BG};
        border: 1px solid {BORDER};
        border-left: 5px solid {BRAND_BLUE};
        border-radius: 7px;
        color: {INK};
        padding: 8px 11px;
        font-weight: 650;
    }}
    QLabel#InlineBanner[severity="success"] {{
        background: {SUCCESS_BG};
        border-color: {SUCCESS_BORDER};
        border-left-color: {SUCCESS_FG};
    }}
    QLabel#InlineBanner[severity="warning"] {{
        background: {WARNING_BG};
        border-color: {WARNING_BORDER};
        border-left-color: {WARNING_FG};
    }}
    QLabel#InlineBanner[severity="error"] {{
        background: {ERROR_BG};
        border-color: {ERROR_BORDER};
        border-left-color: {BRAND_RED};
    }}
    QPushButton#ThemeToggle {{
        min-width: 72px;
    }}
    QPushButton {{
        color: {INK};
        background: {BUTTON_BG};
        border: 1px solid {BORDER};
        border-radius: 6px;
        min-height: 32px;
        padding: 6px 9px;
        font-weight: 600;
    }}
    QPushButton[nav="true"] {{
        min-height: 36px;
        padding: 7px 10px;
        text-align: left;
        background: transparent;
        border-color: transparent;
        color: {INK};
    }}
    QPushButton[nav="true"]:hover {{
        background: {BUTTON_HOVER};
        border-color: {BORDER};
    }}
    QPushButton[nav="true"]:checked {{
        background: {BRAND_BLUE_SOFT};
        border-color: {BRAND_BLUE};
        color: {CHECKED_TEXT};
        font-weight: 750;
    }}
    QPushButton:hover {{
        border-color: {BRAND_BLUE};
        background: {BUTTON_HOVER};
    }}
    QPushButton:focus {{
        border: 2px solid {FOCUS};
    }}
    QPushButton:checked {{
        background: {BRAND_BLUE_SOFT};
        border-color: {BRAND_BLUE};
        color: {CHECKED_TEXT};
        font-weight: 650;
    }}
    QPushButton[role="open"], QPushButton[role="process"], QPushButton[role="save"] {{
        color: {INK};
        border-color: {BORDER};
        background: {BUTTON_BG};
    }}
    QPushButton[role="open"]:hover, QPushButton[role="process"]:hover, QPushButton[role="save"]:hover {{
        border-color: {BRAND_BLUE};
        background: {BRAND_BLUE_SOFT};
    }}
    QPushButton[primary="true"] {{
        background: {BRAND_BLUE};
        color: white;
        border-color: {BRAND_BLUE};
        font-weight: 700;
    }}
    QPushButton[primary="true"]:hover {{
        background: {PRIMARY_HOVER};
        color: white;
        border-color: {PRIMARY_HOVER};
    }}
    QPushButton[nextAction="true"] {{
        border: 2px solid {FOCUS};
    }}
    QPushButton[primary="true"][nextAction="true"] {{
        background: {BRAND_BLUE};
        color: white;
        border: 2px solid {FOCUS};
    }}
    QPushButton[role="danger"] {{
        color: {BRAND_RED_DARK};
        border-color: {BORDER};
        background: {DANGER_BG};
    }}
    QPushButton[role="danger"]:hover {{
        background: {DANGER_HOVER};
        border-color: {BRAND_RED};
    }}
    QPushButton[role="favorite"] {{
        min-width: 58px;
        color: {BRAND_BLUE_DARK};
        background: {CHIP_BG};
        border-color: {BORDER};
    }}
    QPushButton[role="favorite"]:checked {{
        color: white;
        background: {BRAND_BLUE};
        border-color: {BRAND_BLUE};
    }}
    QPushButton:disabled {{
        background: {DISABLED_BG};
        color: {DISABLED_TEXT};
        border-color: {BORDER};
    }}
    QScrollBar:vertical {{
        background: {SCROLL_BG};
        width: 12px;
        margin: 0;
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: {SCROLL_HANDLE};
        min-height: 28px;
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {BRAND_BLUE};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QToolTip {{
        background: {TOOLTIP};
        color: {TOOLTIP_TEXT};
        border: 0;
        padding: 7px 9px;
        border-radius: 4px;
    }}
    QMessageBox QLabel {{
        background: transparent;
    }}
    """
