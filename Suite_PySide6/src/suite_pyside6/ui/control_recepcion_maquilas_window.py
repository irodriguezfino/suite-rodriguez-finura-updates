from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
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
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, labeled_field, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import collapsible_section, confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.responsive import make_flow, make_widgets_resizable
from suite_pyside6.ui.session import settings
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
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
        polish_window(self, context_panel=False)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar TXT", "Validar", "Cruzar SealsReport", "Generar PDF", "Enviar correo")

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
        title = QLabel("Control y Recepción Maquilas")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Valida TXT FAC, corrige incidencias, cruza SealsReport y prepara la salida documental.")
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
        hero_status_label = QLabel("Flujo guiado")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("5 pasos operativos")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)
        steps = step_bar("1 Cargar TXT  ->  2 Validar  ->  3 Cruzar SealsReport  ->  4 Generar PDF  ->  5 Enviar correo")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
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
        self.command_hint = QLabel("Carga el TXT FAC para iniciar el control")
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

        self.txt_button = QPushButton("Cargar TXT FAC")
        self.txt_button.setProperty("primary", True)
        self.txt_button.clicked.connect(self.select_txt)
        actions_layout.addWidget(self.txt_button)

        self.seals_button = QPushButton("Cargar SealsReport")
        self.seals_button.clicked.connect(self.select_seals)
        actions_layout.addWidget(self.seals_button)

        validacion_label = QLabel("VALIDACIÓN")
        validacion_label.setObjectName("GroupLabel")
        validacion_label.setVisible(False)
        validacion_label.setMaximumSize(0, 0)
        actions_layout.addWidget(validacion_label)

        self.revalidate_button = QPushButton("Revalidar")
        self.revalidate_button.clicked.connect(self.revalidate)
        actions_layout.addWidget(self.revalidate_button)

        self.weight_min = QLineEdit()
        self.weight_min.setObjectName("CompactField")
        self.weight_min.setPlaceholderText("Peso min.")
        self.weight_min.setAccessibleDescription("Peso mínimo para filtrar registros, disponible tras validar el TXT.")
        self.weight_min.setMaximumWidth(96)
        actions_layout.addWidget(self.weight_min)

        self.weight_max = QLineEdit()
        self.weight_max.setObjectName("CompactField")
        self.weight_max.setPlaceholderText("Peso max.")
        self.weight_max.setAccessibleDescription("Peso máximo para filtrar registros, disponible tras validar el TXT.")
        self.weight_max.setMaximumWidth(96)
        actions_layout.addWidget(self.weight_max)

        self.weight_button = QPushButton("Filtrar pesos")
        self.weight_button.clicked.connect(self.apply_weight_filter)
        actions_layout.addWidget(self.weight_button)

        self.clear_corrections_button = QPushButton("Limpiar correcciones")
        self.clear_corrections_button.clicked.connect(self.clear_corrections)
        actions_layout.addWidget(self.clear_corrections_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        salida_label.setVisible(False)
        salida_label.setMaximumSize(0, 0)
        actions_layout.addWidget(salida_label)

        self.save_txt_button = QPushButton("Guardar TXT AX")
        self.save_txt_button.clicked.connect(self.save_txt_dialog)
        actions_layout.addWidget(self.save_txt_button)

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
        self.summary.setVisible(False)
        self.summary.setMaximumHeight(0)
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
        email_scroll = QScrollArea()
        email_scroll.setObjectName("InlineSectionScroll")
        email_scroll.setWidgetResizable(True)
        email_scroll.setFrameShape(QFrame.NoFrame)
        email_scroll.setMaximumHeight(176)
        email_scroll.setWidget(email_panel)
        self.email_section = collapsible_section("Correo", email_scroll)

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

        preview_panel = QFrame()
        preview_panel.setObjectName("ControlPreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(8)
        preview_header = QHBoxLayout()
        preview_title = section_label("Registros del TXT FAC")
        self.preview_count = control_pill("0 líneas")
        preview_header.addWidget(preview_title)
        preview_header.addStretch(1)
        preview_header.addWidget(self.preview_count)
        self.preview_table = QTableWidget(0, 6)
        self.preview_table.setObjectName("ControlPreviewTable")
        self.preview_table.setAccessibleName("Vista previa de líneas del TXT FAC")
        self.preview_table.setHorizontalHeaderLabels(["Línea", "Artículo", "Precinto", "Peso (kg)", "Lote", "Estado"])
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.preview_table, 1)

        self.metrics_strip = QFrame()
        self.metrics_strip.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(4)
        self.metric_valid = control_metric_pair(metrics_layout, 0, "Válidos", "0")
        self.metric_pending = control_metric_pair(metrics_layout, 1, "Pendientes", "0")
        self.metric_invalid = control_metric_pair(metrics_layout, 2, "Inválidos", "0")
        self.metric_files = control_metric_pair(metrics_layout, 3, "Archivos", "0")
        preview_layout.addWidget(self.metrics_strip)

        issues_panel = QFrame()
        issues_panel.setObjectName("ControlIssuesPanel")
        issues_layout = QVBoxLayout(issues_panel)
        issues_layout.setContentsMargins(12, 10, 12, 10)
        issues_layout.setSpacing(8)
        issues_header = QHBoxLayout()
        issues_title = section_label("Revisión y correcciones")
        self.issues_count = control_pill("0 detectadas", issue=True)
        issues_header.addWidget(issues_title)
        issues_header.addStretch(1)
        issues_header.addWidget(self.issues_count)
        self.issues_empty = QLabel("No hay incidencias para mostrar")
        self.issues_empty.setObjectName("ControlDropzone")
        self.issues_empty.setAccessibleName("Estado vacío de incidencias")
        self.issues_empty.setAlignment(Qt.AlignCenter)
        self.issues_empty.setWordWrap(True)
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("CorrectionEditor")
        self.preview.setAccessibleName("Editor de correcciones de TXT FAC")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.issues = QPlainTextEdit()
        self.issues.setObjectName("IssuesText")
        self.issues.setAccessibleName("Listado de incidencias del proceso")
        self.issues.setReadOnly(True)
        self.issues.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.issues.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        issues_layout.addLayout(issues_header)
        issues_layout.addWidget(self.issues_empty, 1)
        issues_layout.addWidget(self.issues, 1)
        issues_layout.addWidget(self.preview, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Salida e informe")
        self.rail_state = control_rail_label("Pendiente de TXT", role="state")
        self.rail_detail = control_rail_label("Carga un TXT FAC para iniciar la validación.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar TXT FAC", role="action")
        self.rail_next.setWordWrap(True)
        alerts_title = section_label("Avisos")
        self.rail_alerts = control_rail_label("Sin avisos.")
        self.rail_alerts.setWordWrap(True)
        self.output = QPlainTextEdit()
        self.output.setObjectName("OutputText")
        self.output.setAccessibleName("Resumen de salida TXT AX")
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.output.setMaximumHeight(112)
        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(alerts_title)
        rail_layout.addWidget(self.rail_alerts)
        rail_layout.addWidget(self.metadata_section)
        output_title = section_label("Salida TXT AX")
        rail_layout.addWidget(output_title)
        rail_layout.addWidget(self.output)
        rail_layout.addWidget(self.email_section)
        rail_layout.addStretch(1)

        content_stack = QFrame()
        content_stack.setObjectName("ControlContentStack")
        content_layout = QVBoxLayout(content_stack)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        content_layout.addWidget(preview_panel, 3)
        content_layout.addWidget(issues_panel, 2)

        workspace_layout.addWidget(content_stack, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def select_txt(self) -> None:
        files = open_files(self, "control_recepcion_maquilas/txt", "Selecciona TXT FAC", "TXT (*.txt);;Todos (*.*)")
        if files:
            self.set_txt_files(files)

    def set_txt_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.weight_filter_pending = False
        self.result = process_control_txt(self.paths, self.config_file)
        self.status.setText(f"TXT validado: {len(self.result.validos)} registros válidos.")
        self._refresh()

    def revalidate(self) -> None:
        if not (self.result.invalidos or self.weight_filter_pending):
            return
        self.result = revalidate_corrections(self.result, self.preview.toPlainText())
        self.seals_file = None
        self.weight_filter_pending = False
        if self.result.invalidos:
            self.status.setText(f"Quedan {len(self.result.invalidos)} líneas por corregir.")
            if self.show_dialogs:
                show_inline_message(self, "warning", "Aún quedan líneas que no superan la validación.")
        else:
            self.status.setText("Revalidación correcta. Guarda el TXT AX para continuar.")
            show_inline_message(self, "success", "Revalidación correcta. Guarda el TXT AX para continuar.")
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
        self._populate_preview_table()
        self._refresh_pilot_state()

    def clear_corrections(self) -> None:
        self.weight_min.clear()
        self.weight_max.clear()
        self.weight_filter_pending = False
        self._refresh()
        self.status.setText("Correcciones restauradas.")

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
                show_inline_message(self, "warning", "Carga SealsReport antes de cruzar el albarán.")
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
                "Los campos manuales del informe siguen con sus valores por defecto. Revísalos antes de generar el PDF o vuelve a intentarlo para continuar.",
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
        self._refresh()

    def save_email_template(self) -> None:
        app_settings = settings()
        app_settings.setValue("mail/control_recepcion/subject", self.subject.text().strip() or ASUNTO_DEFECTO)
        app_settings.setValue("mail/control_recepcion/body", self.body_editor.toPlainText().strip() or MENSAJE_DEFECTO)
        self.status.setText("Plantilla de correo guardada.")
        show_inline_message(self, "success", "Plantilla de correo guardada.")

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
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
            self.preview.setPlainText("")
            self.issues.setPlainText("Sin incidencias.")
            self.output.setPlainText("La salida TXT AX aparecerá después de procesar registros válidos.")
        self._populate_preview_table()
        self._refresh_pilot_state()
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
        self._sync_weight_filter_controls()
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar TXT FAC": self.txt_button,
                "Revalidar correcciones": self.revalidate_button,
                "Guardar TXT AX": self.save_txt_button,
                "Cargar SealsReport": self.seals_button,
                "Cruzar albarán": self.process_seals_button,
                "Generar PDF": self.pdf_button,
                "Enviar correo": self.email_button,
            },
            (
                self.txt_button,
                self.revalidate_button,
                self.save_txt_button,
                self.seals_button,
                self.process_seals_button,
                self.pdf_button,
                self.email_button,
            ),
            primary_requires_enabled=False,
        )

    def _sync_weight_filter_controls(self) -> None:
        visible = bool(self.weight_button.isEnabled() or self.weight_filter_pending)
        self.weight_min.setVisible(visible)
        self.weight_max.setVisible(visible)

    def _populate_preview_table(self) -> None:
        rows: list[tuple[str, str, str, str, str, str]] = []
        for registro in self.result.validos[:120]:
            rows.append(
                (
                    str(registro.linea),
                    registro.codigo_fac or "-",
                    registro.precinto or "-",
                    registro.peso or "-",
                    registro.lote or "-",
                    "Válido",
                )
            )
        for registro, motivo in self.result.invalidos[:80]:
            rows.append(
                (
                    str(registro.linea),
                    registro.codigo_fac or "-",
                    registro.precinto or "-",
                    registro.peso or "-",
                    registro.lote or "-",
                    f"Pendiente: {motivo}",
                )
            )
        with bulk_table_update(self.preview_table):
            self.preview_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    if column == 5 and value.startswith("Pendiente"):
                        item.setToolTip(value)
                    self.preview_table.setItem(row_index, column, item)
        total_rows = len(self.result.validos) + len(self.result.invalidos)
        update_count_label(self.preview_count, len(rows), total_rows, "líneas")

    def _refresh_pilot_state(self) -> None:
        validos = len(self.result.validos)
        invalidos = len(self.result.invalidos)
        pendientes = invalidos + int(self.weight_filter_pending)
        files = len(self.paths)
        self.metric_valid.setText(str(validos))
        self.metric_pending.setText(str(pendientes))
        self.metric_invalid.setText(str(invalidos))
        self.metric_files.setText(str(files))
        for label, value in (
            (self.metric_valid, validos),
            (self.metric_pending, pendientes),
            (self.metric_invalid, invalidos),
            (self.metric_files, files),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")
        self.issues_count.setText(f"{pendientes} detectadas" if pendientes else "0 detectadas")
        self.issues_count.setAccessibleDescription(
            f"Incidencias detectadas: {pendientes}. Revisa el panel central si hay pendientes."
        )

        has_issues = bool(self.result.invalidos or self.result.duplicados or self.result.recepcion)
        needs_corrections = bool(self.result.invalidos or self.weight_filter_pending)
        self.issues_empty.setVisible(not has_issues and not needs_corrections)
        self.issues.setVisible(has_issues)
        self.preview.setVisible(needs_corrections)

        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso del proceso")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente acción recomendada: {self.rail_next.text()}")
        self.rail_alerts.setText(self._alerts_text())
        self.rail_alerts.setAccessibleDescription("Avisos del proceso: " + self.rail_alerts.text().replace("\n", ". "))
        self.issues_empty.setText(self._empty_issue_text())

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "correo enviado" in status:
            return "Completado", "Correo enviado correctamente.", 100
        if self.result.pdf_rangos is not None or "pdf guardado" in status:
            return "PDF listo", "Informe generado. El correo puede enviarse con la documentación.", 90
        if self.result.recepcion is not None:
            return "Cruce completado", "Revisa diferencias y genera el PDF de rangos.", 75
        if self.result.invalidos or self.weight_filter_pending:
            return "Revisión pendiente", "Corrige las líneas marcadas y revalida.", 45
        if self._requires_txt_save():
            return "TXT modificado", "Guarda el TXT AX antes de cruzar SealsReport.", 58
        if self._can_continue_to_seals() and self.seals_file is not None:
            return "Listo para cruzar", "SealsReport cargado. Cruza el albarán.", 65
        if self._can_continue_to_seals():
            return "TXT validado", "Carga SealsReport para continuar.", 55
        if self.result.validos:
            return "Validado", "Los registros están listos para generar la salida.", 45
        if self.paths:
            return "TXT cargado", "Valida los datos de entrada.", 25
        return "Pendiente de TXT", "Carga un TXT FAC para iniciar la validación.", 0

    def _next_action_text(self) -> str:
        if not self.paths and not self.result.validos:
            return "Cargar TXT FAC"
        if self.result.invalidos or self.weight_filter_pending:
            return "Revalidar correcciones"
        if self._requires_txt_save():
            return "Guardar TXT AX"
        if self._can_continue_to_seals() and self.seals_file is None:
            return "Cargar SealsReport"
        if self._can_continue_to_seals() and self.seals_file is not None and self.result.recepcion is None:
            return "Cruzar albarán"
        if self.result.recepcion is not None and self.result.pdf_rangos is None:
            return "Generar PDF"
        if self.result.recepcion is not None:
            return "Enviar correo"
        return "Completa el paso actual"

    def _alerts_text(self) -> str:
        alerts: list[str] = []
        if self.result.invalidos:
            alerts.append(f"{len(self.result.invalidos)} líneas pendientes")
        if self.result.duplicados:
            alerts.append(f"{len(self.result.duplicados)} duplicados suprimidos")
        if self.weight_filter_pending:
            alerts.append("Filtro de peso pendiente de revalidar")
        if self._can_continue_to_seals() and self.seals_file is None:
            alerts.append("SealsReport no cargado")
        if self.result.recepcion is not None and not self.recipients.text().strip():
            alerts.append("Correo sin destinatarios")
        if self.result.recepcion is not None and self._metadata_uses_defaults():
            alerts.append("Campos manuales sin revisar")
        return "\n".join(alerts) if alerts else "Sin avisos."

    def _empty_issue_text(self) -> str:
        if not self.paths and not self.result.validos:
            return "No hay incidencias para mostrar.\n\nArrastra aquí los TXT FAC o usa Cargar TXT FAC."
        if self.result.validos and not self.result.invalidos:
            return "Sin incidencias pendientes.\n\nContinúa con SealsReport y la salida."
        return "No hay incidencias para mostrar."

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
            return "No hay registros válidos para generar la salida."
        if self.result.txt_ax is not None:
            return f"TXT AX guardado:\n{self.result.txt_ax}"
        if not self.result.txt_modified:
            return "El TXT original es válido para la recepción."
        return "\n".join(registro.to_line() for registro in self.result.validos[:500])
