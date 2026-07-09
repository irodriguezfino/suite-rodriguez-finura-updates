from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6 import __version__
from suite_pyside6.core.apps import APP_REGISTRY, AppDefinition, categories
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.about_dialog import AboutDialog
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.components import dropzone, empty_state, labeled_field, metric, module_row, panel, work_item
from suite_pyside6.ui.polish import apply_premium_depth, apply_theme_mode, brand_logo_pixmap, focus_next_action, handle_dropped_paths, operational_snapshot, prepare_embedded_window, trigger_next_action
from suite_pyside6.ui.session import recent_app_keys, recent_paths, remember_app_open
from suite_pyside6.ui.theme import base_qss, current_theme_preference


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_view = "bandeja"
        self.current_category = "Todas"
        self.search_text = ""
        self.open_windows: dict[str, QMainWindow] = {}
        self.app_pages: dict[str, QMainWindow] = {}
        self.app_page_indexes: dict[str, int] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        self.category_buttons: dict[str, QPushButton] = {}
        self.active_job_buttons: dict[str, QPushButton] = {}
        self._current_app_key = ""
        self._continue_app_key = ""
        self._closing = False

        self.setWindowTitle("Consola Operativa Rodriguez Finura")
        self.resize(1360, 820)
        self.setMinimumSize(960, 620)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_actions()
        self._build_ui()
        self._refresh_all()

        self.context_timer = QTimer(self)
        self.context_timer.setInterval(700)
        self.context_timer.timeout.connect(self._update_context)
        self.context_timer.start()

    def _build_actions(self) -> None:
        for index, app in enumerate(APP_REGISTRY, start=1):
            action = QAction(self)
            action.setShortcut(f"Alt+{index}")
            action.triggered.connect(lambda _checked=False, item=app: self.open_app(item))
            self.addAction(action)

        shortcuts = (
            ("Ctrl+L", self._focus_search),
            ("Ctrl+1", lambda: self.show_view("bandeja")),
            ("Ctrl+2", lambda: self.show_view("procesos")),
            ("Ctrl+3", lambda: self.show_view("salidas")),
            ("Ctrl+4", lambda: self.show_view("historial")),
            ("Ctrl+5", lambda: self.show_view("ajustes")),
            ("Ctrl+F", self._focus_find),
            ("Ctrl+Return", self._trigger_next),
            ("Ctrl+Enter", self._trigger_next),
            ("Ctrl+W", self._close_current_work),
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
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(16, 14, 16, 14)
        workspace_layout.setSpacing(12)
        root_layout.addWidget(workspace, 1)

        self.header = self._build_header()
        workspace_layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        self.stack = QStackedWidget()
        self.stack.setObjectName("WorkspaceStack")
        body.addWidget(self.stack, 1)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("WorkTabs")
        self.tabs.setAccessibleName("Trabajos abiertos")
        self.tabs.setAccessibleDescription("Lista de trabajos abiertos. Cambia entre pestañas para recuperar una aplicación.")
        self.tabs.setVisible(False)
        self.tabs.addTab(QWidget(), "Inicio")
        self.tab_keys: list[str] = [""]

        self.context_rail = self._build_context_rail()
        self.process_context = self.context_rail
        self.context_rail.setVisible(False)
        body.addWidget(self.context_rail)
        workspace_layout.addLayout(body, 1)

        self.dashboard_page = self._scroll_page(self._build_dashboard())
        self.processes_page = self._scroll_page(self._build_processes_page())
        self.outputs_page = self._scroll_page(self._build_outputs_page())
        self.history_page = self._scroll_page(self._build_history_page())
        self.settings_page = self._scroll_page(self._build_settings_page())

        self.page_indexes = {
            "bandeja": self.stack.addWidget(self.dashboard_page),
            "procesos": self.stack.addWidget(self.processes_page),
            "salidas": self.stack.addWidget(self.outputs_page),
            "historial": self.stack.addWidget(self.history_page),
            "ajustes": self.stack.addWidget(self.settings_page),
        }
        self.setCentralWidget(root)
        self.result_label = QLabel()
        self.result_label.setVisible(False)
        for category in categories():
            button = QPushButton(category)
            button.setCheckable(True)
            button.setChecked(category == "Todas")
            button.setVisible(False)
            self.category_buttons[category] = button
        self._apply_responsive_state()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("ConsoleSidebar")
        sidebar.setAccessibleName("Navegación principal")
        sidebar.setAccessibleDescription("Navegación principal de la consola operativa.")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(240)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        brand = QVBoxLayout()
        brand.setSpacing(5)
        logo = self._brand_logo("RODRIGUEZ.png", 166, 48, "Rodríguez")
        if logo is not None:
            brand.addWidget(logo)
        self.nav_title = QLabel("Rodríguez")
        self.nav_title.setObjectName("SidebarBrandTitle")
        self.nav_title.setWordWrap(True)
        subtitle = QLabel("Consola operativa")
        subtitle.setObjectName("SidebarBrandSubtitle")
        subtitle.setWordWrap(True)
        brand.addWidget(self.nav_title)
        brand.addWidget(subtitle)
        layout.addLayout(brand)

        layout.addWidget(self._nav_label("Trabajo"))
        for key, label in (
            ("bandeja", "Bandeja"),
            ("procesos", "Procesos"),
            ("salidas", "Salidas"),
            ("historial", "Historial"),
            ("ajustes", "Ajustes"),
        ):
            button = self._nav_button(label)
            shortcut = {
                "bandeja": "Ctrl+1",
                "procesos": "Ctrl+2",
                "salidas": "Ctrl+3",
                "historial": "Ctrl+4",
                "ajustes": "Ctrl+5",
            }[key]
            button.setToolTip(f"{label} ({shortcut})")
            button.setAccessibleDescription(f"Ir a {label}. Atajo: {shortcut}.")
            button.clicked.connect(lambda _checked=False, view=key: self.show_view(view))
            self.nav_buttons[key] = button
            layout.addWidget(button)

        layout.addWidget(self._nav_label("Trabajos abiertos"))
        self.active_jobs_box = QVBoxLayout()
        self.active_jobs_box.setSpacing(6)
        layout.addLayout(self.active_jobs_box)
        layout.addStretch(1)

        footer = QLabel(f"v{__version__}  |  Ctrl+F buscar  |  Alt+1-9 abrir  |  Ctrl+Enter siguiente")
        footer.setObjectName("ModuleDescription")
        footer.setWordWrap(True)
        layout.addWidget(footer)
        return sidebar

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("ConsoleHeader")
        layout = QBoxLayout(QBoxLayout.LeftToRight, header)
        self.header_layout = layout
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.workspace_title = QLabel("Bandeja")
        self.workspace_title.setObjectName("ShellTitle")
        self.workspace_subtitle = QLabel("Carga archivos, detecta procesos y continúa trabajos activos.")
        self.workspace_subtitle.setObjectName("ShellSubtitle")
        self.workspace_subtitle.setWordWrap(True)
        self.workspace_subtitle.setMinimumWidth(0)
        title_box.addWidget(self.workspace_title)
        title_box.addWidget(self.workspace_subtitle)
        layout.addLayout(title_box, 1)

        self.compact_context_bar = self._build_compact_context_bar()
        self.compact_context_bar.setVisible(False)
        layout.addWidget(self.compact_context_bar, 2)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar proceso, salida o archivo (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search_changed)
        self.search.setAccessibleName("Buscar en la consola")
        self.search.setAccessibleDescription("Busca procesos por nombre, categoría o descripción. Atajo: Ctrl+F.")
        layout.addWidget(self.search, 1)

        self.header_actions = QWidget()
        self.header_actions.setObjectName("HeaderActions")
        self.header_actions.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        actions_layout = QHBoxLayout(self.header_actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.about_button = QPushButton(f"v{__version__}")
        self.about_button.setToolTip("Versión, diagnóstico y actualizaciones")
        self.about_button.setAccessibleName("Versión y actualizaciones")
        self.about_button.clicked.connect(self.show_about)
        actions_layout.addWidget(self.about_button)

        self.home_button = QPushButton("Bandeja")
        self.home_button.setToolTip("Volver a la bandeja sin cerrar trabajos.")
        self.home_button.setAccessibleName("Volver a Bandeja")
        self.home_button.setAccessibleDescription("Vuelve a la bandeja sin cerrar trabajos abiertos.")
        self.home_button.clicked.connect(self.show_dashboard)
        self.home_button.setVisible(False)
        actions_layout.addWidget(self.home_button)
        layout.addWidget(self.header_actions, 0, Qt.AlignRight)
        return header

    def _build_compact_context_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("CompactContextBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.compact_context_state = QLabel("Pendiente")
        self.compact_context_state.setObjectName("CompactContextValue")
        self.compact_context_state.setWordWrap(True)
        self.compact_context_next = QLabel("Abrir proceso")
        self.compact_context_next.setObjectName("CompactContextValue")
        self.compact_context_next.setWordWrap(True)
        self.compact_context_alerts = QLabel("Sin avisos")
        self.compact_context_alerts.setObjectName("CompactContextValue")
        self.compact_context_alerts.setWordWrap(True)

        for label in (self.compact_context_state, self.compact_context_next, self.compact_context_alerts):
            layout.addWidget(label, 1)

        self.compact_next_button = QPushButton("Siguiente")
        self.compact_next_button.setObjectName("PrimaryButton")
        self.compact_next_button.setProperty("primary", True)
        self.compact_next_button.setToolTip("Ejecutar la siguiente acción recomendada (Ctrl+Enter)")
        self.compact_next_button.setAccessibleName("Ejecutar siguiente acción")
        self.compact_next_button.setAccessibleDescription("Ejecuta la siguiente acción recomendada del trabajo abierto. Atajo: Ctrl+Enter.")
        self.compact_next_button.clicked.connect(self._trigger_next)
        layout.addWidget(self.compact_next_button, 0, Qt.AlignVCenter)
        return bar

    def _build_context_rail(self) -> QFrame:
        rail = QFrame()
        rail.setObjectName("ConsoleRail")
        rail.setMinimumWidth(240)
        rail.setMaximumWidth(264)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Contexto")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.context_title = QLabel("Sin trabajo abierto")
        self.context_title.setObjectName("ModuleTitle")
        self.context_title.setWordWrap(True)
        self.context_app_title = self.context_title
        layout.addWidget(self.context_title)

        self.context_state = self._context_card("Estado", "Pendiente")
        self.context_next = self._context_card("Siguiente acción", "Abre un proceso")
        self.context_alerts = self._context_card("Avisos", "Sin avisos")
        self.process_state = QLabel("Estado: Pendiente")
        self.process_next = QLabel("Siguiente: Abre un proceso")
        self.process_alerts = QLabel("Avisos: Sin avisos")
        for label in (self.process_state, self.process_next, self.process_alerts):
            label.setVisible(False)
        layout.addWidget(self.context_state)
        layout.addWidget(self.context_next)
        layout.addWidget(self.context_alerts)

        self.next_button = QPushButton("Ejecutar siguiente")
        self.next_button.setObjectName("ShellNextAction")
        self.next_button.setProperty("primary", True)
        self.next_button.setToolTip("Ejecutar la siguiente acción recomendada (Ctrl+Enter)")
        self.next_button.setAccessibleName("Ejecutar siguiente acción")
        self.next_button.setAccessibleDescription("Ejecuta la siguiente acción recomendada del trabajo abierto. Atajo: Ctrl+Enter.")
        self.next_button.clicked.connect(self._trigger_next)
        self.next_action_button = self.next_button
        layout.addWidget(self.next_button)
        layout.addStretch(1)
        return rail

    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ConsolePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero_panel, hero_layout = panel(name="HeroPanel")
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(3)
        self.command_title = QLabel("Operación diaria")
        self.command_title.setObjectName("PanelTitle")
        self.command_detail = QLabel("Valida archivos, corrige incidencias y genera salidas desde una consola única.")
        self.command_detail.setObjectName("PanelSubtitle")
        self.command_detail.setWordWrap(True)
        hero_copy.addWidget(self.command_title)
        hero_copy.addWidget(self.command_detail)
        hero_layout.addLayout(hero_copy)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self.dashboard_metrics = metrics
        self.metric_open = metric("Abiertos", "0", "Trabajos en la consola")
        self.metric_recent = metric("Recientes", "0", "Procesos usados")
        self.metric_outputs = metric("Salidas", "0", "Exportaciones registradas")
        self.command_open_value = self.metric_open.property("valueLabel")
        self.command_recent_value = self.metric_recent.property("valueLabel")
        self.command_outputs_value = self.metric_outputs.property("valueLabel")
        metrics.addWidget(self.metric_open, 1)
        metrics.addWidget(self.metric_recent, 1)
        metrics.addWidget(self.metric_outputs, 1)
        hero_layout.addLayout(metrics)

        open_process = QPushButton("Elegir proceso")
        open_process.setProperty("primary", True)
        open_process.setAccessibleName("Elegir proceso")
        open_process.setAccessibleDescription("Abre la lista de procesos para seleccionar una herramienta operativa.")
        open_process.clicked.connect(lambda: self.show_view("procesos"))
        hero_drop = dropzone(
            "Carga o inicia",
            "Arrastra archivos aquí o elige un proceso manualmente.",
            open_process,
        )
        hero_drop.setMaximumHeight(108)
        self._enable_dashboard_drop(hero_drop)
        hero_layout.addWidget(hero_drop)
        layout.addWidget(hero_panel)

        self.continue_strip, continue_layout = panel("Continuar", "Retoma el último trabajo abierto o reciente.")
        continue_row = QHBoxLayout()
        continue_row.setSpacing(10)
        continue_copy = QVBoxLayout()
        continue_copy.setSpacing(2)
        self.continue_title = QLabel("Sin actividad reciente")
        self.continue_title.setObjectName("ModuleTitle")
        self.continue_detail = QLabel("Abre un proceso para fijarlo aquí.")
        self.continue_detail.setObjectName("ModuleDescription")
        self.continue_detail.setWordWrap(True)
        continue_copy.addWidget(self.continue_title)
        continue_copy.addWidget(self.continue_detail)
        continue_row.addLayout(continue_copy, 1)
        self.continue_activity = QLabel("")
        self.continue_activity.setObjectName("ModuleDescription")
        self.continue_activity.setWordWrap(True)
        continue_row.addWidget(self.continue_activity)
        self.continue_button = QPushButton("Continuar")
        self.continue_button.setProperty("primary", True)
        self.continue_button.setAccessibleName("Continuar trabajo")
        self.continue_button.setAccessibleDescription("Abre el último trabajo activo o reciente disponible.")
        self.continue_button.clicked.connect(self._open_continue_app)
        continue_row.addWidget(self.continue_button)
        continue_layout.addLayout(continue_row)
        layout.addWidget(self.continue_strip)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        self.dashboard_columns = columns
        priority_panel, priority_layout = panel("Procesos frecuentes", "Acceso rápido a los flujos más usados.", name="ModulesPanel")
        for key in ("control_recepcion_maquilas", "precintos_jamones", "recepcion_maquilas", "precintos_expedicion"):
            app = self._app_from_key(key)
            if app is not None:
                button = QPushButton("Abrir")
                button.clicked.connect(lambda _checked=False, item=app: self.open_app(item))
                priority_layout.addWidget(work_item(app.title, app.description, "Disponible", button))
        columns.addWidget(priority_panel, 2)

        outputs_panel, self.dashboard_outputs_layout = panel("Actividad", "Salidas recientes y estado operativo.", name="ActivityPanel")
        columns.addWidget(outputs_panel, 1)
        layout.addLayout(columns, 1)
        return page

    def _build_processes_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ConsolePage")
        self.processes_layout = QVBoxLayout(page)
        self.processes_layout.setContentsMargins(0, 0, 0, 0)
        self.processes_layout.setSpacing(12)
        self._render_processes()
        return page

    def _build_outputs_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ConsolePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.outputs_panel, self.outputs_layout = panel("Salidas", "TXT, CSV, Excel y PDF generados por la consola.")
        layout.addWidget(self.outputs_panel)
        layout.addStretch(1)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ConsolePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.history_panel, self.history_layout = panel("Historial", "Procesos y archivos recientes.")
        layout.addWidget(self.history_panel)
        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ConsolePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        settings_panel, settings_layout = panel("Ajustes operativos", "Versión, diagnóstico y configuración de soporte.")
        settings_layout.addWidget(work_item("Versión instalada", f"Suite Rodriguez Finura {__version__}", "Disponible"))
        update_button = QPushButton("Abrir diagnóstico y actualizaciones")
        brand_row = QHBoxLayout()
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(2)
        brand_title = QLabel("Identidad Rodríguez")
        brand_title.setObjectName("ModuleTitle")
        brand_detail = QLabel("Azul corporativo como base y Finura como acento premium.")
        brand_detail.setObjectName("ModuleDescription")
        brand_detail.setWordWrap(True)
        brand_copy.addWidget(brand_title)
        brand_copy.addWidget(brand_detail)
        brand_row.addLayout(brand_copy, 1)
        finura = self._brand_logo("FINURA.png", 96, 34, "Finura")
        if finura is not None:
            finura.setObjectName("BrandSeal")
            brand_row.addWidget(finura, 0, Qt.AlignVCenter)
        settings_layout.addLayout(brand_row)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("ThemePreference")
        self.theme_combo.blockSignals(True)
        self.theme_combo.addItems(["Sistema", "Claro", "Oscuro"])
        self.theme_combo.setCurrentText({"system": "Sistema", "light": "Claro", "dark": "Oscuro"}[current_theme_preference()])
        self.theme_combo.blockSignals(False)
        self.theme_combo.setAccessibleName("Tema visual")
        self.theme_combo.setAccessibleDescription("Selecciona el tema visual de la aplicación: sistema, claro u oscuro.")
        self.theme_combo.currentTextChanged.connect(self._set_theme_preference)
        settings_layout.addWidget(labeled_field("Tema visual", self.theme_combo))

        update_button.setProperty("primary", True)
        update_button.setAccessibleName("Abrir diagnóstico y actualizaciones")
        update_button.setAccessibleDescription("Abre el diálogo de versión, diagnóstico y actualizaciones.")
        update_button.clicked.connect(self.show_about)
        settings_layout.addWidget(update_button)
        layout.addWidget(settings_panel)
        layout.addStretch(1)
        return page

    def _set_theme_preference(self, text: str) -> None:
        apply_theme_mode({"Claro": "light", "Oscuro": "dark", "Sistema": "system"}.get(text, "system"))

    @staticmethod
    def _brand_logo(name: str, width: int, height: int, accessible_name: str) -> QLabel | None:
        path = resource_path(name)
        if not path.exists():
            return None
        pixmap = brand_logo_pixmap(path)
        if pixmap.isNull():
            return None
        label = QLabel()
        label.setObjectName("SidebarBrandLogo")
        label.setAccessibleName(accessible_name)
        label.setPixmap(pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        label.setMinimumHeight(height)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        return label

    @staticmethod
    def _scroll_page(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _nav_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Overline")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _nav_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("NavItem")
        button.setProperty("nav", True)
        button.setCheckable(True)
        button.setAccessibleName(text)
        return button

    def _context_card(self, title: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ContextCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("Overline")
        value_label = QLabel(value)
        value_label.setObjectName("ModuleDescription")
        value_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        frame.setProperty("valueLabel", value_label)
        return frame

    def _process_row(self, app: AppDefinition) -> QFrame:
        button = QPushButton("Abrir")
        button.setProperty("primary", True)
        button.setAccessibleName(f"Abrir {app.title}")
        button.clicked.connect(lambda _checked=False, item=app: self.open_app(item))
        return module_row(app.title, app.description, app.category, "Disponible", app.shortcut, button)

    def _render_processes(self) -> None:
        if not hasattr(self, "processes_layout"):
            return
        self._clear_layout(self.processes_layout)
        apps = self._filtered_apps()
        if hasattr(self, "result_label"):
            suffix = "en Todas"
            if self.search_text:
                self.result_label.setText(f"{len(apps)} procesos encontrados {suffix}")
            else:
                self.result_label.setText(f"{len(apps)} procesos disponibles {suffix}")
            self.result_label.setAccessibleDescription(self.result_label.text())
        if not apps:
            self.processes_layout.addWidget(empty_state("Sin procesos", "Ajusta la busqueda para encontrar el proceso."))
            return
        for category in categories():
            group = [app for app in apps if category == "Todas" or app.category == category]
            if category == "Todas" or not group:
                continue
            group_panel, group_layout = panel(category, f"{len(group)} procesos disponibles")
            for app in group:
                group_layout.addWidget(self._process_row(app))
            self.processes_layout.addWidget(group_panel)
        self.processes_layout.addStretch(1)

    def _refresh_outputs(self) -> None:
        for layout in (getattr(self, "outputs_layout", None), getattr(self, "dashboard_outputs_layout", None)):
            if layout is None:
                continue
            self._clear_layout(layout)
            exports = recent_paths("exports")
            if not exports:
                label = QLabel("Sin salidas generadas todavia.")
                label.setObjectName("DashboardEmpty")
                label.setWordWrap(True)
                layout.addWidget(label)
                continue
            for path in exports[:8]:
                layout.addWidget(work_item(Path(path).name, path, "Generado"))

    def _refresh_history(self) -> None:
        self._clear_layout(self.history_layout)
        recent_apps = recent_app_keys()
        if not recent_apps:
            self.history_layout.addWidget(empty_state("Sin historial", "Abre un proceso para empezar a construir historial."))
            return
        for key in recent_apps:
            app = self._app_from_key(key)
            if app is not None:
                button = QPushButton("Abrir")
                button.clicked.connect(lambda _checked=False, item=app: self.open_app(item))
                self.history_layout.addWidget(work_item(app.title, app.description, "Reciente", button))

    def _refresh_active_jobs(self) -> None:
        self._clear_layout(self.active_jobs_box)
        self.active_job_buttons.clear()
        if not self.app_pages:
            label = QLabel("Sin trabajos abiertos")
            label.setObjectName("ModuleDescription")
            label.setWordWrap(True)
            self.active_jobs_box.addWidget(label)
            return
        for key, page in self.app_pages.items():
            app = self._app_from_key(key)
            if app is None:
                continue
            button = self._nav_button(self._compact_nav_text(app.title, narrow=self.width() < 980))
            button.setToolTip(app.title)
            button.setAccessibleName(app.title)
            button.setChecked(key == self._current_app_key)
            button.clicked.connect(lambda _checked=False, item=app: self.open_app(item))
            self.active_job_buttons[key] = button
            self.active_jobs_box.addWidget(button)

    def _refresh_metrics(self) -> None:
        values = (
            (self.metric_open, str(len(self.app_pages))),
            (self.metric_recent, str(len(recent_app_keys()))),
            (self.metric_outputs, str(len(recent_paths("exports")))),
        )
        for frame, value in values:
            label = frame.property("valueLabel")
            if isinstance(label, QLabel):
                label.setText(value)
        if hasattr(self, "command_title"):
            self.command_title.setText("Operación en curso" if self.app_pages else "Operación diaria")

    def _refresh_continue(self) -> None:
        open_keys = list(self.app_pages.keys())
        recent_keys = recent_app_keys()
        candidate_key = (recent_keys[:1] or open_keys[:1] or [""])[0]
        app = self._app_from_key(candidate_key) if candidate_key else None
        has_activity = app is not None
        self.continue_strip.setVisible(has_activity)
        if not has_activity:
            self._continue_app_key = ""
            return
        self._continue_app_key = app.key
        prefix = "Trabajo abierto" if app.key in open_keys else "Último proceso"
        self.continue_title.setText(f"{prefix}: {app.title}")
        self.continue_detail.setText(app.description)
        self.continue_activity.setText(
            f"Abiertos {len(open_keys)}  |  Recientes {len(recent_keys)}  |  Salidas {len(recent_paths('exports'))}"
        )
        self.continue_button.setToolTip(f"Abrir {app.title}")

    def _open_continue_app(self) -> None:
        app = self._app_from_key(self._continue_app_key)
        if app is not None:
            self.open_app(app)

    def _refresh_all(self) -> None:
        self._refresh_metrics()
        self._refresh_continue()
        self._refresh_outputs()
        self._refresh_history()
        self._refresh_active_jobs()
        self._render_processes()
        self._update_nav_state()
        self._update_context()
        apply_premium_depth(self)

    def _filtered_apps(self) -> list[AppDefinition]:
        text = self.search_text
        if not text:
            return list(APP_REGISTRY)
        result = []
        for app in APP_REGISTRY:
            haystack = " ".join((app.title, app.description, app.category, app.short_description)).lower()
            if text in haystack:
                result.append(app)
        return result

    def show_view(self, view: str) -> None:
        self.current_view = view
        self._current_app_key = ""
        self.stack.setCurrentIndex(self.page_indexes[view])
        titles = {
            "bandeja": ("Bandeja", "Carga archivos, detecta procesos y continúa trabajos activos."),
            "procesos": ("Procesos", "Elige manualmente una herramienta operativa."),
            "salidas": ("Salidas", "Revisa exportaciones y documentos generados."),
            "historial": ("Historial", "Retoma procesos usados recientemente."),
            "ajustes": ("Ajustes", "Versión, diagnóstico y soporte."),
        }
        title, subtitle = titles[view]
        self.workspace_title.setText(title)
        self.workspace_subtitle.setText(subtitle)
        self.search.setVisible(view in {"bandeja", "procesos"})
        self.home_button.setVisible(view != "bandeja")
        self.context_rail.setVisible(False)
        self.compact_context_bar.setVisible(False)
        self._refresh_all()

    def show_dashboard(self) -> None:
        self.show_view("bandeja")
        self.search.setVisible(True)
        self.tabs.setCurrentIndex(0)

    def open_app(self, app: AppDefinition) -> None:
        remember_app_open(app.key)
        window = self.app_pages.get(app.key)
        if window is None:
            window_class = get_window_class(app.key)
            if window_class is None:
                QMessageBox.warning(self, "No disponible", f"{app.title} no tiene una ventana asignada.")
                return
            window = window_class()
            window.setObjectName("EmbeddedAppWindow")
            prepare_embedded_window(window)
            window.setParent(self.stack)
            window.setWindowFlags(Qt.Widget)
            window.destroyed.connect(lambda _obj=None, key=app.key: self._forget_app_page(key))
            self.app_pages[app.key] = window
            self.open_windows[app.key] = window
            self.app_page_indexes[app.key] = self.stack.addWidget(window)
            self.tabs.addTab(QWidget(), app.title)
            self.tab_keys.append(app.key)

        self._current_app_key = app.key
        self.current_view = "trabajo"
        self.stack.setCurrentWidget(window)
        if app.key in self.tab_keys:
            self.tabs.setCurrentIndex(self.tab_keys.index(app.key))
        self.workspace_title.setText(app.title)
        self.workspace_subtitle.setText(app.description)
        self.search.setVisible(False)
        self.home_button.setVisible(True)
        self.context_rail.setVisible(True)
        window.setFocus(Qt.ActiveWindowFocusReason)
        self._refresh_all()
        QTimer.singleShot(0, lambda window=window: focus_next_action(window))
        self._apply_responsive_state()

    def show_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()
        self._refresh_all()

    def _update_context(self) -> None:
        if self._closing:
            return
        app = self._app_from_key(self._current_app_key)
        window = self.app_pages.get(self._current_app_key)
        if app is None or window is None:
            self.context_title.setText("Sin trabajo abierto")
            self._set_context_value(self.context_state, "Selecciona un proceso")
            self._set_context_value(self.context_next, "Abrir proceso")
            self._set_context_value(self.context_alerts, "Sin avisos")
            self.process_state.setText("Estado: Selecciona un proceso")
            self.process_next.setText("Siguiente: Abrir proceso")
            self.process_alerts.setText("Avisos: Sin avisos")
            self.next_button.setEnabled(False)
            self.compact_context_state.setText("Selecciona un proceso")
            self.compact_context_next.setText("Abrir proceso")
            self.compact_context_alerts.setText("Sin avisos")
            self.compact_next_button.setEnabled(False)
            return
        snapshot = operational_snapshot(window)
        self.context_title.setText(app.title)
        self._set_context_value(self.context_state, snapshot["state"])
        self._set_context_value(self.context_next, snapshot["next"])
        self._set_context_value(self.context_alerts, snapshot["alerts"] or "Sin avisos")
        self.process_state.setText(f"Estado: {snapshot['state']}")
        self.process_next.setText(f"Siguiente: {snapshot['next']}")
        self.process_alerts.setText(f"Avisos: {snapshot['alerts'] or 'Sin avisos'}")
        next_label = snapshot["next"] if snapshot["next"] else "Ejecutar"
        full_next_label = f"Siguiente: {next_label}"
        self.next_button.setText(self._compact_action_text(next_label, 22))
        self.next_button.setToolTip(f"{full_next_label} (Ctrl+Enter)")
        self.next_button.setEnabled(snapshot["next"] != "Completa el paso actual")
        self.compact_context_state.setText(f"Estado: {snapshot['state']}")
        self.compact_context_next.setText(f"Siguiente: {snapshot['next']}")
        self.compact_context_alerts.setText(f"Avisos: {snapshot['alerts'] or 'Sin avisos'}")
        self.compact_next_button.setText(self._compact_action_text(next_label, 18))
        self.compact_next_button.setToolTip(f"{full_next_label} (Ctrl+Enter)")
        self.compact_next_button.setEnabled(snapshot["next"] != "Completa el paso actual")

    def _update_process_context(self) -> None:
        self._update_context()

    @staticmethod
    def _compact_action_text(text: str, limit: int = 28) -> str:
        clean = " ".join(str(text).split())
        if len(clean) <= limit:
            return clean
        return clean[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _compact_nav_text(text: str, *, narrow: bool = False) -> str:
        narrow_mapping = {
            "Merma Jamones FAC": "M",
            "Procesador TXT a CSV": "TXT",
            "Palets PDA": "PDA",
            "Precintos Jamones": "PJ",
            "Precintos Expedición": "PE",
            "Precintos Excel a CSV": "XL",
            "Recepción Maquilas": "REC",
            "Control y Recepción Maquilas": "CTL",
            "Pesos": "P",
        }
        compact_mapping = {
            "Merma Jamones FAC": "Merma FAC",
            "Procesador TXT a CSV": "TXT a CSV",
            "Precintos Jamones": "P. Jamones",
            "Precintos Expedición": "P. Exped.",
            "Precintos Excel a CSV": "Excel",
            "Recepción Maquilas": "Recepción",
            "Control y Recepción Maquilas": "Control",
        }
        return (narrow_mapping if narrow else compact_mapping).get(text, text)

    @staticmethod
    def _set_context_value(card: QFrame, value: str) -> None:
        label = card.property("valueLabel")
        if isinstance(label, QLabel):
            label.setText(value)

    def _trigger_next(self) -> None:
        window = self.app_pages.get(self._current_app_key)
        if window is not None and trigger_next_action(window):
            self._update_context()
            self._refresh_all()

    def _close_current_work(self) -> None:
        key = self._current_app_key
        if not key:
            return
        window = self.app_pages.get(key)
        if window is None or not window.close():
            return
        self.stack.removeWidget(window)
        window.setParent(None)
        self.open_windows.pop(key, None)
        self.app_pages.pop(key, None)
        self.app_page_indexes.pop(key, None)
        if key in self.tab_keys:
            index = self.tab_keys.index(key)
            self.tabs.removeTab(index)
            self.tab_keys.pop(index)
        self.show_dashboard()

    def _close_current_tab(self) -> None:
        index = self.tabs.currentIndex()
        if index <= 0 or index >= len(self.tab_keys):
            return
        key = self.tab_keys[index]
        window = self.app_pages.get(key)
        if window is not None and not window.close():
            return
        if window is not None:
            self.stack.removeWidget(window)
            window.setParent(None)
        self.tabs.removeTab(index)
        self.tab_keys.pop(index)
        self.open_windows.pop(key, None)
        self.app_pages.pop(key, None)
        self.app_page_indexes.pop(key, None)
        self.show_dashboard()

    def _on_search_changed(self, text: str) -> None:
        self.search_text = " ".join(text.lower().split())
        self._render_processes()

    def _focus_search(self) -> None:
        if self.current_view not in {"bandeja", "procesos"}:
            self.show_view("procesos")
        self.search.setFocus(Qt.ShortcutFocusReason)
        self.search.selectAll()

    def _focus_find(self) -> None:
        if self.current_view == "trabajo":
            window = self.app_pages.get(self._current_app_key)
            if window is not None:
                for field in window.findChildren(QLineEdit):
                    text = " ".join((field.placeholderText(), field.accessibleName(), field.toolTip())).lower()
                    if field.isVisible() and field.isEnabled() and any(word in text for word in ("buscar", "filtro", "peso")):
                        field.setFocus(Qt.ShortcutFocusReason)
                        field.selectAll()
                        return
                for button in window.findChildren(QPushButton):
                    text = " ".join((button.text(), button.toolTip(), button.accessibleName())).lower()
                    if button.isVisible() and button.isEnabled() and "filtrar" in text:
                        button.setFocus(Qt.ShortcutFocusReason)
                        return
        self._focus_search()

    def _update_nav_state(self) -> None:
        for key, button in self.nav_buttons.items():
            button.setChecked(key == self.current_view)
        for key, button in self.active_job_buttons.items():
            button.setChecked(key == self._current_app_key)

    def _forget_app_page(self, key: str) -> None:
        if self._closing or QApplication.closingDown():
            return
        try:
            self.open_windows.pop(key, None)
            self.app_pages.pop(key, None)
            self.app_page_indexes.pop(key, None)
            if key in self.tab_keys:
                index = self.tab_keys.index(key)
                self.tabs.removeTab(index)
                self.tab_keys.pop(index)
            if self._current_app_key == key:
                self.show_view("bandeja")
            self._refresh_all()
        except RuntimeError:
            return

    def close_embedded_apps_for_update(self) -> bool:
        for key, window in list(self.open_windows.items()):
            if not window.close():
                app = self._app_from_key(key)
                if app is not None:
                    self.open_app(app)
                return False
        return True

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._closing = True
        for key, window in list(self.open_windows.items()):
            if not window.close():
                self._closing = False
                app = self._app_from_key(key)
                if app is not None:
                    self.open_app(app)
                event.ignore()
                return
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if hasattr(self, "header_layout"):
            direction = QBoxLayout.TopToBottom if self.width() < 1120 else QBoxLayout.LeftToRight
            self.header_layout.setDirection(direction)
        self._apply_responsive_state()

    def _apply_responsive_state(self) -> None:
        compact = self.width() < 1120
        narrow = self.width() < 980
        self.sidebar.setMaximumWidth(112 if narrow else 176 if compact else 240)
        self.sidebar.setMinimumWidth(96 if narrow else 164 if compact else 220)
        self.nav_title.setText("SRF" if compact else "Rodriguez Finura")
        if hasattr(self, "command_detail"):
            self.command_detail.setVisible(self.width() > 960)
        if hasattr(self, "dashboard_columns"):
            self.dashboard_columns.setDirection(QBoxLayout.TopToBottom if self.width() < 1320 else QBoxLayout.LeftToRight)
        if hasattr(self, "dashboard_metrics"):
            self.dashboard_metrics.setDirection(QBoxLayout.TopToBottom if self.width() < 900 else QBoxLayout.LeftToRight)
        if hasattr(self, "continue_activity"):
            self.continue_activity.setVisible(self.width() >= 1320)
        if hasattr(self, "context_rail") and self.current_view == "trabajo":
            wide_context = self.width() >= 1000
            self.context_rail.setVisible(wide_context)
            self.compact_context_bar.setVisible(not wide_context)
            self.workspace_subtitle.setVisible(wide_context)
            self.header_actions.setVisible(wide_context)
        elif hasattr(self, "compact_context_bar"):
            self.compact_context_bar.setVisible(False)
            self.workspace_subtitle.setVisible(True)
            self.header_actions.setVisible(True)
        for category, button in self.category_buttons.items():
            count = len(list(APP_REGISTRY)) if category == "Todas" else len([app for app in APP_REGISTRY if app.category == category])
            short = {
                "Todas": "Todo",
                "Excel / CSV": "CSV",
                "Palets y PDA": "PDA",
            }.get(category, category)
            button.setText(f"{short} ({count})" if compact else f"{category} ({count})")
        nav_text = {
            "bandeja": "B" if narrow else "Bandeja",
            "procesos": "Proc" if narrow else "Procesos",
            "salidas": "Sal" if narrow else "Salidas",
            "historial": "Hist" if narrow else "Historial",
            "ajustes": "Aj" if narrow else "Ajustes",
        }
        for key, button in self.nav_buttons.items():
            button.setText(nav_text.get(key, button.text()))
        for key, button in self.active_job_buttons.items():
            app = self._app_from_key(key)
            if app is not None:
                button.setText(self._compact_nav_text(app.title, narrow=narrow))

    def _column_count(self) -> int:
        available = self.width()
        if available < 760:
            return 1
        if available < 1180:
            return 2
        return 3

    def _enable_dashboard_drop(self, drop_target: QFrame) -> None:
        drop_target.setAcceptDrops(True)
        drop_target.setAccessibleDescription("Arrastra archivos para abrir el proceso compatible y cargarlos en la aplicacion.")

        def set_active(active: bool, *, _target=drop_target) -> None:
            _target.setProperty("active", active)
            _target.style().unpolish(_target)
            _target.style().polish(_target)

        def drag_enter(event, *, _target=drop_target) -> None:
            paths = self._paths_from_drop_event(event)
            if paths and self._app_for_dropped_paths(paths) is not None:
                set_active(True, _target=_target)
                event.acceptProposedAction()
            else:
                event.ignore()

        def drag_leave(event, *, _target=drop_target) -> None:
            set_active(False, _target=_target)
            event.accept()

        def drop(event, *, _target=drop_target) -> None:
            set_active(False, _target=_target)
            paths = self._paths_from_drop_event(event)
            if paths and self._open_dropped_paths(paths):
                event.acceptProposedAction()
            else:
                self.command_detail.setText("No se reconocen esos archivos. Elige un proceso manualmente para cargarlos.")
                event.ignore()

        drop_target.dragEnterEvent = drag_enter  # type: ignore[method-assign]
        drop_target.dragMoveEvent = drag_enter  # type: ignore[method-assign]
        drop_target.dragLeaveEvent = drag_leave  # type: ignore[method-assign]
        drop_target.dropEvent = drop  # type: ignore[method-assign]

    def _paths_from_drop_event(self, event) -> list[Path]:
        if not event.mimeData().hasUrls():
            return []
        paths: list[Path] = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.exists():
                paths.append(path)
        return paths

    def _open_dropped_paths(self, paths: list[Path]) -> bool:
        app = self._app_for_dropped_paths(paths)
        if app is None:
            return False
        self.open_app(app)
        window = self.app_pages.get(app.key)
        if window is None:
            return False
        if not handle_dropped_paths(window, paths):
            self.command_detail.setText(f"No se pudieron cargar los archivos en {app.title}. Usa los botones de carga del proceso.")
            return False
        self.command_detail.setText(f"Archivos cargados en {app.title}.")
        QTimer.singleShot(0, lambda window=window: focus_next_action(window))
        return True

    def _app_for_dropped_paths(self, paths: list[Path]) -> AppDefinition | None:
        suffixes = [path.suffix.lower() for path in paths]
        txts = [suffix for suffix in suffixes if suffix == ".txt"]
        csvs = [suffix for suffix in suffixes if suffix == ".csv"]
        excels = [suffix for suffix in suffixes if suffix in {".xlsx", ".xlsm", ".xls"}]
        if csvs and excels:
            return self._app_from_key("mermas")
        if txts and excels:
            return self._app_from_key("recepcion_maquilas")
        if len(txts) > 1:
            return self._app_from_key("control_recepcion_maquilas")
        if txts:
            return self._app_from_key("txt_csv")
        if excels:
            return self._app_from_key("exportar_precintos_excel")
        if csvs:
            return self._app_from_key("mermas")
        return None

    @staticmethod
    def _app_from_key(key: str) -> AppDefinition | None:
        return next((app for app in APP_REGISTRY if app.key == key), None)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif child_layout is not None:
                MainWindow._clear_layout(child_layout)


def run() -> int:
    import sys

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()
