from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.apps import APP_REGISTRY, AppDefinition, apps_for_category, categories
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.about_dialog import AboutDialog
from suite_pyside6.ui.control_recepcion_maquilas_window import ControlRecepcionMaquilasWindow
from suite_pyside6.ui.mermas_window import MermasWindow
from suite_pyside6.ui.palets_window import PaletsWindow
from suite_pyside6.ui.pesos_window import PesosWindow
from suite_pyside6.ui.precintos_expedicion_window import PrecintosExpedicionWindow
from suite_pyside6.ui.precintos_excel_window import PrecintosExcelWindow
from suite_pyside6.ui.precintos_jamones_window import PrecintosJamonesWindow
from suite_pyside6.ui.polish import brand_logo_pixmap, polish_window
from suite_pyside6.ui.responsive import apply_adaptive_layouts, make_flow, register_adaptive_layout
from suite_pyside6.ui.session import favorite_app_keys, is_favorite_app, recent_app_keys, remember_app_open, toggle_favorite_app
from suite_pyside6.ui.recepcion_maquilas_window import RecepcionMaquilasWindow
from suite_pyside6.ui.theme import base_qss, is_dark_mode
from suite_pyside6.ui.txt_csv_window import TxtCsvWindow


WINDOW_CLASSES: dict[str, type[QMainWindow]] = {
    "exportar_precintos_excel": PrecintosExcelWindow,
    "txt_csv": TxtCsvWindow,
    "palets": PaletsWindow,
    "mermas": MermasWindow,
    "precintos_expedicion": PrecintosExpedicionWindow,
    "precintos_jamones": PrecintosJamonesWindow,
    "recepcion_maquilas": RecepcionMaquilasWindow,
    "control_recepcion_maquilas": ControlRecepcionMaquilasWindow,
    "pesos": PesosWindow,
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_category = "Todas"
        self.search_text = ""
        self._last_columns = 0
        self.category_buttons: dict[str, QPushButton] = {}
        self.open_windows: dict[str, QMainWindow] = {}
        self.setWindowTitle("Suite Rodriguez Finura")
        self.resize(1180, 760)
        self.setMinimumSize(720, 560)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_actions()
        self._build_ui()
        polish_window(self)
        self._render_apps()

    def _build_actions(self) -> None:
        for index, app in enumerate(APP_REGISTRY, start=1):
            action = QAction(self)
            action.setShortcut(f"Alt+{index}")
            action.triggered.connect(lambda _checked=False, item=app: self.open_app(item))
            self.addAction(action)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("Header")
        self.header_layout = QBoxLayout(QBoxLayout.LeftToRight, header)
        header_layout = self.header_layout
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(10)

        brand_panel = QFrame()
        brand_panel.setObjectName("BrandPanel")
        brand_layout = QHBoxLayout(brand_panel)
        brand_layout.setContentsMargins(8, 6, 8, 6)
        brand_layout.setSpacing(10)
        for logo_name, width in (("RODRIGUEZ.png", 170), ("FINURA.png", 108)):
            logo_path = resource_path(logo_name)
            if logo_path.exists():
                logo = QLabel()
                logo.setAccessibleName(logo_name.replace(".png", ""))
                pixmap = brand_logo_pixmap(logo_path)
                if not pixmap.isNull():
                    logo.setObjectName("BrandLogo")
                    logo.setPixmap(pixmap.scaledToWidth(width, Qt.SmoothTransformation))
                logo.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                brand_layout.addWidget(logo, 0)
        header_layout.addWidget(brand_panel, 0)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("Panel operativo Rodriguez Finura")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Procesos de jamones, CSV, PDA y maquilas en un entorno de trabajo unico")
        subtitle.setObjectName("WindowSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box, 1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar proceso, archivo o area")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar proceso")
        self.search.setToolTip("Filtra los procesos por nombre, area o descripcion.")
        self.search.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self.search, 0)

        about_button = QPushButton("Acerca de")
        about_button.setObjectName("AboutButton")
        about_button.setToolTip("Ver version instalada y buscar actualizaciones.")
        about_button.clicked.connect(self.show_about)
        header_layout.addWidget(about_button, 0)

        root_layout.addWidget(header)
        self._add_shadow(header, blur=22, y=4, alpha=28)

        metrics = make_flow(spacing=10)
        metrics.setSpacing(10)
        ported = sum(1 for app in APP_REGISTRY if app.migration_status == "ported")
        metrics.addWidget(self._metric_card(str(ported), "Procesos listos", "blue"))
        metrics.addWidget(self._metric_card(str(len(categories()) - 1), "Areas", "red"))
        metrics.addWidget(self._metric_card(str(len(APP_REGISTRY)), "Atajos activos", "green"))
        root_layout.addLayout(metrics)

        self.body_layout = QBoxLayout(QBoxLayout.LeftToRight)
        body = self.body_layout
        body.setSpacing(14)

        self.sidebar = QFrame()
        sidebar = self.sidebar
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(214)
        sidebar.setMaximumWidth(260)
        sidebar_layout = make_flow(sidebar, margin=0, spacing=8)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)

        side_title = QLabel("Areas de trabajo")
        side_title.setObjectName("SectionLabel")
        sidebar_layout.addWidget(side_title)

        for category in self._nav_items():
            count = len(self._apps_for_view(category))
            button = QPushButton(f"{category}  ({count})")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=category: self._select_category(name))
            self.category_buttons[category] = button
            sidebar_layout.addWidget(button)
        body.addWidget(sidebar)
        self._add_shadow(sidebar, blur=16, y=2, alpha=18)

        content_shell = QFrame()
        content_shell.setObjectName("ContentShell")
        content_layout = QVBoxLayout(content_shell)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        self.result_label = QLabel()
        self.result_label.setObjectName("ResultLabel")
        content_layout.addWidget(self.result_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.app_container = QWidget()
        self.app_grid = QGridLayout(self.app_container)
        self.app_grid.setContentsMargins(0, 0, 0, 0)
        self.app_grid.setHorizontalSpacing(12)
        self.app_grid.setVerticalSpacing(12)
        self.scroll.setWidget(self.app_container)
        content_layout.addWidget(self.scroll, 1)

        body.addWidget(content_shell, 1)
        root_layout.addLayout(body, 1)

        self.status = QLabel("Suite operativa. Selecciona un proceso o usa el buscador para empezar.")
        self.status.setObjectName("StatusLabel")
        root_layout.addWidget(self.status)

        self.setCentralWidget(root)
        register_adaptive_layout(self, self.header_layout, breakpoint_width=840)
        register_adaptive_layout(self, self.body_layout, breakpoint_width=900)
        self._apply_responsive_state()

    @staticmethod
    def _add_shadow(widget: QWidget, *, blur: int = 18, y: int = 3, alpha: int = 22) -> None:
        if alpha <= 0:
            widget.setGraphicsEffect(None)
            return
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(max(blur, 18))
        shadow.setOffset(0, max(1, y))
        shadow.setColor(QColor(0, 0, 0, 24 if is_dark_mode() else min(alpha, 8)))
        widget.setGraphicsEffect(shadow)

    def _metric_card(self, value: str, label: str, accent: str) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setProperty("accent", accent)
        self._add_shadow(card, blur=14, y=2, alpha=14)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(0)
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return card

    def _select_category(self, category: str) -> None:
        self.current_category = category
        self._render_apps()

    def _on_search_changed(self, text: str) -> None:
        self.search_text = " ".join(text.lower().split())
        self._render_apps()

    def _filtered_apps(self) -> list[AppDefinition]:
        apps = self._apps_for_view(self.current_category)
        if not self.search_text:
            return apps
        result = []
        for app in apps:
            haystack = " ".join(
                [app.title, app.description, app.short_description, app.category]
            ).lower()
            if self.search_text in haystack:
                result.append(app)
        return result

    def _nav_items(self) -> tuple[str, ...]:
        base = tuple(category for category in categories() if category != "Todas")
        return ("Todas", "Favoritos", "Recientes", *base)

    def _apps_for_view(self, view: str) -> list[AppDefinition]:
        if view == "Favoritos":
            favorites = favorite_app_keys()
            return [app for app in APP_REGISTRY if app.key in favorites]
        if view == "Recientes":
            recent = recent_app_keys()
            return [app for key in recent for app in APP_REGISTRY if app.key == key]
        return list(apps_for_category(view))

    def _render_apps(self) -> None:
        for button_category, button in self.category_buttons.items():
            button.setText(f"{button_category}  ({len(self._apps_for_view(button_category))})")
            button.setChecked(button_category == self.current_category)

        while self.app_grid.count():
            item = self.app_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        apps = self._filtered_apps()
        if self.search_text:
            self.result_label.setText(f"{len(apps)} procesos encontrados en {self.current_category}")
        else:
            self.result_label.setText(f"{len(apps)} procesos disponibles en {self.current_category}")
        if not apps:
            empty = QLabel("Sin resultados. Ajusta la busqueda o cambia de area.")
            empty.setObjectName("EmptyLabel")
            empty.setAlignment(Qt.AlignCenter)
            self.app_grid.addWidget(empty, 0, 0)
            return

        columns = self._column_count()
        self._last_columns = columns
        for index, app in enumerate(apps):
            card = AppCard(app, self)
            self.app_grid.addWidget(card, index // columns, index % columns)
        for col in range(columns):
            self.app_grid.setColumnStretch(col, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        apply_adaptive_layouts(self)
        self._apply_responsive_state()
        if self._column_count() != self._last_columns:
            self._render_apps()

    def _column_count(self) -> int:
        if self.width() < 920:
            return 1
        if self.width() < 1280:
            return 2
        return 3

    def _apply_responsive_state(self) -> None:
        compact = self.width() < 900
        self.sidebar.setMaximumWidth(16777215 if compact else 260)
        self.sidebar.setMinimumWidth(0 if compact else 214)
        self.search.setMinimumWidth(0)

    def open_app(self, app: AppDefinition) -> None:
        remember_app_open(app.key)
        window_class = WINDOW_CLASSES.get(app.key)
        if window_class is not None:
            self._show_app_window(app, window_class)
            return

        self.status.setText("Proceso no disponible en el panel.")
        QMessageBox.warning(self, "No disponible", f"{app.title} no tiene una ventana asignada en el panel.")

    def show_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_app_window(self, app: AppDefinition, window_class: type[QMainWindow]) -> None:
        window = self.open_windows.get(app.key)
        if window is None:
            window = window_class()
            window.destroyed.connect(lambda _obj=None, key=app.key: self.open_windows.pop(key, None))
            self.open_windows[app.key] = window
        window.show()
        window.raise_()
        window.activateWindow()
        self.status.setText(f"Abriendo {app.title} desde el panel")

    def toggle_favorite(self, app: AppDefinition) -> None:
        enabled = toggle_favorite_app(app.key)
        self.status.setText(f"{app.title} {'anadido a' if enabled else 'retirado de'} favoritos.")
        self._render_apps()


class AppCard(QFrame):
    def __init__(self, app: AppDefinition, window: MainWindow) -> None:
        super().__init__()
        self.app = app
        self.window = window
        self.setObjectName("AppCard")
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setAccessibleName(app.title)
        self.setToolTip(app.description)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)
        icon = QLabel(self._initials(app.title))
        icon.setObjectName("AppIcon")
        icon.setAlignment(Qt.AlignCenter)
        top.addWidget(icon, 0, Qt.AlignTop)
        title = QLabel(app.title)
        title.setObjectName("AppTitle")
        title.setWordWrap(True)
        top.addWidget(title, 1, Qt.AlignTop)
        favorite_button = QPushButton("Favorito" if is_favorite_app(app.key) else "Marcar")
        favorite_button.setCheckable(True)
        favorite_button.setChecked(is_favorite_app(app.key))
        favorite_button.setProperty("role", "favorite")
        favorite_button.setAccessibleName(f"Alternar favorito {app.title}")
        favorite_button.setToolTip("Anade o retira este proceso de Favoritos.")
        favorite_button.clicked.connect(lambda _checked=False: window.toggle_favorite(app))
        top.addWidget(favorite_button, 0, Qt.AlignTop)
        layout.addLayout(top)

        description = QLabel(app.short_description)
        description.setObjectName("AppDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        tag = QLabel(app.category)
        tag.setObjectName("CategoryTag")
        meta.addWidget(tag)
        status = QLabel(self._status_text(app))
        status.setObjectName("MigrationTag")
        meta.addWidget(status)
        meta.addStretch(1)
        shortcut = QLabel(app.shortcut)
        shortcut.setObjectName("AppMeta")
        meta.addWidget(shortcut)
        layout.addLayout(meta)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        bottom.addStretch(1)
        open_button = QPushButton("Abrir proceso")
        open_button.setProperty("role", "open")
        open_button.setAccessibleName(f"Abrir {app.title}")
        open_button.setToolTip(f"Abrir {app.title} ({app.shortcut})")
        open_button.clicked.connect(lambda _checked=False: window.open_app(app))
        bottom.addWidget(open_button)
        layout.addLayout(bottom)

    @staticmethod
    def _status_text(app: AppDefinition) -> str:
        if app.migration_status == "core-started":
            return "En preparacion"
        if app.migration_status == "ui-started":
            return "Interfaz lista"
        if app.migration_status == "ported":
            return "Disponible"
        return "Pendiente"

    @staticmethod
    def _initials(title: str) -> str:
        words = [word for word in title.split() if word]
        if not words:
            return "SR"
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][0] + words[1][0]).upper()


def run() -> int:
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
