from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6 import __version__
from suite_pyside6.core.apps import APP_REGISTRY, AppDefinition, apps_for_category, categories
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.about_dialog import AboutDialog
from suite_pyside6.ui.app_windows import WINDOW_CLASSES
from suite_pyside6.ui.polish import (
    brand_logo_pixmap,
    operational_snapshot,
    polish_window,
    prepare_embedded_window,
    trigger_next_action,
)
from suite_pyside6.ui.responsive import apply_adaptive_layouts, make_flow, register_adaptive_layout
from suite_pyside6.ui.session import (
    favorite_app_keys,
    is_favorite_app,
    recent_app_keys,
    recent_paths,
    remember_app_open,
    toggle_favorite_app,
)
from suite_pyside6.ui.theme import base_qss, is_dark_mode


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_category = "Todas"
        self.search_text = ""
        self._last_columns = 0
        self.category_buttons: dict[str, QPushButton] = {}
        self.open_windows: dict[str, QMainWindow] = {}
        self.app_pages: dict[str, QMainWindow] = {}
        self.metric_values: dict[str, QLabel] = {}
        self._closing = False
        self._current_app_key = ""
        self._nav_compact = False
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
        root.setObjectName("SuiteShell")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame()
        sidebar = self.sidebar
        sidebar.setObjectName("NavRail")
        sidebar.setMinimumWidth(244)
        sidebar.setMaximumWidth(286)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 16)
        sidebar_layout.setSpacing(12)

        self.brand_panel = QFrame()
        self.brand_panel.setObjectName("NavBrand")
        brand_layout = QVBoxLayout(self.brand_panel)
        brand_layout.setContentsMargins(12, 12, 12, 12)
        brand_layout.setSpacing(8)
        logo_row = QHBoxLayout()
        logo_row.setSpacing(8)
        for logo_name, width in (("RODRIGUEZ.png", 126), ("FINURA.png", 78)):
            logo_path = resource_path(logo_name)
            if logo_path.exists():
                logo = QLabel()
                logo.setAccessibleName(logo_name.replace(".png", ""))
                pixmap = brand_logo_pixmap(logo_path)
                if not pixmap.isNull():
                    logo.setObjectName("BrandLogo")
                    logo.setPixmap(pixmap.scaledToWidth(width, Qt.SmoothTransformation))
                logo.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                logo_row.addWidget(logo, 0)
        logo_row.addStretch(1)
        brand_layout.addLayout(logo_row)
        self.nav_title = QLabel("Suite Rodriguez Finura")
        self.nav_title.setObjectName("NavTitle")
        self.nav_subtitle = QLabel("Centro operativo")
        self.nav_subtitle.setObjectName("NavSubtitle")
        brand_layout.addWidget(self.nav_title)
        brand_layout.addWidget(self.nav_subtitle)
        sidebar_layout.addWidget(self.brand_panel)

        self.side_title = QLabel("Areas de trabajo")
        self.side_title.setObjectName("SectionLabel")
        sidebar_layout.addWidget(self.side_title)

        nav_flow = make_flow(spacing=8)
        for category in self._nav_items():
            count = len(self._apps_for_view(category))
            button = QPushButton(f"{category}  ({count})")
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=category: self._select_category(name))
            self.category_buttons[category] = button
            nav_flow.addWidget(button)
        sidebar_layout.addLayout(nav_flow)
        sidebar_layout.addStretch(1)

        self.footer = QLabel(f"Version {__version__}\nLista para operar")
        self.footer.setObjectName("NavFooter")
        self.footer.setWordWrap(True)
        sidebar_layout.addWidget(self.footer)
        root_layout.addWidget(sidebar)

        workspace = QWidget()
        workspace.setObjectName("MainWorkspace")
        root_layout.addWidget(workspace, 1)
        root_layout = QVBoxLayout(workspace)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("Header")
        self.header_layout = QBoxLayout(QBoxLayout.LeftToRight, header)
        header_layout = self.header_layout
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        self.workspace_title = QLabel("Centro de mando operativo")
        self.workspace_title.setObjectName("WindowTitle")
        self.workspace_subtitle = QLabel("Procesos de jamones, CSV, PDA y maquilas con acceso rapido y estado claro")
        self.workspace_subtitle.setObjectName("WindowSubtitle")
        title_box.addWidget(self.workspace_title)
        title_box.addWidget(self.workspace_subtitle)
        header_layout.addLayout(title_box, 1)

        self.process_context = QFrame()
        self.process_context.setObjectName("ShellContext")
        process_context_layout = QHBoxLayout(self.process_context)
        process_context_layout.setContentsMargins(8, 6, 8, 6)
        process_context_layout.setSpacing(8)
        self.process_state = self._shell_context_label("Estado", "Pendiente")
        self.process_next = self._shell_context_label("Siguiente", "Completa el paso actual")
        self.process_alerts = self._shell_context_label("Avisos", "Sin avisos")
        process_context_layout.addWidget(self.process_state, 1)
        process_context_layout.addWidget(self.process_next, 1)
        process_context_layout.addWidget(self.process_alerts, 0)
        self.next_action_button = QPushButton("Ejecutar")
        self.next_action_button.setProperty("primary", True)
        self.next_action_button.setToolTip("Ejecuta la siguiente accion disponible del proceso abierto.")
        self.next_action_button.clicked.connect(self._trigger_current_next_action)
        process_context_layout.addWidget(self.next_action_button, 0)
        header_layout.addWidget(self.process_context, 1)

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

        self.home_button = QPushButton("Inicio")
        self.home_button.setToolTip("Volver al centro de mando sin cerrar el proceso actual.")
        self.home_button.clicked.connect(self.show_dashboard)
        header_layout.addWidget(self.home_button, 0)

        root_layout.addWidget(header)
        self._add_shadow(header, blur=22, y=4, alpha=28)

        self.stack = QStackedWidget()
        self.stack.setObjectName("WorkspaceStack")
        self.dashboard_page = QWidget()
        self.dashboard_page.setObjectName("DashboardPage")
        dashboard_layout = QVBoxLayout(self.dashboard_page)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(10)

        metrics = make_flow(spacing=10)
        metrics.setSpacing(10)
        ported = sum(1 for app in APP_REGISTRY if app.migration_status == "ported")
        metrics.addWidget(self._metric_card("ready", str(ported), "Procesos listos", "blue"))
        metrics.addWidget(self._metric_card("recent", str(len(recent_app_keys())), "Recientes", "red"))
        metrics.addWidget(self._metric_card("favorites", str(len(favorite_app_keys())), "Favoritos", "green"))
        dashboard_layout.addLayout(metrics)

        dashboard_panels = QBoxLayout(QBoxLayout.LeftToRight)
        dashboard_panels.setSpacing(10)
        self.open_processes_panel, self.open_processes_layout = self._dashboard_panel("Procesos abiertos")
        self.recent_activity_panel, self.recent_activity_layout = self._dashboard_panel("Actividad reciente")
        self.exports_panel, self.exports_layout = self._dashboard_panel("Ultimas salidas")
        dashboard_panels.addWidget(self.open_processes_panel, 1)
        dashboard_panels.addWidget(self.recent_activity_panel, 1)
        dashboard_panels.addWidget(self.exports_panel, 1)
        dashboard_layout.addLayout(dashboard_panels)
        register_adaptive_layout(self, dashboard_panels, breakpoint_width=1040)

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

        dashboard_layout.addWidget(content_shell, 1)
        self.stack.addWidget(self.dashboard_page)
        root_layout.addWidget(self.stack, 1)

        self.status = QLabel("Suite operativa. Selecciona un proceso o usa el buscador para empezar.")
        self.status.setObjectName("StatusLabel")
        root_layout.addWidget(self.status)

        self.setCentralWidget(root)
        register_adaptive_layout(self, self.header_layout, breakpoint_width=1120)
        self.context_timer = QTimer(self)
        self.context_timer.setInterval(700)
        self.context_timer.timeout.connect(self._update_process_context)
        self.context_timer.start()
        self.show_dashboard()
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

    def _metric_card(self, key: str, value: str, label: str, accent: str) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setProperty("accent", accent)
        self._add_shadow(card, blur=14, y=2, alpha=14)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(0)
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        self.metric_values[key] = value_label
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return card

    def _dashboard_panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("DashboardPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("DashboardPanelTitle")
        layout.addWidget(label)
        return panel, layout

    @staticmethod
    def _shell_context_label(title: str, value: str) -> QLabel:
        label = QLabel(f"{title}: {value}")
        label.setObjectName("ShellContextLabel")
        label.setWordWrap(True)
        return label

    def _refresh_dashboard_overview(self) -> None:
        if self._closing:
            return
        values = {
            "ready": str(sum(1 for app in APP_REGISTRY if app.migration_status == "ported")),
            "recent": str(len(recent_app_keys())),
            "favorites": str(len(favorite_app_keys())),
        }
        for key, value in values.items():
            label = self.metric_values.get(key)
            if label is not None:
                try:
                    label.setText(value)
                except RuntimeError:
                    return
        self._render_open_processes()
        self._render_recent_activity()
        self._render_recent_exports()

    def _render_open_processes(self) -> None:
        self._clear_dashboard_panel(self.open_processes_layout)
        if not self.app_pages:
            self.open_processes_layout.addWidget(self._dashboard_empty("Sin procesos abiertos"))
            return
        for key in self.open_windows:
            app = self._app_from_key(key)
            if app is None:
                continue
            button = QPushButton(app.title)
            button.setProperty("dashboardAction", True)
            button.setToolTip(f"Volver a {app.title} sin perder el estado actual.")
            button.clicked.connect(lambda _checked=False, item=app: self.open_app(item))
            self.open_processes_layout.addWidget(button)

    def _render_recent_activity(self) -> None:
        self._clear_dashboard_panel(self.recent_activity_layout)
        recents = [self._app_from_key(key) for key in recent_app_keys()]
        recents = [app for app in recents if app is not None][:5]
        if not recents:
            self.recent_activity_layout.addWidget(self._dashboard_empty("Sin actividad reciente"))
            return
        for app in recents:
            button = QPushButton(app.title)
            button.setProperty("dashboardAction", True)
            button.setToolTip(f"Abrir {app.title}.")
            button.clicked.connect(lambda _checked=False, item=app: self.open_app(item))
            self.recent_activity_layout.addWidget(button)

    def _render_recent_exports(self) -> None:
        self._clear_dashboard_panel(self.exports_layout)
        exports = recent_paths("exports")[:5]
        if not exports:
            self.exports_layout.addWidget(self._dashboard_empty("Sin salidas recientes"))
            return
        for path in exports:
            label = QLabel(path)
            label.setObjectName("DashboardPath")
            label.setWordWrap(True)
            label.setToolTip(path)
            self.exports_layout.addWidget(label)

    def _clear_dashboard_panel(self, layout: QVBoxLayout) -> None:
        while layout.count() > 1:
            item = layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    @staticmethod
    def _dashboard_empty(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DashboardEmpty")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _app_from_key(key: str) -> AppDefinition | None:
        return next((app for app in APP_REGISTRY if app.key == key), None)

    def _select_category(self, category: str) -> None:
        self.current_category = category
        self.show_dashboard()
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
        self._refresh_dashboard_overview()
        for button_category, button in self.category_buttons.items():
            button.setText(self._nav_button_text(button_category))
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
        available = self.stack.width() if hasattr(self, "stack") else self.width()
        if available < 740:
            return 1
        if available < 1120:
            return 2
        return 3

    def _apply_responsive_state(self) -> None:
        compact = self.width() < 1060
        self._nav_compact = compact
        self.sidebar.setMaximumWidth(176 if compact else 286)
        self.sidebar.setMinimumWidth(164 if compact else 244)
        self.brand_panel.setProperty("compact", compact)
        self.nav_title.setText("SRF" if compact else "Suite Rodriguez Finura")
        self.nav_subtitle.setVisible(not compact)
        self.side_title.setText("Areas" if compact else "Areas de trabajo")
        self.footer.setText(f"v{__version__}" if compact else f"Version {__version__}\nLista para operar")
        self.search.setMinimumWidth(0)
        for category, button in self.category_buttons.items():
            button.setText(self._nav_button_text(category))
            button.setProperty("compact", compact)

    def _nav_button_text(self, category: str) -> str:
        count = len(self._apps_for_view(category))
        if not self._nav_compact:
            return f"{category}  ({count})"
        short = {
            "Todas": "Todo",
            "Favoritos": "Fav",
            "Recientes": "Rec",
            "Excel / CSV": "CSV",
            "Palets y PDA": "PDA",
        }.get(category, category.split()[0])
        return f"{short} ({count})"

    def open_app(self, app: AppDefinition) -> None:
        remember_app_open(app.key)
        self._refresh_dashboard_overview()
        window_class = WINDOW_CLASSES.get(app.key)
        if window_class is not None:
            self._show_app_page(app, window_class)
            return

        self.status.setText("Proceso no disponible en el panel.")
        QMessageBox.warning(self, "No disponible", f"{app.title} no tiene una ventana asignada en el panel.")

    def show_dashboard(self) -> None:
        self.stack.setCurrentWidget(self.dashboard_page)
        self._current_app_key = ""
        self.workspace_title.setText("Centro de mando operativo")
        self.workspace_subtitle.setText("Procesos de jamones, CSV, PDA y maquilas con acceso rapido y estado claro")
        self.home_button.setVisible(False)
        self.process_context.setVisible(False)
        self.status.setText("Suite operativa. Selecciona un proceso o usa el buscador para empezar.")
        self._refresh_dashboard_overview()

    def show_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()

    def _show_app_page(self, app: AppDefinition, window_class: type[QMainWindow]) -> None:
        window = self.app_pages.get(app.key)
        if window is None:
            window = window_class()
            window.setObjectName("EmbeddedAppWindow")
            prepare_embedded_window(window)
            window.setParent(self.stack)
            window.setWindowFlags(Qt.Widget)
            window.destroyed.connect(lambda _obj=None, key=app.key: self._forget_app_page(key))
            self.open_windows[app.key] = window
            self.app_pages[app.key] = window
            self.stack.addWidget(window)
            self._refresh_dashboard_overview()
        self.stack.setCurrentWidget(window)
        self._current_app_key = app.key
        self.workspace_title.setText(app.title)
        self.workspace_subtitle.setText(app.description)
        self.home_button.setVisible(True)
        self.process_context.setVisible(True)
        self.status.setText(f"{app.title} integrado en la ventana principal")
        self._update_process_context()
        window.setFocus(Qt.ActiveWindowFocusReason)

    def _update_process_context(self) -> None:
        if self._closing or not self._current_app_key:
            return
        window = self.app_pages.get(self._current_app_key)
        if window is None:
            return
        snapshot = operational_snapshot(window)
        self.process_state.setText(f"Estado: {snapshot['state']}")
        self.process_next.setText(f"Siguiente: {snapshot['next']}")
        self.process_alerts.setText(f"Avisos: {snapshot['alerts']}")
        self.next_action_button.setText(snapshot["next"])
        self.next_action_button.setEnabled(snapshot["next"] != "Completa el paso actual")

    def _trigger_current_next_action(self) -> None:
        window = self.app_pages.get(self._current_app_key)
        if window is None:
            return
        if trigger_next_action(window):
            self._update_process_context()

    def _forget_app_page(self, key: str) -> None:
        self.open_windows.pop(key, None)
        self.app_pages.pop(key, None)
        self._refresh_dashboard_overview()

    def close_embedded_apps_for_update(self) -> bool:
        for key, window in list(self.open_windows.items()):
            if not window.close():
                app = next((item for item in APP_REGISTRY if item.key == key), None)
                if app is not None:
                    self._show_app_page(app, type(window))
                return False
        return True

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._closing = True
        for key, window in list(self.open_windows.items()):
            if not window.close():
                self._closing = False
                app = next((item for item in APP_REGISTRY if item.key == key), None)
                if app is not None:
                    self._show_app_page(app, type(window))
                event.ignore()
                return
        super().closeEvent(event)

    def toggle_favorite(self, app: AppDefinition) -> None:
        enabled = toggle_favorite_app(app.key)
        self.status.setText(f"{app.title} {'anadido a' if enabled else 'retirado de'} favoritos.")
        self._refresh_dashboard_overview()
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
        favorite_button = QPushButton("Fav" if is_favorite_app(app.key) else "Marcar")
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
        open_button = QPushButton("Abrir")
        open_button.setProperty("primary", True)
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
