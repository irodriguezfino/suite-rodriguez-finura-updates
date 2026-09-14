from __future__ import annotations

from suite_pyside6.ui.components import ModernSelect
from suite_pyside6.ui.visual_controls import ModernCheckBox, ModernSpinBox

import difflib
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QApplication, QFrame, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QProgressBar,
    QSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from suite_pyside6.core.file_compare.detectors import detect_encoding
from suite_pyside6.core.file_compare.models import CompareMode, ComparisonOptions, ComparisonResult
from suite_pyside6.core.file_compare.reports import as_text, write_report
from suite_pyside6.core.file_compare.service import compare_paths
from suite_pyside6.core.file_compare.text import aligned_opcodes
from suite_pyside6.ui.components import ActionMenuButton, section_label, step_bar
from suite_pyside6.ui.polish import polish_window, show_inline_message
from suite_pyside6.ui.background import run_background
from suite_pyside6.ui.theme import base_qss, palette


class FileCompareWindow(QMainWindow):
    """Ventana no bloqueante para el motor comun de comparacion."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Comparador de archivos")
        self.setMinimumSize(760, 540)
        self.setStyleSheet(base_qss())
        self._result: ComparisonResult | None = None
        self._selected_left: Path | None = None
        self._selected_right: Path | None = None
        self._active_left: Path | None = None
        self._active_right: Path | None = None
        self._active_options: ComparisonOptions | None = None
        self._cancelled = False
        self._preview_max_bytes = 2 * 1024 * 1024
        self._preview_max_lines = 12_000
        self._preview_max_highlights = 2_000
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("ControlProductHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(3)
        title = QLabel("Comparador de archivos")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Contrasta archivos o carpetas y revisa las diferencias con precisión.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)
        layout.addWidget(step_bar("1 Seleccionar rutas  →  2 Configurar  →  3 Comparar  →  4 Revisar"))

        options_panel = QFrame()
        options_panel.setObjectName("FormPanel")
        options_layout = QVBoxLayout(options_panel)
        options_layout.setContentsMargins(14, 12, 14, 14)
        options_layout.setSpacing(8)
        options_layout.addWidget(section_label("Rutas y opciones"))
        form = QFormLayout()
        form.setVerticalSpacing(8)
        options_panel.setMinimumHeight(350)
        options_panel.setProperty('contentMinimumHeight', 350)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.left_label = QLabel("Seleccione el primer archivo o carpeta")
        self.right_label = QLabel("Seleccione el segundo archivo o carpeta")
        for label in (self.left_label, self.right_label):
            label.setTextInteractionFlags(label.textInteractionFlags() | Qt.TextSelectableByMouse)
        left_buttons = self._path_buttons(self.left_label, "primer")
        right_buttons = self._path_buttons(self.right_label, "segundo")
        form.addRow("Archivo/carpeta A:", left_buttons)
        form.addRow("Archivo/carpeta B:", right_buttons)
        self.mode = ModernSelect()
        self.mode.addItem("Estricto (bytes)", CompareMode.STRICT.value)
        self.mode.addItem("Semantico cuando sea posible", CompareMode.SEMANTIC.value)
        self.mode.addItem("Automatico", CompareMode.AUTO.value)
        # ModernSelect has a placeholder; keep the original strict default.
        self.mode.setCurrentIndex(0)
        self.maximum = ModernSpinBox(); self.maximum.setRange(1, 10000); self.maximum.setValue(100)
        self.ignore_case = ModernCheckBox("Ignorar mayúsculas/minúsculas")
        self.ignore_whitespace = ModernCheckBox("Ignorar espacios iniciales/finales")
        self.ignore_eol = ModernCheckBox("Ignorar finales de línea")
        form.addRow("Modo:", self.mode)
        form.addRow("Maximo de diferencias:", self.maximum)
        form.addRow("Opciones de texto:", self.ignore_case)
        form.addRow("", self.ignore_whitespace)
        form.addRow("", self.ignore_eol)
        options_layout.addLayout(form)
        layout.addWidget(options_panel)

        actions_frame = QFrame()
        actions_frame.setObjectName("Toolbar")
        actions_frame.setProperty("controlCommand", True)
        actions = QHBoxLayout(actions_frame)
        actions.setContentsMargins(10, 8, 10, 8)
        actions.setSpacing(8)
        self.compare_button = QPushButton("Comparar")
        self.compare_button.setProperty("primary", True)
        self.compare_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.more_actions_button = ActionMenuButton(accessible_name="Más acciones del comparador")
        self.copy_button = self.more_actions_button.add_action("Copiar resultado", self._copy)
        self.save_button = self.more_actions_button.add_action("Guardar informe", self._save)
        self.more_actions_button.menu().addSeparator()
        self.open_left_button = self.more_actions_button.add_action("Abrir archivo A", lambda: self._open_path(self._left_path()))
        self.open_right_button = self.more_actions_button.add_action("Abrir archivo B", lambda: self._open_path(self._right_path()))
        for button in (self.compare_button, self.cancel_button, self.more_actions_button):
            actions.addWidget(button)
        layout.addWidget(actions_frame)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.summary = QLabel("Seleccione dos rutas para iniciar una comparacion.")
        self.summary.setObjectName("StatusLabel")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        details_panel = QFrame()
        details_panel.setObjectName("OutputPanel")
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(12, 10, 12, 12)
        details_layout.setSpacing(6)
        details_layout.addWidget(section_label("Resumen"))
        self.details = QPlainTextEdit(); self.details.setReadOnly(True)
        self.details.setMinimumHeight(92)
        self.details.setMaximumHeight(150)
        details_layout.addWidget(self.details)
        layout.addWidget(details_panel)

        preview_panel = QFrame()
        preview_panel.setObjectName("ControlPreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 10, 12, 12)
        preview_layout.setSpacing(6)
        self.preview_label = QLabel("Vista comparada: el contenido de ambos archivos se alinea y las diferencias se resaltan abajo.")
        self.preview_label.setObjectName("PanelSubtitle")
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(section_label("Comparación visual"))
        preview_layout.addWidget(self.preview_label)
        self.preview_splitter = QSplitter(Qt.Horizontal)
        left_preview_holder, self.left_preview_title, self.left_preview = self._preview_pane("Archivo A")
        right_preview_holder, self.right_preview_title, self.right_preview = self._preview_pane("Archivo B")
        self.preview_splitter.addWidget(left_preview_holder)
        self.preview_splitter.addWidget(right_preview_holder)
        self.preview_splitter.setChildrenCollapsible(False)
        self.preview_splitter.setSizes([1, 1])
        preview_layout.addWidget(self.preview_splitter, 1)
        layout.addWidget(preview_panel, 2)
        self.setCentralWidget(root)
        polish_window(self)
        self.mode.currentIndexChanged.connect(self._invalidate_comparison)
        self.maximum.valueChanged.connect(self._invalidate_comparison)
        for option in (self.ignore_case, self.ignore_whitespace, self.ignore_eol):
            option.toggled.connect(self._invalidate_comparison)

    def flow_state(self):
        if self.property('operationActive'):
            return 3, False, False
        if self._result is not None:
            return 4, bool(self._result.errors), not self._result.errors
        return (2 if self._selected_left and self._selected_right else 1), False, False

    def context_snapshot(self):
        if self._result is not None:
            return {'state': self._result.status_text(), 'next': 'Revisar o guardar informe',
                    'alerts': f'{len(self._result.errors)} errores' if self._result.errors else 'Sin errores de lectura'}
        return {'state': 'Rutas seleccionadas' if self._selected_left and self._selected_right else 'Esperando rutas',
                'next': 'Comparar' if self._selected_left and self._selected_right else 'Seleccionar dos rutas', 'alerts':'Sin resultado vigente'}

    def _invalidate_comparison(self, *_args):
        if self.property('operationActive'):
            return
        self._result = None
        self.setProperty('jobState', 'idle')
        self._job_display.hide()
        self.summary.setText('Selección u opciones cambiadas. Compara de nuevo para obtener un resultado vigente.')
        self.details.clear()
        self._clear_preview()

    def _set_path(self, label, selected):
        if self.property('operationActive'):
            return
        if label is self.left_label:
            self._selected_left = Path(selected)
        else:
            self._selected_right = Path(selected)
        label.setText(str(selected))
        self._invalidate_comparison()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Seleccionar rutas", "Configurar", "Comparar", "Revisar")

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        orientation = Qt.Horizontal if self.width() >= 940 else Qt.Vertical
        if self.preview_splitter.orientation() != orientation:
            self.preview_splitter.setOrientation(orientation)

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
        if self.property("operationActive"):
            return
        selected, _ = QFileDialog.getOpenFileName(self, "Seleccione un archivo")
        if selected: self._set_path(label, selected)

    def _select_folder(self, label: QLabel, _which: str) -> None:
        if self.property("operationActive"):
            return
        selected = QFileDialog.getExistingDirectory(self, "Seleccione una carpeta")
        if selected: self._set_path(label, selected)

    def _left_path(self) -> Path | None:
        return self._selected_left

    def _right_path(self) -> Path | None:
        return self._selected_right

    def _options(self) -> ComparisonOptions:
        return ComparisonOptions(CompareMode(self.mode.currentData()), self.maximum.value(), ignore_case=self.ignore_case.isChecked(), ignore_whitespace=self.ignore_whitespace.isChecked(), ignore_line_endings=self.ignore_eol.isChecked())

    def _start(self) -> None:
        if self.property("operationActive"):
            return
        left, right = self._left_path(), self._right_path()
        if not left or not right:
            QMessageBox.warning(self, "Rutas necesarias", "Seleccione dos archivos o dos carpetas existentes.")
            return
        self._cancelled = False; self._result = None
        self._active_left, self._active_right, self._active_options = left, right, self._options()
        self.compare_button.setEnabled(False); self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 0); self.summary.setText("Comparando en segundo plano…"); self.details.clear()
        self._clear_preview()
        run_background(self,
                       lambda: compare_paths(left, right, self._active_options, cancelled=lambda: self._cancelled),
                       self._finished, self._failed)

    def _cancel(self) -> None:
        from .job_display import request_cancel
        request_cancel(self)
        self._cancelled = True
        self.summary.setText("Cancelacion solicitada; el resultado en curso se descartara al terminar el bloque actual.")
        self.cancel_button.setEnabled(False)

    def _finished(self, result: ComparisonResult) -> None:
        self.cancel_button.setEnabled(False)
        self.summary.setText("Preparando la vista del resultado…")
        if self._cancelled or result.metadata.get("cancelled"):
            self.summary.setText("Comparacion cancelada.")
            self.progress.setRange(0, 1); self.progress.setValue(0)
            self.compare_button.setEnabled(True)
            return
        self._result = result
        state = result.status_text()
        self.summary.setText(f"{state} · {result.detected_type} · {result.total_differences} diferencias · {result.elapsed_seconds:.2f} s")
        self.details.setPlainText(as_text(result))
        self._render_preview(result)
        self.progress.setRange(0, 1); self.progress.setValue(0 if result.errors else 1)
        self.compare_button.setEnabled(True)

    def _failed(self, message: str) -> None:
        self.progress.setRange(0, 1); self.progress.setValue(0)
        self.compare_button.setEnabled(True); self.cancel_button.setEnabled(False)
        self.summary.setText(f"No se pudo completar la comparación: {message}")
        self.details.setPlainText(f"Error de comparación\n{message}")
        self._clear_preview()

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
            if path.stat().st_size > 2 * 1024 * 1024:
                return None
            encoding = detect_encoding(path)
            if not encoding:
                return None
            with path.open(encoding=encoding, newline="") as stream:
                return stream.read().splitlines(keepends=True)
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
        # Per-character matching is quadratic for long lines. Highlighting the
        # line is both clearer and bounded in the visual preview.
        if len(left) + len(right) > 8_000 or len(left) * len(right) > 100_000:
            return ([(0, len(left))] if left else [], [(0, len(right))] if right else [])
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
        cached = result.metadata.get("_text_preview")
        left_lines, right_lines = cached[:2] if cached else (self._read_preview_lines(left), self._read_preview_lines(right))
        if left_lines is None or right_lines is None:
            self.preview_label.setText("Vista previa omitida: uno de los archivos no es texto legible o supera 2 MiB. El resumen sigue disponible arriba.")
            return
        if len(left_lines) > self._preview_max_lines or len(right_lines) > self._preview_max_lines:
            self.preview_label.setText("Vista previa omitida: el archivo supera 12.000 líneas. El resumen sigue disponible arriba.")
            return

        self.preview_label.setText("Contenido completo alineado. Solo los caracteres distintos se marcan en rojo (A) y verde (B).")
        self.left_preview_title.setText(f"Archivo A · {left.name}")
        self.right_preview_title.setText(f"Archivo B · {right.name}")
        codes = cached[2] if cached else aligned_opcodes(
            [self._normalise_preview_line(line) for line in left_lines],
            [self._normalise_preview_line(line) for line in right_lines])[0]
        left_rows: list[str] = []; right_rows: list[str] = []
        left_ranges: list[tuple[int, int, int]] = []
        right_ranges: list[tuple[int, int, int]] = []
        for tag, a_start, a_end, b_start, b_end in codes:
            row_count = max(a_end - a_start, b_end - b_start)
            for offset in range(row_count):
                a_index, b_index = a_start + offset, b_start + offset
                left_value = self._display_line(left_lines[a_index]) if a_index < a_end else None
                right_value = self._display_line(right_lines[b_index]) if b_index < b_end else None
                left_row = self._line_text(a_index + 1 if a_index < a_end else None, left_value)
                right_row = self._line_text(b_index + 1 if b_index < b_end else None, right_value)
                left_rows.append(left_row); right_rows.append(right_row)
                if tag != "equal" and (len(left_ranges) < self._preview_max_highlights or len(right_ranges) < self._preview_max_highlights):
                    left_changes, right_changes = self._changed_character_ranges(left_value, right_value)
                    row = len(left_rows) - 1
                    left_prefix = len(left_row) - len(left_value or "")
                    right_prefix = len(right_row) - len(right_value or "")
                    if len(left_ranges) < self._preview_max_highlights:
                        left_ranges.extend((row, left_prefix + start, left_prefix + end) for start, end in left_changes)
                    if len(right_ranges) < self._preview_max_highlights:
                        right_ranges.extend((row, right_prefix + start, right_prefix + end) for start, end in right_changes)
        left_ranges = left_ranges[:self._preview_max_highlights]
        right_ranges = right_ranges[:self._preview_max_highlights]
        if len(left_ranges) >= self._preview_max_highlights or len(right_ranges) >= self._preview_max_highlights:
            self.preview_label.setText(f"Contenido alineado; resaltado limitado a {self._preview_max_highlights} marcas por lado. Consulta el informe para el recuento y los límites del detalle.")
        self.left_preview.setPlainText("\n".join(left_rows)); self.right_preview.setPlainText("\n".join(right_rows))
        colors = palette()
        self._highlight_ranges(self.left_preview, left_ranges, colors["danger_soft"])
        self._highlight_ranges(self.right_preview, right_ranges, colors["success_soft"])

    def _copy(self) -> None:
        if self._result:
            QApplication.clipboard().setText(as_text(self._result))

    def _save(self) -> None:
        if not self._result:
            return
        path, selected = QFileDialog.getSaveFileName(self, "Guardar informe", "comparacion.html", "HTML (*.html);;JSON (*.json);;Texto (*.txt)")
        if not path: return
        output_format = "json" if "JSON" in selected else "text" if "Texto" in selected else "html"
        result = self._result
        self.summary.setText("Guardando informe…")
        def completed(_value):
            self.summary.setText(f"Informe guardado: {path}")
        def failed(message):
            show_inline_message(self, "error", f"No se guardó el informe. Puedes reintentar: {message}")
        run_background(self, lambda: write_report(result, path, output_format), completed, failed)

    def _open_path(self, path: Path | None) -> None:
        if path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
