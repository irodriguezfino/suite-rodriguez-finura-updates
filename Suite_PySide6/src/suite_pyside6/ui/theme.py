from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QGuiApplication


LIGHT = {
    "background": "#F7F9FC",
    "surface": "#FFFFFF",
    "surface_muted": "#F1F4F8",
    "surface_elevated": "#FFFFFF",
    "border": "#DDE4EE",
    "border_strong": "#B8C5D8",
    "text_primary": "#162033",
    "text_secondary": "#536174",
    "text_muted": "#8491A3",
    "primary": "#123283",
    "primary_hover": "#1B3891",
    "primary_active": "#0B266D",
    "primary_soft": "#EAF0FF",
    "accent_red": "#C32421",
    "accent_red_soft": "#FDEDEC",
    "accent_gold": "#7B6A42",
    "accent_gold_soft": "#F4EFE2",
    "focus_ring": "#1B3891",
    "sidebar_bg": "#123283",
    "sidebar_border": "#0B266D",
    "drop_active_border": "#123283",
    "success": "#167A46",
    "success_soft": "#E8F7EF",
    "warning": "#8A6A22",
    "warning_soft": "#FFF7E3",
    "error": "#C32421",
    "error_soft": "#FDEDEC",
    "info": "#0F6E8C",
    "info_soft": "#E7F6FB",
    "shadow": "rgba(18, 50, 131, 0.10)",
    "bg": "#F7F9FC",
    "surface_2": "#F1F4F8",
    "surface_3": "#E8EDF5",
    "ink": "#162033",
    "muted": "#536174",
    "subtle": "#8491A3",
    "brand": "#C32421",
    "brand_soft": "#FDEDEC",
    "brand_dark": "#9A1917",
    "danger": "#C32421",
    "danger_soft": "#FDEDEC",
}

DARK = {
    "background": "#080704",
    "surface": "#11100B",
    "surface_muted": "#18150E",
    "surface_elevated": "#211C12",
    "border": "#332B1A",
    "border_strong": "#4A3E24",
    "text_primary": "#F8F5EC",
    "text_secondary": "#D8CFB8",
    "text_muted": "#A89D80",
    "primary": "#C8B46F",
    "primary_hover": "#D8C985",
    "primary_active": "#F2E3A4",
    "primary_soft": "#2E2614",
    "accent_red": "#FF7772",
    "accent_red_soft": "#3C1E25",
    "accent_gold": "#C8B46F",
    "accent_gold_soft": "#2E2614",
    "focus_ring": "#D8C985",
    "sidebar_bg": "#050504",
    "sidebar_border": "#4A3E24",
    "drop_active_border": "#D8C985",
    "success": "#6DD58C",
    "success_soft": "#162A18",
    "warning": "#E6B95C",
    "warning_soft": "#342816",
    "error": "#FF7772",
    "error_soft": "#3C1E25",
    "info": "#C8B46F",
    "info_soft": "#2E2614",
    "shadow": "rgba(0, 0, 0, 0.26)",
    "bg": "#080704",
    "surface_2": "#18150E",
    "surface_3": "#211C12",
    "ink": "#F8F5EC",
    "muted": "#D8CFB8",
    "subtle": "#A89D80",
    "brand": "#FF7772",
    "brand_soft": "#3C1E25",
    "brand_dark": "#FFB0AD",
    "danger": "#FF7772",
    "danger_soft": "#3C1E25",
}


def current_theme_preference() -> str:
    value = QSettings("RodriguezFinura", "SuitePySide6").value("theme", "system")
    return str(value) if value in {"light", "dark", "system"} else "system"


def set_theme_mode(mode: str) -> None:
    QSettings("RodriguezFinura", "SuitePySide6").setValue("theme", mode if mode in {"light", "dark", "system"} else "system")


def current_theme_mode() -> str:
    preference = current_theme_preference()
    if preference != "system":
        return preference
    app = QGuiApplication.instance()
    if app is not None and hasattr(app.styleHints(), "colorScheme"):
        return "dark" if app.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light"
    return "light"


def is_dark_mode() -> bool:
    return current_theme_mode() == "dark"


def palette() -> dict[str, str]:
    return DARK if is_dark_mode() else LIGHT


def base_qss() -> str:
    p = palette()
    tooltip_bg = p["surface_elevated"] if is_dark_mode() else p["text_primary"]
    tooltip_fg = p["text_primary"] if is_dark_mode() else p["surface"]
    table_alt = p["surface_2"] if is_dark_mode() else "#FBFCFE"
    selection_fg = p["surface"] if not is_dark_mode() else "#080704"
    primary_fg = "#080704" if is_dark_mode() else "white"
    nav_active_fg = "#080704" if is_dark_mode() else "white"
    sidebar_bg = p.get("sidebar_bg", p["primary"])
    sidebar_border = p.get("sidebar_border", p["primary_active"])
    drop_active_border = p.get("drop_active_border", p["primary"])
    return f"""
    * {{
        outline: 0;
    }}
    QWidget {{
        background: {p["bg"]};
        color: {p["ink"]};
        font-family: Inter, Segoe UI, Arial, sans-serif;
        font-size: 10pt;
    }}
    QMainWindow, QWidget#SuiteShell, QWidget#MainWorkspace, QWidget#DashboardPage, QWidget#ConsolePage {{
        background: {p["bg"]};
    }}
    QLabel {{
        background: transparent;
    }}
    QToolTip {{
        background: {tooltip_bg};
        color: {tooltip_fg};
        border: 0;
        border-radius: 6px;
        padding: 7px 9px;
    }}

    QLabel#WindowTitle, QLabel#ShellTitle {{
        color: {p["ink"]};
        font-size: 18pt;
        font-weight: 700;
    }}
    QLabel#WindowSubtitle, QLabel#ShellSubtitle, QLabel#PanelSubtitle, QLabel#MutedText {{
        color: {p["muted"]};
        font-size: 10pt;
    }}
    QLabel#SectionLabel, QLabel#PanelTitle, QLabel#DashboardPanelTitle {{
        color: {p["ink"]};
        font-size: 11pt;
        font-weight: 650;
    }}
    QLabel#Overline, QLabel#GroupLabel {{
        color: {p["subtle"]};
        font-size: 8.5pt;
        font-weight: 700;
        text-transform: uppercase;
    }}

    QFrame#ConsoleSidebar {{
        background: {sidebar_bg};
        border-right: 1px solid {sidebar_border};
    }}
    QFrame#ConsoleHeader {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#CompactContextBar {{
        background: {p["surface_2"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#ConsoleRail, QFrame#ContextRail {{
        background: {p["surface"]};
        border-left: 1px solid {p["border"]};
    }}
    QFrame#Panel, QFrame#DsPanel, QFrame#DsMetric, QFrame#AppCard, QFrame#FormPanel, QFrame#MailPanel,
    QFrame#ControlPreviewPanel, QFrame#ControlIssuesPanel, QFrame#OutputPanel,
    QFrame#ControlStatusRail, QFrame#Dropzone, QFrame#WorkItem, QFrame#MetricCard, QFrame#ContextCard,
    QFrame#ModuleRow, QFrame#ContinuePanel, QFrame#HeroPanel, QFrame#ActivityPanel,
    QFrame#ModulesPanel {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#ModuleRow:hover, QFrame#WorkItem:hover, QFrame#ContextCard:hover,
    QFrame#DsMetric:hover, QFrame#Dropzone:hover {{
        border-color: {p["border_strong"]};
        background: {p["surface"]};
    }}
    QFrame#Dropzone {{
        border: 1px dashed {p["border_strong"]};
        background: {p["surface_2"]};
    }}
    QFrame#Dropzone[active="true"] {{
        border-color: {drop_active_border};
        background: {p["primary_soft"]};
    }}
    QFrame#Toolbar {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#Stepper {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#Stepper[plainStepper="true"] {{
        background: transparent;
        border: 0;
        border-radius: 0;
    }}
    QFrame#Toolbar[embeddedSurface="true"], QFrame#Stepper[embeddedSurface="true"] {{
        background: transparent;
        border: 0;
        border-radius: 0;
    }}
    QFrame#ControlPilotWorkspace[embeddedSurface="true"] {{
        background: transparent;
        border: 0;
    }}
    QFrame#ControlPreviewPanel[embeddedSurface="true"] {{
        border-color: {p["border_strong"]};
    }}
    QFrame#ControlIssuesPanel[embeddedSurface="true"],
    QFrame#ControlStatusRail[embeddedSurface="true"],
    QFrame#AppCard[embeddedSurface="true"],
    QFrame#FormPanel[embeddedSurface="true"],
    QFrame#MailPanel[embeddedSurface="true"] {{
        background: {p["surface"]};
        border-color: {p["border"]};
    }}
    QFrame#ControlContentStack {{
        background: transparent;
        border: 0;
    }}
    QFrame#ControlMetricStrip {{
        background: {p["surface_2"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#CollapsiblePanel {{
        background: transparent;
        border: 0;
    }}
    QFrame#RecipientEditor {{
        background: {p["surface_2"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        padding: 8px;
    }}
    QFrame#RecipientEditor QLineEdit {{
        min-height: 34px;
    }}
    QFrame#MailActions {{
        border-top: 1px solid {p["border"]};
        padding-top: 8px;
    }}
    QToolButton#CollapsibleHeader {{
        min-height: 34px;
        padding: 0 8px;
        border: 1px solid {p["border"]};
        border-radius: 6px;
        background: {p["surface_2"]};
        color: {p["ink"]};
        font-weight: 700;
    }}
    QToolButton#CollapsibleHeader:hover {{
        border-color: {p["border_strong"]};
        background: {p["surface_3"]};
    }}
    QFrame#ControlProductHero {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QFrame#ControlHeroStatus {{
        background: {p["surface_2"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        min-width: 150px;
    }}
    QFrame#Toolbar[controlCommand="true"] {{
        background: {p["surface"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 8px;
    }}
    QFrame#ControlCommandCopy {{
        background: transparent;
        border: 0;
        min-width: 190px;
    }}

    QPushButton {{
        min-height: 36px;
        padding: 0 12px;
        border-radius: 6px;
        border: 1px solid {p["border"]};
        background: {p["surface"]};
        color: {p["ink"]};
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {p["surface_2"]};
        border-color: {p["border_strong"]};
    }}
    QPushButton:focus {{
        border-width: 2px;
        border-color: {p["focus_ring"]};
        background: {p["primary_soft"]};
        padding: 0 11px;
    }}
    QPushButton:pressed {{
        background: {p["surface_3"]};
        border-color: {p["border_strong"]};
    }}
    QPushButton:disabled {{
        color: {p["subtle"]};
        background: {p["surface_2"]};
        border-color: {p["border"]};
    }}
    QPushButton[primary="true"], QPushButton#PrimaryButton, QPushButton#ShellNextAction {{
        background: {p["primary"]};
        border-color: {p["primary"]};
        color: {primary_fg};
    }}
    QPushButton[primary="true"]:focus, QPushButton#PrimaryButton:focus, QPushButton#ShellNextAction:focus {{
        background: {p["primary_hover"]};
        border-color: {p["primary_hover"]};
        color: {primary_fg};
    }}
    QPushButton[primary="true"]:hover, QPushButton#PrimaryButton:hover, QPushButton#ShellNextAction:hover {{
        background: {p["primary_hover"]};
        border-color: {p["primary_hover"]};
    }}
    QPushButton[primary="true"]:pressed, QPushButton#PrimaryButton:pressed, QPushButton#ShellNextAction:pressed,
    QPushButton[busy="true"] {{
        background: {p["primary_active"]};
        border-color: {p["primary_active"]};
        color: {primary_fg};
    }}
    QPushButton[role="danger"] {{
        color: {p["danger"]};
        background: {p["danger_soft"]};
        border-color: {p["danger_soft"]};
    }}
    QPushButton[nav="true"], QPushButton#NavItem {{
        text-align: left;
        border: 1px solid transparent;
        background: transparent;
        color: rgba(255, 255, 255, 0.78);
        min-height: 38px;
        padding: 0 10px;
    }}
    QPushButton[nav="true"]:hover, QPushButton#NavItem:hover {{
        color: white;
        background: rgba(255, 255, 255, 0.12);
    }}
    QPushButton[nav="true"]:checked, QPushButton#NavItem:checked {{
        color: {nav_active_fg};
        background: {p["primary_hover"]};
        border-color: rgba(255, 255, 255, 0.18);
        font-weight: 700;
    }}
    QPushButton#IconButton, QPushButton#MenuButton, QPushButton#HelpButton, QPushButton#ProfileButton {{
        min-width: 34px;
        max-width: 34px;
        padding: 0;
    }}
    QPushButton[nextAction="true"] {{
        border-color: {p["primary"]};
        font-weight: 750;
    }}

    QLineEdit, QComboBox {{
        min-height: 36px;
        padding: 0 10px;
        border: 1px solid {p["border"]};
        border-radius: 6px;
        background: {p["surface"]};
        color: {p["ink"]};
        selection-background-color: {p["primary"]};
        selection-color: {selection_fg};
    }}
    QLineEdit:hover, QComboBox:hover {{
        border-color: {p["border_strong"]};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-width: 2px;
        border-color: {p["focus_ring"]};
        background: {p["surface"]};
        padding: 0 9px;
    }}
    QLineEdit:disabled, QComboBox:disabled {{
        color: {p["subtle"]};
        background: {p["surface_2"]};
    }}
    QComboBox[modernSelect="true"] {{
        min-height: 38px;
        padding: 0 38px 0 12px;
        border-radius: 8px;
        background: {p["surface_elevated"]};
        font-weight: 600;
    }}
    QComboBox[modernSelect="true"][popupOpen="true"] {{
        border: 2px solid {p["focus_ring"]};
        padding: 0 37px 0 11px;
        background: {p["primary_soft"]};
    }}
    QComboBox[modernSelect="true"][error="true"] {{
        border: 2px solid {p["error"]};
        padding: 0 37px 0 11px;
    }}
    QComboBox[modernSelect="true"]::drop-down {{
        width: 32px;
        border: 0;
        border-left: 1px solid {p["border"]};
        border-top-right-radius: 8px;
        border-bottom-right-radius: 8px;
        background: {p["surface_2"]};
    }}
    QComboBox[modernSelect="true"]:hover::drop-down {{
        background: {p["primary_soft"]};
    }}
    QComboBox[modernSelect="true"]::down-arrow {{
        image: none;
        width: 12px;
        height: 10px;
    }}
    QComboBox[modernSelect="true"] QLineEdit {{
        border: 0;
        background: transparent;
        padding: 0;
        min-height: 0;
        font-weight: 600;
    }}
    QComboBox QAbstractItemView {{
        background: {p["surface_elevated"]};
        color: {p["ink"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 8px;
        padding: 5px;
        outline: 0;
        selection-background-color: {p["primary_soft"]};
        selection-color: {p["ink"]};
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 34px;
        padding: 3px 10px;
        border-radius: 5px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {p["primary_soft"]};
        color: {p["ink"]};
    }}
    QComboBox QAbstractItemView::item:selected {{
        background: {p["primary_soft"]};
        color: {p["ink"]};
        font-weight: 700;
        border-left: 3px solid {p["primary"]};
    }}
    QComboBox QAbstractItemView::item:disabled {{
        color: {p["subtle"]};
    }}
    QToolButton#ActionMenuButton {{
        min-height: 38px;
        padding: 0 10px;
        border: 1px solid {p["border"]};
        border-radius: 8px;
        background: {p["surface_elevated"]};
        color: {p["ink"]};
        font-weight: 600;
    }}
    QToolButton#ActionMenuButton:hover {{
        border-color: {p["border_strong"]};
        background: {p["primary_soft"]};
    }}
    QToolButton#ActionMenuButton:focus {{
        border: 2px solid {p["focus_ring"]};
        padding: 0 9px;
    }}
    QToolButton#ActionMenuButton::menu-indicator {{
        image: none;
        width: 0;
    }}
    QMenu {{
        background: {p["surface_elevated"]};
        color: {p["ink"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        min-height: 30px;
        padding: 4px 28px 4px 12px;
        border-radius: 5px;
    }}
    QMenu::item:selected {{
        background: {p["primary_soft"]};
        color: {p["ink"]};
    }}
    QMenu::separator {{
        height: 1px;
        margin: 5px 8px;
        background: {p["border"]};
    }}
    QWidget#FieldGroup {{
        background: transparent;
    }}
    QLabel#FieldLabel {{
        color: {p["muted"]};
        font-size: 9pt;
        font-weight: 600;
    }}

    QPlainTextEdit, QTextEdit {{
        border: 1px solid {p["border"]};
        border-radius: 8px;
        background: {p["surface"]};
        color: {p["ink"]};
        padding: 10px;
        font-family: Consolas, JetBrains Mono, monospace;
        font-size: 9.5pt;
        selection-background-color: {p["primary"]};
        selection-color: {selection_fg};
    }}
    QPlainTextEdit[emptyState="true"] {{
        color: {p["subtle"]};
        background: {p["surface_2"]};
    }}
    QPlainTextEdit:focus, QTextEdit:focus {{
        border-width: 2px;
        border-color: {p["focus_ring"]};
    }}

    QTableWidget {{
        gridline-color: transparent;
        alternate-background-color: {table_alt};
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        selection-background-color: {p["primary_soft"]};
        selection-color: {p["ink"]};
    }}
    QTableWidget:focus {{
        border-width: 2px;
        border-color: {p["focus_ring"]};
    }}
    QTableWidget::item {{
        min-height: 34px;
        padding: 6px 8px;
        border-bottom: 1px solid {p["border"]};
    }}
    QTableWidget::item:hover {{
        background: {p["surface_2"]};
    }}
    QTableWidget::item:selected {{
        background: {p["primary_soft"]};
        color: {p["ink"]};
    }}
    QHeaderView::section {{
        background: {p["surface_2"]};
        color: {p["muted"]};
        border: 0;
        border-right: 1px solid {p["border"]};
        border-bottom: 1px solid {p["border"]};
        padding: 8px;
        font-weight: 700;
    }}

    QLabel#DsBadge, QLabel#Badge, QLabel#CategoryTag, QLabel#MigrationTag,
    QLabel#ControlCountPill, QLabel#ControlIssuePill, QLabel#ModuleShortcut {{
        border-radius: 999px;
        padding: 3px 8px;
        background: {p["surface_3"]};
        color: {p["muted"]};
        font-size: 8.5pt;
        font-weight: 700;
    }}
    QLabel#DsBadge[tone="success"], QLabel#MigrationTag {{
        color: {p["success"]};
        background: {p["success_soft"]};
    }}
    QLabel#DsBadge[tone="warning"], QLabel#ControlIssuePill {{
        color: {p["warning"]};
        background: {p["warning_soft"]};
    }}
    QLabel#DsBadge[tone="danger"] {{
        color: {p["danger"]};
        background: {p["danger_soft"]};
    }}
    QLabel#DsBadge[tone="info"] {{
        color: {p["info"]};
        background: {p["info_soft"]};
    }}
    QLabel#DsBadge[tone="premium"], QLabel#BrandSeal, QLabel#ModuleShortcut {{
        color: {p["accent_gold"]};
        background: {p["accent_gold_soft"]};
    }}

    QLabel#InlineBanner {{
        border-radius: 8px;
        padding: 10px 12px;
        border: 1px solid {p["border"]};
        background: {p["info_soft"]};
        color: {p["info"]};
        font-weight: 600;
    }}
    QLabel#InlineBanner[severity="success"] {{
        background: {p["success_soft"]};
        color: {p["success"]};
        border-color: {p["success"]};
    }}
    QLabel#InlineBanner[severity="warning"] {{
        background: {p["warning_soft"]};
        color: {p["warning"]};
        border-color: {p["warning"]};
    }}
    QLabel#InlineBanner[severity="error"] {{
        background: {p["danger_soft"]};
        color: {p["danger"]};
        border-color: {p["danger"]};
    }}

    QLabel#StatusLabel, QLabel#ResultLabel {{
        color: {p["muted"]};
        background: transparent;
        font-weight: 600;
    }}
    QLabel#MetricValue, QLabel#DsMetricValue {{
        color: {p["ink"]};
        font-size: 18pt;
        font-weight: 750;
    }}
    QLabel#MetricLabel, QLabel#DsMetricLabel, QLabel#DsMetricDetail {{
        color: {p["muted"]};
        font-weight: 600;
    }}
    QLabel#CompactContextValue {{
        color: {p["muted"]};
        font-size: 9pt;
        font-weight: 650;
    }}
    QLabel#ModuleTitle, QLabel#AppTitle {{
        color: {p["ink"]};
        font-size: 11pt;
        font-weight: 700;
    }}
    QLabel#ModuleDescription, QLabel#AppDescription, QLabel#DashboardEmpty {{
        color: {p["muted"]};
    }}
    QLabel#ModuleIcon, QLabel#AppIcon {{
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        border-radius: 8px;
        background: {p["primary_soft"]};
        color: {p["primary"]};
        font-weight: 800;
    }}
    QLabel#SidebarBrandTitle {{
        color: white;
        font-size: 13pt;
        font-weight: 800;
    }}
    QLabel#SidebarBrandSubtitle {{
        color: rgba(255, 255, 255, 0.78);
        font-weight: 650;
    }}
    QFrame#ConsoleSidebar QLabel#Overline,
    QFrame#ConsoleSidebar QLabel#ModuleDescription {{
        color: rgba(255, 255, 255, 0.72);
    }}
    QLabel#SidebarBrandLogo {{
        background: transparent;
    }}
    QLabel#BrandCaption {{
        color: {p["accent_gold"]};
        font-size: 9pt;
        font-weight: 750;
    }}
    QFrame#AppBrandBar {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
    }}
    QLabel#StepText {{
        color: {p["muted"]};
        font-size: 9pt;
        font-weight: 650;
    }}
    QLabel#StepConnector {{
        color: {p["subtle"]};
    }}
    QLabel#StepBadge {{
        min-width: 24px;
        min-height: 24px;
        max-width: 24px;
        max-height: 24px;
        border-radius: 12px;
        background: {p["surface_3"]};
        color: {p["muted"]};
        font-weight: 800;
    }}
    QLabel#StepBadge[stepState="active"] {{
        background: {p["primary"]};
        color: white;
    }}
    QLabel#StepBadge[stepState="complete"] {{
        background: {p["success_soft"]};
        color: {p["success"]};
    }}
    QLabel#StepBadge[stepState="warning"] {{
        background: {p["warning_soft"]};
        color: {p["warning"]};
    }}
    QLabel#ControlMetricValue {{
        color: {p["ink"]};
        font-size: 15pt;
        font-weight: 750;
    }}
    QLabel#ControlMetricLabel, QLabel#ControlRailDetail, QLabel#ControlRailAction {{
        color: {p["muted"]};
        font-weight: 600;
    }}
    QLabel#ControlCommandTitle {{
        color: {p["ink"]};
        font-size: 11pt;
        font-weight: 750;
    }}
    QLabel#ControlRailState {{
        color: {p["ink"]};
        font-size: 12pt;
        font-weight: 750;
    }}
    QLabel#ControlDropzone {{
        color: {p["muted"]};
        background: {p["surface_2"]};
        border: 1px dashed {p["border_strong"]};
        border-radius: 8px;
        padding: 14px;
    }}
    QProgressBar#ControlProgress {{
        min-height: 8px;
        max-height: 8px;
        border: 0;
        border-radius: 4px;
        background: {p["surface_3"]};
        text-align: center;
        color: transparent;
    }}
    QProgressBar#ControlProgress::chunk {{
        border-radius: 4px;
        background: {p["primary"]};
    }}

    QTabWidget#WorkTabs::pane {{
        border: 0;
        background: transparent;
    }}
    QTabBar::tab {{
        min-height: 34px;
        padding: 0 12px;
        color: {p["muted"]};
        background: transparent;
        border: 0;
        border-radius: 6px;
    }}
    QTabBar::tab:focus {{
        color: {p["ink"]};
        background: {p["primary_soft"]};
        border: 1px solid {p["primary"]};
    }}
    QTabBar::tab:selected {{
        color: {p["ink"]};
        background: {p["surface_2"]};
        font-weight: 700;
    }}

    QScrollArea {{
        border: 0;
        background: transparent;
    }}
    QScrollArea#InlineSectionScroll {{
        border: 1px solid {p["border"]};
        border-radius: 8px;
        background: {p["surface"]};
    }}
    QFrame#NavigationLoadingPage {{
        background: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 12px;
    }}
    QFrame#NavigationSkeleton {{
        background: {p["surface_2"]};
        border-radius: 6px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p["border"]};
        border-radius: 4px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p["border_strong"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QMessageBox, QDialog {{
        background: {p["surface"]};
    }}
    """
