from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.paths import resource_path
from suite_pyside6.core.reparto_merma_precintos import (
    AdjustmentResult,
    DomainValidationError,
    SourceReadResult,
    ValidationIssue,
    build_preview,
    calculate_adjustment,
    read_source_file,
    read_fac_files,
    validate_final_weight,
    validate_work_order,
    write_ax_csv,
    write_ax_csv_records,
)
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, labeled_field, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, polish_window, show_inline_message, sync_recommended_action
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


PREVIEW_LIMIT = 250


class RepartoMermaPrecintosWindow(QMainWindow):
    """Flujo operativo para repartir merma y exportar el CSV de AX."""

    def __init__(self) -> None:
        super().__init__()
        self.source_path: Path | None = None
        self.source_result: SourceReadResult | None = None
        self.adjustment: AdjustmentResult | None = None
        self.final_issues: tuple[ValidationIssue, ...] = ()
        self.export_path: Path | None = None
        self.state = "Inicial"
        self.fac_state = "Inicial"
        self.fac_export_path: Path | None = None
        self.setWindowTitle("Precintos Deshuesado")
        self.resize(1160, 740)
        self.setMinimumSize(760, 560)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar fichero", "Indicar peso final", "Revisar reparto", "Guardar CSV AX")

    def context_snapshot(self) -> dict[str, str] | None:
        """Estado que debe mostrar la barra lateral de la Suite por modo."""

        current = self.stack.currentWidget()
        if current is self.selection_page:
            return {"state": "Elige un modo", "next": "Seleccionar PDA o FAC", "alerts": "Sin avisos"}
        if current is not self.fac_page:
            return None
        result = self.fac_result
        if result is None:
            return {"state": "Sin archivos FAC", "next": "Añadir archivos CSV", "alerts": "Sin avisos"}
        if self.fac_state == "Error de exportación":
            return {"state": "Error de exportación", "next": "Elegir otra ubicación de salida", "alerts": "No se pudo generar el CSV"}
        if self.fac_state in {"Con incidencias", "Sin filas exportables"}:
            return {"state": "Requiere revisión", "next": "Corregir archivos FAC", "alerts": f"{len(result.issues)} incidencias"}
        if self.fac_state == "Orden de trabajo pendiente":
            return {"state": f"{len(result.records)} filas válidas", "next": "Introducir orden de trabajo", "alerts": "Orden pendiente"}
        if self.fac_state == "Exportación completada":
            return {"state": "CSV AX generado", "next": "Iniciar una nueva operación", "alerts": "Sin avisos"}
        return {"state": f"{len(result.records)} filas listas", "next": "Guardar CSV AX", "alerts": "Sin avisos"}

    def _build_ui(self) -> None:
        self.stack = QStackedWidget()
        self.selection_page = self._build_selection_page()
        self.pda_page = self._build_pda_page()
        self.fac_page = self._build_fac_page()
        self.stack.addWidget(self.selection_page)
        self.stack.addWidget(self.pda_page)
        self.stack.addWidget(self.fac_page)
        self.setCentralWidget(self.stack)

    def _build_pda_page(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        hero = QFrame()
        hero.setObjectName("ControlProductHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(14)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel("PDA · Precintos Deshuesado")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Distribuye el peso final proporcionalmente y prepara un CSV AX con orden de trabajo, precinto y peso.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        hero_layout.addLayout(copy, 1)
        hero_status = QFrame()
        hero_status.setObjectName("ControlHeroStatus")
        hero_status_layout = QVBoxLayout(hero_status)
        hero_status_layout.setContentsMargins(10, 8, 10, 8)
        hero_status_layout.setSpacing(3)
        kind = QLabel("SALIDA AX")
        kind.setObjectName("Overline")
        value = QLabel("Orden + precinto + peso")
        value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(kind)
        hero_status_layout.addWidget(value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)
        layout.addWidget(
            step_bar(
                "1 Cargar fichero  ->  2 Indicar peso final  ->  3 Revisar reparto  ->  4 Guardar CSV AX",
                plain=True,
            )
        )

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("flowWrapped", True)
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(8)
        self.pda_back_button = QPushButton("← Cambiar modo")
        self.pda_back_button.setToolTip("Volver a la selección PDA/FAC")
        self.pda_back_button.setAccessibleDescription("Vuelve a la pantalla para elegir entre PDA y FAC.")
        self.pda_back_button.clicked.connect(self.show_selection)
        actions_layout.addWidget(self.pda_back_button)
        command = QFrame()
        command.setObjectName("ControlCommandCopy")
        command_layout = QVBoxLayout(command)
        command_layout.setContentsMargins(0, 0, 0, 0)
        command_layout.setSpacing(2)
        command_label = QLabel("Siguiente acción")
        command_label.setObjectName("Overline")
        self.command_hint = QLabel("Cargar fichero")
        self.command_hint.setObjectName("ControlCommandTitle")
        self.command_hint.setWordWrap(True)
        command_layout.addWidget(command_label)
        command_layout.addWidget(self.command_hint)
        actions_layout.addWidget(command, 1)
        self.load_button = QPushButton("Cargar fichero")
        self.load_button.setProperty("primary", True)
        self.load_button.setAccessibleDescription("Selecciona un Excel de mensajes con precinto en el primer campo y peso en el tercero.")
        self.load_button.clicked.connect(self.select_file)
        self.clear_button = QPushButton("Reiniciar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.load_button)
        actions_layout.addWidget(self.clear_button)
        layout.addWidget(actions)

        self.summary = QLabel("Sin fichero cargado")
        self.summary.setObjectName("ResultLabel")
        self.summary.setAccessibleName("Resumen del fichero")
        layout.addWidget(self.summary)

        workspace = QFrame()
        workspace.setObjectName("ControlPilotWorkspace")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(10)

        preview_panel = QFrame()
        preview_panel.setObjectName("ControlPreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(8)
        preview_header = QHBoxLayout()
        preview_header.addWidget(section_label("Vista previa del reparto"))
        preview_header.addStretch(1)
        self.preview_count = control_pill("0 registros")
        preview_header.addWidget(self.preview_count)
        preview_layout.addLayout(preview_header)

        self.metrics_strip = QFrame()
        self.metrics_strip.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(4)
        self.metric_total = control_metric_pair(metrics_layout, 0, "Registros", "0")
        self.metric_weight = control_metric_pair(metrics_layout, 1, "Peso origen", "-")
        self.metric_final = control_metric_pair(metrics_layout, 2, "Peso final", "-")
        self.metric_loss = control_metric_pair(metrics_layout, 3, "Merma", "-")
        preview_layout.addWidget(self.metrics_strip)

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setAccessibleName("Vista previa de pesos ajustados por precinto")
        self.preview_table.setAccessibleDescription("Tabla de revisión de los pesos ajustados por fila.")
        self.preview_table.setHorizontalHeaderLabels(["Precinto", "Peso original", "Merma aplicada", "Peso ajustado"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.preview_table, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_layout.addWidget(section_label("Control del reparto"))
        self.rail_state = control_rail_label("Inicial", role="state")
        self.rail_detail = control_rail_label("Carga un Excel de mensajes para analizar sus precintos y pesos.")
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        self.rail_progress.setAccessibleName("Progreso del reparto de merma")
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)

        self.final_weight = QLineEdit()
        self.final_weight.setPlaceholderText("Ej.: 19.837,22")
        self.final_weight.setAccessibleDescription("Peso final en kilos. Se aceptan coma o punto decimal; AX exporta dos decimales.")
        self.final_weight.textChanged.connect(self._on_final_weight_changed)
        rail_layout.addWidget(labeled_field("Peso final", self.final_weight, compact=True))
        self.work_order = QLineEdit()
        self.work_order.setPlaceholderText("Ej.: OT-001234")
        self.work_order.setAccessibleDescription("Orden obligatoria para el CSV AX. Se conserva como texto, incluidos los ceros iniciales.")
        self.work_order.textChanged.connect(self._on_work_order_changed)
        rail_layout.addWidget(labeled_field("Orden de trabajo", self.work_order, compact=True))
        rail_layout.addWidget(section_label("Fichero"))
        self.file_detail = control_rail_label("Sin fichero seleccionado")
        rail_layout.addWidget(self.file_detail)
        rail_layout.addWidget(section_label("Formato admitido"))
        rail_layout.addWidget(control_rail_label("Excel .xlsx; cada mensaje en la columna A; precinto en el campo 1 y peso en el campo 3."))

        self.export_button = QPushButton("Guardar CSV AX")
        self.export_button.clicked.connect(self.save_csv_dialog)
        self.export_button.setAccessibleDescription("Guarda un CSV AX con la orden de trabajo, el precinto y el peso ajustado.")
        rail_layout.addWidget(self.export_button)
        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Inicial")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setAccessibleName("Estado del proceso")
        self.status.setAccessibleDescription("Estado actual del proceso de reparto.")
        self.status.setProperty("liveRegion", "polite")
        self.status.setProperty("keepEmbeddedStatus", True)
        layout.addWidget(self.status)
        return root

    def _build_selection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(42, 34, 42, 34)
        layout.setSpacing(18)
        title = QLabel("Precintos Deshuesado")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Elige el origen de los datos para preparar el CSV compatible con AX.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        layout.addStretch(1)
        layout.addWidget(title, 0, Qt.AlignHCenter)
        layout.addWidget(subtitle, 0, Qt.AlignHCenter)
        cards = QHBoxLayout()
        cards.setSpacing(18)
        self.pda_mode_button = self._mode_card(
            "PDA",
            "Procesar ficheros procedentes de PDA y realizar el reparto proporcional del peso final.",
            self.show_pda,
        )
        self.fac_mode_button = self._mode_card(
            "FAC",
            "Procesar uno o varios ficheros de deshuesado procedentes de FAC.",
            self.show_fac,
        )
        cards.addWidget(self.pda_mode_button)
        cards.addWidget(self.fac_mode_button)
        layout.addLayout(cards)
        layout.addStretch(2)
        return page

    @staticmethod
    def _mode_card(title: str, description: str, callback) -> QPushButton:
        button = QPushButton(f"{title}\n\n{description}")
        button.setObjectName("PrimaryButton")
        button.setProperty("primary", True)
        button.setMinimumSize(300, 180)
        button.setAccessibleName(f"Abrir modo {title}")
        button.setAccessibleDescription(description)
        button.setToolTip(f"Abrir modo {title}")
        button.setFocusPolicy(Qt.StrongFocus)
        button.clicked.connect(callback)
        return button

    def _build_fac_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        hero = QFrame()
        hero.setObjectName("ControlProductHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        copy = QVBoxLayout()
        title = QLabel("FAC · Precintos Deshuesado")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Carga CSV de deshuesado. Se exportan únicamente las filas marcadas como SI, sin recalcular su merma.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        hero_layout.addLayout(copy, 1)
        hero_status = QFrame()
        hero_status.setObjectName("ControlHeroStatus")
        hero_status_layout = QVBoxLayout(hero_status)
        hero_status_layout.setContentsMargins(10, 8, 10, 8)
        hero_status_layout.setSpacing(3)
        kind = QLabel("SALIDA AX")
        kind.setObjectName("Overline")
        value = QLabel("Orden + precinto + peso")
        value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(kind)
        hero_status_layout.addWidget(value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)
        layout.addWidget(
            step_bar(
                "1 Cargar archivos  ->  2 Procesar y validar  ->  3 Indicar orden  ->  4 Guardar CSV AX",
                steps=(
                    "Cargar archivos",
                    "Procesar y validar",
                    "Indicar orden de trabajo",
                    "Guardar CSV AX",
                ),
            )
        )

        toolbar = QFrame()
        toolbar.setObjectName("Toolbar")
        # Esta barra permanece como QHBoxLayout: en una página incrustada no
        # debe colapsar ni compactar las acciones críticas de FAC.
        toolbar.setProperty("flowWrapped", True)
        toolbar.setProperty("preserveButtonText", True)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(8)
        self.fac_back_button = QPushButton("← Cambiar modo")
        self.fac_back_button.setToolTip("Volver a la selección PDA/FAC")
        self.fac_back_button.setAccessibleDescription("Vuelve a la pantalla para elegir entre PDA y FAC.")
        self.fac_back_button.clicked.connect(self.show_selection)
        command = QFrame()
        command.setObjectName("ControlCommandCopy")
        command_layout = QVBoxLayout(command)
        command_layout.setContentsMargins(0, 0, 0, 0)
        command_layout.setSpacing(2)
        command_label = QLabel("Siguiente acción")
        command_label.setObjectName("Overline")
        self.fac_command_hint = QLabel("Añadir archivos CSV")
        self.fac_command_hint.setObjectName("ControlCommandTitle")
        self.fac_command_hint.setWordWrap(True)
        command_layout.addWidget(command_label)
        command_layout.addWidget(self.fac_command_hint)
        self.fac_add_button = QPushButton("Añadir archivos CSV")
        self.fac_add_button.setProperty("primary", True)
        self.fac_add_button.setAccessibleDescription("Selecciona uno o varios archivos CSV FAC.")
        self.fac_add_button.clicked.connect(self.select_fac_files)
        self.fac_clear_button = QPushButton("Limpiar")
        self.fac_clear_button.setToolTip("Quita los archivos FAC y la orden de trabajo actual.")
        self.fac_clear_button.setAccessibleDescription("Limpia toda la operación FAC actual.")
        self.fac_clear_button.clicked.connect(self.clear_fac)
        toolbar_layout.addWidget(self.fac_back_button)
        toolbar_layout.addWidget(command, 1)
        toolbar_layout.addWidget(self.fac_add_button)
        toolbar_layout.addWidget(self.fac_clear_button)
        layout.addWidget(toolbar)

        workspace = QFrame()
        workspace.setObjectName("ControlPilotWorkspace")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(10)

        files_panel = QFrame()
        files_panel.setObjectName("ControlPreviewPanel")
        files_layout = QVBoxLayout(files_panel)
        files_layout.setContentsMargins(12, 10, 12, 10)
        files_layout.setSpacing(8)
        files_header = QHBoxLayout()
        files_header.addWidget(section_label("Vista previa de exportación"))
        files_header.addStretch(1)
        self.fac_count = control_pill("0 archivos")
        files_header.addWidget(self.fac_count)
        files_layout.addLayout(files_header)
        self.fac_summary = QLabel("Selecciona uno o varios CSV de FAC.")
        self.fac_summary.setObjectName("ResultLabel")
        self.fac_summary.setWordWrap(True)
        self.fac_summary.setAccessibleName("Resumen de los archivos FAC")
        files_layout.addWidget(self.fac_summary)
        self.fac_metrics_strip = QFrame()
        self.fac_metrics_strip.setObjectName("ControlMetricStrip")
        fac_metrics_layout = QGridLayout(self.fac_metrics_strip)
        fac_metrics_layout.setContentsMargins(8, 7, 8, 7)
        fac_metrics_layout.setHorizontalSpacing(8)
        fac_metrics_layout.setVerticalSpacing(4)
        self.fac_metric_files = control_metric_pair(fac_metrics_layout, 0, "Archivos", "0")
        self.fac_metric_records = control_metric_pair(fac_metrics_layout, 1, "Filas SI", "0")
        self.fac_metric_excluded = control_metric_pair(fac_metrics_layout, 2, "Filas NO", "0")
        self.fac_metric_weight = control_metric_pair(fac_metrics_layout, 3, "Peso FAC", "-")
        files_layout.addWidget(self.fac_metrics_strip)
        self.fac_files_table = QTableWidget(0, 3)
        self.fac_files_table.setHorizontalHeaderLabels(["Archivo", "Estado de lectura", "Acción"])
        self.fac_files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.fac_files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.fac_files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.fac_files_table.setColumnWidth(2, 112)
        self.fac_files_table.setAccessibleName("Archivos FAC seleccionados")
        self.fac_files_table.setAccessibleDescription("Lista ordenada de archivos FAC. Cada fila dispone de una acción Eliminar.")
        files_layout.addWidget(self.fac_files_table, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(260)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_layout.addWidget(section_label("Control del proceso"))
        self.fac_rail_state = control_rail_label("Inicial", role="state")
        self.fac_rail_detail = control_rail_label("Añade uno o varios CSV de deshuesado para validar sus filas.")
        self.fac_rail_progress = QProgressBar()
        self.fac_rail_progress.setObjectName("ControlProgress")
        self.fac_rail_progress.setRange(0, 100)
        self.fac_rail_progress.setTextVisible(True)
        self.fac_rail_progress.setAccessibleName("Progreso de la consolidación FAC")
        rail_layout.addWidget(self.fac_rail_state)
        rail_layout.addWidget(self.fac_rail_detail)
        rail_layout.addWidget(self.fac_rail_progress)
        self.fac_work_order = QLineEdit()
        self.fac_work_order.setPlaceholderText("Ej.: OT-001234")
        self.fac_work_order.setAccessibleDescription("Orden de trabajo obligatoria. Se conserva como texto, incluidos los ceros iniciales.")
        self.fac_work_order.textChanged.connect(self._on_fac_work_order_changed)
        rail_layout.addWidget(labeled_field("Orden de trabajo", self.fac_work_order, compact=True))
        rail_layout.addWidget(section_label("Archivos"))
        self.fac_file_detail = control_rail_label("Sin archivos seleccionados")
        rail_layout.addWidget(self.fac_file_detail)
        rail_layout.addWidget(section_label("Formato de salida"))
        rail_layout.addWidget(control_rail_label("CSV AX: orden, precinto y peso; sin recalcular la merma FAC."))
        rail_layout.addStretch(1)
        self.fac_export_button = QPushButton("Guardar CSV AX")
        self.fac_export_button.setProperty("primary", True)
        self.fac_export_button.setToolTip("Genera el CSV AX con la orden de trabajo visible.")
        self.fac_export_button.setAccessibleDescription("Guarda el CSV AX consolidado de los archivos FAC seleccionados.")
        self.fac_export_button.clicked.connect(self.save_fac_csv_dialog)
        rail_layout.addWidget(self.fac_export_button)

        workspace_layout.addWidget(files_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)
        self.fac_status = QLabel("Inicial")
        self.fac_status.setObjectName("StatusLabel")
        self.fac_status.setWordWrap(True)
        self.fac_status.setProperty("liveRegion", "polite")
        self.fac_status.setProperty("keepEmbeddedStatus", True)
        layout.addWidget(self.fac_status)
        self.fac_paths: list[Path] = []
        self.fac_result = None
        self._refresh_fac()
        return page

    def show_selection(self) -> None:
        self.stack.setCurrentWidget(self.selection_page)
        self._refresh_fac()
        self.pda_mode_button.setFocus(Qt.OtherFocusReason)

    def show_pda(self) -> None:
        self.stack.setCurrentWidget(self.pda_page)
        self.load_button.setFocus(Qt.OtherFocusReason)

    def show_fac(self) -> None:
        self.stack.setCurrentWidget(self.fac_page)
        self._refresh_fac()
        self.fac_add_button.setFocus(Qt.OtherFocusReason)

    def select_fac_files(self) -> None:
        paths = open_files(self, "reparto_merma_precintos/fac_input", "Selecciona archivos FAC", "CSV (*.csv);;Todos (*.*)")
        if paths:
            self.add_fac_paths(paths)

    def add_fac_paths(self, paths: list[Path]) -> None:
        existing = {str(path.resolve()).casefold() for path in self.fac_paths}
        for path in paths:
            key = str(path.resolve()).casefold()
            if key not in existing:
                self.fac_paths.append(path)
                existing.add(key)
        self.fac_export_path = None
        self._analyse_fac()

    def remove_fac_path(self, path: Path) -> None:
        self.fac_paths = [candidate for candidate in self.fac_paths if candidate != path]
        self._analyse_fac()

    def clear_fac(self) -> None:
        if not confirm_discard_work(self, "Limpiar archivos FAC"):
            return
        self.fac_paths = []
        self.fac_result = None
        self.fac_export_path = None
        self.fac_state = "Inicial"
        self.fac_work_order.blockSignals(True)
        self.fac_work_order.clear()
        self.fac_work_order.blockSignals(False)
        self._refresh_fac()

    def _on_fac_work_order_changed(self, _text: str) -> None:
        if self.fac_state == "Exportación completada":
            self.fac_export_path = None
        if self.fac_state not in {"Analizando", "Generando CSV AX"}:
            self._set_fac_state_from_data()
        self._refresh_fac()

    def _analyse_fac(self) -> None:
        if not self.fac_paths:
            self.fac_result = None
            self.fac_state = "Inicial"
            self._refresh_fac()
            return
        self.fac_state = "Analizando"
        self._refresh_fac()
        self.fac_result = read_fac_files(self.fac_paths)
        self.fac_export_path = None
        self._set_fac_state_from_data()
        self._refresh_fac()

    def _refresh_fac(self) -> None:
        result = self.fac_result
        with bulk_table_update(self.fac_files_table):
            self.fac_files_table.setRowCount(len(self.fac_paths))
            for row, path in enumerate(self.fac_paths):
                name = QTableWidgetItem(path.name)
                name.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                has_path_issues = result is not None and any(path.name in issue.message for issue in result.issues)
                status = "Pendiente" if result is None else ("Con incidencias" if has_path_issues else "Leído correctamente")
                status_item = QTableWidgetItem(status)
                status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                remove = QPushButton("Eliminar")
                remove.setMinimumWidth(96)
                remove.setToolTip(f"Quitar {path.name} de la operación FAC")
                remove.setAccessibleName(f"Eliminar {path.name}")
                remove.setAccessibleDescription(f"Elimina {path.name} de la selección FAC.")
                remove.clicked.connect(lambda _checked=False, selected=path: self.remove_fac_path(selected))
                self.fac_files_table.setItem(row, 0, name)
                self.fac_files_table.setItem(row, 1, status_item)
                self.fac_files_table.setCellWidget(row, 2, remove)
        self.fac_clear_button.setEnabled(bool(self.fac_paths) or bool(self.fac_work_order.text().strip()))
        work_order = validate_work_order(self.fac_work_order.text())
        can_export = self.fac_state in {"Listo para exportar", "Error de exportación"} and bool(result and result.is_valid and work_order.is_valid)
        self.fac_export_button.setEnabled(can_export)
        self.fac_export_button.setProperty("primary", can_export)
        self.fac_add_button.setProperty("primary", not can_export)
        for button in (self.fac_add_button, self.fac_export_button):
            button.style().unpolish(button)
            button.style().polish(button)
        update_count_label(self.fac_count, len(self.fac_paths), len(self.fac_paths), "archivos")
        self.fac_metric_files.setText(str(len(self.fac_paths)))
        self.fac_metric_records.setText(str(len(result.records) if result is not None else 0))
        self.fac_metric_excluded.setText(str(result.excluded_no_rows if result is not None else 0))
        self.fac_metric_weight.setText(self._format_weight(result.total_weight) if result is not None else "-")
        self.fac_file_detail.setText(self._fac_file_text())
        if result is None:
            self.fac_summary.setText("Selecciona uno o varios CSV de FAC.")
            self._refresh_fac_pilot_state()
            self._sync_fac_recommended_action()
            return
        self.fac_summary.setText(
            f"{len(self.fac_paths)} archivo(s) | {result.ignored_empty_rows} filas vacías ignoradas | "
            f"{result.excluded_no_rows} filas NO excluidas | {len(result.records)} filas SI exportables | "
            f"peso total: {self._format_weight(result.total_weight)}"
        )
        if self.fac_state == "Con incidencias":
            preview = "\n".join(f"• {issue.message}" for issue in result.issues[:5])
            extra = f"\n... y {len(result.issues) - 5} incidencia(s) más." if len(result.issues) > 5 else ""
            self.fac_status.setText(f"No se generará un CSV parcial hasta corregir {len(result.issues)} incidencia(s):\n{preview}{extra}")
        elif self.fac_state == "Sin filas exportables":
            self.fac_status.setText("No hay filas SI para exportar.")
        elif self.fac_state == "Orden de trabajo pendiente":
            self.fac_status.setText("Datos FAC validados. Introduce la orden de trabajo para activar el guardado.")
        elif self.fac_state == "Listo para exportar":
            self.fac_status.setText("Datos FAC validados y listos para generar el CSV AX.")
        elif self.fac_state == "Generando CSV AX":
            self.fac_status.setText("Generando y validando el CSV AX. Espera a que finalice el proceso.")
        elif self.fac_state == "Exportación completada":
            name = self.fac_export_path.name if self.fac_export_path is not None else "CSV AX"
            self.fac_status.setText(f"Exportación completada: {name} ({len(result.records)} registros).")
        self._refresh_fac_pilot_state()
        self._sync_fac_recommended_action()

    def save_fac_csv_dialog(self) -> None:
        if self.fac_result is None or not self.fac_result.is_valid:
            return
        validation = validate_work_order(self.fac_work_order.text())
        if not validation.is_valid:
            self.fac_status.setText(validation.issues[0].message)
            self.fac_work_order.setFocus(Qt.OtherFocusReason)
            return
        path = save_file(self, "reparto_merma_precintos/fac_export_csv", "Guardar CSV AX", "precintos_deshuesado_fac.csv", "CSV (*.csv);;Todos (*.*)")
        if path is not None:
            self.save_fac_path(path, validation.value)

    def save_fac_path(self, path: Path, work_order: str | None) -> None:
        if self.fac_result is None or not self.fac_result.is_valid:
            return
        validation = validate_work_order(work_order)
        if not validation.is_valid:
            self.fac_status.setText(validation.issues[0].message)
            return
        self.fac_state = "Generando CSV AX"
        self._refresh_fac()
        try:
            write_ax_csv_records(path, [record.as_ax_record() for record in self.fac_result.records], validation.value)
        except (OSError, DomainValidationError, ValueError) as exc:
            self.fac_state = "Error de exportación"
            self.fac_status.setText(f"No se pudo generar el CSV AX: {exc}")
            self._refresh_fac()
        else:
            self.fac_export_path = path
            self.fac_state = "Exportación completada"
            self._refresh_fac()

    def _set_fac_state_from_data(self) -> None:
        """Deriva la etapa FAC sin alterar su lectura ni su exportación."""

        result = self.fac_result
        if result is None:
            self.fac_state = "Inicial"
        elif result.issues:
            self.fac_state = "Con incidencias"
        elif not result.records:
            self.fac_state = "Sin filas exportables"
        elif not validate_work_order(self.fac_work_order.text()).is_valid:
            self.fac_state = "Orden de trabajo pendiente"
        else:
            self.fac_state = "Listo para exportar"

    def _fac_pilot_state(self) -> tuple[str, str, int]:
        states = {
            "Exportación completada": ("CSV AX generado.", 100),
            "Generando CSV AX": ("Escribiendo el CSV compatible con AX.", 92),
            "Listo para exportar": ("Archivos y orden validados. Puedes guardar el CSV AX.", 85),
            "Orden de trabajo pendiente": ("Indica la orden de trabajo para activar la exportación.", 70),
            "Sin filas exportables": ("Añade un archivo con al menos una fila marcada como SI.", 50),
            "Con incidencias": ("Corrige las filas indicadas antes de generar el CSV AX.", 50),
            "Error de exportación": ("Revisa la ubicación de salida e inténtalo de nuevo.", 85),
            "Analizando": ("Leyendo formato, filas y validaciones de los archivos FAC.", 20),
            "Inicial": ("Añade uno o varios CSV de deshuesado para validar sus filas.", 0),
        }
        detail, progress = states.get(self.fac_state, states["Inicial"])
        return self.fac_state, detail, progress

    def _fac_next_action_text(self) -> str:
        if self.fac_state == "Inicial":
            return "Añadir archivos CSV"
        if self.fac_state == "Error de exportación":
            return "Elegir otra ubicación de salida"
        if self.fac_state in {"Con incidencias", "Sin filas exportables"}:
            return "Corregir archivos FAC"
        if self.fac_state == "Orden de trabajo pendiente":
            return "Indicar orden de trabajo"
        if self.fac_state == "Exportación completada":
            return "Iniciar nueva operación"
        return "Guardar CSV AX"

    def _refresh_fac_pilot_state(self) -> None:
        state, detail, progress = self._fac_pilot_state()
        self.fac_rail_state.setText(state)
        self.fac_rail_detail.setText(detail)
        self.fac_rail_progress.setValue(progress)

    def _sync_fac_recommended_action(self) -> None:
        next_action = self._fac_next_action_text()
        self.fac_command_hint.setText(next_action)
        action_buttons = (self.fac_add_button, self.fac_export_button, self.fac_clear_button)
        for button in action_buttons:
            button.setProperty("recommended", False)
        if next_action in {"Añadir archivos CSV", "Corregir archivos FAC", "Iniciar nueva operación"}:
            self.fac_add_button.setProperty("recommended", True)
        elif next_action in {"Guardar CSV AX", "Elegir otra ubicación de salida"}:
            self.fac_export_button.setProperty("recommended", True)
        for button in action_buttons:
            button.style().unpolish(button)
            button.style().polish(button)

    def _fac_file_text(self) -> str:
        if not self.fac_paths:
            return "Sin archivos seleccionados"
        names = [path.name for path in self.fac_paths]
        if len(names) == 1:
            return names[0]
        return f"{names[0]}\n+ {len(names) - 1} archivo(s) más"

    def select_file(self) -> None:
        path = open_file(
            self,
            "reparto_merma_precintos/input",
            "Selecciona fichero de pesos",
            "Excel (*.xlsx);;Todos (*.*)",
        )
        if path is not None:
            self.queue_load_path(path)

    def set_files(self, paths: list[Path]) -> None:
        """Entrada usada por el manejo global de arrastrar y soltar."""
        if paths:
            self.queue_load_path(paths[0])

    def queue_load_path(self, path: Path) -> None:
        if self.source_path is not None and path != self.source_path:
            if not confirm_discard_work(self, "Seleccionar otro fichero"):
                return
        self.adjustment = None
        self.final_issues = ()
        self.export_path = None
        self.state = "Cargando"
        self.status.setText(f"Cargando fichero: {path.name}")
        self._refresh()
        QTimer.singleShot(0, lambda selected_path=path: self.load_path(selected_path))

    def load_path(self, path: Path) -> None:
        self.source_path = path
        self.export_path = None
        self.adjustment = None
        self.final_issues = ()
        self.final_weight.blockSignals(True)
        self.final_weight.clear()
        self.final_weight.blockSignals(False)
        self.work_order.blockSignals(True)
        self.work_order.clear()
        self.work_order.blockSignals(False)
        self.state = "Analizando"
        self.status.setText(f"Analizando fichero: {path.name}")
        self.source_result = read_source_file(path)
        self._recalculate()

    def _on_final_weight_changed(self, _text: str) -> None:
        self.export_path = None
        self._recalculate()

    def _on_work_order_changed(self, _text: str) -> None:
        self.export_path = None
        self._recalculate()

    def _recalculate(self) -> None:
        self.adjustment = None
        self.final_issues = ()
        if self.source_result is None:
            self.state = "Inicial"
        elif self.source_result.errors:
            self.state = "Con errores"
        elif not self.final_weight.text().strip():
            self.state = "Fichero analizado"
        else:
            validation = validate_final_weight(self.final_weight.text(), self.source_result.total_weight)
            self.final_issues = validation.issues
            if not validation.is_valid:
                self.state = "Con errores"
            else:
                try:
                    self.adjustment = calculate_adjustment(self.source_result, self.final_weight.text())
                except (DomainValidationError, ValueError) as exc:
                    self.final_issues = exc.issues if isinstance(exc, DomainValidationError) else (ValidationIssue("CALCULATION_ERROR", str(exc)),)
                    self.state = "Con errores"
                else:
                    self.state = "Listo para exportar" if validate_work_order(self.work_order.text()).is_valid else "Orden de trabajo pendiente"
        self._refresh()

    def save_csv_dialog(self) -> None:
        if self.adjustment is None or not self.export_button.isEnabled():
            return
        path = save_file(
            self,
            "reparto_merma_precintos/export_csv",
            "Guardar CSV AX",
            "reparto_merma_precintos.csv",
            "CSV (*.csv);;Todos (*.*)",
        )
        if path is not None:
            self.save_path(path)

    def save_path(self, path: Path, work_order: str | None = None) -> None:
        if self.adjustment is None:
            return
        if work_order is None:
            work_order = self.work_order.text()
        work_order_validation = validate_work_order(work_order)
        if not work_order_validation.is_valid:
            self.final_issues = work_order_validation.issues
            self.status.setText(work_order_validation.issues[0].message)
            show_inline_message(self, "error", work_order_validation.issues[0].message)
            self._refresh()
            return
        self.state = "Generando archivo"
        self._refresh()
        try:
            write_ax_csv(path, self.adjustment, work_order_validation.value)
        except (OSError, DomainValidationError, ValueError) as exc:
            self.state = "Error de exportación"
            self.final_issues = (ValidationIssue("EXPORT_ERROR", f"No se pudo generar el CSV: {exc}"),)
            self.status.setText(f"Error de exportación: {exc}")
            show_inline_message(self, "error", str(exc))
        else:
            self.export_path = path
            self.state = "Exportación completada"
            self.status.setText(f"CSV AX guardado: {path.name}")
            show_inline_message(self, "success", f"CSV AX guardado: {path.name}")
        self._refresh()

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar reparto"):
            return
        self.source_path = None
        self.source_result = None
        self.adjustment = None
        self.final_issues = ()
        self.export_path = None
        self.final_weight.blockSignals(True)
        self.final_weight.clear()
        self.final_weight.blockSignals(False)
        self.work_order.blockSignals(True)
        self.work_order.clear()
        self.work_order.blockSignals(False)
        self.state = "Inicial"
        self.status.setText("Inicial")
        self._refresh()
        self.load_button.setFocus(Qt.OtherFocusReason)

    def _refresh(self) -> None:
        result = self.source_result
        total_records = len(result.records) if result is not None else 0
        total_weight = result.total_weight if result is not None else None
        final_weight = self.adjustment.final_weight if self.adjustment is not None else None
        loss_text = "-"
        if self.adjustment is not None:
            loss_text = f"{self._format_weight(self.adjustment.absolute_loss)} ({self._format_percentage(self.adjustment.loss_percentage)})"
        self.metric_total.setText(str(total_records))
        self.metric_weight.setText(self._format_weight(total_weight) if total_weight is not None else "-")
        self.metric_final.setText(self._format_weight(final_weight))
        self.metric_loss.setText(loss_text)
        for label, value in (
            (self.metric_total, total_records),
            (self.metric_weight, self._format_weight(total_weight) if total_weight is not None else "-"),
            (self.metric_final, self._format_weight(final_weight)),
            (self.metric_loss, loss_text),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")
        self.file_detail.setText(self._file_text())
        self.summary.setText(self._summary_text())
        self._populate_preview_table()
        can_export = (
            self.state in {"Listo para exportar", "Error de exportación"}
            and self.adjustment is not None
            and self.adjustment.adjusted_total == self.adjustment.final_weight
        )
        self.export_button.setEnabled(can_export)
        self.clear_button.setEnabled(result is not None or bool(self.final_weight.text()) or bool(self.work_order.text()))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _populate_preview_table(self) -> None:
        rows: list[tuple[str, str, str, str]] = []
        if self.source_result is not None:
            preview = build_preview(self.adjustment) if self.adjustment is not None else None
            adjusted = {row.line_number: row for row in preview.rows} if preview is not None else {}
            percentage = self.adjustment.loss_percentage if self.adjustment is not None else None
            for record in self.source_result.records[:PREVIEW_LIMIT]:
                row = adjusted.get(record.line_number)
                rows.append((
                    record.precinto,
                    self._format_weight(record.peso_original),
                    self._format_percentage(percentage) if percentage is not None else "-",
                    self._format_weight(row.peso_ajustado) if row is not None else "-",
                ))
        with bulk_table_update(self.preview_table):
            self.preview_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.preview_table.setItem(row_index, column, item)
        total = len(self.source_result.records) if self.source_result is not None else 0
        update_count_label(self.preview_count, len(rows), total, "registros")

    def _refresh_pilot_state(self) -> None:
        state, detail, progress = self._pilot_state()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleDescription(f"Progreso estimado: {progress} por ciento.")
        if self.state != "Exportación completada":
            self.status.setText(state)

    def _pilot_state(self) -> tuple[str, str, int]:
        states = {
            "Exportación completada": ("El CSV AX se ha guardado y validado correctamente.", 100),
            "Error de exportación": (self._technical_error_text("No se pudo generar el CSV."), 85),
            "Generando archivo": ("Generando y validando los bytes del CSV AX.", 90),
            "Con errores": (self._technical_error_text("Corrige el fichero o el peso final antes de exportar."), 45),
            "Listo para exportar": ("La suma ajustada coincide exactamente con el peso final.", 85),
            "Orden de trabajo pendiente": ("Introduce la orden de trabajo para activar el guardado del CSV AX.", 75),
            "Fichero analizado": ("Introduce el peso final para calcular el reparto.", 55),
            "Analizando": ("Leyendo formato, registros y validaciones.", 20),
            "Cargando": ("Preparando el fichero para su análisis.", 10),
            "Inicial": ("Carga un Excel de mensajes para analizar sus precintos y pesos.", 0),
        }
        detail, progress = states.get(self.state, states["Inicial"])
        return self.state, detail, progress

    def _next_action_text(self) -> str:
        if self.source_result is None:
            return "Cargar fichero"
        if self.state == "Error de exportación":
            return "Elegir otra ubicación de salida"
        if self._blocking_errors():
            return "Corregir el fichero o el peso final"
        if self.adjustment is None:
            return "Indicar peso final"
        if self.state == "Orden de trabajo pendiente":
            return "Indicar orden de trabajo"
        return "Guardar CSV AX"

    def _sync_recommended_action(self) -> None:
        next_action = self._next_action_text()
        sync_recommended_action(
            self,
            next_action,
            {
                "Cargar fichero": self.load_button,
                "Guardar CSV AX": self.export_button,
                "Elegir otra ubicación de salida": self.export_button,
            },
            (self.load_button, self.export_button, self.clear_button),
        )
        # La ventana contiene dos barras de comando (PDA y FAC). El helper
        # compartido resuelve por objectName y puede encontrar la de FAC;
        # actualizamos explícitamente la visible del flujo PDA.
        self.command_hint.setText(next_action)
        self.command_hint.setAccessibleDescription(f"Siguiente acción recomendada: {next_action}")

    def _blocking_errors(self) -> bool:
        source_errors = self.source_result.errors if self.source_result is not None else ()
        return bool(source_errors or any(issue.severity == "error" for issue in self.final_issues))

    def _summary_text(self) -> str:
        if self.source_result is None:
            return "Sin fichero cargado"
        name = self.source_path.name if self.source_path is not None else "Fichero"
        return f"{name} | {len(self.source_result.records)} registros"

    def _file_text(self) -> str:
        if self.source_path is None or self.source_result is None:
            return "Sin fichero seleccionado"
        source_format = self.source_result.source_format
        if source_format is None:
            return f"{self.source_path.name}\nFormato no válido"
        header = "con encabezado de mensaje" if source_format.has_message_header else "sin encabezado de mensaje"
        return f"{self.source_path.name}\nHoja {source_format.worksheet}, columna {source_format.column}, {header}"

    def _technical_error_text(self, fallback: str) -> str:
        source_errors = self.source_result.errors if self.source_result is not None else ()
        issue = next(iter(source_errors or self.final_issues), None)
        return issue.message if issue is not None else fallback

    @staticmethod
    def _format_weight(value: Decimal | None) -> str:
        if value is None:
            return "-"
        return format(value.quantize(Decimal("0.01")), ".2f").replace(".", ",")

    @staticmethod
    def _format_percentage(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), ".2f").replace(".", ",") + " %"

    def flow_state(self) -> tuple[int, bool, bool]:
        if self.stack.currentWidget() is self.fac_page:
            if self.fac_state == "Exportación completada":
                return 4, False, True
            if self.fac_state == "Error de exportación":
                return 4, True, False
            if self.fac_state in {"Con incidencias", "Sin filas exportables"}:
                return 2, True, False
            if self.fac_state in {"Listo para exportar", "Generando CSV AX"}:
                return 4, False, False
            if self.fac_state == "Orden de trabajo pendiente":
                return 2, False, False
            return 1, False, False
        if self.state == "Exportación completada":
            return 4, False, True
        if self.state in {"Con errores", "Error de exportación"}:
            return 2, True, False
        if self.adjustment is not None:
            return 4, False, False
        if self.source_result is not None:
            return 2, False, False
        return 1, False, False
