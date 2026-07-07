from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
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
from suite_pyside6.core.txt_csv import TxtCsvResult, process_txt_files, write_txt_csv
from suite_pyside6.ui.file_dialogs import open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
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

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Procesador TXT a CSV")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Selecciona archivos TXT, revisa la vista previa y guarda el CSV final.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar TXT  ->  2 Procesar  ->  3 Revisar vista previa  ->  4 Guardar CSV")
        steps.setObjectName("StepBar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(7)

        self.select_button = QPushButton("Seleccionar TXT")
        self.select_button.setProperty("primary", True)
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        self.process_button = QPushButton("Procesar archivos")
        self.process_button.clicked.connect(self.process_selected_files)
        actions_layout.addWidget(self.process_button)

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

        preview_panel = QFrame()
        preview_panel.setObjectName("AppCard")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 9, 12, 12)
        preview_title = QLabel("Vista previa / archivos seleccionados")
        preview_title.setObjectName("SectionLabel")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview, 1)
        layout.addWidget(preview_panel, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = TxtCsvResult(selected_files=self.paths)
        self.status.setText(f"{len(self.paths)} archivo(s) cargado(s). Pulsa Procesar archivos.")
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
            show_inline_message(self, "warning", "Selecciona primero uno o varios archivos TXT.")
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
        self.status.setText(f"Archivo guardado correctamente: {path}")
        show_inline_message(self, "success", f"Archivo guardado correctamente: {path}")

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.paths = []
        self.result = TxtCsvResult()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            self.summary.setText(f"Archivos seleccionados: {len(self.paths)}")
            self.preview.setPlainText("\n".join(str(path) for path in self.paths))
        else:
            self.summary.setText(self.result.summary() if self.result.selected_files else "Sin archivos cargados")
            self.preview.setPlainText(
                self.result.preview_text()
                if self.result.selected_files
                else "Arrastra archivos TXT aqui o pulsa Seleccionar TXT para empezar.\n\nFormatos admitidos: .txt"
            )

        self.process_button.setEnabled(bool(self.paths))
        self.save_button.setEnabled(bool(self.result.processed_lines))
        self.clear_button.setEnabled(bool(self.paths or self.result.processed_lines))

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if self.result.processed_lines:
            return 4, False, False
        if self.paths:
            return 2, False, False
        return 1, False, False
