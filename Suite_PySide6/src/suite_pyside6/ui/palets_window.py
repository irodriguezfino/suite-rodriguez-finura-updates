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

from suite_pyside6.core.palets import PaletsResult, integrate_corrections, process_palets_files, validate_final_palets_text, write_palets_csv
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.file_dialogs import open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.responsive import register_adaptive_layout
from suite_pyside6.ui.theme import base_qss


class PaletsWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.result = PaletsResult()
        self.show_dialogs = True
        self.setWindowTitle("Palets PDA a CSV")
        self.resize(1120, 720)
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

        title = QLabel("Palets PDA a CSV")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Selecciona TXT de PDA, valida incidencias y genera el CSV final Stock01.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar TXT  ->  2 Validar  ->  3 Corregir si hace falta  ->  4 Guardar Stock01")
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

        self.process_button = QPushButton("Procesar palets")
        self.process_button.clicked.connect(self.process_selected_files)
        actions_layout.addWidget(self.process_button)

        self.revalidate_button = QPushButton("Revalidar")
        self.revalidate_button.clicked.connect(self.revalidate)
        actions_layout.addWidget(self.revalidate_button)

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
        preview_title = QLabel("Vista previa")
        preview_title.setObjectName("SectionLabel")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview, 1)
        body.addWidget(preview_panel, 3)

        review_panel = QFrame()
        review_panel.setObjectName("AppCard")
        review_layout = QVBoxLayout(review_panel)
        review_layout.setContentsMargins(12, 9, 12, 12)
        review_title = QLabel("Revision / CSV final")
        review_title.setObjectName("SectionLabel")
        self.review = QPlainTextEdit()
        self.review.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.review.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.review.textChanged.connect(self._mark_manual_edit)
        review_layout.addWidget(review_title)
        review_layout.addWidget(self.review, 1)
        body.addWidget(review_panel, 2)

        layout.addLayout(body, 1)
        register_adaptive_layout(self, body, breakpoint_width=900)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = PaletsResult(selected_files=self.paths)
        self.status.setText(f"{len(self.paths)} archivo(s) cargado(s)")
        self._refresh(selected_only=True)

    def select_files(self) -> None:
        files = open_files(
            self,
            "palets/input",
            "Selecciona archivos TXT de PDA",
            "Archivos TXT (*.txt);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def process_selected_files(self) -> None:
        if not self.paths:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Selecciona primero uno o varios archivos TXT.")
            return
        self.result = process_palets_files(self.paths)
        self.status.setText(self.result.summary())
        self._refresh()
        if self.result.pending_correction and self.show_dialogs:
            show_inline_message(self, "warning", "Hay codigos que requieren correccion antes de guardar.")

    def revalidate(self) -> None:
        if self.result.pending_correction:
            updated, invalid = integrate_corrections(self.result.valid_base, self.result.issues, self.review.toPlainText())
            updated.selected_files = list(self.paths)
            if invalid:
                self.result = updated
                self.status.setText(f"Siguen pendientes {len(invalid)} codigo(s) no valido(s).")
                if self.show_dialogs:
                    show_inline_message(self, "warning", "Aun quedan codigos que no cumplen el formato requerido.")
                return
            self.result = updated
            self.status.setText("Validacion completada. Codigos corregidos integrados correctamente.")
            self._refresh()
            return

        palets, invalid = validate_final_palets_text(self.review.toPlainText())
        if invalid:
            self.status.setText("Hay palets modificados con formato no valido.")
            if self.show_dialogs:
                show_inline_message(self, "error", "Hay lineas que no tienen formato CSV final valido.")
            return
        self.result.final_palets = palets
        self.result.detected = ["00" + pallet for pallet in palets]
        self.status.setText("Revalidacion correcta. Puedes guardar el CSV.")
        self._refresh()

    def save_csv_dialog(self) -> None:
        if self.result.pending_correction:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Pulsa Revalidar antes de guardar.")
            return
        if not self.result.final_palets:
            if self.show_dialogs:
                show_inline_message(self, "warning", "No hay datos procesados para guardar.")
            return
        file = save_file(
            self,
            "palets/export_csv",
            "Guardar CSV final",
            "Stock01.csv",
            "CSV (*.csv);;Todos (*.*)",
        )
        if file:
            self.save_csv_path(file)

    def save_csv_path(self, path: Path) -> None:
        write_palets_csv(path, self.result.final_palets)
        self.status.setText(f"Archivo guardado correctamente: {path}")
        show_inline_message(self, "success", f"Archivo guardado correctamente: {path}")

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.paths = []
        self.result = PaletsResult()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            self.summary.setText(f"Archivos seleccionados: {len(self.paths)}")
            self.preview.setPlainText("Archivos seleccionados:\n\n" + "\n".join(str(path) for path in self.paths))
            self._set_review_text("No hay incidencias para revisar. Pulsa Procesar para validar las lecturas.", editable=False)
        else:
            self.summary.setText(self.result.summary())
            self.preview.setPlainText(
                self.result.preview_text()
                if self.result.selected_files
                else "Arrastra TXT de PDA aqui o pulsa Seleccionar TXT para empezar.\n\nSe validaran incidencias antes de generar Stock01."
            )
            if self.result.pending_correction:
                self._set_review_text(self.result.correction_text(), editable=True)
            elif self.result.final_palets:
                self._set_review_text("\n".join(self.result.final_palets), editable=True)
            else:
                self._set_review_text("La revision y el CSV final apareceran aqui despues de procesar.", editable=False)

        self.process_button.setEnabled(bool(self.paths) and not self.result.pending_correction)
        self.revalidate_button.setEnabled(bool(self.result.pending_correction or self.result.final_palets))
        self.save_button.setEnabled(bool(self.result.final_palets) and not self.result.pending_correction)
        self.clear_button.setEnabled(bool(self.paths or self.result.final_palets or self.result.issues))

    def _set_review_text(self, text: str, *, editable: bool) -> None:
        self.review.blockSignals(True)
        self.review.setPlainText(text)
        self.review.blockSignals(False)
        self.review.setReadOnly(not editable)

    def _mark_manual_edit(self) -> None:
        if self.result.final_palets and not self.result.pending_correction:
            self.revalidate_button.setEnabled(True)
            self.save_button.setEnabled(False)
            self.status.setText("Hay cambios en el CSV final. Pulsa Revalidar antes de guardar.")

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if "no valido" in status or self.result.pending_correction:
            return 3, True, False
        if self.result.final_palets:
            return 4, False, False
        if self.paths:
            return 2, False, False
        return 1, False, False
