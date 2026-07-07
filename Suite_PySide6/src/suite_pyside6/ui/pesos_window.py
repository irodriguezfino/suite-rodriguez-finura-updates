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
from suite_pyside6.core.pesos import PesosResult, process_pesos_files
from suite_pyside6.ui.file_dialogs import open_files
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.responsive import register_adaptive_layout
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

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Pesos")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Renombra la primera hoja visible de cada Excel a Hoja1 sin tocar datos ni formatos.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar Excel  ->  2 Renombrar hoja  ->  3 Revisar resultado")
        steps.setObjectName("StepBar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(7)

        self.select_button = QPushButton("Seleccionar Excel")
        self.select_button.setProperty("primary", True)
        self.select_button.setAccessibleName("Seleccionar archivos Excel de pesos")
        self.select_button.setToolTip("Selecciona uno o varios archivos .xlsx o .xlsm.")
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

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

        body = QBoxLayout(QBoxLayout.LeftToRight)
        body.setSpacing(8)

        selected_panel = QFrame()
        selected_panel.setObjectName("AppCard")
        selected_layout = QVBoxLayout(selected_panel)
        selected_layout.setContentsMargins(12, 9, 12, 12)
        selected_title = QLabel("Archivos")
        selected_title.setObjectName("SectionLabel")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        selected_layout.addWidget(selected_title)
        selected_layout.addWidget(self.preview, 1)
        body.addWidget(selected_panel, 3)

        log_panel = QFrame()
        log_panel.setObjectName("AppCard")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(12, 9, 12, 12)
        log_title = QLabel("Resumen")
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

        self.status = QLabel("Listo para seleccionar archivos Excel.")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = PesosResult(selected_files=self.paths)
        self.status.setText("Seleccion completada. Pulsa Renombrar hoja.")
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
            show_inline_message(self, "warning", "Selecciona primero uno o varios archivos Excel.")
            return
        self.result = process_pesos_files(self.paths)
        if self.result.error_count:
            self.status.setText(
                f"Proceso completado con {self.result.processed_count} renombrado(s) y {self.result.error_count} aviso(s)."
            )
            show_inline_message(self, "warning", "Revisa el resumen: hay archivos ignorados o con error.")
        else:
            self.status.setText(f"Proceso completado correctamente: {self.result.ok_count} archivo(s) revisado(s).")
            show_inline_message(self, "success", "Hojas renombradas a Hoja1 correctamente.")
        self._refresh()

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.paths = []
        self.result = PesosResult()
        self.status.setText("Listo para seleccionar archivos Excel.")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            processable = sum(1 for path in self.paths if path.suffix.lower() in {".xlsx", ".xlsm"})
            ignored = len(self.paths) - processable
            self.summary.setText(
                f"Archivos seleccionados: {len(self.paths)} | Excel procesables: {processable} | Ignorados al procesar: {ignored}"
            )
            self.preview.setPlainText("\n".join(str(path) for path in self.paths))
            self.log.setPlainText("Pulsa Renombrar hoja para cambiar la primera hoja visible a Hoja1.")
        else:
            self.summary.setText(self.result.summary() if self.result.selected_files else "Sin archivos cargados")
            self.preview.setPlainText(
                "\n".join(str(path) for path in self.paths)
                if self.paths
                else "Selecciona archivos Excel para empezar."
            )
            self.log.setPlainText(self.result.log_text())

        self.process_button.setEnabled(bool(self.paths))
        self.clear_button.setEnabled(bool(self.paths or self.result.results or self.result.ignored_files))

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if self.result.error_count:
            return 3, True, False
        if "completado" in status:
            return 3, False, True
        if self.paths:
            return 2, False, False
        return 1, False, False
