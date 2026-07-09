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
from suite_pyside6.core.precintos_excel import ProcessResult, process_files, write_precintos_csv
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


class PrecintosExcelWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.result = ProcessResult()
        self.setWindowTitle("Precintos Excel a CSV")
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
        return ("Cargar archivos", "Procesar", "Revisar resultado", "Guardar CSV")

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
        title = QLabel("Precintos Excel a CSV")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Extrae la columna Identificación de Excel y prepara un CSV para Dynamics.")
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
        hero_status_label = QLabel("Exportación")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("Excel a CSV")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)

        steps = step_bar("1 Cargar archivos  ->  2 Procesar  ->  3 Revisar resultado  ->  4 Guardar CSV")
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
        self.command_hint = QLabel("Cargar archivos")
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

        self.select_button = QPushButton("Cargar archivos")
        self.select_button.setProperty("primary", True)
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        proceso_label.setVisible(False)
        proceso_label.setMaximumSize(0, 0)
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar Excel")
        self.process_button.clicked.connect(self.process_selected_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        salida_label.setVisible(False)
        salida_label.setMaximumSize(0, 0)
        actions_layout.addWidget(salida_label)

        self.save_button = QPushButton("Guardar CSV")
        self.save_button.clicked.connect(self.save_csv_dialog)

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
        preview_title = section_label("Precintos detectados")
        self.preview_count = control_pill("0 precintos")
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
        self.metric_precintos = control_metric_pair(metrics_layout, 2, "Precintos", "0")
        self.metric_issues = control_metric_pair(metrics_layout, 3, "Avisos", "0")

        self.preview_table = QTableWidget(0, 2)
        self.preview_table.setAccessibleName("Precintos detectados para exportar")
        self.preview_table.setHorizontalHeaderLabels(["#", "Precinto"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.preview = QPlainTextEdit()
        self.preview.setObjectName("OutputText")
        self.preview.setAccessibleName("Lista textual de precintos detectados")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setMaximumHeight(110)

        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.metrics_strip)
        preview_layout.addWidget(self.preview_table, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Estado de extracción")
        self.rail_state = control_rail_label("Pendiente de archivos", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga archivos. Solo XLSX/XLSM se procesarán.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar archivos", role="action")
        self.rail_next.setWordWrap(True)
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("Sin archivos seleccionados")
        self.rail_files.setWordWrap(True)
        log_title = section_label("Resumen de proceso")
        self.log = QPlainTextEdit()
        self.log.setObjectName("OutputText")
        self.log.setAccessibleName("Resumen de proceso de extracción")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log.setMinimumHeight(90)
        self.log.setMaximumHeight(170)

        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(files_title)
        rail_layout.addWidget(self.rail_files)
        rail_layout.addWidget(self.save_button)
        rail_layout.addWidget(log_title)
        rail_layout.addWidget(self.log, 1)

        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Carga archivos para empezar.")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = ProcessResult(selected_files=self.paths)
        self.status.setText("Selección completada. Procesa los Excel para continuar.")
        self._refresh(selected_only=True)

    def select_files(self) -> None:
        files = open_files(
            self,
            "exportar_precintos_excel/input",
            "Selecciona anexos y archivos",
            "Archivos admitidos (*.xlsx *.xlsm *.xls *.xlsb *.pdf *.csv *.txt);;Excel moderno (*.xlsx *.xlsm);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def process_selected_files(self) -> None:
        if not self.paths:
            show_inline_message(self, "warning", "Carga primero uno o varios archivos.")
            return
        self.result = process_files(self.paths)
        if self.result.precintos:
            self.status.setText(f"Proceso finalizado: {len(self.result.precintos)} precintos listos para guardar.")
        else:
            self.status.setText("No se extrajeron precintos. Revisa que exista la columna Identificación.")
        self._refresh()

    def save_csv_dialog(self) -> None:
        if not self.result.precintos:
            show_inline_message(self, "warning", "Procesa primero los Excel para generar precintos.")
            return
        file = save_file(
            self,
            "exportar_precintos_excel/export_csv",
            "Guardar CSV de precintos",
            "Precintos.csv",
            "CSV (*.csv);;Todos (*.*)",
        )
        if file:
            self.save_csv_path(file)

    def save_csv_path(self, path: Path) -> None:
        write_precintos_csv(path, self.result.precintos)
        self.status.setText(f"CSV guardado: {path.name}")
        show_inline_message(self, "success", f"CSV guardado: {path.name}")
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.paths = []
        self.result = ProcessResult()
        self.status.setText("Carga archivos para empezar.")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            processable = sum(1 for path in self.paths if path.suffix.lower() in {".xlsx", ".xlsm"})
            ignored = len(self.paths) - processable
            self.summary.setText(
                f"{len(self.paths)} archivos seleccionados | Excel procesables: {processable} | Ignorados: {ignored}"
            )
            self.preview.setPlainText("Aquí se mostrarán los precintos extraídos antes de guardar el CSV.")
            self.log.setPlainText("Archivos seleccionados:\n" + "\n".join(f"- {path.name}" for path in self.paths))
            self._fill_preview_table(empty=True)
        else:
            self.summary.setText(self.result.summary() if self.result.selected_files else "Sin archivos cargados")
            self.preview.setPlainText(
                "\n".join(self.result.precintos)
                if self.result.precintos
                else "Aquí se mostrarán los precintos extraídos antes de guardar el CSV."
            )
            self.log.setPlainText(
                self.result.log_text()
                if self.result.selected_files
                else "Carga archivos PDF, Excel u otros; solo se procesarán XLSX/XLSM."
            )
            self._fill_preview_table()

        self.process_button.setEnabled(bool(self.paths))
        self.save_button.setEnabled(bool(self.result.precintos))
        self.clear_button.setEnabled(bool(self.paths or self.result.precintos or self.result.errors))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _fill_preview_table(self, *, empty: bool = False) -> None:
        with bulk_table_update(self.preview_table):
            self.preview_table.setRowCount(0)
            if empty or not self.result.precintos:
                return
            rows = self.result.precintos[:250]
            self.preview_table.setRowCount(len(rows))
            for row_index, precinto in enumerate(rows):
                number_item = QTableWidgetItem(str(row_index + 1))
                number_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                precinto_item = QTableWidgetItem(precinto)
                precinto_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.preview_table.setItem(row_index, 0, number_item)
                self.preview_table.setItem(row_index, 1, precinto_item)

    def _refresh_pilot_state(self) -> None:
        selected_files = self.result.selected_files or self.paths
        excel_count = sum(1 for path in selected_files if path.suffix.lower() in {".xlsx", ".xlsm"})
        issue_count = self.result.issue_count if self.result.selected_files else max(0, len(selected_files) - excel_count)
        self.metric_files.setText(str(len(selected_files)))
        self.metric_excel.setText(str(excel_count))
        self.metric_precintos.setText(str(len(self.result.precintos)))
        self.metric_issues.setText(str(issue_count))
        for label, value in (
            (self.metric_files, len(selected_files)),
            (self.metric_excel, excel_count),
            (self.metric_precintos, len(self.result.precintos)),
            (self.metric_issues, issue_count),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")

        update_count_label(self.preview_count, self.preview_table.rowCount(), len(self.result.precintos), "precintos")
        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso de extracción de precintos")
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
        status = self.status.text().lower()
        if "guardado" in status:
            return "CSV guardado", "El CSV de precintos se ha exportado correctamente.", 100
        if self.result.errors and not self.result.precintos:
            return "Revisión necesaria", "No se han extraído precintos. Revisa el resumen de proceso.", 70
        if self.result.precintos:
            if self.result.issue_count:
                return "Precintos con avisos", "Hay precintos listos y algunos archivos ignorados o con error.", 85
            return "Precintos listos", "Revisa la tabla y guarda el CSV final.", 85
        if self.paths:
            return "Archivos cargados", "Procesa los Excel para extraer la columna Identificación.", 40
        return "Pendiente de archivos", "Carga archivos. Solo XLSX/XLSM se procesarán.", 0

    def _next_action_text(self) -> str:
        if not self.paths:
            return "Cargar archivos"
        if not self.result.precintos:
            return "Procesar Excel"
        return "Guardar CSV"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar archivos": self.select_button,
                "Procesar Excel": self.process_button,
                "Guardar CSV": self.save_button,
            },
            (self.select_button, self.process_button, self.save_button, self.clear_button),
        )

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if self.result.errors and not self.result.precintos:
            return 2, True, False
        if self.result.precintos:
            return 4, False, False
        if self.paths:
            return 2, False, False
        return 1, False, False
