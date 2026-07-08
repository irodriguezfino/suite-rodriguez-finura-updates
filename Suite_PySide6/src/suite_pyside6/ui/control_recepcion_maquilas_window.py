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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.control_recepcion_maquilas import (
    ControlRecepcionResult,
    correction_text,
    parsear_destinatarios,
    process_control_txt,
    revalidate_corrections,
    run_recepcion_with_seals,
    save_pdf_rangos,
    save_txt_ax,
    send_control_email,
    validar_destinatarios,
    weight_filter_text,
    ASUNTO_DEFECTO,
    MENSAJE_DEFECTO,
)
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.components import labeled_field
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import collapsible_section, confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.responsive import make_flow, make_widgets_resizable
from suite_pyside6.ui.session import settings
from suite_pyside6.ui.theme import base_qss


class ControlRecepcionMaquilasWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.seals_file: Path | None = None
        self.config_file: Path | None = resource_path("config_articulos.csv")
        self.result = ControlRecepcionResult()
        self.weight_filter_pending = False
        self._metadata_warning_acknowledged = False
        self.show_dialogs = True
        self.setWindowTitle("Control y Recepción Maquilas")
        self.resize(1180, 760)
        self.setMinimumSize(740, 580)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        self._load_email_template()
        polish_window(self)
        self._refresh()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Control y Recepción Maquilas")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Valida TXT, guarda TXT AX, cruza SealsReport, genera PDF y prepara correo.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Validar TXT  ->  2 Guardar TXT AX  ->  3 Cruzar albarán  ->  4 PDF/correo")
        steps.setObjectName("StepBar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(7)

        self.txt_button = QPushButton("Cargar TXT FAC")
        self.txt_button.setProperty("primary", True)
        self.txt_button.clicked.connect(self.select_txt)
        actions_layout.addWidget(self.txt_button)

        self.save_txt_button = QPushButton("Guardar TXT AX")
        self.save_txt_button.clicked.connect(self.save_txt_dialog)
        actions_layout.addWidget(self.save_txt_button)

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

        self.clear_corrections_button = QPushButton("Limpiar correcciones")
        self.clear_corrections_button.clicked.connect(self.clear_corrections)
        actions_layout.addWidget(self.clear_corrections_button)

        self.seals_button = QPushButton("Cargar SealsReport")
        self.seals_button.clicked.connect(self.select_seals)
        actions_layout.addWidget(self.seals_button)

        self.process_seals_button = QPushButton("Cruzar albarán")
        self.process_seals_button.clicked.connect(self.process_seals)
        actions_layout.addWidget(self.process_seals_button)

        self.pdf_button = QPushButton("Generar PDF rangos")
        self.pdf_button.clicked.connect(self.save_pdf_dialog)
        actions_layout.addWidget(self.pdf_button)

        self.email_button = QPushButton("Enviar correo")
        self.email_button.clicked.connect(self.send_email)
        actions_layout.addWidget(self.email_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        layout.addWidget(self.summary)

        email_panel = QFrame()
        email_panel.setObjectName("MailPanel")
        email_panel_layout = QVBoxLayout(email_panel)
        email_panel_layout.setContentsMargins(8, 6, 8, 6)
        email_panel_layout.setSpacing(6)
        email_fields = QWidget()
        email_layout = make_flow(email_fields, margin=0, spacing=8)
        email_layout.setContentsMargins(0, 0, 0, 0)
        self.recipients = QLineEdit()
        self.recipients.setPlaceholderText("Destinatarios")
        self.subject = QLineEdit(ASUNTO_DEFECTO)
        self.subject.setPlaceholderText("Asunto")
        make_widgets_resizable(self.recipients, self.subject)
        self.save_template_button = QPushButton("Guardar plantilla")
        self.save_template_button.clicked.connect(self.save_email_template)
        email_layout.addWidget(labeled_field("Destinatarios", self.recipients), 2)
        email_layout.addWidget(labeled_field("Asunto", self.subject), 2)
        email_layout.addWidget(self.save_template_button)
        self.body_editor = QPlainTextEdit()
        self.body_editor.setObjectName("MailBody")
        self.body_editor.setMaximumHeight(72)
        self.body_editor.setPlaceholderText("Mensaje del correo")
        email_panel_layout.addWidget(email_fields)
        email_panel_layout.addWidget(labeled_field("Mensaje del correo", self.body_editor))
        layout.addWidget(collapsible_section("Correo", email_panel))

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

    def select_txt(self) -> None:
        files = open_files(self, "control_recepcion_maquilas/txt", "Selecciona TXT de FAC", "TXT (*.txt);;Todos (*.*)")
        if files:
            self.set_txt_files(files)

    def set_txt_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.weight_filter_pending = False
        self.result = process_control_txt(self.paths, self.config_file)
        self.status.setText(f"TXT procesado: {len(self.result.validos)} válidos")
        self._refresh()

    def revalidate(self) -> None:
        if not (self.result.invalidos or self.weight_filter_pending):
            return
        self.result = revalidate_corrections(self.result, self.preview.toPlainText())
        self.seals_file = None
        self.weight_filter_pending = False
        if self.result.invalidos:
            self.status.setText(f"Siguen pendientes {len(self.result.invalidos)} incidencia(s).")
            if self.show_dialogs:
                show_inline_message(self, "warning", "Aun quedan lineas que no superan la validacion.")
        else:
            self.status.setText("Revalidacion correcta. Guarda el TXT AX para continuar.")
            show_inline_message(self, "success", "Revalidacion correcta. Guarda el TXT AX para continuar.")
        self._refresh()

    def apply_weight_filter(self) -> None:
        if self.result.invalidos:
            show_inline_message(self, "warning", "Primero corrige y revalida las incidencias.")
            return
        if not self.result.validos:
            show_inline_message(self, "warning", "Procesa primero uno o varios TXT.")
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
        if pending:
            self.result.txt_ax = None
            self.result.pdf_rangos = None
            self.result.txt_modified = True
        self.status.setText("Filtro aplicado. Revalida si has corregido registros.")
        self._refresh_buttons_only()

    def clear_corrections(self) -> None:
        self.weight_min.clear()
        self.weight_max.clear()
        self.weight_filter_pending = False
        self._refresh()
        self.status.setText("Panel de correccion restaurado.")

    def save_txt_dialog(self) -> None:
        if not self.result.validos:
            return
        file = save_file(self, "control_recepcion_maquilas/export_txt_ax", "Guardar TXT AX", "recepcion_corregida.txt", "TXT (*.txt)")
        if file:
            self.save_txt_ax(file)

    def save_txt_ax(self, path: Path) -> Path:
        saved = save_txt_ax(path, self.result)
        self.status.setText(f"TXT AX guardado: {saved}")
        show_inline_message(self, "success", f"TXT AX guardado: {saved.name}")
        self._refresh()
        return saved

    def select_seals(self) -> None:
        file = open_file(self, "control_recepcion_maquilas/seals", "Selecciona SealsReport", "Excel (*.xlsx *.xlsm);;Todos (*.*)")
        if file:
            self.seals_file = file
            self._refresh()

    def process_seals(self) -> None:
        if self.seals_file is None:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Selecciona SealsReport antes de cruzar.")
            return
        try:
            run_recepcion_with_seals(self.result, self.seals_file, self.config_file)
        except Exception as exc:
            self.status.setText(f"Error: {exc}")
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.status.setText("Cruce con albarán completado.")
        self._refresh()

    def save_pdf_dialog(self) -> None:
        if self.result.recepcion is None:
            return
        if self.show_dialogs and self._metadata_uses_defaults() and not self._metadata_warning_acknowledged:
            self._metadata_warning_acknowledged = True
            show_inline_message(
                self,
                "warning",
                "Los campos manuales del informe no se han modificado. Revisa el desplegable antes de generar el PDF o pulsa de nuevo para continuar.",
            )
            return
        file = save_file(
            self,
            "control_recepcion_maquilas/export_ranges_pdf",
            "Guardar PDF de rangos",
            f"Informe rangos {self.result.recepcion.partida}.pdf",
            "PDF (*.pdf)",
        )
        if file:
            self.save_pdf(file)

    def save_pdf(self, path: Path) -> Path:
        saved = save_pdf_rangos(path, self.result, self._metadata())
        self.status.setText(f"PDF guardado: {saved}")
        show_inline_message(self, "success", f"PDF guardado: {saved.name}")
        self._refresh()
        return saved

    def send_email(self) -> None:
        recipients = parsear_destinatarios(self.recipients.text())
        invalid = validar_destinatarios(recipients)
        if invalid:
            if self.show_dialogs:
                show_inline_message(self, "warning", "\n".join(invalid))
            self.status.setText("Revisa los destinatarios.")
            return
        try:
            send_control_email(
                self.recipients.text(),
                self.result,
                subject=self._render_template(self.subject.text().strip() or ASUNTO_DEFECTO),
                body=self._render_template(self.body_editor.toPlainText().strip() or MENSAJE_DEFECTO),
                metadata=self._metadata(),
            )
        except Exception as exc:
            self.status.setText(f"No se pudo enviar el correo: {exc}")
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.status.setText("Correo enviado correctamente.")
        show_inline_message(self, "success", "Correo enviado correctamente.")

    def save_email_template(self) -> None:
        app_settings = settings()
        app_settings.setValue("mail/control_recepcion/subject", self.subject.text().strip() or ASUNTO_DEFECTO)
        app_settings.setValue("mail/control_recepcion/body", self.body_editor.toPlainText().strip() or MENSAJE_DEFECTO)
        self.status.setText("Plantilla de correo guardada.")
        show_inline_message(self, "success", "Plantilla de correo guardada.")

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.paths = []
        self.seals_file = None
        self.result = ControlRecepcionResult()
        self.weight_filter_pending = False
        self._metadata_warning_acknowledged = False
        self.weight_min.clear()
        self.weight_max.clear()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _requires_txt_save(self) -> bool:
        return bool(self.result.txt_modified and self.result.txt_ax is None)

    def _can_continue_to_seals(self) -> bool:
        return bool(self.result.validos and not self.result.invalidos and not self.weight_filter_pending and not self._requires_txt_save())

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

    def _load_email_template(self) -> None:
        app_settings = settings()
        self.subject.setText(str(app_settings.value("mail/control_recepcion/subject", ASUNTO_DEFECTO) or ASUNTO_DEFECTO))
        self.body_editor.setPlainText(str(app_settings.value("mail/control_recepcion/body", MENSAJE_DEFECTO) or MENSAJE_DEFECTO))

    def _template_values(self) -> dict[str, str]:
        return {
            "tipo_jamon": self.result.tipo.tipo,
            "partida": self.result.partida_sugerida,
            "lote": self.result.lote_sugerido,
            "fecha_recepcion": self.result.validos[0].fecha if self.result.validos else "",
            "registros_validos": str(len(self.result.validos)),
        }

    def _render_template(self, text: str) -> str:
        try:
            return text.format(**self._template_values())
        except Exception:
            return text

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "correo enviado" in status:
            return 4, False, True
        if self.result.pdf_rangos is not None or "pdf guardado" in status:
            return 4, False, True
        if "error" in status or self.result.invalidos or self.weight_filter_pending:
            return 2, True, False
        if self.result.recepcion is not None:
            return 4, False, False
        if self._can_continue_to_seals():
            return 3, False, False
        if self.result.validos:
            return 2, False, False
        if self.paths:
            return 1, True, False
        return 1, False, False

    def _refresh(self) -> None:
        if self.result.validos or self.result.invalidos:
            self.summary.setText(" | ".join(self.result.summary_lines()[:5]))
            self.preview.setReadOnly(not bool(self.result.invalidos or self.weight_filter_pending))
            if not self.weight_filter_pending:
                self.preview.setPlainText(correction_text(self.result) if self.result.invalidos else self.result.preview_text())
            self.issues.setPlainText(self._issues_text())
            self.output.setPlainText(self._output_text())
        else:
            self.summary.setText("Sin archivos cargados")
            self.preview.setReadOnly(True)
            self.preview.setPlainText("Arrastra TXT de FAC aqui o pulsa Cargar TXT FAC para empezar.\n\nDespues podras guardar TXT AX, cruzar SealsReport y generar PDF/correo.")
            self.issues.setPlainText("Sin incidencias.")
            self.output.setPlainText("La salida TXT AX aparecera despues de procesar registros validos.")
        self._refresh_buttons_only()

    def _refresh_buttons_only(self) -> None:
        self.revalidate_button.setEnabled(bool(self.result.invalidos or self.weight_filter_pending))
        self.save_txt_button.setEnabled(bool(self.result.validos and not self.result.invalidos and not self.weight_filter_pending))
        self.seals_button.setEnabled(self._can_continue_to_seals())
        self.process_seals_button.setEnabled(bool(self._can_continue_to_seals() and self.seals_file))
        self.pdf_button.setEnabled(bool(self.result.recepcion))
        self.email_button.setEnabled(bool(self.result.recepcion))
        self.weight_button.setEnabled(bool(self.result.validos and not self.result.invalidos))
        self.clear_corrections_button.setEnabled(bool(self.result.validos or self.result.invalidos or self.weight_filter_pending))
        self.clear_button.setEnabled(bool(self.paths or self.result.validos or self.result.invalidos))

    def _issues_text(self) -> str:
        if not (self.result.invalidos or self.result.duplicados or self.result.recepcion):
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
        if self.result.recepcion is not None:
            if lines:
                lines.append("")
            lines.append("Cruce con albarán:")
            lines.extend(self.result.recepcion.preview_text().splitlines()[:160])
        return "\n".join(lines)

    def _output_text(self) -> str:
        if not self.result.validos:
            return "No hay registros válidos para salida."
        if self.result.txt_ax is not None:
            return f"TXT AX guardado:\n{self.result.txt_ax}"
        if not self.result.txt_modified:
            return "El TXT original es valido para recepcion."
        return "\n".join(registro.to_line() for registro in self.result.validos[:500])
