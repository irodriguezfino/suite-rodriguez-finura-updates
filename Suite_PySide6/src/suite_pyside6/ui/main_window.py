from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon
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
    QTabBar,
    QTabWidget,
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
        self._closing = False
        self._current_app_key = ""
        self._continue_app_key = ""
        self._nav_compact = False
        self._context_forced_open = False
        self.setWindowTitle("Suite Rodriguez Finura")
        self.resize(1220, 780)
        self.setMinimumSize(760, 560)
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
        shortcuts = (
            ("Ctrl+L", self._focus_search),
            ("Ctrl+W", self._close_current_tab),
            ("Ctrl+Tab", self._activate_next_tab),
            ("Ctrl+Shift+Tab", self._activate_previous_tab),
        )
        for sequence, callback in shortcuts:
            action = QAction(self)
            action.setShortcut(sequence)
            action.triggered.connect(callback)
            self.addAction(action)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("SuiteShell")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        workspace = QWidget()
        workspace.setObjectName("MainWorkspace")
        root_layout.addWidget(workspace, 1)
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(16, 14, 16, 14)
        workspace_layout.setSpacing(9)

        header = self._build_header()
        workspace_layout.addWidget(header)
        self._add_shadow(header, blur=18, y=3, alpha=18)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("WorkTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.stack = self.tabs
        body.addWidget(self.tabs, 1)

        self.process_context = self._build_context_rail()
        body.addWidget(self.process_context, 0)
        workspace_layout.addLayout(body, 1)

        self.status = QLabel("Suite operativa. Selecciona un proceso o usa el buscador para empezar.")
        self.status.setObjectName("StatusLabel")
        self.status.setVisible(False)

        self.dashboard_page = self._build_dashboard()
        self.tabs.addTab(self.dashboard_page, "Inicio")
        self.tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)

        self.setCentralWidget(root)
        register_adaptive_layout(self, self.header_layout, breakpoint_width=1120)
        self.context_timer = QTimer(self)
        self.context_timer.setInterval(700)
        self.context_timer.timeout.connect(self._update_process_context)
        self.context_timer.start()
        self.show_dashboard()
        self._apply_responsive_state()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
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
            button = QPushButton(self._nav_button_text(category))
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=category: self._select_category(name))
            self.category_buttons[category] = button
            nav_flow.addWidget(button)
        sidebar_layout.addLayout(nav_flow)

        sidebar_layout.addStretch(1)

        self.user_panel = QFrame()
        self.user_panel.setObjectName("UserPanel")
        user_layout = QHBoxLayout(self.user_panel)
        user_layout.setContentsMargins(10, 9, 10, 9)
        user_layout.setSpacing(8)
        avatar = QLabel("A")
        avatar.setObjectName("UserAvatar")
        avatar.setAlignment(Qt.AlignCenter)
        user_layout.addWidget(avatar, 0, Qt.AlignTop)
        user_text = QVBoxLayout()
        user_text.setSpacing(1)
        user_name = QLabel("Administrador")
        user_name.setObjectName("UserName")
        user_role = QLabel("Operaciones")
        user_role.setObjectName("UserRole")
        user_state = QLabel("En linea")
        user_state.setObjectName("UserState")
        user_text.addWidget(user_name)
        user_text.addWidget(user_role)
        user_text.addWidget(user_state)
        user_layout.addLayout(user_text, 1)
        sidebar_layout.addWidget(self.user_panel)

        self.footer = QLabel(f"Version {__version__}\nLista para operar")
        self.footer.setObjectName("NavFooter")
        self.footer.setWordWrap(True)
        sidebar_layout.addWidget(self.footer)
        return sidebar

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        self.header_layout = QBoxLayout(QBoxLayout.LeftToRight, header)
        self.header_layout.setContentsMargins(14, 12, 14, 12)
        self.header_layout.setSpacing(12)

        self.menu_button = QPushButton("Menu")
        self.menu_button.setObjectName("MenuButton")
        self.menu_button.setToolTip("Mostrar navegacion principal.")
        self.header_layout.addWidget(self.menu_button, 0)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.workspace_title = QLabel("Suite Rodriguez Finura")
        self.workspace_title.setObjectName("WindowTitle")
        self.workspace_subtitle = QLabel("Centro de trabajo unificado con procesos en pestanas")
        self.workspace_subtitle.setObjectName("WindowSubtitle")
        title_box.addWidget(self.workspace_title)
        title_box.addWidget(self.workspace_subtitle)
        self.header_layout.addLayout(title_box, 1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar proceso, archivo, referencia...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar proceso")
        self.search.setToolTip("Filtra los procesos por nombre, area o descripcion.")
        self.search.textChanged.connect(self._on_search_changed)
        self.header_layout.addWidget(self.search, 1)

        self.update_button = QPushButton(f"Actualizado\nv{__version__}")
        self.update_button.setObjectName("UpdateChip")
        self.update_button.setToolTip("Ver version instalada y buscar actualizaciones.")
        self.update_button.clicked.connect(self.show_about)
        self.header_layout.addWidget(self.update_button, 0)

        help_button = QPushButton("Ayuda")
        help_button.setObjectName("HelpButton")
        help_button.setToolTip("Ver informacion de la suite y soporte.")
        help_button.clicked.connect(self.show_about)
        self.header_layout.addWidget(help_button, 0)

        self.profile_button = QPushButton("A")
        self.profile_button.setObjectName("ProfileButton")
        self.profile_button.setToolTip("Perfil de usuario: Administrador.")
        self.header_layout.addWidget(self.profile_button, 0)

        self.home_button = QPushButton("Inicio")
        self.home_button.setToolTip("Volver a la pestana Inicio sin cerrar procesos.")
        self.home_button.clicked.connect(self.show_dashboard)
        self.header_layout.addWidget(self.home_button, 0)
        self.context_button = QPushButton("Contexto")
        self.context_button.setToolTip("Mostrar u ocultar el panel de contexto del proceso.")
        self.context_button.clicked.connect(self._toggle_context_rail)
        self.header_layout.addWidget(self.context_button, 0)
        return header

    def _build_context_rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("ContextRail")
        rail.setMinimumWidth(236)
        rail.setMaximumWidth(288)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Contexto")
        title.setObjectName("DashboardPanelTitle")
        layout.addWidget(title)
        self.context_app_title = QLabel("Inicio")
        self.context_app_title.setObjectName("ContextTitle")
        self.context_app_title.setWordWrap(True)
        layout.addWidget(self.context_app_title)

        state_panel, state_layout = self._context_card("Estado actual")
        self.process_state = self._shell_context_label("Estado", "Pendiente")
        state_layout.addWidget(self.process_state)
        layout.addWidget(state_panel)

        next_panel, next_layout = self._context_card("Siguiente accion")
        self.process_next = self._shell_context_label("Siguiente", "Completa el paso actual")
        next_layout.addWidget(self.process_next)

        self.next_action_button = QPushButton("Ejecutar")
        self.next_action_button.setObjectName("ShellNextAction")
        self.next_action_button.setProperty("primary", True)
        self.next_action_button.setToolTip("Ejecuta la siguiente accion disponible del proceso abierto.")
        self.next_action_button.clicked.connect(self._trigger_current_next_action)
        next_layout.addWidget(self.next_action_button)
        layout.addWidget(next_panel)

        alerts_panel, alerts_layout = self._context_card("Avisos")
        self.process_alerts = self._shell_context_label("Avisos", "Sin avisos")
        alerts_layout.addWidget(self.process_alerts)
        layout.addWidget(alerts_panel)

        self.context_files_panel, self.context_files_layout = self._dashboard_panel("Salidas recientes")
        layout.addWidget(self.context_files_panel)
        layout.addStretch(1)
        return rail

    def _build_dashboard(self) -> QWidget:
        dashboard = QWidget()
        dashboard.setObjectName("DashboardPage")
        dashboard_layout = QVBoxLayout(dashboard)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(10)

        self.continue_strip = QFrame()
        self.continue_strip.setObjectName("ContinueStrip")
        continue_layout = QHBoxLayout(self.continue_strip)
        continue_layout.setContentsMargins(12, 10, 12, 10)
        continue_layout.setSpacing(10)
        continue_text = QVBoxLayout()
        continue_text.setSpacing(2)
        self.continue_title = QLabel("Continuar trabajo")
        self.continue_title.setObjectName("ContinueTitle")
        self.continue_detail = QLabel("Sin actividad reciente")
        self.continue_detail.setObjectName("ContinueDetail")
        self.continue_detail.setWordWrap(True)
        continue_text.addWidget(self.continue_title)
        continue_text.addWidget(self.continue_detail)
        continue_layout.addLayout(continue_text, 1)
        self.continue_activity = QLabel("")
        self.continue_activity.setObjectName("ContinueMeta")
        continue_layout.addWidget(self.continue_activity, 0)
        self.continue_button = QPushButton("Continuar")
        self.continue_button.setProperty("primary", True)
        self.continue_button.setToolTip("Abrir el ultimo proceso relevante.")
        self.continue_button.clicked.connect(self._open_continue_app)
        continue_layout.addWidget(self.continue_button, 0)
        dashboard_layout.addWidget(self.continue_strip)

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
        self.app_grid.setHorizontalSpacing(10)
        self.app_grid.setVerticalSpacing(10)
        self.scroll.setWidget(self.app_container)
        content_layout.addWidget(self.scroll, 1)

        dashboard_layout.addWidget(content_shell, 1)
        return dashboard

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

    def _dashboard_panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("DashboardPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(7)
        label = QLabel(title)
        label.setObjectName("DashboardPanelTitle")
        layout.addWidget(label)
        return panel, layout

    def _context_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("ContextCard")
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
        self._render_continue_strip()
        self._render_context_exports()

    def _render_continue_strip(self) -> None:
        open_keys = list(self.open_windows.keys())
        recent_keys = recent_app_keys()
        favorite_keys = favorite_app_keys()
        candidate_key = (open_keys[-1:] or recent_keys[:1] or favorite_keys[:1] or [""])[0]
        app = self._app_from_key(candidate_key) if candidate_key else None
        exports = recent_paths("exports")
        has_activity = app is not None or bool(exports)
        self.continue_strip.setVisible(has_activity)
        if not has_activity:
            self._continue_app_key = ""
            return
        self._continue_app_key = app.key if app is not None else ""
        if app is not None:
            prefix = "Proceso abierto" if app.key in open_keys else "Ultimo proceso"
            self.continue_title.setText(f"{prefix}: {app.title}")
            self.continue_detail.setText(app.description)
            self.continue_button.setVisible(True)
            self.continue_button.setToolTip(f"Abrir {app.title}.")
        else:
            self.continue_title.setText("Ultima salida disponible")
            self.continue_detail.setText(Path(exports[0]).name)
            self.continue_button.setVisible(False)
        activity_parts = [
            f"Abiertos {len(open_keys)}",
            f"Recientes {len(recent_keys)}",
            f"Favoritos {len(favorite_keys)}",
        ]
        if exports:
            activity_parts.append(f"Salida {Path(exports[0]).name}")
        self.continue_activity.setText("  |  ".join(activity_parts))

    def _open_continue_app(self) -> None:
        app = self._app_from_key(self._continue_app_key)
        if app is not None:
            self.open_app(app)

    def _render_context_exports(self) -> None:
        self._clear_dashboard_panel(self.context_files_layout)
        exports = recent_paths("exports")[:4]
        if not exports:
            self.context_files_layout.addWidget(self._dashboard_empty("Sin salidas registradas"))
            return
        for path in exports:
            self.context_files_layout.addWidget(self._path_label(path))

    @staticmethod
    def _dashboard_button(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("dashboardAction", True)
        button.setToolTip(tooltip)
        return button

    @staticmethod
    def _path_label(path: str) -> QLabel:
        display = Path(path).name or path
        label = QLabel(display)
        label.setObjectName("DashboardPath")
        label.setWordWrap(True)
        label.setToolTip(path)
        label.setAccessibleName(f"Salida reciente: {display}")
        return label

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
        available = self.tabs.width() if hasattr(self, "tabs") else self.width()
        if available < 760:
            return 1
        if available < 1180:
            return 2
        return 3

    def _apply_responsive_state(self) -> None:
        compact = self.width() < 1060
        narrow = self.width() < 960
        self._nav_compact = compact
        self.sidebar.setMaximumWidth(132 if narrow else 176 if compact else 286)
        self.sidebar.setMinimumWidth(118 if narrow else 164 if compact else 244)
        self.brand_panel.setProperty("compact", compact)
        self.brand_panel.setVisible(not narrow)
        self.nav_title.setText("SRF" if compact else "Suite Rodriguez Finura")
        self.nav_subtitle.setVisible(not compact)
        self.side_title.setText("Areas" if compact else "Areas de trabajo")
        self.footer.setText(f"v{__version__}" if compact else f"Version {__version__}\nLista para operar")
        self.user_panel.setVisible(not compact)
        self.search.setMinimumWidth(0)
        self.process_context.setMaximumWidth(252 if compact else 288)
        if hasattr(self, "context_button"):
            show_context_toggle = bool(self._current_app_key and narrow)
            self.context_button.setVisible(show_context_toggle)
            if self._current_app_key:
                self.process_context.setVisible((not narrow) or self._context_forced_open)
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
        if self.tabs.currentIndex() != 0:
            self.tabs.setCurrentIndex(0)
        self._current_app_key = ""
        self.workspace_title.setText("Suite Rodriguez Finura")
        self.workspace_subtitle.setText("Centro de trabajo unificado con procesos en pestanas")
        self.home_button.setVisible(False)
        self.context_button.setVisible(False)
        self.process_context.setVisible(False)
        self._context_forced_open = False
        self.search.setVisible(True)
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
            window.setParent(self.tabs)
            window.setWindowFlags(Qt.Widget)
            window.destroyed.connect(lambda _obj=None, key=app.key: self._forget_app_page(key))
            self.open_windows[app.key] = window
            self.app_pages[app.key] = window
            self.tabs.addTab(window, app.title)
            self.tabs.setTabToolTip(self.tabs.indexOf(window), app.description)
            self._refresh_dashboard_overview()
        self.tabs.setCurrentWidget(window)
        self._activate_app_context(app)
        window.setFocus(Qt.ActiveWindowFocusReason)

    def _activate_app_context(self, app: AppDefinition) -> None:
        self._current_app_key = app.key
        self.workspace_title.setText(app.title)
        self.workspace_subtitle.setText(app.description)
        self.context_app_title.setText(app.title)
        self.home_button.setVisible(True)
        narrow = self.width() < 960
        self.context_button.setVisible(narrow)
        self.process_context.setVisible((not narrow) or self._context_forced_open)
        self.search.setVisible(False)
        self.status.setText(f"{app.title} integrado en la ventana principal")
        self._update_process_context()
        self._apply_responsive_state()

    def _toggle_context_rail(self) -> None:
        if not self._current_app_key:
            return
        self._context_forced_open = not self.process_context.isVisible()
        self.process_context.setVisible(self._context_forced_open)

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is None:
            return
        if widget is self.dashboard_page:
            self.show_dashboard()
            return
        for key, page in self.app_pages.items():
            if page is widget:
                app = self._app_from_key(key)
                if app is not None:
                    self._activate_app_context(app)
                return

    def _close_tab(self, index: int) -> None:
        if index <= 0:
            return
        widget = self.tabs.widget(index)
        key = next((item for item, page in self.app_pages.items() if page is widget), "")
        if widget is None or not key:
            return
        if not widget.close():
            return
        self.tabs.removeTab(index)
        self.open_windows.pop(key, None)
        self.app_pages.pop(key, None)
        self._refresh_dashboard_overview()
        if self.tabs.currentIndex() == 0:
            self.show_dashboard()

    def _close_current_tab(self) -> None:
        self._close_tab(self.tabs.currentIndex())

    def _activate_next_tab(self) -> None:
        count = self.tabs.count()
        if count > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % count)

    def _activate_previous_tab(self) -> None:
        count = self.tabs.count()
        if count > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % count)

    def _focus_search(self) -> None:
        self.show_dashboard()
        self.search.setFocus(Qt.ShortcutFocusReason)
        self.search.selectAll()

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
        self.next_action_button.setText(self._compact_action_text(snapshot["next"]))
        self.next_action_button.setToolTip(f"Siguiente accion: {snapshot['next']}")
        self.next_action_button.setEnabled(snapshot["next"] != "Completa el paso actual")

    @staticmethod
    def _compact_action_text(text: str, limit: int = 28) -> str:
        clean = " ".join(str(text).split())
        if len(clean) <= limit:
            return clean
        return clean[: max(0, limit - 3)].rstrip() + "..."

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
        self.setMinimumHeight(138)
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
        favorite_button = QPushButton("★" if is_favorite_app(app.key) else "☆")
        favorite_button.setCheckable(True)
        favorite_button.setChecked(is_favorite_app(app.key))
        favorite_button.setProperty("role", "favorite")
        favorite_button.setAccessibleName(f"Alternar favorito: {app.title}")
        favorite_button.setAccessibleDescription(
            "Marcado como favorito." if is_favorite_app(app.key) else "No marcado como favorito."
        )
        favorite_button.setToolTip(
            "Quitar de Favoritos." if is_favorite_app(app.key) else "Anadir a Favoritos."
        )
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
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()
