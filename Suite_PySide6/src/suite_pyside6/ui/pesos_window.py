from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
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
from suite_pyside6.core.pesos import PesosResult, process_pesos_files
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_files
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.responsive import register_adaptive_layout
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


class PesosWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.result = PesosResult()
        self.setWindowTitle("Pesos - Renombrar hoja Excel")
        self.resize(1040, 680)
        self.setMinimumSize(720, 540)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar Excel", "Renombrar hoja", "Revisar resultado")

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
        subtitle = QLabel("Normaliza Excel de pesos renombrando la primera hoja visible a Hoja1.")
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

        steps = step_bar("1 Cargar Excel  ->  2 Renombrar hoja  ->  3 Revisar resultado")
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
        self.select_button.setToolTip("Carga uno o varios archivos .xlsx o .xlsm.")
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        proceso_label.setVisible(False)
        proceso_label.setMaximumSize(0, 0)
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Renombrar hoja")
        self.process_button.setAccessibleName("Renombrar hoja a Hoja1")
        self.process_button.setToolTip("Cambia solo el nombre de la primera hoja visible a Hoja1.")
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

        self.result_table = QTableWidget(0, 4)
        self.result_table.setAccessibleName("Resultado de renombrado de hojas Excel")
        self.result_table.setAccessibleDescription("Lista de archivos de pesos con estado, hoja anterior y detalle.")
        self.result_table.setHorizontalHeaderLabels(["Archivo", "Estado", "Hoja anterior", "Detalle"])
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
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

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Control del lote")
        self.rail_state = control_rail_label("Pendiente de Excel", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga archivos XLSX o XLSM para preparar la hoja Hoja1.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar Excel", role="action")
        self.rail_next.setWordWrap(True)
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("Sin archivos seleccionados")
        self.rail_files.setWordWrap(True)
        log_title = section_label("Resumen de proceso")
        self.log = QPlainTextEdit()
        self.log.setObjectName("OutputText")
        self.log.setAccessibleName("Resumen del proceso de pesos")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log.setMinimumHeight(110)

        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(files_title)
        rail_layout.addWidget(self.rail_files)
        rail_layout.addWidget(log_title)
        rail_layout.addWidget(self.log, 1)

        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)
        register_adaptive_layout(self, workspace_layout, breakpoint_width=900)

        self.status = QLabel("Carga archivos Excel para empezar.")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = PesosResult(selected_files=self.paths)
        self.status.setText("Selección completada. Renombra la hoja para continuar.")
        self._refresh(selected_only=True)

    def select_files(self) -> None:
        files = open_files(
            self,
            "pesos/input",
            "Selecciona archivos Excel de pesos",
            "Excel moderno (*.xlsx *.xlsm);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def process_selected_files(self) -> None:
        if not self.paths:
            show_inline_message(self, "warning", "Carga primero uno o varios archivos Excel.")
            return
        self.result = process_pesos_files(self.paths)
        if self.result.error_count:
            self.status.setText(
                f"Proceso completado con {self.result.processed_count} archivos renombrados y {self.result.error_count} avisos."
            )
            show_inline_message(self, "warning", "Revisa el resumen: hay archivos ignorados o con error.")
        else:
            self.status.setText(f"Proceso completado: {self.result.ok_count} archivos revisados.")
            show_inline_message(self, "success", "Hojas renombradas a Hoja1 correctamente.")
        self._refresh()

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.paths = []
        self.result = PesosResult()
        self.status.setText("Carga archivos Excel para empezar.")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            processable = sum(1 for path in self.paths if path.suffix.lower() in {".xlsx", ".xlsm"})
            ignored = len(self.paths) - processable
            self.summary.setText(
                f"{len(self.paths)} archivos seleccionados | Excel procesables: {processable} | Ignorados: {ignored}"
            )
            self.preview.setPlainText("Archivos seleccionados:\n" + "\n".join(str(path) for path in self.paths))
            self.log.setPlainText("Renombra la primera hoja visible como Hoja1.")
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

        self.process_button.setEnabled(bool(self.paths))
        self.clear_button.setEnabled(bool(self.paths or self.result.results or self.result.ignored_files))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _fill_result_table(self, *, selected_only: bool = False) -> None:
        with bulk_table_update(self.result_table):
            self.result_table.setRowCount(0)
            rows: list[tuple[str, str, str, str]] = []
            if selected_only:
                for path in self.paths:
                    suffix = path.suffix.lower()
                    if suffix in {".xlsx", ".xlsm"}:
                        rows.append((path.name, "Pendiente", "-", "Se renombrará la primera hoja visible."))
                    elif suffix in {".xls", ".xlsb"}:
                        rows.append((path.name, "Ignorado", "-", "Formato Excel antiguo o no soportado."))
                    else:
                        rows.append((path.name, "Ignorado", "-", "No es un Excel XLSX/XLSM."))
            else:
                for item in self.result.results:
                    if item.success and item.changed:
                        rows.append((item.path.name, "Renombrado", item.before or "-", f"Ahora se llama {item.after}."))
                    elif item.success:
                        rows.append((item.path.name, "Correcto", item.before or item.after, "Ya estaba en Hoja1."))
                    else:
                        rows.append((item.path.name, "Error", item.before or "-", item.message or "No se pudo procesar."))
                for path in self.result.ignored_files:
                    suffix = path.suffix.lower()
                    detail = "Formato Excel antiguo o no soportado." if suffix in {".xls", ".xlsb"} else "No es un Excel XLSX/XLSM."
                    rows.append((path.name, "Ignorado", "-", detail))

            self.result_table.setRowCount(len(rows))
            for row_index, values in enumerate(rows):
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.result_table.setItem(row_index, column, item)

    def _refresh_pilot_state(self) -> None:
        selected_files = self.result.selected_files or self.paths
        excel_count = sum(1 for path in selected_files if path.suffix.lower() in {".xlsx", ".xlsm"})
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
        has_output = bool(self.result.results or self.result.ignored_files)
        if has_output and self.result.error_count:
            return "Completado con avisos", "Algunos archivos se ignoraron o no pudieron modificarse.", 100
        if has_output:
            return "Lote completado", "Los Excel procesables ya tienen la primera hoja como Hoja1.", 100
        if self.paths:
            return "Excel cargados", "Revisa el lote y renombra la hoja para ejecutar el cambio.", 45
        return "Pendiente de Excel", "Carga archivos XLSX o XLSM para preparar la hoja Hoja1.", 0

    def _next_action_text(self) -> str:
        if not self.paths:
            return "Cargar Excel"
        if not self.result.results and not self.result.ignored_files:
            return "Renombrar hoja"
        return "Revisar resultado"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar Excel": self.select_button,
                "Renombrar hoja": self.process_button,
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
