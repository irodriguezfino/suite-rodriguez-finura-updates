from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QBoxLayout,
    QAbstractItemView,
    QFrame,
    QCheckBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
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
from suite_pyside6.core.pesos import (
    OLD_EXCEL_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    PesosProgress,
    PesosResult,
    SheetRename,
    VaciadoType,
    process_pesos_files,
)
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_files
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.responsive import register_adaptive_layout
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


class _PesosWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)

    def __init__(self, paths: list[Path], vaciados: dict[Path, VaciadoType]) -> None:
        super().__init__()
        self.paths = paths
        self.vaciados = vaciados

    def run(self) -> None:
        try:
            result = process_pesos_files(self.paths, self.vaciados, self.progress.emit)
        except Exception as exc:  # final safeguard: the UI must always recover
            result = PesosResult(
                selected_files=self.paths,
                results=[SheetRename(path=self.paths[0], success=False, message=str(exc))] if self.paths else [],
            )
        self.finished.emit(result)


class PesosWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.vaciados: dict[Path, VaciadoType] = {}
        self.result = PesosResult()
        self._thread: QThread | None = None
        self._worker: _PesosWorker | None = None
        self._processing = False
        self._progress_value = 0
        self._progress_message = ""
        self.setWindowTitle("Pesos - Procesar Excel")
        self.resize(1180, 720)
        self.setMinimumSize(720, 540)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar Excel", "Elegir vaciado y procesar", "Revisar resultado")

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

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(3)
        title = QLabel("Pesos")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Renombra la primera hoja visible a Hoja1 y permite ajustar los pesos bruto y neto por lote.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)

        hero_status = QFrame()
        hero_status.setObjectName("ControlHeroStatus")
        hero_status_layout = QVBoxLayout(hero_status)
        hero_status_layout.setContentsMargins(10, 8, 10, 8)
        hero_status_layout.setSpacing(3)
        hero_status_label = QLabel("Excel")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("Hoja1")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)

        steps = step_bar("1 Cargar Excel  ->  2 Elegir vaciado  ->  3 Procesar y revisar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("controlCommand", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(8)

        command_panel = QFrame()
        command_panel.setObjectName("ControlCommandCopy")
        command_copy = QVBoxLayout(command_panel)
        command_copy.setContentsMargins(0, 0, 0, 0)
        command_copy.setSpacing(2)
        command_label = QLabel("Siguiente acción")
        command_label.setObjectName("Overline")
        self.command_hint = QLabel("Cargar Excel")
        self.command_hint.setObjectName("ControlCommandTitle")
        self.command_hint.setWordWrap(True)
        command_copy.addWidget(command_label)
        command_copy.addWidget(self.command_hint)
        actions_layout.addWidget(command_panel, 1)

        entrada_label = QLabel("ENTRADA")
        entrada_label.setObjectName("GroupLabel")
        entrada_label.setVisible(False)
        entrada_label.setMaximumSize(0, 0)
        actions_layout.addWidget(entrada_label)

        self.select_button = QPushButton("Cargar Excel")
        self.select_button.setProperty("primary", True)
        self.select_button.setAccessibleName("Cargar archivos Excel de pesos")
        self.select_button.setToolTip("Carga uno o varios archivos .xlsx, .xlsm o .xls.")
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        proceso_label.setVisible(False)
        proceso_label.setMaximumSize(0, 0)
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar lote")
        self.process_button.setAccessibleName("Procesar lotes de pesos")
        self.process_button.setToolTip("Renombra la hoja y aplica el vaciado seleccionado en cada archivo.")
        self.process_button.clicked.connect(self.process_selected_files)
        actions_layout.addWidget(self.process_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
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
        preview_header.setSpacing(8)
        preview_title = section_label("Resultado por archivo")
        self.preview_count = control_pill("0 archivos")
        preview_header.addWidget(preview_title)
        preview_header.addStretch(1)
        preview_header.addWidget(self.preview_count)

        self.metrics_strip = QFrame()
        self.metrics_strip.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(4)
        self.metric_files = control_metric_pair(metrics_layout, 0, "Archivos", "0")
        self.metric_excel = control_metric_pair(metrics_layout, 1, "Excel", "0")
        self.metric_renamed = control_metric_pair(metrics_layout, 2, "Renombrados", "0")
        self.metric_issues = control_metric_pair(metrics_layout, 3, "Avisos", "0")

        self.result_table = QTableWidget(0, 6)
        self.result_table.setAccessibleName("Lotes de pesos y selección de vaciado")
        self.result_table.setAccessibleDescription("Lista de archivos de pesos, selección de vaciado y resultado del proceso.")
        self.result_table.setHorizontalHeaderLabels(["Archivo", "Vaciado Normal", "Vaciado Completo", "Estado", "Hoja anterior", "Detalle"])
        header = self.result_table.horizontalHeader()
        header.setMinimumSectionSize(96)
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        # Checkbox text, indicator and cell margins all fit without clipping.
        normal_width = max(164, header.fontMetrics().horizontalAdvance("Vaciado Normal") + 52)
        complete_width = max(180, header.fontMetrics().horizontalAdvance("Vaciado Completo") + 52)
        self.result_table.setColumnWidth(1, normal_width)
        self.result_table.setColumnWidth(2, complete_width)
        self.result_table.verticalHeader().setDefaultSectionSize(42)
        self.result_table.verticalHeader().setMinimumSectionSize(42)
        # The table is a status/selection surface: the controls inside it own
        # keyboard focus.  Disabling item selection avoids the native blue
        # focus rectangle around the embedded check boxes.
        self.result_table.setProperty("disableTableSelection", True)
        self.result_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.result_table.setFocusPolicy(Qt.NoFocus)
        self.result_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.preview = QPlainTextEdit()
        self.preview.setObjectName("OutputText")
        self.preview.setAccessibleName("Archivos seleccionados")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setMaximumHeight(110)

        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.metrics_strip)
        preview_layout.addWidget(self.result_table, 1)

        self.rail = QFrame()
        self.rail.setObjectName("ControlStatusRail")
        self.rail.setMinimumWidth(300)
        self.rail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        rail_layout = QVBoxLayout(self.rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Control del lote")
        self.rail_state = control_rail_label("Pendiente de Excel", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga archivos XLSX, XLSM o XLS para preparar la hoja Hoja1.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        self.rail_progress_text = control_rail_label("Preparado — 0 %")
        self.rail_progress_text.setWordWrap(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar Excel", role="action")
        self.rail_next.setWordWrap(True)
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("Sin archivos seleccionados")
        self.rail_files.setWordWrap(True)
        log_title = section_label("Resumen de proceso")
        self.log = QPlainTextEdit()
        self.log.setObjectName("LotControlLog")
        self.log.setAccessibleName("Resumen del proceso de pesos")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log.setMinimumHeight(110)

        rail_layout.addWidget(rail_title)
        self.rail_sections = QBoxLayout(QBoxLayout.TopToBottom)
        self.rail_sections.setSpacing(12)

        rail_primary = QFrame()
        rail_primary.setObjectName("LotControlPrimary")
        rail_primary_layout = QVBoxLayout(rail_primary)
        rail_primary_layout.setContentsMargins(0, 0, 0, 0)
        rail_primary_layout.setSpacing(6)
        rail_primary_layout.addWidget(self.rail_state)
        rail_primary_layout.addWidget(self.rail_detail)
        rail_primary_layout.addWidget(self.rail_progress)
        rail_primary_layout.addWidget(self.rail_progress_text)
        rail_primary_layout.addWidget(next_title)
        rail_primary_layout.addWidget(self.rail_next)

        rail_secondary = QFrame()
        rail_secondary.setObjectName("LotControlSecondary")
        rail_secondary_layout = QVBoxLayout(rail_secondary)
        rail_secondary_layout.setContentsMargins(0, 0, 0, 0)
        rail_secondary_layout.setSpacing(6)
        rail_secondary_layout.addWidget(files_title)
        rail_secondary_layout.addWidget(self.rail_files)
        rail_secondary_layout.addWidget(log_title)
        rail_secondary_layout.addWidget(self.log, 1)

        self.rail_sections.addWidget(rail_primary, 3)
        self.rail_sections.addWidget(rail_secondary, 2)
        rail_layout.addLayout(self.rail_sections, 1)

        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(self.rail, 2)
        layout.addWidget(workspace, 1)
        # The table needs priority at medium widths.  Stack the control below
        # it before its narrow side rail becomes a column of wrapped text.
        register_adaptive_layout(self, workspace_layout, breakpoint_width=1280)
        register_adaptive_layout(
            self,
            self.rail_sections,
            breakpoint_width=1280,
            wide_direction=QBoxLayout.TopToBottom,
            narrow_direction=QBoxLayout.LeftToRight,
        )

        self.status = QLabel("Carga archivos Excel para empezar.")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.vaciados = {path: "ninguno" for path in self.paths}
        self.result = PesosResult(selected_files=self.paths)
        self._progress_value = 0
        self._progress_message = ""
        self.rail_progress_text.setText("Preparado — 0 %")
        self.status.setText("Selección completada. Elige vaciado por archivo o procesa solo el renombrado.")
        self._refresh(selected_only=True)

    def select_files(self) -> None:
        files = open_files(
            self,
            "pesos/input",
            "Selecciona archivos Excel de pesos",
            "Excel (*.xlsx *.xlsm *.xls);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def process_selected_files(self) -> None:
        if not self.paths or self._processing:
            show_inline_message(self, "warning", "Carga primero uno o varios archivos Excel.")
            return
        self._processing = True
        self._progress_value = 0
        self._progress_message = "Validando archivos…"
        self.rail_progress.setValue(0)
        self.rail_detail.setText(self._progress_message)
        self.rail_progress_text.setText("Validando archivos… — 0 %")
        self.status.setText(self._progress_message)
        self._set_processing_controls(False)
        self.setProperty("operationActive", True)
        self._thread = QThread(self)
        self._worker = _PesosWorker(list(self.paths), dict(self.vaciados))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_processing_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.start()

    def _on_progress(self, update: PesosProgress) -> None:
        self._progress_value = min(100, int((update.completed * 100) / max(1, update.total)))
        self._progress_message = update.message
        self.rail_progress.setValue(self._progress_value)
        self.rail_detail.setText(update.message)
        self.rail_progress_text.setText(f"{update.message} — {self._progress_value} %")
        self.status.setText(update.message)

    def _on_processing_finished(self, result: PesosResult) -> None:
        self.result = result
        self._processing = False
        if self.result.error_count:
            self.status.setText(
                f"Proceso detenido con {self.result.error_count} avisos. No se ha marcado como completado."
            )
            self.rail_progress_text.setText(f"Proceso fallido — {self._progress_value} %")
            show_inline_message(self, "warning", "Revisa el resumen: hay archivos ignorados o con error.")
        else:
            self.status.setText(f"Proceso completado: {self.result.ok_count} archivos revisados.")
            self._progress_value = 100
            self._progress_message = "Proceso completado."
            self.rail_progress_text.setText("Proceso completado — 100 %")
            show_inline_message(self, "success", "Hojas renombradas a Hoja1 correctamente.")
        self._set_processing_controls(True)
        self._refresh()

    def _thread_finished(self) -> None:
        self.setProperty("operationActive", False)
        self._thread = None
        self._worker = None

    def _set_processing_controls(self, enabled: bool) -> None:
        self.select_button.setEnabled(enabled)
        self.process_button.setEnabled(enabled and bool(self.paths))
        self.clear_button.setEnabled(enabled and bool(self.paths or self.result.results or self.result.ignored_files))
        self.result_table.setEnabled(enabled)

    def clear(self) -> None:
        if self._processing:
            return
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.paths = []
        self.vaciados = {}
        self.result = PesosResult()
        self._progress_value = 0
        self._progress_message = ""
        self.rail_progress_text.setText("Preparado — 0 %")
        self.status.setText("Carga archivos Excel para empezar.")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            processable = sum(1 for path in self.paths if path.suffix.lower() in SUPPORTED_EXTENSIONS)
            ignored = len(self.paths) - processable
            self.summary.setText(
                f"{len(self.paths)} archivos seleccionados | Excel procesables: {processable} | Ignorados: {ignored}"
            )
            self.preview.setPlainText("Archivos seleccionados:\n" + "\n".join(str(path) for path in self.paths))
            self.log.setPlainText("Elige Vaciado Normal, Completo o deja ambas opciones desmarcadas para renombrar solamente.")
            self._fill_result_table(selected_only=True)
        else:
            self.summary.setText(self.result.summary() if self.result.selected_files else "Sin archivos cargados")
            self.preview.setPlainText(
                "Archivos seleccionados:\n" + "\n".join(str(path) for path in (self.result.selected_files or self.paths))
                if self.paths or self.result.selected_files
                else "Carga archivos Excel para empezar."
            )
            self.log.setPlainText(self.result.log_text())
            self._fill_result_table()

        self.process_button.setEnabled(bool(self.paths) and not self._processing)
        self.clear_button.setEnabled(bool(self.paths or self.result.results or self.result.ignored_files) and not self._processing)
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _fill_result_table(self, *, selected_only: bool = False) -> None:
        with bulk_table_update(self.result_table):
            self.result_table.setRowCount(0)
            rows: list[tuple[Path, str, str, str, str]] = []
            if selected_only:
                for path in self.paths:
                    suffix = path.suffix.lower()
                    if suffix in SUPPORTED_EXTENSIONS:
                        rows.append((path, "Pendiente", "-", "Se renombrará la primera hoja visible.", ""))
                    elif suffix in OLD_EXCEL_EXTENSIONS:
                        rows.append((path, "Ignorado", "-", "Formato Excel antiguo o no soportado.", ""))
                    else:
                        rows.append((path, "Ignorado", "-", "No es un Excel XLSX/XLSM/XLS.", ""))
            else:
                for item in self.result.results:
                    if item.success and item.changed:
                        detail = f"Ahora se llama {item.after}."
                        if item.adjusted_weights:
                            detail += f" Ajustados {item.adjusted_weights} pesos en {item.adjusted_sheets} hoja(s)."
                        rows.append((item.path, "Renombrado", item.before or "-", detail, item.vaciado))
                    elif item.success:
                        detail = "Ya estaba en Hoja1."
                        if item.adjusted_weights:
                            detail += f" Ajustados {item.adjusted_weights} pesos en {item.adjusted_sheets} hoja(s)."
                        rows.append((item.path, "Correcto", item.before or item.after, detail, item.vaciado))
                    else:
                        rows.append((item.path, "Error", item.before or "-", item.message or "No se pudo procesar.", item.vaciado))
                for path in self.result.ignored_files:
                    suffix = path.suffix.lower()
                    detail = "Formato Excel antiguo o no soportado." if suffix in OLD_EXCEL_EXTENSIONS else "No es un Excel XLSX/XLSM/XLS."
                    rows.append((path, "Ignorado", "-", detail, "ninguno"))

            self.result_table.setRowCount(len(rows))
            for row_index, (path, state, before, detail, saved_vaciado) in enumerate(rows):
                active_vaciado = self.vaciados.get(path, saved_vaciado or "ninguno")
                normal = self._vaciado_checkbox(path, "normal", active_vaciado == "normal", selected_only)
                complete = self._vaciado_checkbox(path, "completo", active_vaciado == "completo", selected_only)
                self.result_table.setCellWidget(row_index, 1, normal)
                self.result_table.setCellWidget(row_index, 2, complete)
                for column, holder in ((1, normal), (2, complete)):
                    if self.result_table.columnWidth(column) < holder.sizeHint().width():
                        self.result_table.setColumnWidth(column, holder.sizeHint().width())
                for column, value in enumerate((path.name, state, before, detail)):
                    target_column = (0, 3, 4, 5)[column]
                    item = QTableWidgetItem(value)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.result_table.setItem(row_index, target_column, item)

    def _vaciado_checkbox(self, path: Path, mode: VaciadoType, checked: bool, editable: bool) -> QWidget:
        label = "Vaciado Normal" if mode == "normal" else "Vaciado Completo"
        checkbox = QCheckBox(label)
        checkbox.setObjectName("VaciadoCheck")
        checkbox.setChecked(checked)
        checkbox.setEnabled(editable and path.suffix.lower() in SUPPORTED_EXTENSIONS and not self._processing)
        checkbox.setAccessibleName(f"{label} para {path.name}")
        checkbox.setToolTip(label)
        checkbox.setMinimumWidth(checkbox.fontMetrics().horizontalAdvance(label) + 30)
        checkbox.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        checkbox.toggled.connect(lambda selected, p=path, m=mode: self._set_vaciado(p, m, selected))
        holder = QWidget()
        holder.setObjectName("VaciadoCheckHolder")
        holder.setAccessibleName(checkbox.accessibleName())
        holder.setToolTip(label)
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(9, 3, 9, 3)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(checkbox)
        return holder

    def _set_vaciado(self, path: Path, mode: VaciadoType, selected: bool) -> None:
        if self._processing:
            return
        current = self.vaciados.get(path, "ninguno")
        if selected:
            self.vaciados[path] = mode
        elif current == mode:
            self.vaciados[path] = "ninguno"
        else:
            return
        # Rebuilding the row makes the other check box reflect mutual exclusion
        # immediately, while still allowing the active option to be cleared.
        self._fill_result_table(selected_only=not bool(self.result.results or self.result.ignored_files))

    def _refresh_pilot_state(self) -> None:
        selected_files = self.result.selected_files or self.paths
        excel_count = sum(1 for path in selected_files if path.suffix.lower() in SUPPORTED_EXTENSIONS)
        issue_count = self.result.error_count if self.result.selected_files else max(0, len(selected_files) - excel_count)
        self.metric_files.setText(str(len(selected_files)))
        self.metric_excel.setText(str(excel_count))
        self.metric_renamed.setText(str(self.result.processed_count))
        self.metric_issues.setText(str(issue_count))
        for label, value in (
            (self.metric_files, len(selected_files)),
            (self.metric_excel, excel_count),
            (self.metric_renamed, self.result.processed_count),
            (self.metric_issues, issue_count),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")

        visible_rows = self.result_table.rowCount()
        total_rows = len(selected_files) if selected_files else visible_rows
        update_count_label(self.preview_count, visible_rows, total_rows, "archivos")
        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso del renombrado de hojas")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente acción recomendada: {self.rail_next.text()}")
        if selected_files:
            shown = [path.name for path in selected_files[:4]]
            suffix = f"\n+{len(selected_files) - 4} más" if len(selected_files) > 4 else ""
            self.rail_files.setText("\n".join(shown) + suffix)
        else:
            self.rail_files.setText("Sin archivos seleccionados")

    def _pilot_state_text(self) -> tuple[str, str, int]:
        if self._processing:
            return "Procesando lote", self._progress_message or "Validando archivos…", self._progress_value
        has_output = bool(self.result.results or self.result.ignored_files)
        if has_output and self.result.error_count:
            return "Proceso detenido", "Corrige los avisos antes de volver a ejecutar el lote.", self._progress_value
        if has_output:
            return "Lote completado", "Los Excel procesables ya están procesados y su primera hoja se llama Hoja1.", 100
        if self.paths:
            return "Excel cargados", "Elige el vaciado por archivo y procesa el lote.", 0
        return "Pendiente de Excel", "Carga archivos XLSX, XLSM o XLS para preparar la hoja Hoja1.", 0

    def _next_action_text(self) -> str:
        if not self.paths:
            return "Cargar Excel"
        if not self.result.results and not self.result.ignored_files:
            return "Procesar lote"
        return "Revisar resultado"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar Excel": self.select_button,
                "Procesar lote": self.process_button,
            },
            (self.select_button, self.process_button, self.clear_button),
        )

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if self.result.error_count:
            return 3, True, False
        if "completado" in status or self.result.results or self.result.ignored_files:
            return 3, False, True
        if self.paths:
            return 2, False, False
        return 1, False, False
