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
from suite_pyside6.core.txt_csv import TxtCsvResult, process_txt_files, write_txt_csv
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


class TxtCsvWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.result = TxtCsvResult()
        self.setWindowTitle("Procesador TXT a CSV")
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
        return ("Cargar TXT", "Procesar", "Revisar vista previa", "Guardar CSV")

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
        title = QLabel("Procesador TXT a CSV")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Convierte TXT operativos en CSV revisable y listo para exportar.")
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
        hero_status_label = QLabel("Conversión")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("TXT a CSV")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)

        steps = step_bar("1 Cargar TXT  ->  2 Procesar  ->  3 Revisar vista previa  ->  4 Guardar CSV")
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
        self.command_hint = QLabel("Cargar TXT")
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

        self.select_button = QPushButton("Cargar TXT")
        self.select_button.setProperty("primary", True)
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        proceso_label.setVisible(False)
        proceso_label.setMaximumSize(0, 0)
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar archivos")
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
        preview_title = section_label("Vista previa CSV")
        self.preview_count = control_pill("0 líneas")
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
        self.metric_lines = control_metric_pair(metrics_layout, 1, "Líneas", "0")
        self.metric_errors = control_metric_pair(metrics_layout, 2, "Errores", "0")
        self.metric_ready = control_metric_pair(metrics_layout, 3, "Salida", "-")

        self.preview_table = QTableWidget(0, 2)
        self.preview_table.setAccessibleName("Vista previa de líneas CSV procesadas")
        self.preview_table.setHorizontalHeaderLabels(["#", "Línea CSV"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Estado de conversión")
        self.rail_state = control_rail_label("Pendiente de TXT", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga uno o varios TXT para preparar la conversión.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar TXT", role="action")
        self.rail_next.setWordWrap(True)
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("Sin archivos seleccionados")
        self.rail_files.setWordWrap(True)
        detail_title = section_label("Detalle")
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("OutputText")
        self.preview.setAccessibleName("Detalle de archivos y conversión")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setMinimumHeight(80)
        self.preview.setMaximumHeight(140)

        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.metrics_strip)
        preview_layout.addWidget(self.preview_table, 1)

        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(files_title)
        rail_layout.addWidget(self.rail_files)
        rail_layout.addWidget(self.save_button)
        rail_layout.addWidget(detail_title)
        rail_layout.addWidget(self.preview, 1)

        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = TxtCsvResult(selected_files=self.paths)
        self.status.setText(f"{len(self.paths)} archivos cargados. Procesa los archivos para continuar.")
        self._refresh(selected_only=True)

    def select_files(self) -> None:
        files = open_files(
            self,
            "txt_csv/input",
            "Selecciona archivos TXT",
            "Archivos TXT (*.txt);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def process_selected_files(self) -> None:
        if not self.paths:
            show_inline_message(self, "warning", "Carga primero uno o varios archivos TXT.")
            return
        self.result = process_txt_files(self.paths)
        self.status.setText(self.result.summary())
        self._refresh()

    def save_csv_dialog(self) -> None:
        if not self.result.processed_lines:
            show_inline_message(self, "warning", "No hay datos procesados para guardar.")
            return
        file = save_file(
            self,
            "txt_csv/export_csv",
            "Guardar CSV",
            "resultado.csv",
            "CSV (*.csv);;Todos (*.*)",
        )
        if file:
            self.save_csv_path(file)

    def save_csv_path(self, path: Path) -> None:
        write_txt_csv(path, self.result.processed_lines)
        self.status.setText(f"CSV guardado: {path}")
        show_inline_message(self, "success", f"CSV guardado: {path.name}")
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.paths = []
        self.result = TxtCsvResult()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            self.summary.setText(f"{len(self.paths)} archivos seleccionados")
            self.preview.setPlainText("\n".join(str(path) for path in self.paths))
            self._fill_preview_table(empty=True)
        else:
            self.summary.setText(self.result.summary() if self.result.selected_files else "Sin archivos cargados")
            self.preview.setPlainText(
                self.result.preview_text()
                if self.result.selected_files
                else "Arrastra archivos TXT aquí o carga TXT para empezar.\n\nFormato admitido: .txt"
            )
            self._fill_preview_table()

        self.process_button.setEnabled(bool(self.paths))
        self.save_button.setEnabled(bool(self.result.processed_lines))
        self.clear_button.setEnabled(bool(self.paths or self.result.processed_lines))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _fill_preview_table(self, *, empty: bool = False) -> None:
        with bulk_table_update(self.preview_table):
            self.preview_table.setRowCount(0)
            if empty or not self.result.processed_lines:
                return
            rows = self.result.processed_lines[:100]
            self.preview_table.setRowCount(len(rows))
            for row_index, line in enumerate(rows):
                number_item = QTableWidgetItem(str(row_index + 1))
                number_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                line_item = QTableWidgetItem(line)
                line_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.preview_table.setItem(row_index, 0, number_item)
                self.preview_table.setItem(row_index, 1, line_item)

    def _refresh_pilot_state(self) -> None:
        lines = len(self.result.processed_lines)
        errors = self.result.error_count
        self.metric_files.setText(str(len(self.paths)))
        self.metric_lines.setText(str(lines))
        self.metric_errors.setText(str(errors))
        self.metric_ready.setText("Listo" if lines else "-")
        for label, value in (
            (self.metric_files, len(self.paths)),
            (self.metric_lines, lines),
            (self.metric_errors, errors),
            (self.metric_ready, "Listo" if lines else "Pendiente"),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")

        update_count_label(self.preview_count, min(lines, self.preview_table.rowCount()), lines, "líneas")
        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso de conversión TXT a CSV")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente acción recomendada: {self.rail_next.text()}")
        if self.paths:
            shown = [path.name for path in self.paths[:4]]
            suffix = f"\n+{len(self.paths) - 4} más" if len(self.paths) > 4 else ""
            self.rail_files.setText("\n".join(shown) + suffix)
        else:
            self.rail_files.setText("Sin archivos seleccionados")

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "guardado" in status:
            return "CSV guardado", "El archivo CSV se ha exportado correctamente.", 100
        if self.result.processed_lines:
            if self.result.error_count:
                return "Conversión con avisos", "Revisa los errores detectados antes de guardar.", 85
            return "CSV listo", "Revisa la vista previa y guarda el CSV final.", 85
        if self.paths:
            return "TXT cargados", "Procesa los archivos para generar la vista previa CSV.", 40
        return "Pendiente de TXT", "Carga uno o varios TXT para preparar la conversión.", 0

    def _next_action_text(self) -> str:
        if not self.paths:
            return "Cargar TXT"
        if not self.result.processed_lines:
            return "Procesar archivos"
        return "Guardar CSV"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar TXT": self.select_button,
                "Procesar archivos": self.process_button,
                "Guardar CSV": self.save_button,
            },
            (self.select_button, self.process_button, self.save_button, self.clear_button),
        )

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if self.result.processed_lines:
            return 4, False, False
        if self.paths:
            return 2, False, False
        return 1, False, False
