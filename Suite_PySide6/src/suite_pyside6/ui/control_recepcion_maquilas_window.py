from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.control_recepcion_maquilas import (
    ControlRecepcionResult,
    albaran_recepcion,
    correction_text,
    parsear_destinatarios,
    process_control_txt,
    revalidate_corrections,
    run_recepcion_with_seals,
    save_pdf_rangos,
    save_txt_ax,
    send_control_email,
    validar_destinatarios,
    ASUNTO_DEFECTO,
    MENSAJE_DEFECTO,
)
from suite_pyside6.core.empresas_clientes import EmpresasClientesLoadResult, load_empresas_clientes
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.components import ModernSelect, control_metric_pair, control_pill, labeled_field, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import collapsible_section, confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.responsive import make_flow, make_widgets_resizable
from suite_pyside6.ui.session import settings
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


ASUNTO_LEGACY_DEFECTO = "Recepcion maquilas - documentacion"
RECIPIENTS_KEY = "mail/control_recepcion_precintos/recipients"
LEGACY_RECIPIENT_1_KEY = "mail/control_recepcion_precintos/recipient_1"
LEGACY_RECIPIENT_2_KEY = "mail/control_recepcion_precintos/recipient_2"
LEGACY_RECIPIENTS_KEY = "mail/control_recepcion_precintos/recent_recipients"


def responsive_labeled_field(label_text: str, field: QWidget) -> QWidget:
    """Campo etiquetado que puede comprimirse y refluye dentro de paneles estrechos."""
    group = labeled_field(label_text, field)
    group.setMinimumWidth(0)
    group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    group.setProperty("flowCanShrink", True)
    label = group.findChild(QLabel, "FieldLabel")
    if label is not None:
        label.setWordWrap(True)
    return group


class ControlRecepcionPrecintosWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.seals_file: Path | None = None
        self.config_file: Path | None = resource_path("config_articulos.csv")
        self.result = ControlRecepcionResult()
        self.empresas_clientes_result: EmpresasClientesLoadResult | None = None
        self.empresas_clientes: tuple[str, ...] = ()
        self._metadata_warning_acknowledged = False
        self.show_dialogs = True
        self.setWindowTitle("Control y Recepción Precintos")
        self.resize(1180, 760)
        self.setMinimumSize(740, 580)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self.setProperty("contextPanelOutputOnly", True)
        self._build_ui()
        self.reload_empresas_clientes()
        self._load_email_template()
        polish_window(self, context_panel=True, body_scroll=False)
        self._install_output_context_section()
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar TXT", "Validar", "Cruzar SealsReport", "Enviar correo")

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
        title = QLabel("Control y Recepción Precintos")
        title.setObjectName("WindowTitle")
        self.standard_description = QLabel("Valida TXT FAC, corrige incidencias, cruza SealsReport y prepara la salida documental.")
        self.standard_description.setObjectName("WindowSubtitle")
        self.standard_description.setWordWrap(True)
        hero_copy.addWidget(title)
        hero_copy.addWidget(self.standard_description)
        hero_layout.addLayout(hero_copy, 1)

        hero_status = QFrame()
        hero_status.setObjectName("ControlHeroStatus")
        hero_status_layout = QVBoxLayout(hero_status)
        hero_status_layout.setContentsMargins(10, 8, 10, 8)
        hero_status_layout.setSpacing(3)
        hero_status_label = QLabel("Flujo guiado")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("4 pasos operativos")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)
        steps = step_bar("1 Cargar TXT  ->  2 Validar  ->  3 Cruzar SealsReport  ->  4 Enviar correo")
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
        email_panel.setMinimumWidth(0)
        email_panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        email_panel_layout = QVBoxLayout(email_panel)
        email_panel_layout.setContentsMargins(12, 10, 12, 12)
        email_panel_layout.setSpacing(12)
        self.recipient_fields: list[QLineEdit] = []
        self._recipient_rows: dict[QLineEdit, QWidget] = {}
        self.recipients_editor = QFrame()
        self.recipients_editor.setObjectName("RecipientEditor")
        self.recipients_editor.setMinimumWidth(0)
        self.recipients_editor.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        recipients_editor_layout = QVBoxLayout(self.recipients_editor)
        recipients_editor_layout.setContentsMargins(0, 0, 0, 0)
        recipients_editor_layout.setSpacing(8)
        recipients_hint = QLabel("Los cambios son temporales hasta que guardes la lista habitual.")
        recipients_hint.setObjectName("FieldHint")
        recipients_hint.setWordWrap(True)
        self.add_recipient_button = QPushButton("Añadir destinatario")
        self.add_recipient_button.clicked.connect(lambda: self._add_recipient_field(focus=True))
        self.recipients_rows = QWidget()
        self.recipients_rows.setMinimumWidth(0)
        self.recipients_rows.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.recipients_rows_layout = QVBoxLayout(self.recipients_rows)
        self.recipients_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.recipients_rows_layout.setSpacing(6)
        # La ayuda ocupa todo el ancho: con el botón a su lado se comprimía a
        # demasiadas líneas en el carril lateral y ocultaba asunto y mensaje.
        recipients_editor_layout.addWidget(recipients_hint)
        recipients_editor_layout.addWidget(self.recipients_rows)
        self.subject = QLineEdit(ASUNTO_DEFECTO)
        self.subject.setPlaceholderText("Asunto")
        make_widgets_resizable(self.subject)
        self.save_template_button = QPushButton("Guardar destinatarios habituales")
        self.save_template_button.clicked.connect(self.save_email_template)
        self.body_editor = QPlainTextEdit()
        self.body_editor.setObjectName("MailBody")
        self.body_editor.setMinimumHeight(120)
        self.body_editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.body_editor.setPlaceholderText("Mensaje del correo")
        email_actions = QFrame()
        email_actions.setObjectName("MailActions")
        email_actions_layout = QHBoxLayout(email_actions)
        email_actions_layout.setContentsMargins(0, 0, 0, 0)
        email_actions_layout.setSpacing(8)
        email_actions_layout.addWidget(self.add_recipient_button)
        email_actions_layout.addWidget(self.save_template_button)
        email_actions_layout.addStretch(1)
        email_panel_layout.addWidget(responsive_labeled_field("Destinatarios", self.recipients_editor))
        email_panel_layout.addWidget(responsive_labeled_field("Asunto", self.subject))
        body_field = responsive_labeled_field("Mensaje del correo", self.body_editor)
        body_field.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        email_panel_layout.addWidget(body_field)
        email_scroll = QScrollArea()
        email_scroll.setObjectName("InlineSectionScroll")
        email_scroll.setWidgetResizable(True)
        email_scroll.setFrameShape(QFrame.NoFrame)
        email_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        email_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        email_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        email_scroll.setWidget(email_panel)
        self.email_scroll = email_scroll
        # El contenido puede desplazarse, pero la acción de guardar permanece
        # accesible al final del panel incluso con muchos destinatarios.
        email_content = QWidget()
        email_content.setMinimumWidth(0)
        email_content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        email_content_layout = QVBoxLayout(email_content)
        email_content_layout.setContentsMargins(0, 0, 0, 0)
        email_content_layout.setSpacing(6)
        email_content_layout.addWidget(email_scroll, 1)
        email_content_layout.addWidget(email_actions)
        self.email_actions = email_actions
        self.email_section = collapsible_section("Correo", email_content)

        metadata = QFrame()
        metadata.setObjectName("FormPanel")
        metadata_layout = make_flow(metadata, margin=0, spacing=8)
        metadata_layout.setContentsMargins(10, 7, 10, 7)
        self.ganadero = QLineEdit("EMBUTIDOS RODRIGUEZ")
        self.ganadero.setPlaceholderText("Ganadero")
        self.empresa_cliente = ModernSelect(placeholder="Selecciona una empresa cliente")
        self.empresa_cliente.setAccessibleName("Empresa cliente")
        self.empresa_cliente.setToolTip("Selecciona una empresa cliente de la lista configurable.")
        self.empresa_cliente.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
            self.empresa_cliente,
            self.origen,
            self.dac,
            self.contrato,
            self.control_temperatura,
            self.ph,
            self.especificacion,
            self.observaciones,
        )
        metadata_layout.addWidget(responsive_labeled_field("Ganadero", self.ganadero), 0, 0)
        metadata_layout.addWidget(responsive_labeled_field("Empresa cliente", self.empresa_cliente), 0, 1)
        metadata_layout.addWidget(responsive_labeled_field("Origen", self.origen), 0, 2)
        metadata_layout.addWidget(responsive_labeled_field("N DAC", self.dac), 0, 3)
        metadata_layout.addWidget(responsive_labeled_field("Contrato", self.contrato), 1, 0)
        metadata_layout.addWidget(responsive_labeled_field("Control temperatura", self.control_temperatura), 1, 1)
        metadata_layout.addWidget(responsive_labeled_field("PH", self.ph), 1, 2)
        metadata_layout.addWidget(responsive_labeled_field("Especificación", self.especificacion), 1, 3)
        metadata_layout.addWidget(responsive_labeled_field("Observaciones", self.observaciones), 2, 0, 1, 4)
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
        self.empresa_cliente.currentIndexChanged.connect(self._on_empresa_cliente_changed)
        metadata_scroll = QScrollArea()
        metadata_scroll.setObjectName("InlineSectionScroll")
        metadata_scroll.setWidgetResizable(True)
        metadata_scroll.setFrameShape(QFrame.NoFrame)
        metadata_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        metadata_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        metadata_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        metadata_scroll.setWidget(metadata)
        self.metadata_scroll = metadata_scroll
        self.metadata_section = collapsible_section("Campos manuales informe", metadata_scroll)
        self._configure_auxiliary_accordion()

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
        rail.setMinimumWidth(0)
        rail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rail_layout = QVBoxLayout(rail)
        self.rail_layout = rail_layout
        rail_layout.setContentsMargins(10, 8, 10, 8)
        rail_layout.setSpacing(8)
        self.output = QPlainTextEdit()
        self.output.setObjectName("OutputText")
        self.output.setAccessibleName("Resumen de salida TXT AX")
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.output.setMinimumHeight(120)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rail_layout.addWidget(self.metadata_section, 1)
        rail_layout.addWidget(self.email_section, 1)

        content_stack = QFrame()
        content_stack.setObjectName("ControlContentStack")
        content_layout = QVBoxLayout(content_stack)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        content_layout.addWidget(preview_panel, 3)
        content_layout.addWidget(issues_panel, 2)

        # El carril de formularios crece hacia la izquierda sin invadir el
        # contexto superior; ambos acordeones comparten el mismo ancho.
        workspace_layout.addWidget(content_stack, 3)
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
        self.result = process_control_txt(self.paths, self.config_file)
        self.status.setText(f"TXT validado: {len(self.result.validos)} registros válidos.")
        self._refresh()

    def revalidate(self) -> None:
        if not self.result.invalidos:
            return
        self.result = revalidate_corrections(self.result, self.preview.toPlainText())
        self.seals_file = None
        if self.result.invalidos:
            self.status.setText(f"Quedan {len(self.result.invalidos)} líneas por corregir.")
            if self.show_dialogs:
                show_inline_message(self, "warning", "Aún quedan líneas que no superan la validación.")
        else:
            self.status.setText("Revalidación correcta. Guarda el TXT AX para continuar.")
            show_inline_message(self, "success", "Revalidación correcta. Guarda el TXT AX para continuar.")
        self._refresh()

    def clear_corrections(self) -> None:
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
        if not self._validate_empresa_cliente():
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
        if not self._validate_empresa_cliente():
            raise ValueError(self._empresa_cliente_validation_message())
        saved = save_pdf_rangos(path, self.result, self._metadata())
        self.status.setText(f"PDF guardado: {saved}")
        show_inline_message(self, "success", f"PDF guardado: {saved.name}")
        self._refresh()
        return saved

    def send_email(self) -> None:
        if not self._validate_empresa_cliente():
            return
        recipients = self._validated_recipients()
        if recipients is None:
            message = self._recipient_validation_message
            if self.show_dialogs:
                show_inline_message(self, "warning", message)
            self.status.setText(message)
            return
        try:
            send_control_email(
                "; ".join(recipients),
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
        recipients = self._validated_recipients()
        if recipients is None:
            message = self._recipient_validation_message
            self.status.setText(message)
            if self.show_dialogs:
                show_inline_message(self, "warning", message)
            return
        app_settings = settings()
        self._save_recipient_preferences(recipients, app_settings)
        app_settings.setValue("mail/control_recepcion_precintos/subject", self.subject.text().strip() or ASUNTO_DEFECTO)
        app_settings.setValue("mail/control_recepcion_precintos/body", self.body_editor.toPlainText().strip() or MENSAJE_DEFECTO)
        app_settings.sync()
        self.status.setText("Destinatarios habituales guardados.")
        show_inline_message(self, "success", "Destinatarios habituales guardados.")

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.paths = []
        self.seals_file = None
        self.result = ControlRecepcionResult()
        self._metadata_warning_acknowledged = False
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _requires_txt_save(self) -> bool:
        return bool(self.result.txt_modified and self.result.txt_ax is None)

    def _can_continue_to_seals(self) -> bool:
        return bool(self.result.validos and not self.result.invalidos and not self._requires_txt_save())

    def _metadata(self) -> dict[str, str]:
        return {
            "ganadero": self.ganadero.text().strip(),
            "empresa_cliente": self._selected_empresa_cliente(),
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
            "empresa_cliente": "",
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

    def _on_empresa_cliente_changed(self, _index: int) -> None:
        self._mark_metadata_changed()
        if self._selected_empresa_cliente():
            self.empresa_cliente.setProperty("error", False)
            self.empresa_cliente.style().unpolish(self.empresa_cliente)
            self.empresa_cliente.style().polish(self.empresa_cliente)

    def reload_empresas_clientes(self) -> None:
        """Recarga el TXT al abrir Campos manuales, conservando una seleccion valida."""

        selected = self._selected_empresa_cliente()
        self.empresas_clientes_result = load_empresas_clientes()
        self.empresas_clientes = self.empresas_clientes_result.companies
        self.empresa_cliente.blockSignals(True)
        self.empresa_cliente.clear()
        for company in self.empresas_clientes:
            self.empresa_cliente.add_option(company, company)
        index = self.empresa_cliente.findData(selected) if selected else -1
        self.empresa_cliente.setCurrentIndex(index)
        self.empresa_cliente.blockSignals(False)
        self.empresa_cliente.setProperty("error", False)
        self.empresa_cliente.style().unpolish(self.empresa_cliente)
        self.empresa_cliente.style().polish(self.empresa_cliente)
        if selected and not self._selected_empresa_cliente():
            self._mark_metadata_changed()

    def _selected_empresa_cliente(self) -> str:
        value = self.empresa_cliente.currentData()
        if not isinstance(value, str) or value not in self.empresas_clientes:
            return ""
        return value

    def _empresa_cliente_validation_message(self) -> str:
        if not self.empresas_clientes:
            return "No hay empresas cliente válidas. Revisa el archivo empresas_clientes.txt y vuelve a abrir Campos manuales informe."
        return "Selecciona una empresa cliente antes de generar el informe."

    def _validate_empresa_cliente(self) -> bool:
        if self._selected_empresa_cliente():
            self.empresa_cliente.setProperty("error", False)
            return True
        message = self._empresa_cliente_validation_message()
        self.empresa_cliente.setProperty("error", True)
        self.empresa_cliente.style().unpolish(self.empresa_cliente)
        self.empresa_cliente.style().polish(self.empresa_cliente)
        self.empresa_cliente.setFocus(Qt.OtherFocusReason)
        self.status.setText(message)
        if self.show_dialogs:
            show_inline_message(self, "warning", message)
        return False

    def _configure_auxiliary_accordion(self) -> None:
        self._accordion_sections = (self.metadata_section, self.email_section)
        self._accordion_headers = (
            self.metadata_section.findChild(QToolButton, "CollapsibleHeader"),
            self.email_section.findChild(QToolButton, "CollapsibleHeader"),
        )
        self._accordion_headers = tuple(header for header in self._accordion_headers if header is not None)
        self._metadata_header = self.metadata_section.findChild(QToolButton, "CollapsibleHeader")
        self._accordion_syncing = False
        for header in self._accordion_headers:
            header.toggled.connect(lambda checked, source=header: self._sync_auxiliary_accordion(source, checked))
        self._refresh_auxiliary_panel_layout()

    def _install_output_context_section(self) -> None:
        """Ubica el único visor TXT en la zona de contexto compartida."""
        context_panel = self.findChild(QFrame, "ContextPanel")
        if context_panel is None or context_panel.layout() is None:
            return
        self.output_section = collapsible_section("Salida TXT AX", self.output)
        self.output_section.setObjectName("ContextOutputSection")
        self.output_section.setMinimumWidth(0)
        self.output_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.output_section.setProperty("flowCanShrink", True)
        context_panel.layout().addWidget(self.output_section)

    def _sync_auxiliary_accordion(self, source: QToolButton, expanded: bool) -> None:
        if self._accordion_syncing:
            return
        self._accordion_syncing = True
        try:
            if expanded and source is self._metadata_header:
                self.reload_empresas_clientes()
            if expanded:
                for header in self._accordion_headers:
                    if header is not source and header.isChecked():
                        header.setChecked(False)
        finally:
            self._accordion_syncing = False
        self._refresh_auxiliary_panel_layout()

    def _refresh_auxiliary_panel_layout(self) -> None:
        sections = getattr(self, "_accordion_sections", ())
        headers = getattr(self, "_accordion_headers", ())
        for section in sections:
            if section is not None:
                section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                section.updateGeometry()
        rail_layout = getattr(self, "rail_layout", None)
        if rail_layout is not None:
            for section, header in zip(sections, headers):
                is_open = header.isChecked()
                rail_layout.setStretch(rail_layout.indexOf(section), 3 if is_open else 0)
            rail_layout.invalidate()
            rail_layout.activate()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if hasattr(self, "metadata_section"):
            self._refresh_auxiliary_panel_layout()

    def _add_recipient_field(self, value: str = "", *, index: int | None = None, focus: bool = False) -> QLineEdit:
        field = QLineEdit(value)
        field.setPlaceholderText("correo@empresa.com")
        field.setAccessibleName("Destinatario")
        field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        field.editingFinished.connect(self._normalize_recipient_fields)
        field.returnPressed.connect(lambda: QTimer.singleShot(0, self._commit_recipient_field))
        remove_button = QPushButton("Eliminar")
        remove_button.setProperty("destructive", True)
        remove_button.setAccessibleName("Eliminar destinatario")
        remove_button.clicked.connect(lambda _checked=False, current=field: self._remove_recipient_field(current))
        row = QWidget()
        row.setMinimumWidth(0)
        row.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(field, 1)
        row_layout.addWidget(remove_button)
        target_index = len(self.recipient_fields) if index is None else index
        self.recipient_fields.insert(target_index, field)
        self._recipient_rows[field] = row
        self.recipients_rows_layout.insertWidget(target_index, row)
        if focus:
            field.setFocus(Qt.TabFocusReason)
        return field

    def _remove_recipient_field(self, field: QLineEdit) -> None:
        row = self._recipient_rows.pop(field, None)
        if row is None:
            return
        self.recipient_fields.remove(field)
        self.recipients_rows_layout.removeWidget(row)
        row.deleteLater()
        self.recipients_rows.updateGeometry()

    def _normalize_recipient_fields(self) -> None:
        values = parsear_destinatarios("; ".join(field.text() for field in self.recipient_fields))
        current = [field.text().strip() for field in self.recipient_fields if field.text().strip()]
        if values != current:
            self._set_recipient_fields(values)

    def _commit_recipient_field(self) -> None:
        self._normalize_recipient_fields()
        if self.recipient_fields and self.recipient_fields[-1].text().strip():
            self._add_recipient_field(focus=True)

    def _set_recipient_fields(self, values: list[str], *, ensure_empty_field: bool = True) -> None:
        for field in tuple(self.recipient_fields):
            self._remove_recipient_field(field)
        for value in values:
            self._add_recipient_field(value)
        if ensure_empty_field and not self.recipient_fields:
            self._add_recipient_field()

    def _validated_recipients(self) -> list[str] | None:
        self._normalize_recipient_fields()
        values = [field.text().strip() for field in self.recipient_fields if field.text().strip()]
        invalid = set(validar_destinatarios(values))
        for field in self.recipient_fields:
            value = field.text().strip()
            has_error = bool(value and value in invalid)
            field.setProperty("error", has_error)
            field.style().unpolish(field)
            field.style().polish(field)
        if not values:
            self._recipient_validation_message = "Introduce al menos un destinatario válido."
            return None
        if invalid:
            self._recipient_validation_message = "Dirección no válida: " + ", ".join(sorted(invalid))
            return None
        self._recipient_validation_message = ""
        return parsear_destinatarios("; ".join(values))

    def _save_recipient_preferences(self, recipients: list[str], app_settings=None) -> None:
        if app_settings is None:
            app_settings = settings()
        app_settings.setValue(RECIPIENTS_KEY, recipients)
        app_settings.sync()

    @staticmethod
    def _setting_values(value: object) -> list[str]:
        def flatten(item: object) -> list[str]:
            if isinstance(item, str):
                return [item]
            if isinstance(item, (list, tuple)):
                return [part for nested in item for part in flatten(nested)]
            return [str(item)] if item is not None else []

        return parsear_destinatarios("; ".join(part.strip() for part in flatten(value) if part.strip()))

    @staticmethod
    def _valid_recipient_values(values: list[str]) -> list[str]:
        return [value for value in parsear_destinatarios("; ".join(values)) if not validar_destinatarios([value])]

    def _load_recipient_preferences(self, app_settings) -> None:
        configured = self._valid_recipient_values(self._setting_values(app_settings.value(RECIPIENTS_KEY, [])))
        if not configured:
            legacy_fields = self._setting_values(
                [
                    app_settings.value(LEGACY_RECIPIENT_1_KEY, ""),
                    app_settings.value(LEGACY_RECIPIENT_2_KEY, ""),
                    app_settings.value(LEGACY_RECIPIENTS_KEY, []),
                ]
            )
            configured = self._valid_recipient_values(legacy_fields)
        self._save_recipient_preferences(configured, app_settings)
        self._set_recipient_fields(configured)

    def _load_email_template(self) -> None:
        app_settings = settings()
        self._load_recipient_preferences(app_settings)
        subject = str(
            app_settings.value(
                "mail/control_recepcion_precintos/subject",
                app_settings.value("mail/control_recepcion/subject", ASUNTO_DEFECTO),
            )
            or ASUNTO_DEFECTO
        )
        if subject in {ASUNTO_LEGACY_DEFECTO, "Recepción maquilas - albarán {albaran}"}:
            subject = ASUNTO_DEFECTO
        self.subject.setText(subject)
        self.body_editor.setPlainText(
            str(
                app_settings.value(
                    "mail/control_recepcion_precintos/body",
                    app_settings.value("mail/control_recepcion/body", MENSAJE_DEFECTO),
                )
                or MENSAJE_DEFECTO
            )
        )

    def _template_values(self) -> dict[str, str]:
        return {
            "tipo_jamon": self.result.tipo.tipo,
            "partida": self.result.partida_sugerida,
            "lote": self.result.lote_sugerido,
            "fecha_recepcion": self.result.validos[0].fecha if self.result.validos else "",
            "registros_validos": str(len(self.result.validos)),
            "albaran": albaran_recepcion(self.result),
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
        if "error" in status or self.result.invalidos:
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
            self.preview.setReadOnly(not bool(self.result.invalidos))
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
        self.revalidate_button.setEnabled(bool(self.result.invalidos))
        self.save_txt_button.setEnabled(bool(self.result.validos and not self.result.invalidos))
        self.seals_button.setEnabled(self._can_continue_to_seals())
        self.process_seals_button.setEnabled(bool(self._can_continue_to_seals() and self.seals_file))
        self.pdf_button.setEnabled(bool(self.result.recepcion))
        self.email_button.setEnabled(bool(self.result.recepcion))
        self.clear_corrections_button.setEnabled(bool(self.result.validos or self.result.invalidos))
        self.clear_button.setEnabled(bool(self.paths or self.result.validos or self.result.invalidos))
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
        pendientes = invalidos
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
        needs_corrections = bool(self.result.invalidos)
        self.issues_empty.setVisible(not has_issues and not needs_corrections)
        self.issues.setVisible(has_issues)
        self.preview.setVisible(needs_corrections)

        state, detail, _progress = self._pilot_state_text()
        next_action = self._next_action_text()
        self.command_hint.setText(next_action)
        self.command_hint.setToolTip(detail)
        self.command_hint.setAccessibleDescription(f"{state}. {detail}")
        self.issues_empty.setText(self._empty_issue_text())

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "correo enviado" in status:
            return "Completado", "Correo enviado correctamente.", 100
        if self.result.pdf_rangos is not None or "pdf guardado" in status:
            return "PDF listo", "Informe generado. El correo puede enviarse con la documentación.", 90
        if self.result.recepcion is not None:
            return "Cruce completado", "Listo para enviar correo; el PDF de rangos se adjunta automaticamente si no lo guardaste.", 82
        if self.result.invalidos:
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
        if self.result.invalidos:
            return "Revalidar correcciones"
        if self._requires_txt_save():
            return "Guardar TXT AX"
        if self._can_continue_to_seals() and self.seals_file is None:
            return "Cargar SealsReport"
        if self._can_continue_to_seals() and self.seals_file is not None and self.result.recepcion is None:
            return "Cruzar albarán"
        if self.result.recepcion is not None:
            return "Enviar correo"
        return "Completa el paso actual"

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


# Compatibilidad de importación para automatizaciones internas antiguas.
ControlRecepcionMaquilasWindow = ControlRecepcionPrecintosWindow
