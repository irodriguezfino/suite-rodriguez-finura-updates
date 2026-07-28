from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QApplication, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QProgressBar,
    QSpinBox, QVBoxLayout, QWidget,
)

from suite_pyside6.core.file_compare.models import CompareMode, ComparisonOptions, ComparisonResult
from suite_pyside6.core.file_compare.reports import as_text, write_report
from suite_pyside6.core.file_compare.service import compare_paths


class _Worker(QObject):
    finished = Signal(object)

    def __init__(self, left: Path, right: Path, options: ComparisonOptions) -> None:
        super().__init__()
        self.left, self.right, self.options = left, right, options

    def run(self) -> None:
        self.finished.emit(compare_paths(self.left, self.right, self.options))


class FileCompareWindow(QMainWindow):
    """Ventana no bloqueante para el motor comun de comparacion."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Comparador de archivos")
        self.setMinimumSize(820, 560)
        self._thread: QThread | None = None
        self._worker: _Worker | None = None
        self._result: ComparisonResult | None = None
        self._cancelled = False
        root = QWidget(self)
        layout = QVBoxLayout(root)
        form = QFormLayout()
        self.left_label = QLabel("Seleccione el primer archivo o carpeta")
        self.right_label = QLabel("Seleccione el segundo archivo o carpeta")
        for label in (self.left_label, self.right_label):
            label.setTextInteractionFlags(label.textInteractionFlags() | Qt.TextSelectableByMouse)
        left_buttons = self._path_buttons(self.left_label, "primer")
        right_buttons = self._path_buttons(self.right_label, "segundo")
        form.addRow("Archivo/carpeta A:", left_buttons)
        form.addRow("Archivo/carpeta B:", right_buttons)
        self.mode = QComboBox()
        self.mode.addItem("Estricto (bytes)", CompareMode.STRICT.value)
        self.mode.addItem("Semantico cuando sea posible", CompareMode.SEMANTIC.value)
        self.mode.addItem("Automatico", CompareMode.AUTO.value)
        self.maximum = QSpinBox(); self.maximum.setRange(1, 10000); self.maximum.setValue(100)
        self.ignore_case = QCheckBox("Ignorar mayusculas/minusculas")
        self.ignore_whitespace = QCheckBox("Ignorar espacios iniciales/finales")
        self.ignore_eol = QCheckBox("Ignorar finales de linea")
        form.addRow("Modo:", self.mode)
        form.addRow("Maximo de diferencias:", self.maximum)
        form.addRow("Opciones de texto:", self.ignore_case)
        form.addRow("", self.ignore_whitespace)
        form.addRow("", self.ignore_eol)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.compare_button = QPushButton("Comparar")
        self.compare_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.copy_button = QPushButton("Copiar resultado")
        self.copy_button.clicked.connect(self._copy)
        self.save_button = QPushButton("Guardar informe")
        self.save_button.clicked.connect(self._save)
        self.open_left_button = QPushButton("Abrir A")
        self.open_left_button.clicked.connect(lambda: self._open_path(self._left_path()))
        self.open_right_button = QPushButton("Abrir B")
        self.open_right_button.clicked.connect(lambda: self._open_path(self._right_path()))
        for button in (self.compare_button, self.cancel_button, self.copy_button, self.save_button, self.open_left_button, self.open_right_button): actions.addWidget(button)
        layout.addLayout(actions)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.summary = QLabel("Seleccione dos rutas para iniciar una comparacion.")
        layout.addWidget(self.summary)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        self.setCentralWidget(root)

    def _path_buttons(self, label: QLabel, which: str) -> QWidget:
        holder = QWidget(); layout = QHBoxLayout(holder); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 1)
        file_button = QPushButton("Archivo")
        file_button.clicked.connect(lambda: self._select_file(label, which))
        folder_button = QPushButton("Carpeta")
        folder_button.clicked.connect(lambda: self._select_folder(label, which))
        layout.addWidget(file_button); layout.addWidget(folder_button)
        return holder

    def _select_file(self, label: QLabel, _which: str) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Seleccione un archivo")
        if selected: label.setText(selected)

    def _select_folder(self, label: QLabel, _which: str) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Seleccione una carpeta")
        if selected: label.setText(selected)

    def _left_path(self) -> Path | None:
        path = Path(self.left_label.text())
        return path if path.exists() else None

    def _right_path(self) -> Path | None:
        path = Path(self.right_label.text())
        return path if path.exists() else None

    def _options(self) -> ComparisonOptions:
        return ComparisonOptions(CompareMode(self.mode.currentData()), self.maximum.value(), ignore_case=self.ignore_case.isChecked(), ignore_whitespace=self.ignore_whitespace.isChecked(), ignore_line_endings=self.ignore_eol.isChecked())

    def _start(self) -> None:
        left, right = self._left_path(), self._right_path()
        if not left or not right:
            QMessageBox.warning(self, "Rutas necesarias", "Seleccione dos archivos o dos carpetas existentes.")
            return
        self._cancelled = False; self._result = None
        self.compare_button.setEnabled(False); self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 0); self.summary.setText("Comparando en segundo plano…"); self.details.clear()
        self._thread = QThread(self); self._worker = _Worker(left, right, self._options())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _cancel(self) -> None:
        self._cancelled = True
        self.summary.setText("Cancelacion solicitada; el resultado en curso se descartara al terminar el bloque actual.")
        self.cancel_button.setEnabled(False)

    def _finished(self, result: ComparisonResult) -> None:
        self.progress.setRange(0, 1); self.progress.setValue(1); self.compare_button.setEnabled(True); self.cancel_button.setEnabled(False)
        if self._cancelled:
            self.summary.setText("Comparacion cancelada.")
            return
        self._result = result
        state = "IGUALES" if result.strict_equal else "DIFERENTES"
        self.summary.setText(f"{state} · {result.detected_type} · {result.total_differences} diferencias · {result.elapsed_seconds:.2f} s")
        self.details.setPlainText(as_text(result))

    def _copy(self) -> None:
        if self._result:
            QApplication.clipboard().setText(as_text(self._result))

    def _save(self) -> None:
        if not self._result:
            return
        path, selected = QFileDialog.getSaveFileName(self, "Guardar informe", "comparacion.html", "HTML (*.html);;JSON (*.json);;Texto (*.txt)")
        if not path: return
        output_format = "json" if "JSON" in selected else "text" if "Texto" in selected else "html"
        write_report(self._result, path, output_format)
        self.summary.setText(f"Informe guardado: {path}")

    def _open_path(self, path: Path | None) -> None:
        if path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
