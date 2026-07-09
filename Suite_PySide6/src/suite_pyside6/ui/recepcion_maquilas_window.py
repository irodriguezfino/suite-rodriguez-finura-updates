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
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
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
from suite_pyside6.ui.components import control_rail_label, labeled_field, section_label, step_bar
from suite_pyside6.ui.file_dialogs import choose_directory, open_file, save_file
from suite_pyside6.ui.polish import collapsible_section, confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
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

        hero = QFrame()
        hero.setObjectName("ControlProductHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(14)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(3)
        title = QLabel("Recepción Maquilas")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Compara TXT recibido con SealsReport y genera informes PDF de diferencias y rangos.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)

        hero_status = QFrame()
        hero_status.setObjectName("ControlHeroStatus")
        hero_status_layout = QVBoxLayout(hero_status)
        hero_status_layout.setContentsMargins(10, 8, 10, 8)
        hero_status_layout.setSpacing(3)
        hero_status_label = QLabel("Comparativa")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("TXT vs SealsReport")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)
        steps = step_bar("1 Cargar TXT  ->  2 Cargar SealsReport  ->  3 Procesar  ->  4 Generar PDFs")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("controlCommand", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(8)

        command_panel = QFrame()
        command_panel.setObjectName("ControlCommandCopy")
        command_copy = QVBoxLayout(command_panel)
        command_copy.setContentsMargins(0, 0, 0, 0)
        command_copy.setSpacing(2)
        command_label = QLabel("Siguiente acción")
        command_label.setObjectName("Overline")
        self.command_hint = QLabel("Carga TXT de recepción y SealsReport")
        self.command_hint.setObjectName("ControlCommandTitle")
        self.command_hint.setWordWrap(True)
        command_copy.addWidget(command_label)
        command_copy.addWidget(self.command_hint)
        actions_layout.addWidget(command_panel, 1)

        entrada_label = QLabel("ENTRADA")
        entrada_label.setObjectName("GroupLabel")
        entrada_label.setVisible(False)
        entrada_label.setMaximumSize(0, 0)
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
        proceso_label.setVisible(False)
        proceso_label.setMaximumSize(0, 0)
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar recepción")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        salida_label.setVisible(False)
        salida_label.setMaximumSize(0, 0)
        actions_layout.addWidget(salida_label)

        self.pdf_diff_button = QPushButton("Generar PDF diferencias")
        self.pdf_diff_button.clicked.connect(self.save_diff_dialog)

        self.pdf_ranges_button = QPushButton("Generar PDF rangos")
        self.pdf_ranges_button.clicked.connect(self.save_ranges_dialog)

        self.pdf_both_button = QPushButton("Generar ambos PDFs")
        self.pdf_both_button.clicked.connect(self.save_both_dialog)

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
        self.origen = QLineEdit("España")
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
        self.especificacion.setPlaceholderText("Especificación")
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
        metadata_layout.addWidget(labeled_field("Especificación", self.especificacion), 1, 2)
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
        metadata_scroll = QScrollArea()
        metadata_scroll.setObjectName("InlineSectionScroll")
        metadata_scroll.setWidgetResizable(True)
        metadata_scroll.setFrameShape(QFrame.NoFrame)
        metadata_scroll.setMaximumHeight(152)
        metadata_scroll.setWidget(metadata)
        self.metadata_section = collapsible_section("Campos manuales informe", metadata_scroll)

        workspace = QFrame()
        workspace.setObjectName("ControlPilotWorkspace")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(10)

        panel = QFrame()
        panel.setObjectName("ControlPreviewPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(8)
        panel_title = section_label("Comparativa y avisos")
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("OutputText")
        self.preview.setAccessibleName("Resumen de comparativa de recepción")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(self.preview, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Estado y salida")
        self.rail_state = control_rail_label("Pendiente de archivos", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga TXT de recepción y SealsReport para iniciar la comparativa.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar TXT recepción", role="action")
        self.rail_next.setWordWrap(True)
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("TXT: -\nSealsReport: -\nConfig: config_articulos.csv")
        self.rail_files.setWordWrap(True)
        reports_title = section_label("Informes PDF")
        self.rail_reports = control_rail_label("Disponibles tras procesar la comparativa.")
        self.rail_reports.setWordWrap(True)
        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(files_title)
        rail_layout.addWidget(self.rail_files)
        rail_layout.addWidget(reports_title)
        rail_layout.addWidget(self.rail_reports)
        rail_layout.addWidget(self.pdf_both_button)
        rail_layout.addWidget(self.pdf_diff_button)
        rail_layout.addWidget(self.pdf_ranges_button)
        rail_layout.addWidget(self.metadata_section)
        rail_layout.addStretch(1)

        workspace_layout.addWidget(panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def select_txt(self) -> None:
        file = open_file(self, "recepcion_maquilas/txt", "Selecciona TXT de recepción", "TXT (*.txt);;Todos (*.*)")
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
                show_inline_message(self, "warning", "Carga el TXT y SealsReport antes de procesar.")
            return
        try:
            self.result = process_recepcion_maquilas(self.txt_file, self.seals_file, self.config_file)
        except Exception as exc:
            self.status.setText(f"Error: {exc}")
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.status.setText(f"Comparativa procesada: partida {self.result.partida}.")
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
        folder = choose_directory(self, "recepcion_maquilas/export_both_pdf", "Selecciona la carpeta de salida")
        if folder:
            self.save_both_pdfs(folder)

    def save_diff_pdf(self, path: Path) -> None:
        generar_pdf_diferencias(path, self.result)
        self.status.setText(f"PDF diferencias guardado: {path}")
        show_inline_message(self, "success", f"PDF diferencias guardado: {path.name}")
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def save_ranges_pdf(self, path: Path) -> None:
        generar_pdf_rangos(path, self.result, self._metadata())
        self.status.setText(f"PDF rangos guardado: {path}")
        show_inline_message(self, "success", f"PDF rangos guardado: {path.name}")
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def save_both_pdfs(self, folder: Path) -> tuple[Path, Path]:
        folder.mkdir(parents=True, exist_ok=True)
        diff = folder / f"Informe diferencias {self.result.partida}.pdf"
        ranges = folder / f"Informe rangos {self.result.partida}.pdf"
        generar_pdf_diferencias(diff, self.result)
        generar_pdf_rangos(ranges, self.result, self._metadata())
        self.status.setText(f"Informes generados en {folder}")
        show_inline_message(self, "success", f"PDFs generados: {diff.name} y {ranges.name}")
        self._refresh_pilot_state()
        self._sync_recommended_action()
        return diff, ranges

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
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
            "origen": "España",
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
            "Los campos manuales del informe siguen con sus valores por defecto. Revísalos antes de generar el PDF o vuelve a intentarlo para continuar.",
        )
        return False

    def _refresh_pilot_state(self) -> None:
        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso del proceso")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente acción recomendada: {self.rail_next.text()}")

        txt_name = self.txt_file.name if self.txt_file else "-"
        seals_name = self.seals_file.name if self.seals_file else "-"
        config_name = self.config_file.name if self.config_file else "-"
        self.rail_files.setText(f"TXT: {txt_name}\nSealsReport: {seals_name}\nConfig: {config_name}")
        if self.result.registros_txt:
            self.rail_reports.setText("PDFs listos para generar.")
        else:
            self.rail_reports.setText("Disponibles tras procesar la comparativa.")

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "pdf" in status or "informes generados" in status:
            return "Informes generados", "Los PDFs se han guardado correctamente.", 100
        if "error" in status:
            return "Revisión necesaria", self.status.text(), 60
        if self.result.registros_txt:
            return "Comparativa procesada", "Revisa las diferencias y genera los PDF necesarios.", 80
        if self.txt_file is not None and self.seals_file is not None:
            return "Listo para procesar", "Ambos archivos están cargados. Procesa la comparativa.", 45
        if self.txt_file is not None:
            return "TXT cargado", "Carga SealsReport para poder comparar.", 25
        if self.seals_file is not None:
            return "SealsReport cargado", "Carga el TXT de recepción para continuar.", 25
        return "Pendiente de archivos", "Carga TXT de recepción y SealsReport para iniciar la comparativa.", 0

    def _next_action_text(self) -> str:
        if self.txt_file is None:
            return "Cargar TXT recepción"
        if self.seals_file is None:
            return "Cargar SealsReport"
        if not self.result.registros_txt:
            return "Procesar recepción"
        return "Generar PDFs"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        buttons = (
            self.txt_button,
            self.seals_button,
            self.config_button,
            self.process_button,
            self.pdf_diff_button,
            self.pdf_ranges_button,
            self.pdf_both_button,
            self.clear_button,
        )
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar TXT recepción": self.txt_button,
                "Cargar SealsReport": self.seals_button,
                "Procesar recepción": self.process_button,
                "Generar PDFs": self.pdf_both_button,
            },
            buttons,
        )

    def _refresh(self) -> None:
        txt_name = self.txt_file.name if self.txt_file else "-"
        seals_name = self.seals_file.name if self.seals_file else "-"
        config_name = self.config_file.name if self.config_file else "-"
        if self.result.registros_txt:
            self.summary.setText(" | ".join(self.result.summary_lines()[2:8]))
            self.preview.setPlainText(self.result.preview_text())
        else:
            if self.txt_file is not None and self.seals_file is not None:
                self.summary.setText(f"Listo para procesar | Config: {config_name}")
            elif self.txt_file is not None:
                self.summary.setText(f"TXT cargado: {txt_name} | Falta SealsReport")
            elif self.seals_file is not None:
                self.summary.setText(f"SealsReport cargado: {seals_name} | Falta TXT")
            else:
                self.summary.setText("Pendiente de TXT y SealsReport")
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
        self._refresh_pilot_state()
        self._sync_recommended_action()

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
