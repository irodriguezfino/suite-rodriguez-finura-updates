from __future__ import annotations

import difflib
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QApplication, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QProgressBar,
    QSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from suite_pyside6.core.file_compare.detectors import detect_encoding
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
        self._active_left: Path | None = None
        self._active_right: Path | None = None
        self._active_options: ComparisonOptions | None = None
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
        self.details.setMaximumHeight(150)
        layout.addWidget(self.details)
        self.preview_label = QLabel("Vista comparada: el contenido de ambos archivos se alinea y las diferencias se resaltan abajo.")
        layout.addWidget(self.preview_label)
        self.preview_splitter = QSplitter(Qt.Horizontal)
        left_preview_holder, self.left_preview_title, self.left_preview = self._preview_pane("Archivo A")
        right_preview_holder, self.right_preview_title, self.right_preview = self._preview_pane("Archivo B")
        self.preview_splitter.addWidget(left_preview_holder)
        self.preview_splitter.addWidget(right_preview_holder)
        self.preview_splitter.setSizes([410, 410])
        layout.addWidget(self.preview_splitter, 2)
        self.setCentralWidget(root)

    def _preview_pane(self, title: str) -> tuple[QWidget, QLabel, QPlainTextEdit]:
        holder = QWidget()
        layout = QVBoxLayout(holder); layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        editor = QPlainTextEdit(); editor.setReadOnly(True); editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        editor.setPlaceholderText("El contenido comparable aparecera aqui.")
        layout.addWidget(label); layout.addWidget(editor, 1)
        return holder, label, editor

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
        self._active_left, self._active_right, self._active_options = left, right, self._options()
        self.compare_button.setEnabled(False); self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 0); self.summary.setText("Comparando en segundo plano…"); self.details.clear()
        self._clear_preview()
        self._thread = QThread(self); self._worker = _Worker(left, right, self._active_options)
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
        self._render_preview(result)

    def _clear_preview(self) -> None:
        self.left_preview_title.setText("Archivo A")
        self.right_preview_title.setText("Archivo B")
        self.left_preview.clear(); self.right_preview.clear()
        self.left_preview.setExtraSelections([]); self.right_preview.setExtraSelections([])

    @staticmethod
    def _display_line(line: str) -> str:
        return line.rstrip("\r\n")

    def _normalise_preview_line(self, line: str) -> str:
        options = self._active_options or ComparisonOptions()
        if options.ignore_line_endings:
            line = line.replace("\r\n", "\n").replace("\r", "\n")
        if options.ignore_whitespace:
            line = line.strip()
        if options.ignore_case:
            line = line.casefold()
        return line

    @staticmethod
    def _read_preview_lines(path: Path) -> list[str] | None:
        try:
            encoding = detect_encoding(path)
            return path.read_text(encoding=encoding).splitlines(keepends=True) if encoding else None
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def _line_text(number: int | None, value: str | None) -> str:
        return f"{number:>6} | {value}" if number is not None else "       |"

    @staticmethod
    def _highlight_ranges(editor: QPlainTextEdit, ranges: list[tuple[int, int, int]], colour: str) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        for row, start, end in ranges:
            if start >= end:
                continue
            block = editor.document().findBlockByNumber(row)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(editor.document())
            selection.cursor.setPosition(block.position() + start)
            selection.cursor.setPosition(block.position() + end, QTextCursor.KeepAnchor)
            selection.format.setBackground(QColor(colour))
            selections.append(selection)
        editor.setExtraSelections(selections)

    @staticmethod
    def _changed_character_ranges(left: str | None, right: str | None) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        if left is None:
            return [], [(0, len(right or ""))]
        if right is None:
            return [(0, len(left))], []
        left_ranges: list[tuple[int, int]] = []
        right_ranges: list[tuple[int, int]] = []
        matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if tag == "equal":
                continue
            if left_start < left_end:
                left_ranges.append((left_start, left_end))
            if right_start < right_end:
                right_ranges.append((right_start, right_end))
        return left_ranges, right_ranges

    def _render_preview(self, result: ComparisonResult) -> None:
        left, right = self._active_left, self._active_right
        self._clear_preview()
        if not left or not right or left.is_dir() or right.is_dir() or result.detected_type != "text":
            self.preview_label.setText("Vista comparada disponible para archivos de texto; el detalle de esta comparacion aparece arriba.")
            return
        left_lines, right_lines = self._read_preview_lines(left), self._read_preview_lines(right)
        if left_lines is None or right_lines is None:
            self.preview_label.setText("No se pudo mostrar el contenido de uno de los archivos como texto.")
            return

        self.preview_label.setText("Contenido completo alineado. Solo los caracteres distintos se marcan en rojo (A) y verde (B).")
        self.left_preview_title.setText(f"Archivo A · {left.name}")
        self.right_preview_title.setText(f"Archivo B · {right.name}")
        matcher = difflib.SequenceMatcher(
            None,
            [self._normalise_preview_line(line) for line in left_lines],
            [self._normalise_preview_line(line) for line in right_lines],
            autojunk=False,
        )
        left_rows: list[str] = []; right_rows: list[str] = []
        left_ranges: list[tuple[int, int, int]] = []
        right_ranges: list[tuple[int, int, int]] = []
        for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
            row_count = max(a_end - a_start, b_end - b_start)
            for offset in range(row_count):
                a_index, b_index = a_start + offset, b_start + offset
                left_value = self._display_line(left_lines[a_index]) if a_index < a_end else None
                right_value = self._display_line(right_lines[b_index]) if b_index < b_end else None
                left_row = self._line_text(a_index + 1 if a_index < a_end else None, left_value)
                right_row = self._line_text(b_index + 1 if b_index < b_end else None, right_value)
                left_rows.append(left_row); right_rows.append(right_row)
                if tag != "equal":
                    left_changes, right_changes = self._changed_character_ranges(left_value, right_value)
                    row = len(left_rows) - 1
                    left_prefix = len(left_row) - len(left_value or "")
                    right_prefix = len(right_row) - len(right_value or "")
                    left_ranges.extend((row, left_prefix + start, left_prefix + end) for start, end in left_changes)
                    right_ranges.extend((row, right_prefix + start, right_prefix + end) for start, end in right_changes)
        self.left_preview.setPlainText("\n".join(left_rows)); self.right_preview.setPlainText("\n".join(right_rows))
        self._highlight_ranges(self.left_preview, left_ranges, "#ffe1e1")
        self._highlight_ranges(self.right_preview, right_ranges, "#ddf6e5")

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
