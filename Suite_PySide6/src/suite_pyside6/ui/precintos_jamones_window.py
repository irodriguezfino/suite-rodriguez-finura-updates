from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.paths import resource_path
from suite_pyside6.core.precintos_jamones import (
    PrecintosJamonesResult,
    correction_text,
    process_precintos_jamones,
    revalidate_corrections,
    save_precintos_csv,
    save_precintos_txt,
    weight_filter_text,
)
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.theme import base_qss


class PrecintosJamonesWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.official_excel: Path | None = None
        self.result = PrecintosJamonesResult()
        self.last_attachments: list[Path] = []
        self.weight_filter_pending = False
        self.show_dialogs = True
        self.setWindowTitle("Precintos Jamones")
        self.resize(1160, 740)
        self.setMinimumSize(740, 580)
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

        title = QLabel("Precintos Jamones")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Valida precintos, duplicados, Excel oficial y exporta TXT/CSV.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar TXT/CSV  ->  2 Revisar incidencias  ->  3 Revalidar  ->  4 Guardar TXT/CSV")
        steps.setObjectName("StepBar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(7)

        self.type_combo = QComboBox()
        self.type_combo.setObjectName("CompactField")
        self.type_combo.addItems(["Blanco", "Iberico"])
        self.type_combo.currentTextChanged.connect(lambda _text: self.process_files() if self.paths else None)
        actions_layout.addWidget(self.type_combo)

        self.txt_button = QPushButton("Cargar TXT/CSV")
        self.txt_button.setProperty("primary", True)
        self.txt_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.txt_button)

        self.official_button = QPushButton("Cargar Excel oficial")
        self.official_button.clicked.connect(self.select_official)
        actions_layout.addWidget(self.official_button)

        self.process_button = QPushButton("Procesar control")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        self.revalidate_button = QPushButton("Revalidar")
        self.revalidate_button.clicked.connect(self.revalidate)
        actions_layout.addWidget(self.revalidate_button)

        self.weight_min = QLineEdit()
        self.weight_min.setObjectName("CompactField")
        self.weight_min.setPlaceholderText("Peso min.")
        self.weight_min.setMaximumWidth(96)
        actions_layout.addWidget(self.weight_min)

        self.weight_max = QLineEdit()
        self.weight_max.setObjectName("CompactField")
        self.weight_max.setPlaceholderText("Peso max.")
        self.weight_max.setMaximumWidth(96)
        actions_layout.addWidget(self.weight_max)

        self.weight_button = QPushButton("Filtrar pesos")
        self.weight_button.clicked.connect(self.apply_weight_filter)
        actions_layout.addWidget(self.weight_button)

        self.clear_filter_button = QPushButton("Limpiar filtro")
        self.clear_filter_button.clicked.connect(self.clear_weight_filter)
        actions_layout.addWidget(self.clear_filter_button)

        self.save_txt_button = QPushButton("Guardar TXT")
        self.save_txt_button.clicked.connect(self.save_txt_dialog)
        actions_layout.addWidget(self.save_txt_button)

        self.save_csv_button = QPushButton("Guardar CSV")
        self.save_csv_button.clicked.connect(self.save_csv_dialog)
        actions_layout.addWidget(self.save_csv_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        layout.addWidget(self.summary)

        panel = QFrame()
        panel.setObjectName("AppCard")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 9, 12, 12)
        panel_title = QLabel("Panel de trabajo")
        panel_title.setObjectName("SectionLabel")
        tabs = QTabWidget()
        tabs.setObjectName("WorkTabs")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.issues = QPlainTextEdit()
        self.issues.setReadOnly(True)
        self.issues.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.issues.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tabs.addTab(self.preview, "Resumen")
        tabs.addTab(self.issues, "Incidencias")
        tabs.addTab(self.output, "Salida")
        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(tabs, 1)
        layout.addWidget(panel, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def select_files(self) -> None:
        files = open_files(
            self,
            "precintos_jamones/input",
            "Selecciona ficheros de precintos",
            "TXT/CSV (*.txt *.csv);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def select_official(self) -> None:
        file = open_file(self, "precintos_jamones/oficial", "Selecciona Excel oficial", "Excel (*.xlsx *.xlsm);;Todos (*.*)")
        if file:
            self.official_excel = file
            if self.paths:
                self.process_files()
            else:
                self._refresh()

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.process_files()

    def process_files(self) -> None:
        if not self.paths:
            return
        try:
            self.result = process_precintos_jamones(self.paths, self.type_combo.currentText(), self.official_excel)
        except Exception as exc:
            self.status.setText(f"Error: {exc}")
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.weight_filter_pending = False
        self.status.setText(f"Proceso completado: {len(self.result.validos)} registros validos")
        self._refresh()

    def revalidate(self) -> None:
        if not (self.result.invalidos or self.weight_filter_pending):
            return
        self.result = revalidate_corrections(self.result, self.preview.toPlainText())
        self.last_attachments = []
        self.weight_filter_pending = False
        if self.result.invalidos:
            self.status.setText(f"Siguen pendientes {len(self.result.invalidos)} incidencia(s).")
            if self.show_dialogs:
                show_inline_message(self, "warning", "Aun quedan lineas que no superan la validacion.")
        else:
            self.status.setText("Revalidacion correcta. Ya puedes guardar TXT o CSV.")
            show_inline_message(self, "success", "Revalidacion correcta. Ya puedes guardar TXT o CSV.")
        self._refresh()

    def apply_weight_filter(self) -> None:
        if not self.result.validos:
            show_inline_message(self, "warning", "Procesa primero uno o varios ficheros.")
            return
        try:
            editor, resumen, pending = weight_filter_text(self.result, self.weight_min.text(), self.weight_max.text())
        except Exception as exc:
            self.status.setText(str(exc))
            if self.show_dialogs:
                show_inline_message(self, "warning", str(exc))
            return
        self.preview.setReadOnly(not pending)
        self.preview.setPlainText(editor if pending else self.result.preview_text() + "\n\n" + resumen)
        self.weight_filter_pending = pending
        self.last_attachments = []
        self.status.setText("Filtro de pesos aplicado. Modifica registros si procede y pulsa Revalidar.")
        self._refresh_buttons_only()

    def clear_weight_filter(self) -> None:
        self.weight_min.clear()
        self.weight_max.clear()
        self.weight_filter_pending = False
        self._refresh()
        self.status.setText("Filtro de pesos limpiado.")

    def save_txt_dialog(self) -> None:
        if not self.result.validos:
            return
        file = save_file(self, "precintos_jamones/export_txt", "Guardar TXT", "precintos_jamones.txt", "TXT (*.txt)")
        if file:
            self.save_txt(file)

    def save_csv_dialog(self) -> None:
        if not self.result.validos:
            return
        file = save_file(self, "precintos_jamones/export_csv", "Guardar CSV", "precintos_jamones.csv", "CSV (*.csv)")
        if file:
            self.save_csv(file)

    def save_txt(self, path: Path) -> Path:
        saved = save_precintos_txt(path, self.result)
        self.last_attachments = [saved]
        self.status.setText(f"TXT guardado: {saved}")
        show_inline_message(self, "success", f"TXT guardado: {saved.name}")
        return saved

    def save_csv(self, path: Path) -> list[Path]:
        summary = save_precintos_csv(path, self.result)
        self.last_attachments = [path] + ([summary] if summary is not None else [])
        self.status.setText("CSV guardado" + (f" con resumen: {summary.name}" if summary else f": {path.name}"))
        show_inline_message(self, "success", "CSV guardado" + (f" con resumen: {summary.name}" if summary else f": {path.name}"))
        return self.last_attachments

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.paths = []
        self.official_excel = None
        self.result = PrecintosJamonesResult()
        self.last_attachments = []
        self.weight_filter_pending = False
        self.weight_min.clear()
        self.weight_max.clear()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self) -> None:
        if self.result.validos or self.result.invalidos:
            self.summary.setText(" | ".join(self.result.summary_lines()))
            self.preview.setReadOnly(not bool(self.result.invalidos or self.weight_filter_pending))
            if not self.weight_filter_pending:
                self.preview.setPlainText(correction_text(self.result) if self.result.invalidos else self.result.preview_text())
            self.issues.setPlainText(self._issues_text())
            self.output.setPlainText(self._output_text())
        else:
            official = self.official_excel.name if self.official_excel else "-"
            self.summary.setText(f"Archivos: {len(self.paths)} | Excel oficial: {official}")
            self.preview.setReadOnly(True)
            self.preview.setPlainText("Selecciona TXT/CSV de precintos para empezar.")
            self.issues.setPlainText("Sin incidencias.")
            self.output.setPlainText("La salida TXT/CSV aparecera despues de procesar registros validos.")
        self._refresh_buttons_only()

    def _refresh_buttons_only(self) -> None:
        can_save = bool(self.result.validos and not self.result.invalidos and not self.weight_filter_pending)
        self.process_button.setEnabled(bool(self.paths))
        self.revalidate_button.setEnabled(bool(self.result.invalidos or self.weight_filter_pending))
        self.save_txt_button.setEnabled(can_save)
        self.save_csv_button.setEnabled(can_save)
        self.weight_button.setEnabled(bool(self.result.validos and not self.result.invalidos))
        self.clear_filter_button.setEnabled(bool(self.result.validos or self.result.invalidos or self.weight_filter_pending))
        self.clear_button.setEnabled(bool(self.paths or self.result.validos or self.result.invalidos or self.official_excel))

    def _template_values(self) -> dict[str, str]:
        return {
            "tipo_jamon": self.result.tipo_jamon,
            "registros_validos": str(len(self.result.validos)),
            "incidencias": str(len(self.result.invalidos)),
            "duplicados": str(len(self.result.duplicados)),
        }

    def _render_template(self, text: str) -> str:
        try:
            return text.format(**self._template_values())
        except Exception:
            return text

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if self.result.invalidos or self.weight_filter_pending:
            return 3, True, False
        if self.result.validos:
            return 4, False, False
        if self.paths:
            return 2, False, False
        return 1, False, False

    def _issues_text(self) -> str:
        if not (self.result.invalidos or self.result.duplicados or self.result.oficiales):
            return "Sin incidencias."
        lines: list[str] = []
        if self.result.invalidos:
            lines.append("Incidencias pendientes:")
            lines.extend(
                f"- {registro.archivo}:{registro.linea} {registro.precinto or '(sin precinto)'} | {motivo}"
                for registro, motivo in self.result.invalidos[:120]
            )
        if self.result.duplicados:
            if lines:
                lines.append("")
            lines.append("Duplicados suprimidos:")
            lines.extend(
                f"- {registro.precinto} | {registro.fecha} {registro.hora} | {registro.archivo}:{registro.linea}"
                for registro in self.result.duplicados[:80]
            )
        if self.result.oficiales:
            extra, missing = self.result.differences()
            if extra:
                if lines:
                    lines.append("")
                lines.append("Leidos fuera del Excel oficial:")
                lines.extend(f"- {item}" for item in sorted(extra)[:120])
            if missing:
                if lines:
                    lines.append("")
                lines.append("Oficiales no leidos:")
                lines.extend(f"- {item}" for item in sorted(missing)[:120])
        return "\n".join(lines)

    def _output_text(self) -> str:
        if not self.result.validos:
            return "No hay registros validos para salida."
        return "\n".join(registro.a_linea().lstrip("\ufeff") for registro in self.result.validos[:500])
