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

from suite_pyside6.core.mermas import MermasResult, process_mermas, save_mermas_excel
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.components import ModernSelect, control_metric_pair, control_pill, control_rail_label, labeled_field, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


class MermasWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.final_files: list[Path] = []
        self.origin_file: Path | None = None
        self.result = MermasResult()
        self.show_dialogs = True
        self.setWindowTitle("Merma Jamones FAC")
        self.resize(1120, 720)
        self.setMinimumSize(720, 540)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar finales", "Cargar origen", "Procesar", "Guardar Excel")

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
        title = QLabel("Merma Jamones FAC")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Cruza CSV finales con origen, filtra cumplimiento y genera el Excel de merma.")
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
        hero_status_label = QLabel("Cruce FAC")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("CSV a Excel")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)

        steps = step_bar("1 Cargar finales  ->  2 Cargar origen  ->  3 Filtrar/procesar  ->  4 Guardar Excel")
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
        self.command_hint = QLabel("Cargar CSVs finales")
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

        self.final_button = QPushButton("Cargar CSVs finales")
        self.final_button.setProperty("primary", True)
        self.final_button.clicked.connect(self.select_final_files)
        actions_layout.addWidget(self.final_button)

        self.origin_button = QPushButton("Cargar origen")
        self.origin_button.clicked.connect(self.select_origin_file)
        actions_layout.addWidget(self.origin_button)

        self.filter_combo = ModernSelect(placeholder="Filtra el cumplimiento")
        self.filter_combo.setProperty("filterSelect", True)
        self.filter_combo.setAccessibleName("Filtro de cumplimiento")
        self.filter_combo.setAccessibleDescription("Filtra los resultados por cumplimiento. Abre las opciones con Espacio o Enter.")
        self.filter_combo.add_option("SI", description="Mostrar sólo los registros que cumplen")
        self.filter_combo.add_option("NO", description="Mostrar sólo los registros que no cumplen")
        self.filter_combo.add_option("TODOS", description="Mostrar todos los registros")
        self.filter_combo.currentTextChanged.connect(lambda _text: self._refresh())

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        proceso_label.setVisible(False)
        proceso_label.setMaximumSize(0, 0)
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar cruce")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        salida_label.setVisible(False)
        salida_label.setMaximumSize(0, 0)
        actions_layout.addWidget(salida_label)

        self.save_button = QPushButton("Guardar Excel")
        self.save_button.clicked.connect(self.save_dialog)

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

        panel = QFrame()
        panel.setObjectName("ControlPreviewPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(8)
        panel_header = QHBoxLayout()
        panel_header.setSpacing(8)
        panel_title = section_label("Resultado del cruce")
        self.result_count = control_pill("0 registros")
        panel_header.addWidget(panel_title)
        panel_header.addStretch(1)
        panel_header.addWidget(self.result_count)

        self.result_table = QTableWidget(0, 0)
        self.result_table.setAccessibleName("Vista previa del resultado de mermas")
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.metrics_strip = QFrame()
        self.metrics_strip.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(4)
        self.metric_final_files = control_metric_pair(metrics_layout, 0, "Finales", "0")
        self.metric_rows = control_metric_pair(metrics_layout, 1, "Leídas", "0")
        self.metric_result = control_metric_pair(metrics_layout, 2, "Resultado", "0")
        self.metric_lotes = control_metric_pair(metrics_layout, 3, "Lotes", "0")

        panel_layout.addLayout(panel_header)
        panel_layout.addWidget(self.metrics_strip)
        panel_layout.addWidget(self.result_table, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Control del cruce")
        self.rail_state = control_rail_label("Pendiente de archivos", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga los CSV finales y el archivo de origen para preparar el cruce.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar CSVs finales", role="action")
        self.rail_next.setWordWrap(True)
        filter_title = section_label("Filtro")
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("Finales: 0\nOrigen: -")
        self.rail_files.setWordWrap(True)
        log_title = section_label("Detalle")
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("OutputText")
        self.preview.setAccessibleName("Detalle del proceso de mermas")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setMinimumHeight(90)
        self.preview.setMaximumHeight(180)
        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(filter_title)
        rail_layout.addWidget(labeled_field("Cumple", self.filter_combo, compact=True))
        rail_layout.addWidget(files_title)
        rail_layout.addWidget(self.rail_files)
        rail_layout.addWidget(self.save_button)
        rail_layout.addWidget(log_title)
        rail_layout.addWidget(self.preview, 1)

        workspace_layout.addWidget(panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def select_final_files(self) -> None:
        files = open_files(
            self,
            "mermas/finales",
            "Selecciona archivos CSV finales",
            "Archivos CSV (*.csv);;Todos (*.*)",
        )
        if files:
            self.set_final_files(files)

    def select_origin_file(self) -> None:
        file = open_file(
            self,
            "mermas/origen",
            "Selecciona archivo de origen",
            "Origen (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls);;Todos (*.*)",
        )
        if file:
            self.set_origin_file(file)

    def set_final_files(self, paths: list[Path]) -> None:
        self.final_files = list(paths)
        self.status.setText(f"{len(self.final_files)} archivos finales cargados.")
        self._refresh(selected_only=True)

    def set_origin_file(self, path: Path) -> None:
        self.origin_file = path
        self.status.setText(f"Origen cargado: {path.name}")
        self._refresh(selected_only=True)

    def process_files(self) -> None:
        if not self.final_files:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Carga primero uno o más CSV finales.")
            return
        if self.origin_file is None:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Carga primero el archivo de origen.")
            return
        try:
            self.result = process_mermas(self.final_files, self.origin_file, self.filter_combo.currentText())  # type: ignore[arg-type]
        except Exception as exc:
            self.status.setText(f"Error: {exc}")
            self._refresh_pilot_state()
            self._sync_recommended_action()
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.status.setText(f"Cruce completado: {len(self.result.dataframe)} registros.")
        self._refresh()

    def save_dialog(self) -> None:
        if self.result.dataframe.empty:
            if self.show_dialogs:
                show_inline_message(self, "warning", "No hay resultados para guardar.")
            return
        file = save_file(
            self,
            "mermas/export_excel",
            "Guardar resultado en Excel",
            "resultado_mermas.xlsx",
            "Excel (*.xlsx)",
        )
        if file:
            self.save_path(file)

    def save_path(self, path: Path) -> None:
        save_mermas_excel(path, self.result)
        self.status.setText(f"Excel guardado: {path}")
        show_inline_message(self, "success", f"Excel guardado: {path.name}")
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.final_files = []
        self.origin_file = None
        self.result = MermasResult()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            lines = ["CSV finales:"]
            lines.extend(str(path) for path in self.final_files)
            lines.append("")
            lines.append("Archivo de origen:")
            lines.append(str(self.origin_file) if self.origin_file else "")
            self.preview.setPlainText("\n".join(lines).strip())
            self.summary.setText(f"Finales: {len(self.final_files)} | Origen: {'sí' if self.origin_file else 'no'}")
            self._fill_result_table(empty=True)
        else:
            self.summary.setText(
                " | ".join(self.result.summary.lines()[:4])
                if not self.result.dataframe.empty
                else "Sin archivos cargados"
            )
            self.preview.setPlainText(self.result.preview_text() if not self.result.dataframe.empty else "Selecciona los CSV finales y el archivo de origen para empezar.")
            self._fill_result_table()
        self.process_button.setEnabled(bool(self.final_files and self.origin_file))
        self.save_button.setEnabled(not self.result.dataframe.empty)
        self.clear_button.setEnabled(bool(self.final_files or self.origin_file or not self.result.dataframe.empty))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _fill_result_table(self, *, empty: bool = False) -> None:
        with bulk_table_update(self.result_table):
            self.result_table.clear()
            self.result_table.setRowCount(0)
            self.result_table.setColumnCount(0)
            if empty or self.result.dataframe.empty:
                return
            frame = self.result.dataframe.head(100)
            columns = [str(column) for column in frame.columns]
            self.result_table.setColumnCount(len(columns))
            self.result_table.setHorizontalHeaderLabels(columns)
            self.result_table.setRowCount(len(frame))
            for row_index, (_index, row) in enumerate(frame.iterrows()):
                for column_index, column in enumerate(frame.columns):
                    item = QTableWidgetItem(str(row[column]))
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.result_table.setItem(row_index, column_index, item)
            header = self.result_table.horizontalHeader()
            for column_index in range(len(columns)):
                header.setSectionResizeMode(column_index, QHeaderView.ResizeToContents)
            if columns:
                header.setSectionResizeMode(len(columns) - 1, QHeaderView.Stretch)

    def _refresh_pilot_state(self) -> None:
        summary = self.result.summary
        result_rows = 0 if self.result.dataframe.empty else len(self.result.dataframe)
        self.metric_final_files.setText(str(len(self.final_files)))
        self.metric_rows.setText(str(summary.filas_leidas if summary.filas_leidas else "-"))
        self.metric_result.setText(str(result_rows))
        self.metric_lotes.setText(str(summary.lotes_origen_informados if summary.lotes_origen_informados else "-"))
        for label, value in (
            (self.metric_final_files, len(self.final_files)),
            (self.metric_rows, summary.filas_leidas if summary.filas_leidas else 0),
            (self.metric_result, result_rows),
            (self.metric_lotes, summary.lotes_origen_informados if summary.lotes_origen_informados else 0),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")

        update_count_label(self.result_count, self.result_table.rowCount(), result_rows, "registros")
        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso del cruce de mermas")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente acción recomendada: {self.rail_next.text()}")
        origin_name = self.origin_file.name if self.origin_file else "-"
        self.rail_files.setText(f"Finales: {len(self.final_files)}\nOrigen: {origin_name}\nFiltro: {self.filter_combo.currentText()}")

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "guardado" in status:
            return "Excel guardado", "El resultado de merma se ha exportado correctamente.", 100
        if "error" in status:
            return "Revisión necesaria", self.status.text(), 65
        if not self.result.dataframe.empty:
            return "Cruce completado", "Revisa la tabla y guarda el Excel de resultado.", 85
        if self.final_files and self.origin_file:
            return "Listo para procesar", "Los finales y el origen están cargados. Ejecuta el cruce.", 55
        if self.final_files:
            return "Finales cargados", "Carga el archivo de origen para completar la preparación.", 30
        if self.origin_file:
            return "Origen cargado", "Carga uno o varios CSV finales FAC para continuar.", 25
        return "Pendiente de archivos", "Carga los CSV finales y el archivo de origen para preparar el cruce.", 0

    def _next_action_text(self) -> str:
        if not self.final_files:
            return "Cargar CSVs finales"
        if self.origin_file is None:
            return "Cargar origen"
        if self.result.dataframe.empty:
            return "Procesar cruce"
        return "Guardar Excel"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar CSVs finales": self.final_button,
                "Cargar origen": self.origin_button,
                "Procesar cruce": self.process_button,
                "Guardar Excel": self.save_button,
            },
            (self.final_button, self.origin_button, self.process_button, self.save_button, self.clear_button),
        )

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if "error" in status:
            return 3, True, False
        if not self.result.dataframe.empty:
            return 4, False, False
        if self.final_files and self.origin_file:
            return 3, False, False
        if self.final_files:
            return 2, False, False
        if self.origin_file:
            return 1, True, False
        return 1, False, False
