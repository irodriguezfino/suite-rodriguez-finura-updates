from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.paths import resource_path
from suite_pyside6.core.precintos_jamones import (
    PrecintosJamonesResult,
    correction_text,
    process_precintos_jamones,
    revalidate_corrections,
    save_precintos_csv,
    save_precintos_txt,
    weight_filter_text,
)
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.theme import base_qss


class PrecintosJamonesWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.official_excel: Path | None = None
        self.result = PrecintosJamonesResult()
        self.last_attachments: list[Path] = []
        self.weight_filter_pending = False
        self.show_dialogs = True
        self.setWindowTitle("Precintos Jamones")
        self.resize(1160, 740)
        self.setMinimumSize(740, 580)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self, context_panel=False)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar TXT/CSV", "Validar", "Revisar incidencias", "Guardar TXT/CSV")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Precintos Jamones")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Valida precintos, duplicados, Excel oficial y exporta TXT/CSV.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar TXT/CSV  ->  2 Revisar incidencias  ->  3 Revalidar  ->  4 Guardar TXT/CSV")
        steps.setObjectName("StepBar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(7)

        self.type_combo = QComboBox()
        self.type_combo.setObjectName("CompactField")
        self.type_combo.addItems(["Blanco", "Iberico"])
        self.type_combo.currentTextChanged.connect(lambda _text: self.process_files() if self.paths else None)

        entrada_label = QLabel("ENTRADA")
        entrada_label.setObjectName("GroupLabel")
        actions_layout.addWidget(entrada_label)
        actions_layout.addWidget(self.type_combo)

        self.txt_button = QPushButton("Cargar TXT/CSV")
        self.txt_button.setProperty("primary", True)
        self.txt_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.txt_button)

        self.official_button = QPushButton("Cargar Excel oficial")
        self.official_button.clicked.connect(self.select_official)
        actions_layout.addWidget(self.official_button)

        validacion_label = QLabel("VALIDACIÓN")
        validacion_label.setObjectName("GroupLabel")
        validacion_label.setText("VALIDACION")
        actions_layout.addWidget(validacion_label)

        self.process_button = QPushButton("Procesar control")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        self.revalidate_button = QPushButton("Revalidar")
        self.revalidate_button.clicked.connect(self.revalidate)
        actions_layout.addWidget(self.revalidate_button)

        self.weight_min = QLineEdit()
        self.weight_min.setObjectName("CompactField")
        self.weight_min.setPlaceholderText("Peso min.")
        self.weight_min.setAccessibleDescription("Peso mínimo para filtrar registros, disponible tras procesar.")
        self.weight_min.setAccessibleDescription("Peso minimo para filtrar registros, disponible tras procesar.")
        self.weight_min.setMaximumWidth(96)
        actions_layout.addWidget(self.weight_min)

        self.weight_max = QLineEdit()
        self.weight_max.setObjectName("CompactField")
        self.weight_max.setPlaceholderText("Peso max.")
        self.weight_max.setAccessibleDescription("Peso máximo para filtrar registros, disponible tras procesar.")
        self.weight_max.setAccessibleDescription("Peso maximo para filtrar registros, disponible tras procesar.")
        self.weight_max.setMaximumWidth(96)
        actions_layout.addWidget(self.weight_max)

        self.weight_button = QPushButton("Filtrar pesos")
        self.weight_button.clicked.connect(self.apply_weight_filter)
        actions_layout.addWidget(self.weight_button)

        self.clear_filter_button = QPushButton("Limpiar filtro")
        self.clear_filter_button.clicked.connect(self.clear_weight_filter)
        actions_layout.addWidget(self.clear_filter_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        actions_layout.addWidget(salida_label)

        self.save_txt_button = QPushButton("Guardar TXT")
        self.save_txt_button.clicked.connect(self.save_txt_dialog)
        actions_layout.addWidget(self.save_txt_button)

        self.save_csv_button = QPushButton("Guardar CSV")
        self.save_csv_button.clicked.connect(self.save_csv_dialog)
        actions_layout.addWidget(self.save_csv_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        self.summary.setVisible(False)
        self.summary.setMaximumHeight(0)
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
        preview_title = QLabel("Vista previa")
        preview_title.setObjectName("SectionLabel")
        self.preview_count = QLabel("0 lineas")
        self.preview_count.setObjectName("ControlCountPill")
        preview_header.addWidget(preview_title)
        preview_header.addStretch(1)
        preview_header.addWidget(self.preview_count)
        self.preview_table = QTableWidget(0, 6)
        self.preview_table.setObjectName("ControlPreviewTable")
        self.preview_table.setAccessibleName("Vista previa de precintos de jamones")
        self.preview_table.setHorizontalHeaderLabels(["Linea", "Codigo", "Precinto", "Peso", "Lote", "Estado"])
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.preview_table, 1)

        self.metrics_strip = QFrame()
        self.metrics_strip.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(4)
        self.metric_valid = self._metric_pair(metrics_layout, 0, "Validos", "0")
        self.metric_pending = self._metric_pair(metrics_layout, 1, "Pendientes", "0")
        self.metric_duplicate = self._metric_pair(metrics_layout, 2, "Duplicados", "0")
        self.metric_files = self._metric_pair(metrics_layout, 3, "Archivos", "0")
        preview_layout.addWidget(self.metrics_strip)

        issues_panel = QFrame()
        issues_panel.setObjectName("ControlIssuesPanel")
        issues_layout = QVBoxLayout(issues_panel)
        issues_layout.setContentsMargins(12, 10, 12, 10)
        issues_layout.setSpacing(8)
        issues_header = QHBoxLayout()
        issues_title = QLabel("Incidencias")
        issues_title.setObjectName("SectionLabel")
        self.issues_count = QLabel("0 detectadas")
        self.issues_count.setObjectName("ControlIssuePill")
        issues_header.addWidget(issues_title)
        issues_header.addStretch(1)
        issues_header.addWidget(self.issues_count)
        self.issues_empty = QLabel("No hay incidencias para mostrar")
        self.issues_empty.setObjectName("ControlDropzone")
        self.issues_empty.setAccessibleName("Estado vacio de incidencias")
        self.issues_empty.setAlignment(Qt.AlignCenter)
        self.issues_empty.setWordWrap(True)
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("CorrectionEditor")
        self.preview.setAccessibleName("Editor de correcciones de precintos")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.issues = QPlainTextEdit()
        self.issues.setObjectName("IssuesText")
        self.issues.setAccessibleName("Listado de incidencias de precintos")
        self.issues.setReadOnly(True)
        self.issues.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.issues.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        issues_layout.addLayout(issues_header)
        issues_layout.addWidget(self.issues_empty, 1)
        issues_layout.addWidget(self.issues, 1)
        issues_layout.addWidget(self.preview, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = QLabel("Estado actual")
        rail_title.setObjectName("SectionLabel")
        self.rail_state = QLabel("Pendiente de TXT/CSV")
        self.rail_state.setObjectName("ControlRailState")
        self.rail_detail = QLabel("Carga uno o varios ficheros para iniciar la validacion.")
        self.rail_detail.setObjectName("ControlRailDetail")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = QLabel("Siguiente accion")
        next_title.setObjectName("SectionLabel")
        self.rail_next = QLabel("Cargar TXT/CSV")
        self.rail_next.setObjectName("ControlRailAction")
        self.rail_next.setWordWrap(True)
        alerts_title = QLabel("Avisos")
        alerts_title.setObjectName("SectionLabel")
        self.rail_alerts = QLabel("Sin avisos.")
        self.rail_alerts.setObjectName("ControlRailDetail")
        self.rail_alerts.setWordWrap(True)
        self.output = QPlainTextEdit()
        self.output.setObjectName("OutputText")
        self.output.setAccessibleName("Vista de salida TXT/CSV")
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.output.setMaximumHeight(150)
        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(alerts_title)
        rail_layout.addWidget(self.rail_alerts)
        rail_layout.addWidget(QLabel("Salida"))
        rail_layout.addWidget(self.output)
        rail_layout.addStretch(1)

        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(issues_panel, 3)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def _metric_pair(self, layout: QGridLayout, column: int, label: str, value: str) -> QLabel:
        value_label = QLabel(value)
        value_label.setObjectName("ControlMetricValue")
        value_label.setAccessibleName(label)
        value_label.setAccessibleDescription(f"{label}: {value}")
        text_label = QLabel(label)
        text_label.setObjectName("ControlMetricLabel")
        layout.addWidget(value_label, 0, column)
        layout.addWidget(text_label, 1, column)
        return value_label

    def select_files(self) -> None:
        files = open_files(
            self,
            "precintos_jamones/input",
            "Selecciona ficheros de precintos",
            "TXT/CSV (*.txt *.csv);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def select_official(self) -> None:
        file = open_file(self, "precintos_jamones/oficial", "Selecciona Excel oficial", "Excel (*.xlsx *.xlsm);;Todos (*.*)")
        if file:
            self.official_excel = file
            if self.paths:
                self.process_files()
            else:
                self._refresh()

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.process_files()

    def process_files(self) -> None:
        if not self.paths:
            return
        try:
            self.result = process_precintos_jamones(self.paths, self.type_combo.currentText(), self.official_excel)
        except Exception as exc:
            self.status.setText(f"Error: {exc}")
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.weight_filter_pending = False
        self.status.setText(f"Proceso completado: {len(self.result.validos)} registros validos")
        self._refresh()

    def revalidate(self) -> None:
        if not (self.result.invalidos or self.weight_filter_pending):
            return
        self.result = revalidate_corrections(self.result, self.preview.toPlainText())
        self.last_attachments = []
        self.weight_filter_pending = False
        if self.result.invalidos:
            self.status.setText(f"Siguen pendientes {len(self.result.invalidos)} incidencia(s).")
            if self.show_dialogs:
                show_inline_message(self, "warning", "Aun quedan lineas que no superan la validacion.")
        else:
            self.status.setText("Revalidacion correcta. Ya puedes guardar TXT o CSV.")
            show_inline_message(self, "success", "Revalidacion correcta. Ya puedes guardar TXT o CSV.")
        self._refresh()

    def apply_weight_filter(self) -> None:
        if not self.result.validos:
            show_inline_message(self, "warning", "Procesa primero uno o varios ficheros.")
            return
        try:
            editor, resumen, pending = weight_filter_text(self.result, self.weight_min.text(), self.weight_max.text())
        except Exception as exc:
            self.status.setText(str(exc))
            if self.show_dialogs:
                show_inline_message(self, "warning", str(exc))
            return
        self.preview.setReadOnly(not pending)
        self.preview.setPlainText(editor if pending else self.result.preview_text() + "\n\n" + resumen)
        self.weight_filter_pending = pending
        self.last_attachments = []
        self.status.setText("Filtro de pesos aplicado. Modifica registros si procede y pulsa Revalidar.")
        self._refresh_buttons_only()

    def clear_weight_filter(self) -> None:
        self.weight_min.clear()
        self.weight_max.clear()
        self.weight_filter_pending = False
        self._refresh()
        self.status.setText("Filtro de pesos limpiado.")

    def save_txt_dialog(self) -> None:
        if not self.result.validos:
            return
        file = save_file(self, "precintos_jamones/export_txt", "Guardar TXT", "precintos_jamones.txt", "TXT (*.txt)")
        if file:
            self.save_txt(file)

    def save_csv_dialog(self) -> None:
        if not self.result.validos:
            return
        file = save_file(self, "precintos_jamones/export_csv", "Guardar CSV", "precintos_jamones.csv", "CSV (*.csv)")
        if file:
            self.save_csv(file)

    def save_txt(self, path: Path) -> Path:
        saved = save_precintos_txt(path, self.result)
        self.last_attachments = [saved]
        self.status.setText(f"TXT guardado: {saved}")
        show_inline_message(self, "success", f"TXT guardado: {saved.name}")
        return saved

    def save_csv(self, path: Path) -> list[Path]:
        summary = save_precintos_csv(path, self.result)
        self.last_attachments = [path] + ([summary] if summary is not None else [])
        self.status.setText("CSV guardado" + (f" con resumen: {summary.name}" if summary else f": {path.name}"))
        show_inline_message(self, "success", "CSV guardado" + (f" con resumen: {summary.name}" if summary else f": {path.name}"))
        return self.last_attachments

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.paths = []
        self.official_excel = None
        self.result = PrecintosJamonesResult()
        self.last_attachments = []
        self.weight_filter_pending = False
        self.weight_min.clear()
        self.weight_max.clear()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self) -> None:
        if self.result.validos or self.result.invalidos:
            self.summary.setText(" | ".join(self.result.summary_lines()))
            self.preview.setReadOnly(not bool(self.result.invalidos or self.weight_filter_pending))
            if not self.weight_filter_pending:
                self.preview.setPlainText(correction_text(self.result) if self.result.invalidos else self.result.preview_text())
            self.issues.setPlainText(self._issues_text())
            self.output.setPlainText(self._output_text())
        else:
            official = self.official_excel.name if self.official_excel else "-"
            self.summary.setText(f"Archivos: {len(self.paths)} | Excel oficial: {official}")
            self.preview.setReadOnly(True)
            self.preview.setPlainText("Arrastra TXT/CSV de precintos aqui o usa Cargar TXT/CSV para empezar.")
            self.issues.setPlainText("Sin incidencias.")
            self.output.setPlainText("La salida TXT/CSV aparecera despues de procesar registros validos.")
        self._populate_preview_table()
        self._refresh_buttons_only()

    def _refresh_buttons_only(self) -> None:
        can_save = bool(self.result.validos and not self.result.invalidos and not self.weight_filter_pending)
        self.process_button.setEnabled(bool(self.paths))
        self.revalidate_button.setEnabled(bool(self.result.invalidos or self.weight_filter_pending))
        self.save_txt_button.setEnabled(can_save)
        self.save_csv_button.setEnabled(can_save)
        self.weight_button.setEnabled(bool(self.result.validos and not self.result.invalidos))
        self.clear_filter_button.setEnabled(bool(self.result.validos or self.result.invalidos or self.weight_filter_pending))
        self.clear_button.setEnabled(bool(self.paths or self.result.validos or self.result.invalidos or self.official_excel))
        self._sync_weight_filter_controls()
        self._refresh_pilot_state()

    def _sync_weight_filter_controls(self) -> None:
        visible = bool(self.weight_button.isEnabled() or self.weight_filter_pending)
        self.weight_min.setVisible(visible)
        self.weight_max.setVisible(visible)

    def _populate_preview_table(self) -> None:
        rows: list[tuple[str, str, str, str, str, str]] = []
        for registro in self.result.validos[:120]:
            rows.append(
                (
                    str(registro.linea),
                    registro.codigo_articulo or "-",
                    registro.precinto or "-",
                    registro.peso or "-",
                    registro.lote or "-",
                    "Valido",
                )
            )
        for registro, motivo in self.result.invalidos[:80]:
            rows.append(
                (
                    str(registro.linea),
                    registro.codigo_articulo or "-",
                    registro.precinto or "-",
                    registro.peso or "-",
                    registro.lote or "-",
                    f"Pendiente: {motivo}",
                )
            )
        self.preview_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, value in enumerate(row):
                item = QTableWidgetItem(value)
                if column == 5 and value.startswith("Pendiente"):
                    item.setToolTip(value)
                self.preview_table.setItem(row_index, column, item)
        self.preview_count.setText(f"{len(rows)} lineas" if rows else "0 lineas")

    def _refresh_pilot_state(self) -> None:
        validos = len(self.result.validos)
        invalidos = len(self.result.invalidos)
        duplicados = len(self.result.duplicados)
        pendientes = invalidos + int(self.weight_filter_pending)
        files = len(self.paths)
        self.metric_valid.setText(str(validos))
        self.metric_pending.setText(str(pendientes))
        self.metric_duplicate.setText(str(duplicados))
        self.metric_files.setText(str(files))
        for label, value in (
            (self.metric_valid, validos),
            (self.metric_pending, pendientes),
            (self.metric_duplicate, duplicados),
            (self.metric_files, files),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")
        self.issues_count.setText(f"{pendientes} detectadas" if pendientes else "0 detectadas")
        self.issues_count.setAccessibleDescription(
            f"Incidencias detectadas: {pendientes}. Revisa el panel central si hay pendientes."
        )

        has_issues = bool(self.result.invalidos or self.result.duplicados or self.result.oficiales)
        needs_corrections = bool(self.result.invalidos or self.weight_filter_pending)
        self.issues_empty.setVisible(not has_issues and not needs_corrections)
        self.issues.setVisible(has_issues)
        self.preview.setVisible(needs_corrections)

        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso del proceso")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente accion recomendada: {self.rail_next.text()}")
        self.rail_alerts.setText(self._alerts_text())
        self.rail_alerts.setAccessibleDescription("Avisos del proceso: " + self.rail_alerts.text().replace("\n", ". "))
        self.issues_empty.setText(self._empty_issue_text())

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "guardado" in status:
            return "Salida guardada", "El archivo de salida se ha generado correctamente.", 100
        if self.result.invalidos or self.weight_filter_pending:
            return "Revision pendiente", "Corrige las lineas marcadas y pulsa Revalidar.", 55
        if self.result.validos:
            return "Validado", "Los precintos estan listos para guardar TXT o CSV.", 80
        if self.paths:
            return "Archivos cargados", "Pulsa Procesar control para validar los registros.", 25
        if self.official_excel:
            return "Excel oficial cargado", "Carga TXT/CSV de precintos para comparar contra el oficial.", 15
        return "Pendiente de TXT/CSV", "Carga uno o varios ficheros para iniciar la validacion.", 0

    def _next_action_text(self) -> str:
        if not self.paths and not self.result.validos:
            return "Cargar TXT/CSV"
        if self.paths and not (self.result.validos or self.result.invalidos):
            return "Procesar control"
        if self.result.invalidos or self.weight_filter_pending:
            return "Revalidar correcciones"
        if self.result.validos:
            return "Guardar TXT o CSV"
        return "Completa el paso actual"

    def _alerts_text(self) -> str:
        alerts: list[str] = []
        if self.result.invalidos:
            alerts.append(f"{len(self.result.invalidos)} lineas pendientes")
        if self.result.duplicados:
            alerts.append(f"{len(self.result.duplicados)} duplicados suprimidos")
        if self.weight_filter_pending:
            alerts.append("Filtro de peso pendiente de revalidar")
        if self.result.oficiales:
            extra, missing = self.result.differences()
            if extra:
                alerts.append(f"{len(extra)} precintos fuera del Excel oficial")
            if missing:
                alerts.append(f"{len(missing)} precintos oficiales no leidos")
        return "\n".join(alerts) if alerts else "Sin avisos."

    def _empty_issue_text(self) -> str:
        if not self.paths and not self.result.validos:
            return "No hay incidencias para mostrar.\n\nArrastra aqui los TXT/CSV de precintos o usa Cargar TXT/CSV."
        if self.result.validos and not self.result.invalidos:
            return "Sin incidencias pendientes.\n\nLos registros estan preparados para salida."
        return "No hay incidencias para mostrar."

    def _template_values(self) -> dict[str, str]:
        return {
            "tipo_jamon": self.result.tipo_jamon,
            "registros_validos": str(len(self.result.validos)),
            "incidencias": str(len(self.result.invalidos)),
            "duplicados": str(len(self.result.duplicados)),
        }

    def _render_template(self, text: str) -> str:
        try:
            return text.format(**self._template_values())
        except Exception:
            return text

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if self.result.invalidos or self.weight_filter_pending:
            return 3, True, False
        if self.result.validos:
            return 4, False, False
        if self.paths:
            return 2, False, False
        return 1, False, False

    def _issues_text(self) -> str:
        if not (self.result.invalidos or self.result.duplicados or self.result.oficiales):
            return "Sin incidencias."
        lines: list[str] = []
        if self.result.invalidos:
            lines.append("Incidencias pendientes:")
            lines.extend(
                f"- {registro.archivo}:{registro.linea} {registro.precinto or '(sin precinto)'} | {motivo}"
                for registro, motivo in self.result.invalidos[:120]
            )
        if self.result.duplicados:
            if lines:
                lines.append("")
            lines.append("Duplicados suprimidos:")
            lines.extend(
                f"- {registro.precinto} | {registro.fecha} {registro.hora} | {registro.archivo}:{registro.linea}"
                for registro in self.result.duplicados[:80]
            )
        if self.result.oficiales:
            extra, missing = self.result.differences()
            if extra:
                if lines:
                    lines.append("")
                lines.append("Leidos fuera del Excel oficial:")
                lines.extend(f"- {item}" for item in sorted(extra)[:120])
            if missing:
                if lines:
                    lines.append("")
                lines.append("Oficiales no leidos:")
                lines.extend(f"- {item}" for item in sorted(missing)[:120])
        return "\n".join(lines)

    def _output_text(self) -> str:
        if not self.result.validos:
            return "No hay registros validos para salida."
        return "\n".join(registro.a_linea().lstrip("\ufeff") for registro in self.result.validos[:500])
