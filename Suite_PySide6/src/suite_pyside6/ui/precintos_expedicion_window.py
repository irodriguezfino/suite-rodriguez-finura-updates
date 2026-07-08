from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QTabWidget,
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
from suite_pyside6.ui.file_dialogs import choose_directory, open_files
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
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
        return ("Cargar Excel", "Seleccionar pallets", "Comprobar", "Guardar TXT")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Precintos Expedición")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Genera TXT de expedición para AX desde Excel de entrada y salidas.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar Excel  ->  2 Seleccionar pallets  ->  3 Comprobar  ->  4 Guardar TXT")
        steps.setObjectName("StepBar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(7)

        entrada_label = QLabel("ENTRADA")
        entrada_label.setObjectName("GroupLabel")
        actions_layout.addWidget(entrada_label)

        self.select_button = QPushButton("Seleccionar Excel")
        self.select_button.setProperty("primary", True)
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        validacion_label = QLabel("VALIDACIÓN")
        validacion_label.setObjectName("GroupLabel")
        actions_layout.addWidget(validacion_label)

        self.suggest_button = QPushButton("Sugerir pallets")
        self.suggest_button.clicked.connect(self.suggest_pallets)
        actions_layout.addWidget(self.suggest_button)

        self.process_button = QPushButton("Comprobar salida")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        actions_layout.addWidget(salida_label)

        self.save_button = QPushButton("Guardar TXT")
        self.save_button.clicked.connect(self.save_dialog)
        actions_layout.addWidget(self.save_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        layout.addWidget(self.summary)

        left = QFrame()
        left.setObjectName("AppCard")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 9, 12, 12)
        left_title = QLabel("Pallets de entrada")
        left_title.setObjectName("SectionLabel")
        self.pallet_table = QTableWidget(0, 4)
        self.pallet_table.setHorizontalHeaderLabels(["Usar", "Pallet", "Precintos", "Kilos"])
        self.pallet_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.pallet_table.verticalHeader().setVisible(False)
        self.pallet_table.itemChanged.connect(self._on_pallet_changed)
        left_layout.addWidget(left_title)
        left_layout.addWidget(self.pallet_table, 1)

        right = QFrame()
        right.setObjectName("AppCard")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 9, 12, 12)
        right_title = QLabel("Salidas y nombres TXT")
        right_title.setObjectName("SectionLabel")
        self.output_table = QTableWidget(0, 6)
        self.output_table.setHorizontalHeaderLabels(["Salida", "Jumbos", "Unidades", "Kilos", "TXT", "Estado"])
        self.output_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.output_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.output_table.verticalHeader().setVisible(False)
        right_layout.addWidget(right_title)
        right_layout.addWidget(self.output_table, 1)

        preview_panel = QFrame()
        preview_panel.setObjectName("AppCard")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 9, 12, 12)
        preview_title = QLabel("Vista previa / log")
        preview_title.setObjectName("SectionLabel")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview, 1)

        tabs = QTabWidget()
        tabs.setObjectName("WorkTabs")
        tabs.addTab(left, "Pallets")
        tabs.addTab(right, "Salidas TXT")
        tabs.addTab(preview_panel, "Log")
        layout.addWidget(tabs, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def select_files(self) -> None:
        files = open_files(
            self,
            "precintos_expedicion/input",
            "Seleccionar Excel de entrada y salidas",
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
                self.status.setText(f"Sugerencia aplicada: {len(suggested)} pallet(s) para {units} unidades.")
            else:
                self.status.setText("No hay combinación exacta. Selecciona pallets manualmente.")

    def process_files(self) -> None:
        if self.carga.entrada is None or not self.carga.salidas:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Selecciona primero un Excel de entrada y una o varias salidas.")
            return
        try:
            entradas = self.carga.entrada.filas
            filtradas = filtrar_precintos_por_pallets(entradas, self._selected_pallets_ordered())  # type: ignore[arg-type]
            self.result = generar_txts_expedicion(filtradas, self.carga.salidas, inicio=datetime.now())
        except Exception as exc:
            self.result = None
            self.status.setText(f"No se genero ningun TXT: {exc}")
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
        folder = choose_directory(self, "precintos_expedicion/export_txt", "Carpeta para guardar los TXT de expedicion")
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
        return saved

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
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
            self.preview.setPlainText("Selecciona un Excel de entrada y una o varias salidas para empezar.")

        ready = self.carga.ready()
        self.suggest_button.setEnabled(ready)
        self.process_button.setEnabled(ready and bool(self.selected_pallets))
        self.save_button.setEnabled(self.result is not None)
        self.clear_button.setEnabled(bool(self.paths or self.result))

    def _fill_pallet_table(self) -> None:
        self.pallet_table.blockSignals(True)
        self.pallet_table.setRowCount(0)
        for row, pallet in enumerate(self.pallets):
            count, weight = self.pallet_data.get(pallet, (0, Decimal("0")))
            self.pallet_table.insertRow(row)
            check_item = QTableWidgetItem("")
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            check_item.setCheckState(Qt.Checked if pallet in self.selected_pallets else Qt.Unchecked)
            self.pallet_table.setItem(row, 0, check_item)
            self._set_table_text(self.pallet_table, row, 1, pallet)
            self._set_table_text(self.pallet_table, row, 2, str(count))
            self._set_table_text(self.pallet_table, row, 3, texto_decimal(weight.quantize(Decimal("0.001"))))
        self.pallet_table.blockSignals(False)

    def _fill_output_table(self) -> None:
        self.output_table.blockSignals(True)
        self.output_table.setRowCount(0)
        for row, salida in enumerate(self.carga.salidas):
            units, kilos, jumbos = totales_salida(salida)
            status = "OK" if self.result is not None else "Pendiente"
            name = self._output_name(salida)
            if not name and status == "OK":
                status = "Requiere nombre"
            self.output_table.insertRow(row)
            self._set_table_text(self.output_table, row, 0, salida.ruta.name)
            self._set_table_text(self.output_table, row, 1, str(jumbos))
            self._set_table_text(self.output_table, row, 2, str(units))
            self._set_table_text(self.output_table, row, 3, texto_decimal(kilos.quantize(Decimal("0.001"))))
            name_item = QTableWidgetItem(texto_nombre_txt(name))
            name_item.setData(Qt.UserRole, str(salida.ruta))
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.output_table.setItem(row, 4, name_item)
            self._set_table_text(self.output_table, row, 5, status)
        self.output_table.blockSignals(False)

    def _summary_text(self) -> str:
        if not self.paths:
            return "Sin archivos cargados"
        if self.carga.entrada is None or not self.carga.salidas:
            return f"Archivos: {len(self.paths)} | Revisa deteccion"
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
        if "no se genero" in status or "falta nombre" in status:
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
