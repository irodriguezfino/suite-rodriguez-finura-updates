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
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
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
    validate_final_weight,
    write_ax_csv,
)
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, labeled_field, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_file, save_file
from suite_pyside6.ui.polish import polish_window, show_inline_message, sync_recommended_action
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
        self.setWindowTitle("Reparto de Merma por Precintos")
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

    def _build_ui(self) -> None:
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
        title = QLabel("Reparto de Merma por Precintos")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Distribuye el peso final proporcionalmente y prepara un CSV de dos columnas para AX.")
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
        value = QLabel("Precinto + peso")
        value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(kind)
        hero_status_layout.addWidget(value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)
        layout.addWidget(step_bar("1 Cargar fichero  ->  2 Indicar peso final  ->  3 Revisar reparto  ->  4 Guardar CSV AX"))

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("controlCommand", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(8)
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
        self.load_button.setAccessibleDescription("Selecciona un TXT o CSV con precinto en la primera columna y peso en la tercera.")
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
        self.metric_valid = control_metric_pair(metrics_layout, 1, "Válidos", "0")
        self.metric_errors = control_metric_pair(metrics_layout, 2, "Errores", "0")
        self.metric_weight = control_metric_pair(metrics_layout, 3, "Peso origen", "-")
        preview_layout.addWidget(self.metrics_strip)

        self.preview_table = QTableWidget(0, 5)
        self.preview_table.setAccessibleName("Vista previa de pesos ajustados por precinto")
        self.preview_table.setAccessibleDescription("Tabla de revisión de los registros válidos y de las incidencias por fila.")
        self.preview_table.setHorizontalHeaderLabels(["Precinto", "Peso original", "Merma aplicada", "Peso ajustado", "Estado"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
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
        self.rail_detail = control_rail_label("Carga un TXT o CSV para analizar sus precintos y pesos.")
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
        rail_layout.addWidget(section_label("Fichero"))
        self.file_detail = control_rail_label("Sin fichero seleccionado")
        rail_layout.addWidget(self.file_detail)
        rail_layout.addWidget(section_label("Formato admitido"))
        rail_layout.addWidget(control_rail_label("TXT o CSV; ; como separador; precinto en la columna 1 y peso en la columna 3."))

        self.export_button = QPushButton("Guardar CSV AX")
        self.export_button.clicked.connect(self.save_csv_dialog)
        self.export_button.setAccessibleDescription("Guarda un CSV AX con solo precinto y peso ajustado.")
        rail_layout.addWidget(self.export_button)
        rail_layout.addWidget(section_label("Incidencias y avisos"))
        self.issues = QPlainTextEdit()
        self.issues.setObjectName("OutputText")
        self.issues.setAccessibleName("Incidencias y avisos de validación")
        self.issues.setReadOnly(True)
        self.issues.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.issues.setMinimumHeight(92)
        self.issues.setMaximumHeight(180)
        rail_layout.addWidget(self.issues, 1)

        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Inicial")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setAccessibleName("Estado del proceso")
        self.status.setAccessibleDescription("Estado actual del proceso de reparto.")
        self.status.setProperty("liveRegion", "polite")
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def select_file(self) -> None:
        path = open_file(
            self,
            "reparto_merma_precintos/input",
            "Selecciona fichero de pesos",
            "TXT o CSV (*.txt *.csv);;TXT (*.txt);;CSV (*.csv);;Todos (*.*)",
        )
        if path is not None:
            self.queue_load_path(path)

    def set_files(self, paths: list[Path]) -> None:
        """Entrada usada por el manejo global de arrastrar y soltar."""
        if paths:
            self.queue_load_path(paths[0])

    def queue_load_path(self, path: Path) -> None:
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
        self.state = "Analizando"
        self.status.setText(f"Analizando fichero: {path.name}")
        self.source_result = read_source_file(path)
        self._recalculate()

    def _on_final_weight_changed(self, _text: str) -> None:
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
            self.state = "Con advertencias" if self.source_result.warnings else "Fichero analizado"
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
                    self.state = "Con advertencias" if self.adjustment.warnings or self.source_result.warnings else "Listo para exportar"
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

    def save_path(self, path: Path) -> None:
        if self.adjustment is None:
            return
        self.state = "Generando archivo"
        self._refresh()
        try:
            write_ax_csv(path, self.adjustment)
        except (OSError, DomainValidationError, ValueError) as exc:
            self.state = "Error de exportación"
            self.final_issues = (ValidationIssue("EXPORT_ERROR", str(exc)),)
            self.status.setText(f"Error de exportación: {exc}")
            show_inline_message(self, "error", str(exc))
        else:
            self.export_path = path
            self.state = "Exportación completada"
            self.status.setText(f"CSV AX guardado: {path.name}")
            show_inline_message(self, "success", f"CSV AX guardado: {path.name}")
        self._refresh()

    def clear(self) -> None:
        self.source_path = None
        self.source_result = None
        self.adjustment = None
        self.final_issues = ()
        self.export_path = None
        self.final_weight.blockSignals(True)
        self.final_weight.clear()
        self.final_weight.blockSignals(False)
        self.state = "Inicial"
        self.status.setText("Inicial")
        self._refresh()
        self.load_button.setFocus(Qt.OtherFocusReason)

    def _refresh(self) -> None:
        result = self.source_result
        total_records = len(result.records) if result is not None else 0
        error_count = len(result.errors) if result is not None else 0
        final_errors = len([issue for issue in self.final_issues if issue.severity == "error"])
        valid_count = total_records if result is not None and not result.errors else 0
        total_weight = result.total_weight if result is not None else None
        self.metric_total.setText(str(total_records))
        self.metric_valid.setText(str(valid_count))
        self.metric_errors.setText(str(error_count + final_errors))
        self.metric_weight.setText(self._format_weight(total_weight) if total_weight is not None else "-")
        for label, value in (
            (self.metric_total, total_records),
            (self.metric_valid, valid_count),
            (self.metric_errors, error_count + final_errors),
            (self.metric_weight, self._format_weight(total_weight) if total_weight is not None else "-"),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")
        self.file_detail.setText(self._file_text())
        self.summary.setText(self._summary_text())
        self.issues.setPlainText(self._issues_text())
        self._populate_preview_table()
        can_export = self.adjustment is not None and not self._blocking_errors() and self.adjustment.adjusted_total == self.adjustment.final_weight
        self.export_button.setEnabled(can_export)
        self.clear_button.setEnabled(result is not None or bool(self.final_weight.text()))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _populate_preview_table(self) -> None:
        rows: list[tuple[str, str, str, str, str]] = []
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
                    "Listo" if row is not None else "Pendiente de peso final",
                ))
            remaining = max(0, PREVIEW_LIMIT - len(rows))
            for issue in self.source_result.errors[:remaining]:
                if issue.line_number is not None:
                    rows.append((f"Línea {issue.line_number}", "-", "-", "-", f"Error: {issue.message}"))
        with bulk_table_update(self.preview_table):
            self.preview_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.preview_table.setItem(row_index, column, item)
        issue_rows = len([issue for issue in self.source_result.errors if issue.line_number is not None]) if self.source_result else 0
        total = (len(self.source_result.records) if self.source_result is not None else 0) + issue_rows
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
            "Error de exportación": ("No se pudo generar el CSV; revisa las incidencias.", 85),
            "Generando archivo": ("Generando y validando los bytes del CSV AX.", 90),
            "Con errores": ("Corrige las incidencias antes de exportar.", 45),
            "Listo para exportar": ("La suma ajustada coincide exactamente con el peso final.", 85),
            "Con advertencias": ("Revisa los avisos; una ganancia de peso puede exportarse si no hay errores.", 80),
            "Fichero analizado": ("Introduce el peso final para calcular el reparto.", 55),
            "Analizando": ("Leyendo formato, registros y validaciones.", 20),
            "Cargando": ("Preparando el fichero para su análisis.", 10),
            "Inicial": ("Carga un TXT o CSV para analizar sus precintos y pesos.", 0),
        }
        detail, progress = states.get(self.state, states["Inicial"])
        return self.state, detail, progress

    def _next_action_text(self) -> str:
        if self.source_result is None:
            return "Cargar fichero"
        if self._blocking_errors():
            return "Corregir incidencias"
        if self.adjustment is None:
            return "Indicar peso final"
        return "Guardar CSV AX"

    def _sync_recommended_action(self) -> None:
        sync_recommended_action(
            self,
            self._next_action_text(),
            {"Cargar fichero": self.load_button, "Guardar CSV AX": self.export_button},
            (self.load_button, self.export_button, self.clear_button),
        )

    def _blocking_errors(self) -> bool:
        source_errors = self.source_result.errors if self.source_result is not None else ()
        return bool(source_errors or any(issue.severity == "error" for issue in self.final_issues))

    def _summary_text(self) -> str:
        if self.source_result is None:
            return "Sin fichero cargado"
        name = self.source_path.name if self.source_path is not None else "Fichero"
        return f"{name} | {len(self.source_result.records)} registros | {len(self.source_result.errors)} errores"

    def _file_text(self) -> str:
        if self.source_path is None or self.source_result is None:
            return "Sin fichero seleccionado"
        source_format = self.source_result.source_format
        if source_format is None:
            return f"{self.source_path.name}\nFormato no válido"
        return f"{self.source_path.name}\n{source_format.encoding}, {source_format.line_ending}, separador {source_format.delimiter}"

    def _issues_text(self) -> str:
        issues: list[ValidationIssue] = []
        if self.source_result is not None:
            issues.extend(self.source_result.issues)
        issues.extend(self.final_issues)
        if not issues:
            return "Sin incidencias.\n\nEl CSV AX contendrá exclusivamente Precinto y Peso ajustado."
        lines = []
        for issue in issues[:160]:
            location = f"Línea {issue.line_number}: " if issue.line_number is not None else ""
            prefix = "Error" if issue.severity == "error" else "Aviso"
            lines.append(f"{prefix}: {location}{issue.message}")
        if len(issues) > 160:
            lines.append(f"... {len(issues) - 160} incidencias más")
        return "\n".join(lines)

    @staticmethod
    def _format_weight(value: Decimal | None) -> str:
        if value is None:
            return "-"
        return format(value.quantize(Decimal("0.01")), ".2f").replace(".", ",")

    @staticmethod
    def _format_percentage(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), ".2f").replace(".", ",") + " %"

    def flow_state(self) -> tuple[int, bool, bool]:
        if self.state == "Exportación completada":
            return 4, False, True
        if self.state in {"Con errores", "Error de exportación"}:
            return 2, True, False
        if self.adjustment is not None:
            return 4, self.state == "Con advertencias", False
        if self.source_result is not None:
            return 2, False, False
        return 1, False, False
