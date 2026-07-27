from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QApplication,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.paths import resource_path
from suite_pyside6.core.precintos_txt_ax import (
    PrecintosTxtAxResult,
    csv_filename_from_source,
    ensure_csv_extension,
    process_txt_file,
    write_ax_csv,
)
from suite_pyside6.ui.components import control_metric_pair, control_rail_label, dropzone, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_file, save_file
from suite_pyside6.ui.polish import confirm_discard_work, polish_window, show_inline_message, sync_recommended_action
from suite_pyside6.ui.theme import base_qss


LOGGER = logging.getLogger(__name__)


class PrecintosTxtAxWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.source_path: Path | None = None
        self.output_path: Path | None = None
        self.is_processing = False
        self.result = PrecintosTxtAxResult()
        self.setWindowTitle("Precintos TXT a CSV AX")
        self.resize(1040, 720)
        self.setMinimumSize(900, 620)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Seleccionar TXT", "Convertir a CSV", "Guardar CSV")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("ControlProductHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(14)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(3)
        title = QLabel("Precintos TXT a CSV AX")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Extrae los precintos situados a la derecha de la flecha y prepara el CSV para Dynamics AX.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)
        hero_state = QFrame()
        hero_state.setObjectName("ControlHeroStatus")
        hero_state_layout = QVBoxLayout(hero_state)
        hero_state_layout.setContentsMargins(10, 8, 10, 8)
        hero_state_layout.setSpacing(2)
        state_label = QLabel("Salida")
        state_label.setObjectName("Overline")
        state_value = QLabel("CSV AX")
        state_value.setObjectName("ModuleTitle")
        hero_state_layout.addWidget(state_label)
        hero_state_layout.addWidget(state_value)
        hero_layout.addWidget(hero_state)
        layout.addWidget(hero)

        layout.addWidget(step_bar("1 Seleccionar TXT  ->  2 Convertir a CSV  ->  3 Guardar CSV"))

        self.select_button = QPushButton("Seleccionar TXT")
        self.select_button.setProperty("primary", True)
        self.select_button.setAccessibleName("Seleccionar archivo TXT")
        self.select_button.clicked.connect(self.select_file)
        self.upload_area = dropzone(
            "Arrastra un archivo TXT aquí",
            "También puedes seleccionarlo con el teclado. El archivo se procesa únicamente en este equipo.",
            self.select_button,
        )
        self.upload_area.setAccessibleName("Área de carga de archivo TXT")
        self.upload_area.setAccessibleDescription("Arrastra un archivo TXT o activa el botón Seleccionar TXT.")
        self.upload_area.setMaximumHeight(145)
        self._enable_upload_drop()
        layout.addWidget(self.upload_area)

        self.file_name = QLabel()
        self.file_name.setObjectName("ResultLabel")
        self.file_name.setWordWrap(True)
        self.file_name.setAccessibleName("Archivo seleccionado")
        layout.addWidget(self.file_name)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("controlCommand", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(8)
        command_panel = QWidget()
        command_copy = QVBoxLayout(command_panel)
        command_copy.setContentsMargins(0, 0, 0, 0)
        command_copy.setSpacing(2)
        command_label = QLabel("Siguiente acción")
        command_label.setObjectName("Overline")
        self.command_hint = QLabel()
        self.command_hint.setObjectName("ControlCommandTitle")
        command_copy.addWidget(command_label)
        command_copy.addWidget(self.command_hint)
        actions_layout.addWidget(command_panel, 1)
        self.convert_button = QPushButton("Convertir a CSV")
        self.convert_button.setProperty("primary", True)
        self.convert_button.clicked.connect(self.convert_and_request_save)
        self.clear_button = QPushButton("Seleccionar otro archivo")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.convert_button)
        actions_layout.addWidget(self.clear_button)
        layout.addWidget(actions)

        workspace = QFrame()
        workspace.setObjectName("ControlPilotWorkspace")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(10)

        summary_panel = QFrame()
        summary_panel.setObjectName("ControlPreviewPanel")
        summary_layout = QVBoxLayout(summary_panel)
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(8)
        summary_layout.addWidget(section_label("Resumen de conversión"))
        metrics = QFrame()
        metrics.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(metrics)
        self.metrics_layout = metrics_layout
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(10)
        for column in range(5):
            metrics_layout.setColumnStretch(column, 1)
        self.metric_lines = control_metric_pair(metrics_layout, 0, "Líneas totales", "0")
        self.metric_valid = control_metric_pair(metrics_layout, 1, "Líneas válidas", "0")
        self.metric_exported = control_metric_pair(metrics_layout, 2, "Precintos detectados", "0")
        self.metric_duplicates = control_metric_pair(metrics_layout, 3, "Duplicados", "0")
        self.metric_skipped = control_metric_pair(metrics_layout, 4, "Líneas ignoradas", "0")
        summary_layout.addWidget(metrics)
        self.summary = QLabel()
        self.summary.setObjectName("ModuleDescription")
        self.summary.setWordWrap(True)
        self.summary.setAccessibleName("Resumen del resultado")
        summary_layout.addWidget(self.summary)
        summary_layout.addWidget(section_label("Precintos leídos"))
        self.precintos_list = QPlainTextEdit()
        self.precintos_list.setObjectName("PrecintosList")
        self.precintos_list.setReadOnly(True)
        self.precintos_list.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.precintos_list.setMinimumHeight(130)
        self.precintos_list.setMaximumHeight(180)
        self.precintos_list.setPlaceholderText("Los precintos detectados aparecerán aquí.")
        self.precintos_list.setAccessibleName("Listado completo de precintos leídos")
        summary_layout.addWidget(self.precintos_list)
        summary_layout.addWidget(section_label("Líneas ignoradas"))
        self.ignored_empty = QLabel("No se han ignorado líneas durante el procesamiento.")
        self.ignored_empty.setObjectName("ModuleDescription")
        self.ignored_empty.setWordWrap(True)
        summary_layout.addWidget(self.ignored_empty)
        self.ignored_table = QTableWidget(0, 3)
        self.ignored_table.setObjectName("IgnoredLinesTable")
        self.ignored_table.setHorizontalHeaderLabels(("N.º línea", "Contenido original", "Motivo"))
        self.ignored_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ignored_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ignored_table.setAlternatingRowColors(True)
        self.ignored_table.setWordWrap(False)
        self.ignored_table.setMinimumHeight(120)
        self.ignored_table.setMaximumHeight(180)
        self.ignored_table.setAccessibleName("Tabla de líneas ignoradas")
        self.ignored_table.verticalHeader().setVisible(False)
        ignored_header = self.ignored_table.horizontalHeader()
        ignored_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        ignored_header.setSectionResizeMode(1, QHeaderView.Stretch)
        ignored_header.setSectionResizeMode(2, QHeaderView.Stretch)
        summary_layout.addWidget(self.ignored_table)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_layout.addWidget(section_label("Estado"))
        self.rail_state = control_rail_label("Pendiente de TXT", role="state")
        self.rail_detail = control_rail_label("Selecciona o arrastra un archivo TXT para empezar.")
        self.rail_next = control_rail_label("Seleccionar TXT", role="action")
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(section_label("Siguiente acción"))
        rail_layout.addWidget(self.rail_next)
        rail_layout.addStretch(1)

        workspace_layout.addWidget(summary_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel()
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Estado de la conversión")
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def _enable_upload_drop(self) -> None:
        self.upload_area.setAcceptDrops(True)

        def dropped_paths(event) -> list[Path]:
            return [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.isLocalFile()
            ]

        def drag_enter(event) -> None:
            if dropped_paths(event):
                event.acceptProposedAction()
            else:
                event.ignore()

        def drop(event) -> None:
            paths = dropped_paths(event)
            if not paths:
                event.ignore()
                return
            self.load_path(paths[0])
            event.acceptProposedAction()

        self.upload_area.dragEnterEvent = drag_enter  # type: ignore[method-assign]
        self.upload_area.dragMoveEvent = drag_enter  # type: ignore[method-assign]
        self.upload_area.dropEvent = drop  # type: ignore[method-assign]

    def set_files(self, paths: list[Path]) -> None:
        if not paths:
            return
        self.load_path(paths[0])

    def load_path(self, path: Path) -> None:
        if path.suffix.lower() != ".txt":
            self.source_path = None
            self.output_path = None
            self.result = PrecintosTxtAxResult()
            self.status.setText("El archivo seleccionado debe tener extensión .txt.")
            self._refresh()
            return
        self.source_path = path
        self.output_path = None
        self.result = PrecintosTxtAxResult(source_path=path)
        LOGGER.info("Archivo TXT seleccionado para precintos AX: %s", path)
        self.is_processing = True
        self.status.setText("Procesando el archivo TXT…")
        self._refresh()
        QApplication.processEvents()
        try:
            self.result = process_txt_file(path)
        except (OSError, UnicodeError):
            LOGGER.exception("No se pudo procesar el TXT de precintos: %s", path)
            self.result = PrecintosTxtAxResult(source_path=path)
            self.status.setText("No se ha podido leer o procesar el archivo seleccionado.")
        else:
            if self.result.precintos:
                self.status.setText("Archivo procesado. Pulsa Convertir a CSV para elegir dónde guardarlo.")
            else:
                self.status.setText("No se han encontrado precintos válidos en el archivo.")
        finally:
            self.is_processing = False
            self._refresh()

    def select_file(self) -> None:
        path = open_file(self, "precintos_txt_ax/input", "Selecciona un archivo TXT", "Archivos TXT (*.txt);;Todos (*.*)")
        if path is not None:
            self.load_path(path)

    def convert_and_request_save(self) -> None:
        """Request an output destination for the already processed TXT."""
        LOGGER.info("Clic recibido en Convertir a CSV")
        self.save_csv_dialog()

    def save_csv_dialog(self) -> None:
        if not self.result.precintos or self.source_path is None:
            LOGGER.warning("Se solicitó guardar CSV sin precintos convertidos")
            self.status.setText("No se han encontrado precintos válidos en el archivo.")
            self._refresh()
            return
        LOGGER.info("Abriendo diálogo para guardar CSV de: %s", self.source_path)
        path = save_file(
            self,
            "precintos_txt_ax/export_csv",
            "Guardar CSV de precintos",
            csv_filename_from_source(self.source_path),
            "CSV (*.csv);;Todos (*.*)",
        )
        if path is not None:
            self.save_path(path)
        else:
            LOGGER.info("Guardado de CSV cancelado por el usuario")
            self.status.setText("Conversión lista. El guardado del CSV se ha cancelado.")
            self._refresh()

    def save_path(self, path: Path) -> None:
        path = ensure_csv_extension(path)
        try:
            LOGGER.info("Escritura de CSV solicitada en: %s", path)
            write_ax_csv(path, self.result.precintos)
            if not path.is_file():
                raise OSError("El archivo CSV no se creó en la ruta indicada")
        except (OSError, UnicodeError):
            LOGGER.exception("No se pudo generar el CSV de precintos: %s", path)
            self.status.setText("No se ha podido generar el CSV seleccionado.")
            self._refresh()
            return
        self.output_path = path
        show_inline_message(self, "success", f"CSV guardado: {path.name}")
        self.status.setText(f"CSV generado correctamente: {path}")
        self._refresh()

    def clear(self) -> None:
        if self.source_path is not None and not confirm_discard_work(self, "Seleccionar otro archivo"):
            return
        self.source_path = None
        self.output_path = None
        self.result = PrecintosTxtAxResult()
        self.status.setText("Selecciona o arrastra un archivo TXT para empezar.")
        self._refresh()

    def _refresh(self) -> None:
        self.file_name.setText(
            f"Archivo seleccionado: {self.source_path.name}" if self.source_path else "Sin archivo seleccionado"
        )
        self.metric_lines.setText(str(self.result.lines_read))
        self.metric_exported.setText(str(self.result.exported_count))
        self.metric_valid.setText(str(self.result.valid_lines))
        self.metric_skipped.setText(str(self.result.skipped_lines))
        self.metric_duplicates.setText(str(self.result.duplicate_count))
        for label, value in (
            (self.metric_lines, self.result.lines_read),
            (self.metric_exported, self.result.exported_count),
            (self.metric_valid, self.result.valid_lines),
            (self.metric_skipped, self.result.skipped_lines),
            (self.metric_duplicates, self.result.duplicate_count),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")
        self.precintos_list.setPlainText("\n".join(self.result.precintos))
        self._refresh_ignored_lines()
        if self.source_path is None:
            self.summary.setText("El CSV incluirá una única columna, sin cabecera.")
        elif self.output_path is not None:
            self.summary.setText(f"{self.result.summary()}\nCSV generado: {self.output_path}")
        else:
            self.summary.setText(self.result.summary())
        state, detail = self._state_text()
        self.rail_state.setText(state)
        self.rail_detail.setText(detail)
        next_action = self._next_action_text()
        self.rail_next.setText(next_action)
        self.command_hint.setText(next_action)
        self.convert_button.setEnabled(bool(self.result.precintos) and not self.is_processing)
        self.clear_button.setEnabled(self.source_path is not None)
        sync_recommended_action(
            self,
            next_action,
            {
                "Seleccionar TXT": self.select_button,
                "Convertir a CSV": self.convert_button,
                "Seleccionar otro archivo": self.clear_button,
            },
            (self.select_button, self.convert_button, self.clear_button),
        )

    def _refresh_ignored_lines(self) -> None:
        ignored_lines = self.result.ignored_lines
        self.ignored_empty.setVisible(not ignored_lines)
        self.ignored_table.setVisible(bool(ignored_lines))
        self.ignored_table.setRowCount(len(ignored_lines))
        for row, ignored_line in enumerate(ignored_lines):
            line_number = QTableWidgetItem(str(ignored_line.line_number))
            line_number.setTextAlignment(Qt.AlignCenter)
            original_content = QTableWidgetItem(ignored_line.original_content)
            original_content.setToolTip(ignored_line.original_content or "Línea vacía")
            reason = QTableWidgetItem(ignored_line.reason)
            reason.setToolTip(ignored_line.reason)
            self.ignored_table.setItem(row, 0, line_number)
            self.ignored_table.setItem(row, 1, original_content)
            self.ignored_table.setItem(row, 2, reason)

    def _state_text(self) -> tuple[str, str]:
        if "generado correctamente" in self.status.text().lower():
            return "CSV generado", "El CSV está listo para importarse en AX."
        if self.result.precintos:
            return "Precintos listos", "El archivo ya está procesado. Pulsa Convertir a CSV para guardarlo."
        if self.source_path is not None and self.result.lines_read:
            return "Sin datos válidos", "No se ha encontrado ningún valor después de la flecha."
        if self.source_path is not None:
            return "TXT procesado", "No se ha encontrado ningún precinto válido."
        return "Pendiente de TXT", "Selecciona o arrastra un archivo TXT para empezar."

    def _next_action_text(self) -> str:
        if self.source_path is None:
            return "Seleccionar TXT"
        if not self.result.precintos:
            return "Seleccionar otro archivo"
        return "Convertir a CSV"

    def flow_state(self) -> tuple[int, bool, bool]:
        if "generado correctamente" in self.status.text().lower():
            return 3, False, True
        if self.source_path is not None and self.result.lines_read and not self.result.precintos:
            return 2, True, False
        if self.result.precintos:
            return 3, False, False
        if self.source_path is not None:
            return 2, False, False
        return 1, False, False
