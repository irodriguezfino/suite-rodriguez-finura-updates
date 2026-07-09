from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
from suite_pyside6.core.precintos_expedicion import (
    ExcelDetectado,
    ExpedicionCarga,
    ResultadoGeneracion,
    buscar_combinacion_pallets_exacta,
    cargar_excels,
    filtrar_precintos_por_pallets,
    generar_txts_expedicion,
    guardar_txts_expedicion,
    normalizar_nombre_txt_usuario,
    pallets_disponibles,
    resumen_pivot_entrada,
    texto_decimal,
    texto_nombre_txt,
    totales_salida,
)
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, section_label, step_bar
from suite_pyside6.ui.file_dialogs import choose_directory, open_files
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


class PrecintosExpedicionWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.carga = ExpedicionCarga(None, [], [], [])
        self.pallets: list[str] = []
        self.pallet_data: dict[str, tuple[int, Decimal]] = {}
        self.selected_pallets: set[str] = set()
        self.result: ResultadoGeneracion | None = None
        self.show_dialogs = True
        self.setWindowTitle("Precintos Expedición")
        self.resize(1220, 760)
        self.setMinimumSize(740, 580)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar Excel", "Elegir pallets", "Comprobar", "Guardar TXT")

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
        title = QLabel("Precintos Expedición")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Selecciona pallets de entrada, valida salidas AX y guarda los TXT de expedición.")
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
        hero_status_label = QLabel("Salida AX")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("Excel a TXT")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)

        steps = step_bar("1 Cargar Excel  ->  2 Elegir pallets  ->  3 Comprobar  ->  4 Guardar TXT")
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
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        validacion_label = QLabel("VALIDACIÓN")
        validacion_label.setObjectName("GroupLabel")
        validacion_label.setVisible(False)
        validacion_label.setMaximumSize(0, 0)
        actions_layout.addWidget(validacion_label)

        self.suggest_button = QPushButton("Sugerir pallets")
        self.suggest_button.clicked.connect(self.suggest_pallets)
        actions_layout.addWidget(self.suggest_button)

        self.process_button = QPushButton("Comprobar salida")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        salida_label.setVisible(False)
        salida_label.setMaximumSize(0, 0)
        actions_layout.addWidget(salida_label)

        self.save_button = QPushButton("Guardar TXT")
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

        main_column = QFrame()
        main_column.setObjectName("ControlPreviewPanel")
        main_layout = QVBoxLayout(main_column)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        left_header = QHBoxLayout()
        left_header.setSpacing(8)
        left_title = section_label("Pallets de entrada")
        self.pallet_count = control_pill("0 pallets")
        left_header.addWidget(left_title)
        left_header.addStretch(1)
        left_header.addWidget(self.pallet_count)
        self.pallet_table = QTableWidget(0, 4)
        self.pallet_table.setAccessibleName("Pallets de entrada")
        self.pallet_table.setHorizontalHeaderLabels(["Usar", "Pallet", "Precintos", "Kilos"])
        self.pallet_table.horizontalHeader().setStretchLastSection(False)
        self.pallet_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pallet_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.pallet_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pallet_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.pallet_table.itemChanged.connect(self._on_pallet_changed)
        self.pallet_table.setMinimumHeight(150)
        main_layout.addLayout(left_header)
        main_layout.addWidget(self.pallet_table, 2)

        self.metrics_strip = QFrame()
        self.metrics_strip.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(4)
        self.metric_outputs = control_metric_pair(metrics_layout, 0, "Salidas", "0")
        self.metric_selected = control_metric_pair(metrics_layout, 1, "Pallets", "0")
        self.metric_units = control_metric_pair(metrics_layout, 2, "Unidades", "0")
        self.metric_kilos = control_metric_pair(metrics_layout, 3, "Kilos", "0")
        main_layout.addWidget(self.metrics_strip)

        output_header = QHBoxLayout()
        output_header.setSpacing(8)
        right_title = section_label("Salidas y nombres TXT")
        self.output_count = control_pill("0 salidas")
        output_header.addWidget(right_title)
        output_header.addStretch(1)
        output_header.addWidget(self.output_count)
        self.output_table = QTableWidget(0, 6)
        self.output_table.setProperty("allowCellEditing", True)
        self.output_table.setAccessibleName("Salidas y nombres TXT")
        self.output_table.setHorizontalHeaderLabels(["Salida", "Jumbos", "Unidades", "Kilos", "TXT", "Estado"])
        self.output_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.output_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.output_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.output_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.output_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.output_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.output_table.setMinimumHeight(140)
        main_layout.addLayout(output_header)
        main_layout.addWidget(self.output_table, 2)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Estado de expedición")
        self.rail_state = control_rail_label("Pendiente de Excel", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga el Excel de entrada y una o varias salidas para empezar.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar Excel", role="action")
        self.rail_next.setWordWrap(True)
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("Entrada: -\nSalidas: 0")
        self.rail_files.setWordWrap(True)
        log_title = section_label("Detalle")
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("OutputText")
        self.preview.setAccessibleName("Detalle de detección y vista previa TXT")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setMinimumHeight(90)
        self.preview.setMaximumHeight(170)
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
        rail_layout.addWidget(self.preview, 1)

        workspace_layout.addWidget(main_column, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def select_files(self) -> None:
        files = open_files(
            self,
            "precintos_expedicion/input",
            "Selecciona Excel de entrada y salidas",
            "Excel moderno (*.xlsx *.xlsm);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def set_files(self, paths: list[Path]) -> None:
        existing = {str(path.resolve()).lower() for path in self.paths if path.exists()}
        for path in paths:
            key = str(path.resolve()).lower() if path.exists() else str(path).lower()
            if key not in existing:
                self.paths.append(path)
                existing.add(key)
        self.result = None
        self.load_excels()

    def load_excels(self) -> None:
        self.carga = cargar_excels(self.paths)
        self.selected_pallets.clear()
        self.pallets = []
        self.pallet_data = {}
        if self.carga.entrada is not None and self.carga.salidas:
            entradas = self.carga.entrada.filas
            self.pallets = pallets_disponibles(entradas)  # type: ignore[arg-type]
            resumen = resumen_pivot_entrada(entradas)  # type: ignore[arg-type]
            self.pallet_data = {pallet: (cuenta, peso) for _codigo, pallet, cuenta, peso in resumen}
            self.suggest_pallets(silent=True)
        self._refresh()

    def suggest_pallets(self, silent: bool = False) -> None:
        if self.carga.entrada is None or not self.carga.salidas:
            if not silent and self.show_dialogs:
                show_inline_message(self, "warning", "Carga un Excel de entrada y una o varias salidas.")
            return
        units = sum(totales_salida(salida)[0] for salida in self.carga.salidas)
        suggested = buscar_combinacion_pallets_exacta(self.pallets, self.pallet_data, units)
        self.selected_pallets = set(suggested)
        self.result = None
        self._refresh()
        if not silent:
            if suggested:
                self.status.setText(f"Sugerencia aplicada: {len(suggested)} pallets para {units} unidades.")
            else:
                self.status.setText("No hay combinación exacta. Selecciona los pallets manualmente.")
            self._refresh_pilot_state()
            self._sync_recommended_action()

    def process_files(self) -> None:
        if self.carga.entrada is None or not self.carga.salidas:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Carga primero un Excel de entrada y una o varias salidas.")
            return
        try:
            entradas = self.carga.entrada.filas
            filtradas = filtrar_precintos_por_pallets(entradas, self._selected_pallets_ordered())  # type: ignore[arg-type]
            self.result = generar_txts_expedicion(filtradas, self.carga.salidas, inicio=datetime.now())
        except Exception as exc:
            self.result = None
            self.status.setText(f"No se generó ningún TXT: {exc}")
            self._refresh()
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.status.setText(f"Comprobación correcta: {len(self.result.salidas)} TXT listos para guardar.")
        self._refresh()

    def save_dialog(self) -> None:
        if self.result is None:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Genera primero los TXT.")
            return
        try:
            self._validate_output_names()
        except Exception as exc:
            self.status.setText(str(exc))
            if self.show_dialogs:
                show_inline_message(self, "warning", str(exc))
            return
        folder = choose_directory(self, "precintos_expedicion/export_txt", "Carpeta para guardar los TXT de expedición")
        if folder:
            self.save_to_directory(folder)

    def save_to_directory(self, folder: Path) -> list[Path]:
        if self.result is None:
            raise ValueError("Genera primero los TXT.")
        manual_names = self._manual_names()
        self._validate_output_names(manual_names)
        saved = guardar_txts_expedicion(self.result, folder, manual_names)
        self.status.setText(f"TXT guardados: {', '.join(path.name for path in saved)}")
        show_inline_message(self, "success", f"TXT guardados: {', '.join(path.name for path in saved)}")
        self._refresh_pilot_state()
        self._sync_recommended_action()
        return saved

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.paths = []
        self.carga = ExpedicionCarga(None, [], [], [])
        self.pallets = []
        self.pallet_data = {}
        self.selected_pallets.clear()
        self.result = None
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self) -> None:
        self._fill_pallet_table()
        self._fill_output_table()
        self.summary.setText(self._summary_text())
        if self.result is not None:
            self.preview.setPlainText(self.result.preview_text())
        elif self.carga.log:
            self.preview.setPlainText("Resultado de detección:\n" + "\n".join(self.carga.log))
        elif self.paths:
            self.preview.setPlainText("Archivos seleccionados:\n\n" + "\n".join(str(path) for path in self.paths))
        else:
            self.preview.setPlainText("Carga un Excel de entrada y una o varias salidas para empezar.")

        ready = self.carga.ready()
        self.suggest_button.setEnabled(ready)
        self.process_button.setEnabled(ready and bool(self.selected_pallets))
        self.save_button.setEnabled(self.result is not None)
        self.clear_button.setEnabled(bool(self.paths or self.result))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _fill_pallet_table(self) -> None:
        with bulk_table_update(self.pallet_table):
            self.pallet_table.setRowCount(len(self.pallets))
            for row, pallet in enumerate(self.pallets):
                count, weight = self.pallet_data.get(pallet, (0, Decimal("0")))
                check_item = QTableWidgetItem("")
                check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                check_item.setCheckState(Qt.Checked if pallet in self.selected_pallets else Qt.Unchecked)
                self.pallet_table.setItem(row, 0, check_item)
                self._set_table_text(self.pallet_table, row, 1, pallet)
                self._set_table_text(self.pallet_table, row, 2, str(count))
                self._set_table_text(self.pallet_table, row, 3, texto_decimal(weight.quantize(Decimal("0.001"))))

    def _fill_output_table(self) -> None:
        with bulk_table_update(self.output_table):
            self.output_table.setRowCount(len(self.carga.salidas))
            for row, salida in enumerate(self.carga.salidas):
                units, kilos, jumbos = totales_salida(salida)
                status = "OK" if self.result is not None else "Pendiente"
                name = self._output_name(salida)
                if not name and status == "OK":
                    status = "Requiere nombre"
                self._set_table_text(self.output_table, row, 0, salida.ruta.name)
                self._set_table_text(self.output_table, row, 1, str(jumbos))
                self._set_table_text(self.output_table, row, 2, str(units))
                self._set_table_text(self.output_table, row, 3, texto_decimal(kilos.quantize(Decimal("0.001"))))
                name_item = QTableWidgetItem(texto_nombre_txt(name))
                name_item.setData(Qt.UserRole, str(salida.ruta))
                name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                self.output_table.setItem(row, 4, name_item)
                self._set_table_text(self.output_table, row, 5, status)

    def _refresh_pilot_state(self) -> None:
        outputs, units, kilos = self._output_totals()
        selected = len(self.selected_pallets)
        self.metric_outputs.setText(str(outputs))
        self.metric_selected.setText(f"{selected}/{len(self.pallets)}")
        self.metric_units.setText(str(units))
        self.metric_kilos.setText(texto_decimal(kilos) if kilos else "0")
        for label, value in (
            (self.metric_outputs, outputs),
            (self.metric_selected, f"{selected} de {len(self.pallets)}"),
            (self.metric_units, units),
            (self.metric_kilos, texto_decimal(kilos) if kilos else "0"),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")

        update_count_label(self.pallet_count, self.pallet_table.rowCount(), len(self.pallets), "pallets")
        update_count_label(self.output_count, self.output_table.rowCount(), outputs, "salidas")
        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso de expedición")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente acción recomendada: {self.rail_next.text()}")
        entrada = self.carga.entrada.ruta.name if self.carga.entrada is not None else "-"
        self.rail_files.setText(f"Entrada: {entrada}\nSalidas: {outputs}\nArchivos cargados: {len(self.paths)}")

    def _output_totals(self) -> tuple[int, int, Decimal]:
        units = 0
        kilos = Decimal("0")
        for salida in self.carga.salidas:
            salida_units, salida_kilos, _jumbos = totales_salida(salida)
            units += salida_units
            kilos += salida_kilos
        return len(self.carga.salidas), units, kilos

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "txt guardados" in status:
            return "TXT guardados", "Los archivos de expedición se han guardado correctamente.", 100
        if "no se genero" in status or "no se generó" in status or "falta nombre" in status:
            return "Revisión necesaria", self.status.text(), 70
        if self.result is not None:
            return "TXT listos", "Revisa nombres de salida y guarda los TXT en carpeta.", 85
        if self.carga.ready() and self.selected_pallets:
            return "Listo para comprobar", "Hay pallets seleccionados para contrastar con las salidas.", 60
        if self.carga.ready():
            return "Excel detectado", "Elige pallets o aplica la sugerencia para preparar la salida.", 40
        if self.paths:
            return "Revisar detección", "Falta entrada o salida válida. Revisa el resumen de archivos.", 20
        return "Pendiente de Excel", "Carga el Excel de entrada y una o varias salidas para empezar.", 0

    def _next_action_text(self) -> str:
        if not self.paths or not self.carga.ready():
            return "Cargar Excel"
        if not self.selected_pallets:
            return "Sugerir pallets"
        if self.result is None:
            return "Comprobar salida"
        return "Guardar TXT"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar Excel": self.select_button,
                "Sugerir pallets": self.suggest_button,
                "Comprobar salida": self.process_button,
                "Guardar TXT": self.save_button,
            },
            (self.select_button, self.suggest_button, self.process_button, self.save_button, self.clear_button),
        )

    def _summary_text(self) -> str:
        if not self.paths:
            return "Sin archivos cargados"
        if self.carga.entrada is None or not self.carga.salidas:
            return f"Archivos: {len(self.paths)} | Revisa detección"
        units = sum(totales_salida(salida)[0] for salida in self.carga.salidas)
        kilos = sum((totales_salida(salida)[1] for salida in self.carga.salidas), Decimal("0"))
        return (
            f"Entrada: {self.carga.entrada.ruta.name} | Salidas: {len(self.carga.salidas)} | "
            f"Pallets: {len(self.pallets)} | Seleccionados: {len(self.selected_pallets)} | "
            f"Unidades: {units} | Kilos: {texto_decimal(kilos)}"
        )

    def _selected_pallets_ordered(self) -> list[str]:
        return [pallet for pallet in self.pallets if pallet in self.selected_pallets]

    def _manual_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for row in range(self.output_table.rowCount()):
            item = self.output_table.item(row, 4)
            if item is None:
                continue
            route = item.data(Qt.UserRole)
            text = item.text().strip()
            if text and text != "Requiere nombre":
                names[str(route)] = normalizar_nombre_txt_usuario(text)
        return names

    def _validate_output_names(self, names: dict[str, str] | None = None) -> None:
        if self.result is None:
            return
        names = names if names is not None else self._manual_names()
        usados: set[str] = set()
        pendientes: list[str] = []
        for salida in self.result.salidas:
            nombre = salida.nombre_txt or names.get(str(salida.ruta_origen))
            if not nombre:
                pendientes.append(salida.ruta_origen.name)
                continue
            normalizado = normalizar_nombre_txt_usuario(nombre)
            clave = normalizado.lower()
            if clave in usados:
                raise ValueError(f"Nombre TXT duplicado: {normalizado}")
            usados.add(clave)
        if pendientes:
            raise ValueError("Falta nombre TXT para: " + ", ".join(pendientes))

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "txt guardados" in status:
            return 4, False, True
        if "no se genero" in status or "no se generó" in status or "falta nombre" in status:
            return 3, True, False
        if self.result is not None:
            return 4, False, False
        if self.carga.ready() and self.selected_pallets:
            return 3, False, False
        if self.carga.ready():
            return 2, False, False
        if self.paths:
            return 1, True, False
        return 1, False, False

    @staticmethod
    def _output_name(salida: ExcelDetectado) -> str | None:
        from suite_pyside6.core.precintos_expedicion import nombre_txt_desde_salida

        return nombre_txt_desde_salida(salida.ruta)

    @staticmethod
    def _set_table_text(table: QTableWidget, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        table.setItem(row, column, item)

    def _on_pallet_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        pallet_item = self.pallet_table.item(item.row(), 1)
        if pallet_item is None:
            return
        pallet = pallet_item.text()
        if item.checkState() == Qt.Checked:
            self.selected_pallets.add(pallet)
        else:
            self.selected_pallets.discard(pallet)
        self.result = None
        self._refresh()
