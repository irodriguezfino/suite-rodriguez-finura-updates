from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.paths import resource_path
from suite_pyside6.core.recepcion_maquilas import (
    RecepcionResult,
    generar_pdf_diferencias,
    generar_pdf_rangos,
    process_recepcion_maquilas,
)
from suite_pyside6.ui.components import labeled_field
from suite_pyside6.ui.file_dialogs import choose_directory, open_file, save_file
from suite_pyside6.ui.polish import collapsible_section, confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.responsive import make_flow, make_widgets_resizable
from suite_pyside6.ui.theme import base_qss


class RecepcionMaquilasWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.txt_file: Path | None = None
        self.seals_file: Path | None = None
        self.config_file: Path | None = resource_path("config_articulos.csv")
        self.result = RecepcionResult()
        self._metadata_warning_acknowledged = False
        self.show_dialogs = True
        self.setWindowTitle("Recepción Maquilas")
        self.resize(1160, 740)
        self.setMinimumSize(720, 560)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar TXT", "Cargar SealsReport", "Procesar", "Generar PDFs")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Recepción Maquilas")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Compara TXT recibido con SealsReport y genera informes PDF.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar TXT  ->  2 Cargar SealsReport  ->  3 Procesar  ->  4 Generar PDFs")
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

        self.txt_button = QPushButton("Cargar TXT recepción")
        self.txt_button.setProperty("primary", True)
        self.txt_button.clicked.connect(self.select_txt)
        actions_layout.addWidget(self.txt_button)

        self.seals_button = QPushButton("Cargar SealsReport")
        self.seals_button.clicked.connect(self.select_seals)
        actions_layout.addWidget(self.seals_button)

        self.config_button = QPushButton("Configurar rangos")
        self.config_button.clicked.connect(self.select_config)
        actions_layout.addWidget(self.config_button)

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar recepción")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        actions_layout.addWidget(salida_label)

        self.pdf_diff_button = QPushButton("Generar PDF diferencias")
        self.pdf_diff_button.clicked.connect(self.save_diff_dialog)
        actions_layout.addWidget(self.pdf_diff_button)

        self.pdf_ranges_button = QPushButton("Generar PDF rangos")
        self.pdf_ranges_button.clicked.connect(self.save_ranges_dialog)
        actions_layout.addWidget(self.pdf_ranges_button)

        self.pdf_both_button = QPushButton("Generar ambos PDFs")
        self.pdf_both_button.clicked.connect(self.save_both_dialog)
        actions_layout.addWidget(self.pdf_both_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        layout.addWidget(self.summary)

        metadata = QFrame()
        metadata.setObjectName("FormPanel")
        metadata_layout = make_flow(metadata, margin=0, spacing=8)
        metadata_layout.setContentsMargins(10, 7, 10, 7)
        self.ganadero = QLineEdit("EMBUTIDOS RODRIGUEZ")
        self.ganadero.setPlaceholderText("Ganadero")
        self.origen = QLineEdit("Espana")
        self.origen.setPlaceholderText("Origen")
        self.dac = QLineEdit()
        self.dac.setPlaceholderText("N DAC")
        self.contrato = QLineEdit()
        self.contrato.setPlaceholderText("Contrato")
        self.control_temperatura = QLineEdit("OK")
        self.control_temperatura.setPlaceholderText("Control de temperatura")
        self.ph = QLineEdit("OK")
        self.ph.setPlaceholderText("PH")
        self.especificacion = QLineEdit("Anexo 5,5 ER Rev 13 FES 01")
        self.especificacion.setPlaceholderText("Especificacion")
        self.observaciones = QLineEdit()
        self.observaciones.setPlaceholderText("Observaciones")
        make_widgets_resizable(
            self.ganadero,
            self.origen,
            self.dac,
            self.contrato,
            self.control_temperatura,
            self.ph,
            self.especificacion,
            self.observaciones,
        )
        metadata_layout.addWidget(labeled_field("Ganadero", self.ganadero), 0, 0)
        metadata_layout.addWidget(labeled_field("Origen", self.origen), 0, 1)
        metadata_layout.addWidget(labeled_field("N DAC", self.dac), 0, 2)
        metadata_layout.addWidget(labeled_field("Contrato", self.contrato), 0, 3)
        metadata_layout.addWidget(labeled_field("Control temperatura", self.control_temperatura), 1, 0)
        metadata_layout.addWidget(labeled_field("PH", self.ph), 1, 1)
        metadata_layout.addWidget(labeled_field("Especificacion", self.especificacion), 1, 2)
        metadata_layout.addWidget(labeled_field("Observaciones", self.observaciones), 1, 3)
        for field in (
            self.ganadero,
            self.origen,
            self.dac,
            self.contrato,
            self.control_temperatura,
            self.ph,
            self.especificacion,
            self.observaciones,
        ):
            field.textChanged.connect(self._mark_metadata_changed)
        layout.addWidget(collapsible_section("Campos manuales informe", metadata))

        panel = QFrame()
        panel.setObjectName("AppCard")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 9, 12, 12)
        panel_title = QLabel("Resumen y avisos")
        panel_title.setObjectName("SectionLabel")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(self.preview, 1)
        layout.addWidget(panel, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def select_txt(self) -> None:
        file = open_file(self, "recepcion_maquilas/txt", "Selecciona TXT recibido", "TXT (*.txt);;Todos (*.*)")
        if file:
            self.set_txt_file(file)

    def select_seals(self) -> None:
        file = open_file(self, "recepcion_maquilas/seals", "Selecciona SealsReport", "Excel (*.xlsx *.xlsm);;Todos (*.*)")
        if file:
            self.set_seals_file(file)

    def select_config(self) -> None:
        file = open_file(self, "recepcion_maquilas/config", "Selecciona config_articulos.csv", "CSV (*.csv);;Todos (*.*)")
        if file:
            self.config_file = file
            self._refresh()

    def set_txt_file(self, path: Path) -> None:
        self.txt_file = path
        self.result = RecepcionResult()
        self._refresh()

    def set_seals_file(self, path: Path) -> None:
        self.seals_file = path
        self.result = RecepcionResult()
        self._refresh()

    def process_files(self) -> None:
        if self.txt_file is None or self.seals_file is None:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Selecciona TXT y SealsReport antes de procesar.")
            return
        try:
            self.result = process_recepcion_maquilas(self.txt_file, self.seals_file, self.config_file)
        except Exception as exc:
            self.status.setText(f"Error: {exc}")
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.status.setText(f"Proceso completado: partida {self.result.partida}")
        self._refresh()

    def save_diff_dialog(self) -> None:
        if not self.result.registros_txt:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Procesa primero los archivos.")
            return
        if not self._confirm_metadata_reviewed():
            return
        file = save_file(
            self,
            "recepcion_maquilas/export_diff_pdf",
            "Guardar PDF de diferencias",
            f"Informe diferencias {self.result.partida}.pdf",
            "PDF (*.pdf)",
        )
        if file:
            self.save_diff_pdf(file)

    def save_ranges_dialog(self) -> None:
        if not self.result.registros_txt:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Procesa primero los archivos.")
            return
        if not self._confirm_metadata_reviewed():
            return
        file = save_file(
            self,
            "recepcion_maquilas/export_ranges_pdf",
            "Guardar PDF de rangos",
            f"Informe rangos {self.result.partida}.pdf",
            "PDF (*.pdf)",
        )
        if file:
            self.save_ranges_pdf(file)

    def save_both_dialog(self) -> None:
        if not self.result.registros_txt:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Procesa primero los archivos.")
            return
        if not self._confirm_metadata_reviewed():
            return
        folder = choose_directory(self, "recepcion_maquilas/export_both_pdf", "Selecciona carpeta de salida")
        if folder:
            self.save_both_pdfs(folder)

    def save_diff_pdf(self, path: Path) -> None:
        generar_pdf_diferencias(path, self.result)
        self.status.setText(f"PDF diferencias guardado: {path}")
        show_inline_message(self, "success", f"PDF diferencias guardado: {path.name}")

    def save_ranges_pdf(self, path: Path) -> None:
        generar_pdf_rangos(path, self.result, self._metadata())
        self.status.setText(f"PDF rangos guardado: {path}")
        show_inline_message(self, "success", f"PDF rangos guardado: {path.name}")

    def save_both_pdfs(self, folder: Path) -> tuple[Path, Path]:
        folder.mkdir(parents=True, exist_ok=True)
        diff = folder / f"Informe diferencias {self.result.partida}.pdf"
        ranges = folder / f"Informe rangos {self.result.partida}.pdf"
        generar_pdf_diferencias(diff, self.result)
        generar_pdf_rangos(ranges, self.result, self._metadata())
        self.status.setText(f"Informes generados en {folder}")
        show_inline_message(self, "success", f"PDFs generados: {diff.name} y {ranges.name}")
        return diff, ranges

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.txt_file = None
        self.seals_file = None
        self.result = RecepcionResult()
        self._metadata_warning_acknowledged = False
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _metadata(self) -> dict[str, str]:
        return {
            "ganadero": self.ganadero.text().strip(),
            "origen": self.origen.text().strip(),
            "dac": self.dac.text().strip(),
            "contrato": self.contrato.text().strip(),
            "control_temperatura": self.control_temperatura.text().strip(),
            "ph": self.ph.text().strip(),
            "observaciones": self.observaciones.text().strip(),
            "especificacion": self.especificacion.text().strip(),
        }

    def _default_metadata(self) -> dict[str, str]:
        return {
            "ganadero": "EMBUTIDOS RODRIGUEZ",
            "origen": "Espana",
            "dac": "",
            "contrato": "",
            "control_temperatura": "OK",
            "ph": "OK",
            "observaciones": "",
            "especificacion": "Anexo 5,5 ER Rev 13 FES 01",
        }

    def _metadata_uses_defaults(self) -> bool:
        return self._metadata() == self._default_metadata()

    def _mark_metadata_changed(self) -> None:
        self._metadata_warning_acknowledged = False

    def _confirm_metadata_reviewed(self) -> bool:
        if not self.show_dialogs or not self._metadata_uses_defaults() or self._metadata_warning_acknowledged:
            return True
        self._metadata_warning_acknowledged = True
        show_inline_message(
            self,
            "warning",
            "Los campos manuales del informe no se han modificado. Revisa el desplegable antes de generar PDF o pulsa de nuevo para continuar.",
        )
        return False

    def _refresh(self) -> None:
        txt_name = self.txt_file.name if self.txt_file else "-"
        seals_name = self.seals_file.name if self.seals_file else "-"
        config_name = self.config_file.name if self.config_file else "-"
        if self.result.registros_txt:
            self.summary.setText(" | ".join(self.result.summary_lines()[2:8]))
            self.preview.setPlainText(self.result.preview_text())
        else:
            self.summary.setText(f"TXT: {txt_name} | SealsReport: {seals_name} | Config: {config_name}")
            self.preview.setPlainText(
                "Archivos seleccionados:\n"
                f"TXT: {self.txt_file or ''}\n"
                f"SealsReport: {self.seals_file or ''}\n"
                f"Config: {self.config_file or ''}"
            )
        self.process_button.setEnabled(self.txt_file is not None and self.seals_file is not None)
        self.pdf_diff_button.setEnabled(bool(self.result.registros_txt))
        self.pdf_ranges_button.setEnabled(bool(self.result.registros_txt))
        self.pdf_both_button.setEnabled(bool(self.result.registros_txt))
        self.clear_button.setEnabled(bool(self.txt_file or self.seals_file or self.result.registros_txt))

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "pdf" in status or "informes generados" in status:
            return 4, False, True
        if "error" in status:
            return 3, True, False
        if self.result.registros_txt:
            return 4, False, False
        if self.txt_file is not None and self.seals_file is not None:
            return 3, False, False
        if self.txt_file is not None:
            return 2, False, False
        if self.seals_file is not None:
            return 1, True, False
        return 1, False, False
