from __future__ import annotations

from dataclasses import asdict
import json

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPageLayout, QPageSize, QPainter, QPen
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.numerador_etiquetas import (
    DEFAULT_BODY,
    DEFAULT_SUBJECT,
    LabelLayout,
    MAX_LABELS_PER_JOB,
    SequenceFormatError,
    increment_code,
    invalid_recipients,
    parse_recipients,
    render_mail_template,
    send_label_status_email,
    sequence_values,
)
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.background import run_background
from suite_pyside6.ui.components import ActionMenuButton, labeled_field, metric, panel, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_file, save_file
from suite_pyside6.ui.polish import collapsible_section, polish_window, show_inline_message, sync_recommended_action
from suite_pyside6.ui.responsive import register_adaptive_layout
from suite_pyside6.ui.session import settings
from suite_pyside6.ui.theme import base_qss, palette


class NoWheelSpinBox(QSpinBox):
    """Evita alterar importes o cantidades al desplazar la página con el ratón."""

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """Los cambios de medidas se hacen con teclado, flechas o el editor visual."""

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        event.ignore()


class LabelEditorCanvas(QWidget):
    """Vista previa física con una zona única que se puede desplazar con el ratón."""

    layout_moved = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = LabelLayout()
        self._text = "0001"
        self._drag_offset: QPointF | None = None
        self.setMinimumSize(270, 430)
        self.setAccessibleName("Editor visual de zona de impresión")
        self.setAccessibleDescription("Arrastra la zona punteada para situar el identificador.")

    def set_layout_model(self, layout: LabelLayout) -> None:
        self._layout = layout.normalized()
        self.update()

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        label_rect, scale = self._label_rect()
        tokens = palette()
        painter.fillRect(self.rect(), QColor(tokens["surface_muted"]))
        painter.fillRect(label_rect, QColor(Qt.GlobalColor.white))
        painter.setPen(QPen(QColor(tokens["border_strong"]), 1.5))
        painter.drawRect(label_rect)
        layout = self._layout
        zone = self._zone_rect()
        painter.setPen(QPen(QColor(tokens["primary"]), 1.6, Qt.DashLine))
        painter.drawRect(zone)
        painter.setPen(QColor(tokens["text_muted"]))
        caption = QFont()
        caption.setPointSize(8)
        painter.setFont(caption)
        painter.drawText(label_rect.adjusted(6, 5, -6, -5), Qt.AlignLeft | Qt.AlignTop, "Etiqueta")
        font = QFont(layout.font_family)
        font.setBold(layout.bold)
        font.setPixelSize(max(1, min(int(layout.font_size_pt * 25.4 / 72 * scale), int(zone.height() * 0.82))))
        painter.setFont(font)
        painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawText(zone, self._align_flag(layout.alignment) | Qt.AlignVCenter, self._text)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self._zone_rect().contains(event.position()):
            self._drag_offset = event.position() - self._zone_rect().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_offset is None:
            super().mouseMoveEvent(event)
            return
        label_rect, scale = self._label_rect()
        layout = self._layout
        point = event.position() - self._drag_offset
        x = min(max(0.0, (point.x() - label_rect.x()) / scale), layout.width_mm - layout.zone_width_mm)
        y = min(max(0.0, (point.y() - label_rect.y()) / scale), layout.height_mm - layout.zone_height_mm)
        self.layout_moved.emit(x, y)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_offset is not None and event.button() == Qt.LeftButton:
            self._drag_offset = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _label_rect(self) -> tuple[QRectF, float]:
        available = QRectF(self.rect()).adjusted(18, 18, -18, -18)
        scale = min(available.width() / self._layout.width_mm, available.height() / self._layout.height_mm)
        width, height = self._layout.width_mm * scale, self._layout.height_mm * scale
        return QRectF(available.center().x() - width / 2, available.center().y() - height / 2, width, height), scale

    def _zone_rect(self) -> QRectF:
        label_rect, scale = self._label_rect()
        layout = self._layout
        return QRectF(label_rect.x() + layout.x_mm * scale, label_rect.y() + layout.y_mm * scale, layout.zone_width_mm * scale, layout.zone_height_mm * scale)

    @staticmethod
    def _align_flag(value: str) -> Qt.AlignmentFlag:
        return {"left": Qt.AlignLeft, "right": Qt.AlignRight}.get(value, Qt.AlignHCenter)


class NumeradorEtiquetasWindow(QMainWindow):
    SETTINGS_PREFIX = "labels/numerador"
    DESIGN_FILE_FORMAT = "rodriguez-finura/numerador-etiquetas"
    DESIGN_FILE_VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self.layout_model = LabelLayout()
        self.last_code = ""
        self.last_first_code = ""
        self.last_quantity = 0
        self.pending_job: tuple[str, int, str] | None = None
        self._updating_controls = False
        self.setWindowTitle("Numerador de Etiquetas")
        self.resize(1180, 800)
        self.setMinimumSize(760, 600)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._load_state()
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Definir secuencia", "Elegir diseño", "Enviar a impresora", "Confirmar impresión")

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)

        hero = QFrame(); hero.setObjectName("ControlProductHero")
        hero_layout = QHBoxLayout(hero); hero_layout.setContentsMargins(14, 12, 14, 12)
        copy = QVBoxLayout()
        title = QLabel("Numerador de Etiquetas"); title.setObjectName("WindowTitle")
        subtitle = QLabel("Diseña etiquetas reutilizables, imprime una secuencia y registra únicamente el último código confirmado.")
        subtitle.setObjectName("WindowSubtitle"); subtitle.setWordWrap(True)
        copy.addWidget(title); copy.addWidget(subtitle); hero_layout.addLayout(copy, 1)
        root_layout.addWidget(hero)
        root_layout.addWidget(step_bar("1 Secuencia  →  2 Diseño guardado  →  3 Imprimir  →  4 Confirmar"))

        toolbar = QFrame(); toolbar.setObjectName("Toolbar"); toolbar.setProperty("controlCommand", True)
        toolbar_layout = QHBoxLayout(toolbar); toolbar_layout.setContentsMargins(10, 8, 10, 8)
        hint = QVBoxLayout()
        hint_label = QLabel("Siguiente acción"); hint_label.setObjectName("Overline")
        self.command_hint = QLabel(); self.command_hint.setObjectName("ControlCommandTitle")
        hint.addWidget(hint_label); hint.addWidget(self.command_hint); toolbar_layout.addLayout(hint, 1)
        self.print_button = QPushButton("Enviar a impresora"); self.print_button.clicked.connect(self.print_labels)
        self.confirm_button = QPushButton("Confirmar impresión"); self.confirm_button.clicked.connect(self.confirm_print)
        self.discard_pending_button = QPushButton("Descartar pendiente"); self.discard_pending_button.clicked.connect(self.discard_pending)
        toolbar_layout.addWidget(self.print_button); toolbar_layout.addWidget(self.confirm_button); toolbar_layout.addWidget(self.discard_pending_button)
        root_layout.addWidget(toolbar)

        metric_layout = QHBoxLayout()
        self.first_metric = metric("Primera etiqueta", "—", "Valor de inicio")
        self.last_metric = metric("Última prevista", "—", "Solo se registra al confirmar")
        self.next_metric = metric("Siguiente sugerida", "—", "Último valor local confirmado")
        metric_layout.addWidget(self.first_metric); metric_layout.addWidget(self.last_metric); metric_layout.addWidget(self.next_metric)
        root_layout.addLayout(metric_layout)
        # Three narrow metric cards are harder to scan than a short vertical
        # sequence when the editor is embedded in a compact workspace.
        register_adaptive_layout(self, metric_layout, breakpoint_width=980)

        workspace = QHBoxLayout(); workspace.setSpacing(10)
        preview_panel, preview_layout = panel("Editor de etiqueta", "Arrastra la zona punteada o usa los campos exactos en milímetros.")
        self.canvas = LabelEditorCanvas(); self.canvas.layout_moved.connect(self.move_zone)
        preview_layout.addWidget(self.canvas, 1)
        note = QLabel("El contorno punteado solo sirve para editar y nunca se imprime."); note.setObjectName("MutedText"); note.setWordWrap(True)
        preview_layout.addWidget(note)
        workspace.addWidget(preview_panel, 5)

        controls_panel, controls = panel("Contenido y diseño", "El contador incrementa el último bloque numérico y conserva letras, prefijos y sufijos.", name="FormPanel")
        controls.addWidget(section_label("Secuencia"))
        sequence = QGridLayout(); sequence.setSpacing(8)
        self.first_code = QLineEdit(self._initial_first_code()); self.first_code.setPlaceholderText("Ej.: RF-000123-A"); self.first_code.textChanged.connect(self._refresh)
        self.quantity = NoWheelSpinBox(); self.quantity.setRange(1, MAX_LABELS_PER_JOB); self.quantity.setValue(self.pending_job[1] if self.pending_job else 1); self.quantity.valueChanged.connect(self._refresh)
        self.last_confirmed_label = QLabel(); self.last_confirmed_label.setObjectName("MutedText"); self.last_confirmed_label.setWordWrap(True)
        sequence.addWidget(labeled_field("Primer código", self.first_code), 0, 0, 1, 2)
        sequence.addWidget(labeled_field("Cantidad", self.quantity), 1, 0); sequence.addWidget(self.last_confirmed_label, 1, 1)
        controls.addLayout(sequence)

        controls.addWidget(section_label("Diseños guardados"))
        designs = QGridLayout(); designs.setSpacing(8)
        self.design_selector = QComboBox(); self.design_selector.currentIndexChanged.connect(self._on_design_selected)
        self.load_design_button = QPushButton("Cargar diseño"); self.load_design_button.clicked.connect(self.load_selected_design)
        self.save_design_button = QPushButton("Guardar diseño actual"); self.save_design_button.clicked.connect(self.save_design)
        self.design_actions_button = ActionMenuButton(accessible_name="Más acciones de diseño")
        self.delete_design_button = self.design_actions_button.add_action("Eliminar diseño", self.delete_design, destructive=True)
        self.export_design_button = self.design_actions_button.add_action("Exportar diseño", self.export_selected_design)
        self.import_design_button = self.design_actions_button.add_action("Importar diseño", self.import_design)
        designs.addWidget(labeled_field("Diseño", self.design_selector, compact=True), 0, 0, 1, 2)
        designs.addWidget(self.load_design_button, 1, 0); designs.addWidget(self.save_design_button, 1, 1)
        designs.addWidget(self.design_actions_button, 2, 0, 1, 2)
        controls.addLayout(designs)

        dimensions_content = QWidget()
        dimensions = QGridLayout(dimensions_content); dimensions.setContentsMargins(0, 4, 0, 4); dimensions.setSpacing(8)
        self.label_width = self._mm_spin(10, 300, 50); self.label_height = self._mm_spin(10, 300, 120)
        self.zone_x = self._mm_spin(0, 300, 5); self.zone_y = self._mm_spin(0, 300, 42)
        self.zone_width = self._mm_spin(2, 300, 40); self.zone_height = self._mm_spin(2, 300, 36)
        for row, pair in enumerate((("Ancho etiqueta", self.label_width, "Alto etiqueta", self.label_height), ("X", self.zone_x, "Y", self.zone_y), ("Ancho zona", self.zone_width, "Alto zona", self.zone_height))):
            dimensions.addWidget(labeled_field(pair[0], pair[1], compact=True), row, 0)
            dimensions.addWidget(labeled_field(pair[2], pair[3], compact=True), row, 1)
        self.center_zone_button = QPushButton("Centrar zona"); self.center_zone_button.clicked.connect(self.center_zone)
        dimensions.addWidget(self.center_zone_button, 3, 0, 1, 2)
        self.dimensions_section = collapsible_section("Medidas y zona", dimensions_content)
        controls.addWidget(self.dimensions_section)

        typography_content = QWidget()
        typography = QGridLayout(typography_content); typography.setContentsMargins(0, 4, 0, 4); typography.setSpacing(8)
        self.font_family = QFontComboBox()
        self.font_size = NoWheelDoubleSpinBox(); self.font_size.setRange(6, 288); self.font_size.setDecimals(1); self.font_size.setSuffix(" pt")
        self.alignment = QComboBox(); self.alignment.addItem("Izquierda", "left"); self.alignment.addItem("Centrado", "center"); self.alignment.addItem("Derecha", "right")
        self.bold = QCheckBox("Negrita")
        typography.addWidget(labeled_field("Fuente", self.font_family, compact=True), 0, 0, 1, 2)
        typography.addWidget(labeled_field("Tamaño", self.font_size, compact=True), 1, 0); typography.addWidget(labeled_field("Alineación", self.alignment, compact=True), 1, 1)
        typography.addWidget(self.bold, 2, 0, 1, 2)
        self.typography_section = collapsible_section("Tipografía", typography_content)
        controls.addWidget(self.typography_section); controls.addStretch(1)
        workspace.addWidget(controls_panel, 4)
        register_adaptive_layout(self, workspace, breakpoint_width=980)
        root_layout.addLayout(workspace, 1)

        mail_panel, mail = panel(name="MailPanel")
        mail_grid = QGridLayout(); mail_grid.setSpacing(8)
        self.recipients = QLineEdit(); self.recipients.setPlaceholderText("nombre@empresa.es; otro@empresa.es")
        self.subject = QLineEdit(); self.body_editor = QPlainTextEdit(); self.body_editor.setObjectName("MailBody"); self.body_editor.setMinimumHeight(88)
        self.save_mail_button = QPushButton("Guardar plantilla"); self.save_mail_button.clicked.connect(self.save_mail_template)
        self.email_button = QPushButton("Enviar correo"); self.email_button.clicked.connect(self.send_email)
        mail_grid.addWidget(labeled_field("Destinatarios", self.recipients), 0, 0); mail_grid.addWidget(labeled_field("Asunto", self.subject), 0, 1); mail_grid.addWidget(self.save_mail_button, 0, 2, Qt.AlignBottom)
        mail.addLayout(mail_grid); mail.addWidget(labeled_field("Mensaje", self.body_editor))
        vars_hint = QLabel("Variables: {primero_codigo}, {cantidad}, {ultimo_codigo}, {siguiente_codigo}."); vars_hint.setObjectName("MutedText")
        mail.addWidget(vars_hint); mail.addWidget(self.email_button, 0, Qt.AlignRight)
        self.mail_section = collapsible_section("Aviso por correo (opcional)", mail_panel)
        root_layout.addWidget(self.mail_section)

        self.status = QLabel(); self.status.setObjectName("StatusLabel"); self.status.setAlignment(Qt.AlignCenter); self.status.setWordWrap(True); self.status.setProperty("liveRegion", "polite")
        root_layout.addWidget(self.status)
        scroll.setWidget(root); self.setCentralWidget(scroll)
        for control in (self.label_width, self.label_height, self.zone_x, self.zone_y, self.zone_width, self.zone_height, self.font_size): control.valueChanged.connect(self._on_layout_changed)
        self.font_family.currentFontChanged.connect(self._on_layout_changed); self.alignment.currentIndexChanged.connect(self._on_layout_changed); self.bold.toggled.connect(self._on_layout_changed)
        self._apply_model_to_controls(); self._reload_design_selector(); self._load_mail_template()

    @staticmethod
    def _mm_spin(minimum: float, maximum: float, value: float) -> NoWheelDoubleSpinBox:
        spin = NoWheelDoubleSpinBox(); spin.setRange(minimum, maximum); spin.setDecimals(1); spin.setSingleStep(0.5); spin.setSuffix(" mm"); spin.setValue(value); return spin

    def _initial_first_code(self) -> str:
        if self.pending_job: return self.pending_job[0]
        try: return increment_code(self.last_code) if self.last_code else "0001"
        except SequenceFormatError: return "0001"

    def _load_state(self) -> None:
        app = settings(); default = LabelLayout(); raw = app.value(f"{self.SETTINGS_PREFIX}/layout", "")
        try: values = json.loads(str(raw)) if raw else {}
        except (TypeError, ValueError, json.JSONDecodeError): values = {}
        merged = {**asdict(default), **{key: value for key, value in values.items() if key in asdict(default)}}
        self.layout_model = LabelLayout(**merged).normalized()
        self.last_code = str(app.value(f"{self.SETTINGS_PREFIX}/state/last_code", "") or "")
        self.last_first_code = str(app.value(f"{self.SETTINGS_PREFIX}/state/last_first", "") or "")
        try: self.last_quantity = int(app.value(f"{self.SETTINGS_PREFIX}/state/last_quantity", 0) or 0)
        except (TypeError, ValueError): self.last_quantity = 0
        first = str(app.value(f"{self.SETTINGS_PREFIX}/pending/first", "") or "")
        try:
            quantity, last = int(app.value(f"{self.SETTINGS_PREFIX}/pending/quantity", 0) or 0), str(app.value(f"{self.SETTINGS_PREFIX}/pending/last", "") or "")
            self.pending_job = (first, quantity, last) if first and quantity > 0 and last else None
        except (TypeError, ValueError): self.pending_job = None

    def _apply_model_to_controls(self) -> None:
        self._updating_controls = True; item = self.layout_model
        self.label_width.setValue(item.width_mm); self.label_height.setValue(item.height_mm); self.zone_x.setValue(item.x_mm); self.zone_y.setValue(item.y_mm); self.zone_width.setValue(item.zone_width_mm); self.zone_height.setValue(item.zone_height_mm)
        self.font_family.setCurrentFont(QFont(item.font_family)); self.font_size.setValue(item.font_size_pt); self.alignment.setCurrentIndex(max(0, self.alignment.findData(item.alignment))); self.bold.setChecked(item.bold)
        self._updating_controls = False; self.canvas.set_layout_model(item)

    def _on_layout_changed(self, *_args) -> None:
        if self._updating_controls: return
        self.layout_model = LabelLayout(width_mm=self.label_width.value(), height_mm=self.label_height.value(), x_mm=self.zone_x.value(), y_mm=self.zone_y.value(), zone_width_mm=self.zone_width.value(), zone_height_mm=self.zone_height.value(), font_family=self.font_family.currentFont().family(), font_size_pt=self.font_size.value(), alignment=str(self.alignment.currentData() or "center"), bold=self.bold.isChecked()).normalized()
        self._apply_model_to_controls(); self._persist_layout(); self._refresh()

    def move_zone(self, x: float, y: float) -> None:
        self.layout_model = LabelLayout(**{**asdict(self.layout_model), "x_mm": x, "y_mm": y}).normalized(); self._apply_model_to_controls(); self._persist_layout(); self._refresh()

    def center_zone(self) -> None:
        item = self.layout_model; self.move_zone((item.width_mm - item.zone_width_mm) / 2, (item.height_mm - item.zone_height_mm) / 2)

    def _designs(self) -> dict[str, dict]:
        raw = settings().value(f"{self.SETTINGS_PREFIX}/designs", "")
        try: value = json.loads(str(raw)) if raw else {}
        except (TypeError, ValueError, json.JSONDecodeError): value = {}
        return value if isinstance(value, dict) else {}

    def _save_designs(self, designs: dict[str, dict]) -> None:
        app = settings(); app.setValue(f"{self.SETTINGS_PREFIX}/designs", json.dumps(designs, ensure_ascii=False, separators=(",", ":"))); app.sync()

    def _reload_design_selector(self, selected: str = "") -> None:
        names = sorted(self._designs(), key=str.casefold); current = selected or self.design_selector.currentData() or ""
        self.design_selector.blockSignals(True); self.design_selector.clear(); self.design_selector.addItem("Selecciona un diseño guardado", "")
        for name in names: self.design_selector.addItem(name, name)
        self.design_selector.setCurrentIndex(max(0, self.design_selector.findData(current))); self.design_selector.blockSignals(False); self._on_design_selected()

    def _on_design_selected(self, *_args) -> None:
        selected = bool(self.design_selector.currentData()); self.load_design_button.setEnabled(selected); self.delete_design_button.setEnabled(selected); self.export_design_button.setEnabled(selected)

    def save_design(self) -> None:
        current = str(self.design_selector.currentData() or "")
        name, accepted = QInputDialog.getText(self, "Guardar diseño de etiqueta", "Nombre del diseño:", text=current)
        name = " ".join(name.split())
        if not accepted or not name: return
        designs = self._designs(); designs[name] = asdict(self.layout_model); self._save_designs(designs); self._reload_design_selector(name)
        self.status.setText(f"Diseño «{name}» guardado."); show_inline_message(self, "success", f"Diseño «{name}» guardado para reutilizarlo cuando quieras.")

    def load_selected_design(self) -> None:
        name = str(self.design_selector.currentData() or ""); values = self._designs().get(name)
        if not name or not isinstance(values, dict): return
        try: self.layout_model = LabelLayout(**{**asdict(LabelLayout()), **values}).normalized()
        except (TypeError, ValueError):
            self.status.setText("El diseño guardado no es válido."); return
        self._apply_model_to_controls(); self._persist_layout(); self.status.setText(f"Diseño «{name}» cargado."); self._refresh()

    def delete_design(self) -> None:
        name = str(self.design_selector.currentData() or "")
        if not name or QMessageBox.question(self, "Eliminar diseño", f"¿Eliminar el diseño «{name}»?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        designs = self._designs(); designs.pop(name, None); self._save_designs(designs); self._reload_design_selector(); self.status.setText(f"Diseño «{name}» eliminado.")

    def export_selected_design(self) -> None:
        name = str(self.design_selector.currentData() or "")
        layout = self._designs().get(name)
        if not name or not isinstance(layout, dict):
            self.status.setText("Selecciona un diseño guardado para exportarlo.")
            return
        path = save_file(
            self,
            "numerador_etiquetas/design_export",
            "Exportar diseño de etiqueta",
            "diseno_etiqueta.json",
            "Diseño de etiqueta (*.json)",
        )
        if path is None:
            return
        if not path.suffix:
            path = path.with_suffix(".json")
        payload = {
            "format": self.DESIGN_FILE_FORMAT,
            "version": self.DESIGN_FILE_VERSION,
            "name": name,
            "layout": layout,
        }
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.status.setText(f"No se pudo exportar el diseño: {exc}")
            show_inline_message(self, "error", str(exc))
            return
        self.status.setText(f"Diseño «{name}» exportado: {path.name}")
        show_inline_message(self, "success", f"Diseño exportado. Puedes compartir el archivo {path.name} con otro equipo.")

    def import_design(self) -> None:
        path = open_file(
            self,
            "numerador_etiquetas/design_import",
            "Importar diseño de etiqueta",
            "Diseño de etiqueta (*.json)",
        )
        if path is None:
            return
        try:
            if path.stat().st_size > 1_000_000:
                raise ValueError("El archivo de diseño es demasiado grande.")
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            name, layout = self._decode_design_file(payload)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.status.setText(f"No se pudo importar el diseño: {exc}")
            show_inline_message(self, "error", "El archivo no contiene un diseño de etiqueta válido.")
            return
        requested_name, accepted = QInputDialog.getText(self, "Importar diseño de etiqueta", "Nombre del diseño:", text=name)
        requested_name = " ".join(requested_name.split())
        if not accepted or not requested_name:
            return
        designs = self._designs()
        if requested_name in designs and QMessageBox.question(
            self,
            "Reemplazar diseño",
            f"Ya existe un diseño llamado «{requested_name}». ¿Quieres reemplazarlo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        designs[requested_name] = asdict(layout)
        self._save_designs(designs)
        self._reload_design_selector(requested_name)
        self.layout_model = layout
        self._apply_model_to_controls()
        self._persist_layout()
        self.status.setText(f"Diseño «{requested_name}» importado y cargado.")
        show_inline_message(self, "success", "Diseño importado correctamente. La etiqueta usa ahora la misma configuración del otro equipo.")
        self._refresh()

    def _decode_design_file(self, payload: object) -> tuple[str, LabelLayout]:
        if not isinstance(payload, dict) or payload.get("format") != self.DESIGN_FILE_FORMAT:
            raise ValueError("Formato de archivo no reconocido.")
        if payload.get("version") != self.DESIGN_FILE_VERSION:
            raise ValueError("La versión del diseño no es compatible.")
        name = " ".join(str(payload.get("name") or "").split())
        layout_data = payload.get("layout")
        if not name or not isinstance(layout_data, dict):
            raise ValueError("Falta el nombre o la configuración del diseño.")
        defaults = asdict(LabelLayout())
        values = {**defaults, **{key: value for key, value in layout_data.items() if key in defaults}}
        try:
            return name, LabelLayout(**values).normalized()
        except (TypeError, ValueError) as exc:
            raise ValueError("Las medidas o el formato del diseño no son válidos.") from exc

    def _sequence(self) -> tuple[str, ...]: return sequence_values(self.first_code.text(), self.quantity.value())

    def print_labels(self) -> None:
        if self.pending_job: return
        try: values = self._sequence()
        except (SequenceFormatError, ValueError) as exc: self.status.setText(str(exc)); show_inline_message(self, "warning", str(exc)); self._refresh(); return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution); self._configure_printer(printer, self.layout_model)
        dialog = QPrintDialog(printer, self); dialog.setWindowTitle("Imprimir etiquetas")
        for option in (QAbstractPrintDialog.PrintDialogOption.PrintPageRange, QAbstractPrintDialog.PrintDialogOption.PrintSelection, QAbstractPrintDialog.PrintDialogOption.PrintToFile): dialog.setOption(option, False)
        if dialog.exec() != QDialog.Accepted: self.status.setText("Impresión cancelada antes de enviar el trabajo."); return
        if printer.copyCount() != 1 or printer.printRange() != QPrinter.PrintRange.AllPages:
            self.status.setText("Para proteger la secuencia, imprime una única copia de todas las etiquetas."); show_inline_message(self, "warning", "La cantidad se controla desde esta aplicación; no uses copias ni rangos."); return
        self._configure_printer(printer, self.layout_model)
        try: self._render_print_job(printer, values)
        except Exception as exc: self.status.setText(f"No se pudo enviar el trabajo: {exc}"); show_inline_message(self, "error", str(exc)); return
        self.pending_job = (values[0], len(values), values[-1]); self._persist_pending(); self.status.setText("Trabajo enviado. Confirma solo después de comprobar físicamente las etiquetas."); show_inline_message(self, "warning", "Impresión pendiente de confirmación física; el último código no se ha actualizado."); self._refresh()

    @staticmethod
    def _configure_printer(printer: QPrinter, layout: LabelLayout) -> None:
        printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat); printer.setFullPage(True)
        printer.setPageSize(QPageSize(QSizeF(layout.width_mm, layout.height_mm), QPageSize.Unit.Millimeter, "Etiqueta configurada"))
        printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)

    def _render_print_job(self, printer: QPrinter, values: tuple[str, ...]) -> None:
        painter = QPainter()
        if not painter.begin(printer): raise RuntimeError("El controlador no aceptó el trabajo de impresión.")
        try:
            for index, value in enumerate(values):
                if index and not printer.newPage(): raise RuntimeError("No se pudo crear la siguiente etiqueta.")
                self._draw_label(painter, printer, value)
        finally: painter.end()

    def _draw_label(self, painter: QPainter, printer: QPrinter, value: str) -> None:
        item = self.layout_model; page = QRectF(printer.pageRect(QPrinter.Unit.DevicePixel)); painter.save(); painter.translate(page.x(), page.y()); painter.scale(page.width() / item.width_mm, page.height() / item.height_mm)
        font = QFont(item.font_family); font.setBold(item.bold); font.setPixelSize(max(1, round(item.font_size_pt * 25.4 / 72))); painter.setFont(font); painter.setPen(QColor(Qt.GlobalColor.black))
        alignment = {"left": Qt.AlignLeft, "right": Qt.AlignRight}.get(item.alignment, Qt.AlignHCenter)
        painter.drawText(QRectF(item.x_mm, item.y_mm, item.zone_width_mm, item.zone_height_mm), alignment | Qt.AlignVCenter, value); painter.restore()

    def confirm_print(self) -> None:
        if not self.pending_job: return
        self.last_first_code, self.last_quantity, self.last_code = self.pending_job; self.pending_job = None
        app = settings(); app.setValue(f"{self.SETTINGS_PREFIX}/state/last_code", self.last_code); app.setValue(f"{self.SETTINGS_PREFIX}/state/last_first", self.last_first_code); app.setValue(f"{self.SETTINGS_PREFIX}/state/last_quantity", self.last_quantity); self._clear_pending()
        self.first_code.setText(increment_code(self.last_code)); self.status.setText(f"Impresión confirmada. Último código registrado: {self.last_code}."); show_inline_message(self, "success", f"Impresión confirmada. Siguiente código: {self.first_code.text()}."); self._refresh()

    def discard_pending(self) -> None:
        if not self.pending_job: return
        answer = QMessageBox.warning(self, "Descartar impresión pendiente", "El último código no se actualizará. Úsalo solo si no debe registrarse la impresión.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes: return
        self.pending_job = None; self._clear_pending(); self.status.setText("Impresión pendiente descartada; no se ha modificado el último código."); self._refresh()

    def send_email(self) -> None:
        if not self.last_code: self.status.setText("Confirma una impresión antes de enviar el aviso."); return
        recipients = parse_recipients(self.recipients.text())
        if not recipients or invalid_recipients(recipients): self.status.setText("Revisa los destinatarios del correo."); show_inline_message(self, "warning", "Introduce al menos un destinatario válido."); return
        values = {"primero_codigo": self.last_first_code, "cantidad": str(self.last_quantity), "ultimo_codigo": self.last_code, "siguiente_codigo": increment_code(self.last_code)}
        recipients_text = self.recipients.text()
        subject = render_mail_template(self.subject.text().strip() or DEFAULT_SUBJECT, values)
        body = render_mail_template(self.body_editor.toPlainText().strip() or DEFAULT_BODY, values)
        self.status.setText("Enviando correo en segundo plano…")
        def completed(_value: object) -> None:
            self.status.setText("Correo enviado correctamente.")
            show_inline_message(self, "success", "Correo enviado correctamente.")
        def failed(message: str) -> None:
            self.status.setText(f"No se pudo enviar el correo: {message}")
            show_inline_message(self, "error", message)
        if not run_background(
            self,
            lambda: send_label_status_email(recipients_text, subject=subject, body=body),
            completed,
            failed,
        ):
            show_inline_message(self, "warning", "Ya hay una operación en curso.")

    def save_mail_template(self) -> None:
        app = settings(); app.setValue(f"{self.SETTINGS_PREFIX}/mail/recipients", self.recipients.text().strip()); app.setValue(f"{self.SETTINGS_PREFIX}/mail/subject", self.subject.text().strip() or DEFAULT_SUBJECT); app.setValue(f"{self.SETTINGS_PREFIX}/mail/body", self.body_editor.toPlainText().strip() or DEFAULT_BODY); app.sync(); self.status.setText("Plantilla de correo guardada.")

    def _load_mail_template(self) -> None:
        app = settings(); self.recipients.setText(str(app.value(f"{self.SETTINGS_PREFIX}/mail/recipients", "") or "")); self.subject.setText(str(app.value(f"{self.SETTINGS_PREFIX}/mail/subject", DEFAULT_SUBJECT) or DEFAULT_SUBJECT)); self.body_editor.setPlainText(str(app.value(f"{self.SETTINGS_PREFIX}/mail/body", DEFAULT_BODY) or DEFAULT_BODY))

    def _persist_layout(self) -> None:
        app = settings(); app.setValue(f"{self.SETTINGS_PREFIX}/layout", json.dumps(asdict(self.layout_model), ensure_ascii=False, separators=(",", ":"))); app.sync()

    def _persist_pending(self) -> None:
        if not self.pending_job: return
        first, quantity, last = self.pending_job; app = settings(); app.setValue(f"{self.SETTINGS_PREFIX}/pending/first", first); app.setValue(f"{self.SETTINGS_PREFIX}/pending/quantity", quantity); app.setValue(f"{self.SETTINGS_PREFIX}/pending/last", last); app.sync()

    def _clear_pending(self) -> None:
        app = settings()
        for key in ("first", "quantity", "last"): app.remove(f"{self.SETTINGS_PREFIX}/pending/{key}")
        app.sync()

    def _refresh(self, *_args) -> None:
        try: values, error = self._sequence(), ""
        except (SequenceFormatError, ValueError) as exc: values, error = (), str(exc)
        first, last = (values[0], values[-1]) if values else ("—", "—")
        for card, value in ((self.first_metric, first), (self.last_metric, last), (self.next_metric, increment_code(self.last_code) if self.last_code else "—")):
            label = card.property("valueLabel")
            if isinstance(label, QLabel): label.setText(value)
        self.canvas.set_text(first if values else self.first_code.text().strip() or "?"); self.canvas.set_layout_model(self.layout_model)
        self.last_confirmed_label.setText(f"Último confirmado en este equipo: {self.last_code}. Siguiente sugerido: {increment_code(self.last_code)}." if self.last_code else "Aún no hay una impresión confirmada en este equipo.")
        pending = self.pending_job is not None; self.print_button.setEnabled(bool(values) and not pending); self.confirm_button.setEnabled(pending); self.discard_pending_button.setEnabled(pending); self.email_button.setEnabled(bool(self.last_code))
        if error: self.status.setText(error)
        elif pending: self.status.setText("Hay una impresión pendiente de confirmación física.")
        elif not self.status.text() or self.status.text().startswith("Hay una impresión"): self.status.setText("Define el código y la cantidad; el diseño activo se conserva en este equipo.")
        next_text = "Confirmar impresión" if pending else "Corregir código inicial" if error else "Enviar a impresora"
        sync_recommended_action(self, next_text, {"Enviar a impresora": self.print_button, "Confirmar impresión": self.confirm_button}, (self.print_button, self.confirm_button, self.discard_pending_button, self.email_button))

    def flow_state(self) -> tuple[int, bool, bool]:
        if self.pending_job: return 3, False, False
        if self.last_code: return 4, False, True
        return 1, False, False

    def _recommended_action(self) -> str:
        return "Confirmar impresión" if self.pending_job else "Enviar a impresora"
