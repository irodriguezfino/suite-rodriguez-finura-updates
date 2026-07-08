from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.paths import resource_path
from suite_pyside6.core.precintos_excel import ProcessResult, process_files, write_precintos_csv
from suite_pyside6.ui.file_dialogs import open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.responsive import register_adaptive_layout
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

        title = QLabel("Precintos Excel a CSV")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Extrae la columna Identificacion de XLSX/XLSM y genera un CSV Windows para Dynamics.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar archivos  ->  2 Procesar  ->  3 Revisar resultado  ->  4 Guardar CSV")
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

        self.select_button = QPushButton("Seleccionar archivos")
        self.select_button.setProperty("primary", True)
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar Excel")
        self.process_button.clicked.connect(self.process_selected_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        actions_layout.addWidget(salida_label)

        self.save_button = QPushButton("Guardar CSV")
        self.save_button.clicked.connect(self.save_csv_dialog)
        actions_layout.addWidget(self.save_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        layout.addWidget(self.summary)

        body = QBoxLayout(QBoxLayout.LeftToRight)
        body.setSpacing(8)

        preview_panel = QFrame()
        preview_panel.setObjectName("AppCard")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 9, 12, 12)
        preview_title = QLabel("Precintos detectados")
        preview_title.setObjectName("SectionLabel")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview, 1)
        body.addWidget(preview_panel, 3)

        log_panel = QFrame()
        log_panel.setObjectName("AppCard")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(12, 9, 12, 12)
        log_title = QLabel("Resumen de proceso")
        log_title.setObjectName("SectionLabel")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log, 1)
        body.addWidget(log_panel, 2)

        layout.addLayout(body, 1)
        register_adaptive_layout(self, body, breakpoint_width=880)

        self.status = QLabel("Listo para seleccionar archivos.")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = ProcessResult(selected_files=self.paths)
        self.status.setText("Seleccion completada. Pulsa Procesar Excel.")
        self._refresh(selected_only=True)

    def select_files(self) -> None:
        files = open_files(
            self,
            "exportar_precintos_excel/input",
            "Seleccionar anexos y archivos",
            "Archivos admitidos (*.xlsx *.xlsm *.xls *.xlsb *.pdf *.csv *.txt);;Excel moderno (*.xlsx *.xlsm);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def process_selected_files(self) -> None:
        if not self.paths:
            show_inline_message(self, "warning", "Selecciona primero uno o varios archivos.")
            return
        self.result = process_files(self.paths)
        if self.result.precintos:
            self.status.setText(f"Proceso finalizado: {len(self.result.precintos)} precintos listos para guardar.")
        else:
            self.status.setText("No se extrajeron precintos. Revisa que exista la columna Identificacion.")
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
        self.status.setText(f"CSV guardado en formato Windows: {path.name}")
        show_inline_message(self, "success", f"CSV guardado en formato Windows: {path.name}")

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.paths = []
        self.result = ProcessResult()
        self.status.setText("Listo para seleccionar archivos.")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            processable = sum(1 for path in self.paths if path.suffix.lower() in {".xlsx", ".xlsm"})
            ignored = len(self.paths) - processable
            self.summary.setText(
                f"Archivos seleccionados: {len(self.paths)} | Excel procesables: {processable} | Ignorados al procesar: {ignored}"
            )
            self.preview.setPlainText("Aqui se mostraran los precintos extraidos antes de guardar el CSV.")
            self.log.setPlainText("Archivos seleccionados:\n" + "\n".join(f"- {path.name}" for path in self.paths))
        else:
            self.summary.setText(self.result.summary() if self.result.selected_files else "Sin archivos cargados")
            self.preview.setPlainText(
                "\n".join(self.result.precintos)
                if self.result.precintos
                else "Aqui se mostraran los precintos extraidos antes de guardar el CSV."
            )
            self.log.setPlainText(
                self.result.log_text()
                if self.result.selected_files
                else "Selecciona archivos PDF, Excel u otros; solo se procesaran XLSX/XLSM."
            )

        self.process_button.setEnabled(bool(self.paths))
        self.save_button.setEnabled(bool(self.result.precintos))
        self.clear_button.setEnabled(bool(self.paths or self.result.precintos or self.result.errors))

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
