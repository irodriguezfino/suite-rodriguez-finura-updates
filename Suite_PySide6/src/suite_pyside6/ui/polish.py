from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.responsive import make_flow, make_widgets_resizable
from suite_pyside6.ui.theme import base_qss, current_theme_mode, is_dark_mode, set_theme_mode


_BRAND_PIXMAP_CACHE: dict[str, QPixmap] = {}


def polish_window(
    widget: QWidget,
    *,
    brand_bar: bool = False,
    context_panel: bool = True,
    stepper: bool = True,
) -> None:
    """Apply small visual affordances shared by the suite windows."""
    widget.setProperty("theme", current_theme_mode())
    if brand_bar or _should_inject_default_brand_bar(widget):
        _inject_app_brand_bar(widget)
    if stepper:
        _replace_step_bars(widget)
    if context_panel:
        _inject_context_panel(widget)
    _inject_inline_banner(widget)
    _ensure_theme_toggle(widget)
    _wrap_toolbars_for_overflow(widget)
    _wrap_operational_body(widget)
    _enable_drag_drop(widget)
    _install_close_guard(widget)

    for button in widget.findChildren(QPushButton):
        original_text = _clean_text(button.text())
        text = original_text.lower()
        button.setCursor(Qt.PointingHandCursor)
        button.setIcon(QIcon())
        _set_button_role(button, text)
        _set_shortcut(button, text)
        if not button.accessibleName():
            button.setAccessibleName(original_text)
        if not button.toolTip():
            button.setToolTip(original_text)
        _append_shortcut_tooltip(button)
        _compact_toolbar_button(button, original_text)
        _patch_button_enabled(button, widget)
        _refresh_style(button)

    title = widget.windowTitle() or "Suite Rodriguez Finura"
    for index, field in enumerate(widget.findChildren(QLineEdit), start=1):
        if not field.accessibleName():
            name = field.placeholderText() or f"Campo de texto {index} de {title}"
            field.setAccessibleName(name)

    for index, combo in enumerate(widget.findChildren(QComboBox), start=1):
        if not combo.accessibleName():
            combo.setAccessibleName(f"Selector {index} de {title}")

    for index, table in enumerate(widget.findChildren(QTableWidget), start=1):
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        if not table.accessibleName():
            table.setAccessibleName(f"Tabla {index} de {title}")

    for index, editor in enumerate(widget.findChildren(QPlainTextEdit), start=1):
        editor.setTabChangesFocus(True)
        if not editor.accessibleName():
            editor.setAccessibleName(f"Area de resultados {index} de {title}")
        _patch_editor_empty_state(editor)

    for label_name in ("WindowSubtitle", "ResultLabel", "StatusLabel", "InlineBanner"):
        for label in widget.findChildren(QLabel, label_name):
            label.setWordWrap(True)

    _apply_tab_order(widget)
    _patch_context_labels(widget)
    _update_context_panel(widget)
    _update_flow_indicator(widget)


def prepare_embedded_window(widget: QMainWindow) -> None:
    """Adapt an operational window so it reads as an in-shell page."""
    widget.setProperty("embeddedPage", True)
    widget.setMinimumSize(0, 0)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    central = widget.centralWidget()
    if central is not None:
        central.setMinimumSize(0, 0)
        central.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = central.layout()
        if layout is not None:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(max(6, min(layout.spacing(), 8)))

    for bar in widget.findChildren(QFrame, "AppBrandBar"):
        bar.setVisible(False)
        bar.setMaximumHeight(0)
    for label_name in ("WindowTitle", "WindowSubtitle"):
        for label in widget.findChildren(QLabel, label_name):
            label.setVisible(False)
            label.setMaximumHeight(0)
    for panel in widget.findChildren(QFrame, "ContextPanel"):
        panel.setVisible(False)
        panel.setMaximumHeight(0)
    for scroll in widget.findChildren(QScrollArea, "WindowScroll"):
        scroll.setMinimumSize(0, 0)
        content = scroll.widget()
        if content is not None:
            content.setMinimumSize(0, 0)
    _refresh_style(widget)


def operational_snapshot(widget: QWidget) -> dict[str, str]:
    """Return the compact operational state used by the shell header."""
    _update_context_panel(widget)
    status = widget.findChild(QLabel, "StatusLabel")
    summary = widget.findChild(QLabel, "ResultLabel")
    state_text = status.text() if status is not None and status.text() else "Pendiente"
    summary_text = summary.text() if summary is not None else ""
    next_button = _next_action_button(widget)
    combined = " ".join(part for part in (state_text, summary_text) if part)
    return {
        "state": _compact_text(_state_summary(state_text, summary_text), 72),
        "next": _compact_text(_clean_text(next_button.text()) if next_button is not None else "Completa el paso actual", 72),
        "alerts": _alert_text(combined),
    }


def trigger_next_action(widget: QWidget) -> bool:
    button = _next_action_button(widget)
    if button is None or not button.isEnabled():
        return False
    button.click()
    _update_context_panel(widget)
    return True


def show_inline_message(widget: QWidget, severity: str, text: str) -> None:
    banner = widget.findChild(QLabel, "InlineBanner")
    if banner is None:
        return
    banner.setProperty("severity", severity)
    banner.setText(text)
    banner.setVisible(True)
    _refresh_style(banner)
    status = widget.findChild(QLabel, "StatusLabel")
    if status is not None:
        widget.setProperty("inlineUpdating", True)
        status.setText(text)
        widget.setProperty("inlineUpdating", False)


def clear_inline_message(widget: QWidget) -> None:
    banner = widget.findChild(QLabel, "InlineBanner")
    if banner is not None:
        banner.clear()
        banner.setVisible(False)


def collapsible_section(title: str, content: QWidget, *, expanded: bool = False) -> QFrame:
    section = QFrame()
    section.setObjectName("CollapsiblePanel")
    section_layout = QVBoxLayout(section)
    section_layout.setContentsMargins(0, 0, 0, 0)
    section_layout.setSpacing(0)
    header = QToolButton()
    header.setObjectName("CollapsibleHeader")
    header.setText(title)
    header.setCheckable(True)
    header.setChecked(expanded)
    header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
    header.setAccessibleName(title)
    content.setVisible(expanded)

    def toggle(checked: bool, *, _header=header, _content=content) -> None:
        _header.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        _content.setVisible(checked)

    header.toggled.connect(toggle)
    section_layout.addWidget(header)
    section_layout.addWidget(content)
    return section


def _inject_app_brand_bar(widget: QWidget) -> None:
    if not isinstance(widget, QMainWindow):
        return
    central = widget.centralWidget()
    if central is None or central.findChild(QFrame, "Header") is not None:
        return
    if central.findChild(QFrame, "AppBrandBar") is not None:
        return
    layout = central.layout()
    if layout is None:
        return

    bar = QFrame()
    bar.setObjectName("AppBrandBar")
    bar.setMinimumHeight(48)
    bar.setMaximumHeight(56)
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(12, 6, 12, 6)
    bar_layout.setSpacing(10)

    for logo_name, size in (("RODRIGUEZ.png", QSize(116, 30)), ("FINURA.png", QSize(72, 28))):
        logo_path = resource_path(logo_name)
        if logo_path.exists():
            logo = QLabel()
            logo.setAccessibleName(logo_name.replace(".png", ""))
            logo.setObjectName("BrandLogo")
            pixmap = brand_logo_pixmap(logo_path)
            if not pixmap.isNull():
                logo.setPixmap(pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                logo.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                logo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                bar_layout.addWidget(logo)

    caption = QLabel("Suite Rodriguez Finura")
    caption.setObjectName("BrandCaption")
    bar_layout.addWidget(caption)
    bar_layout.addStretch(1)
    bar_layout.addWidget(_theme_toggle_button(), 0, Qt.AlignVCenter)
    layout.insertWidget(0, bar)


def _should_inject_default_brand_bar(widget: QWidget) -> bool:
    if not isinstance(widget, QMainWindow):
        return False
    central = widget.centralWidget()
    return central is not None and central.findChild(QFrame, "Header") is None


def brand_logo_pixmap(path: Path) -> QPixmap:
    key = str(path.resolve())
    cached = _BRAND_PIXMAP_CACHE.get(key)
    if cached is not None:
        return QPixmap(cached)
    pixmap = _transparent_edge_black(QPixmap(str(path)))
    _BRAND_PIXMAP_CACHE[key] = QPixmap(pixmap)
    return pixmap


def _transparent_edge_black(pixmap: QPixmap) -> QPixmap:
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return pixmap

    visited: set[tuple[int, int]] = set()
    pending: list[tuple[int, int]] = []
    for x in range(width):
        pending.append((x, 0))
        pending.append((x, height - 1))
    for y in range(height):
        pending.append((0, y))
        pending.append((width - 1, y))

    while pending:
        x, y = pending.pop()
        if (x, y) in visited or x < 0 or y < 0 or x >= width or y >= height:
            continue
        visited.add((x, y))
        color = QColor(image.pixel(x, y))
        if color.red() > 18 or color.green() > 18 or color.blue() > 18:
            continue
        color.setAlpha(0)
        image.setPixelColor(x, y, color)
        pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    return QPixmap.fromImage(image)


def _ensure_theme_toggle(widget: QWidget) -> None:
    if widget.findChild(QPushButton, "ThemeToggle") is not None:
        return
    header = widget.findChild(QFrame, "Header")
    if header is None or header.layout() is None:
        return
    header.layout().addWidget(_theme_toggle_button())


def _wrap_toolbars_for_overflow(widget: QWidget) -> None:
    if not isinstance(widget, QMainWindow):
        return
    for toolbar in widget.findChildren(QFrame, "Toolbar"):
        if toolbar.property("flowWrapped"):
            continue
        parent = toolbar.parentWidget()
        parent_layout = parent.layout() if parent is not None else None
        if parent_layout is None:
            continue
        index = parent_layout.indexOf(toolbar)
        if index < 0:
            continue
        original_layout = toolbar.layout()
        if original_layout is None:
            continue

        flow_toolbar = QFrame(parent)
        flow_toolbar.setObjectName("Toolbar")
        flow_toolbar.setProperty("flowWrapped", True)
        flow_toolbar.setProperty("lockFlowMinimumHeight", True)
        if toolbar.property("preserveButtonText"):
            flow_toolbar.setProperty("preserveButtonText", True)
        flow_toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        flow_layout = make_flow(flow_toolbar, margin=0, spacing=7)
        flow_layout.setContentsMargins(4, 4, 4, 4)

        while original_layout.count():
            item = original_layout.takeAt(0)
            child = item.widget()
            if child is None:
                continue
            child.setParent(flow_toolbar)
            flow_layout.addWidget(child)

        parent_layout.replaceWidget(toolbar, flow_toolbar)
        toolbar.setParent(None)
        toolbar.deleteLater()


def _wrap_operational_body(widget: QWidget) -> None:
    if not isinstance(widget, QMainWindow) or widget.property("bodyScrollWrapped"):
        return
    central = widget.centralWidget()
    if central is None or central.findChild(QFrame, "Header") is not None:
        return
    layout = central.layout()
    if layout is None or layout.count() < 2:
        return
    status = central.findChild(QLabel, "StatusLabel")
    if status is None:
        return

    content = QWidget()
    content.setObjectName("WindowScrollContent")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(layout.spacing())

    status_item = None
    while layout.count():
        item = layout.takeAt(0)
        child = item.widget()
        child_layout = item.layout()
        if child is status:
            status_item = item
            continue
        if child is not None:
            child.setParent(content)
            content_layout.addWidget(child)
        elif child_layout is not None:
            content_layout.addLayout(child_layout)
        else:
            content_layout.addItem(item)

    scroll = QScrollArea()
    scroll.setObjectName("WindowScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    if status_item is not None:
        layout.addItem(status_item)
    else:
        layout.addWidget(status)
    widget.setProperty("bodyScrollWrapped", True)


def _inject_context_panel(widget: QWidget) -> None:
    if not isinstance(widget, QMainWindow):
        return
    central = widget.centralWidget()
    if central is None or central.findChild(QFrame, "Header") is not None:
        return
    if central.findChild(QFrame, "ContextPanel") is not None:
        return
    layout = central.layout()
    if layout is None:
        return
    toolbar = central.findChild(QFrame, "Toolbar")
    if toolbar is None:
        return

    panel = QFrame()
    panel.setObjectName("ContextPanel")
    panel.setProperty("lockFlowMinimumHeight", True)
    panel.setMinimumHeight(48)
    panel_layout = make_flow(panel, margin=0, spacing=8)
    panel_layout.setContentsMargins(10, 8, 10, 8)

    for key, title in (("State", "Estado"), ("Next", "Siguiente accion"), ("Alerts", "Avisos")):
        card = QFrame()
        card.setObjectName("ContextItem")
        card.setMinimumWidth(210)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(8, 5, 8, 5)
        card_layout.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("ContextLabel")
        value = QLabel("Pendiente")
        value.setObjectName(f"Context{key}Value")
        value.setWordWrap(True)
        card_layout.addWidget(label)
        card_layout.addWidget(value, 1)
        panel_layout.addWidget(card)

    index = layout.indexOf(toolbar)
    layout.insertWidget(index + 1, panel)


def _inject_inline_banner(widget: QWidget) -> None:
    if not isinstance(widget, QMainWindow):
        return
    central = widget.centralWidget()
    if central is None or central.findChild(QLabel, "InlineBanner") is not None:
        return
    layout = central.layout()
    if layout is None:
        return
    anchor = central.findChild(QFrame, "ContextPanel") or central.findChild(QFrame, "Toolbar")
    if anchor is None:
        return
    banner = QLabel("")
    banner.setObjectName("InlineBanner")
    banner.setProperty("severity", "info")
    banner.setWordWrap(True)
    banner.setVisible(False)
    layout.insertWidget(layout.indexOf(anchor) + 1, banner)


def _patch_context_labels(widget: QWidget) -> None:
    for label_name in ("ResultLabel", "StatusLabel"):
        label = widget.findChild(QLabel, label_name)
        if label is None or label.property("contextPatched"):
            continue
        original = label.setText

        def set_text(text: str, *, _original=original, _widget=widget) -> None:
            _original(text)
            if not _widget.property("inlineUpdating"):
                clear_inline_message(_widget)
            _update_context_panel(_widget)
            _update_flow_indicator(_widget)

        label.setText = set_text  # type: ignore[method-assign]
        label.setProperty("contextPatched", True)


def _patch_button_enabled(button: QPushButton, widget: QWidget) -> None:
    if button.property("enabledPatched"):
        return
    original = button.setEnabled

    def set_enabled(enabled: bool, *, _original=original, _button=button, _widget=widget) -> None:
        _original(enabled)
        _update_disabled_tooltip(_button, enabled)
        _update_context_panel(_widget)
        _update_flow_indicator(_widget)

    button.setEnabled = set_enabled  # type: ignore[method-assign]
    button.setProperty("enabledPatched", True)
    _update_disabled_tooltip(button, button.isEnabled())


def _patch_editor_empty_state(editor: QPlainTextEdit) -> None:
    if editor.property("emptyStatePatched"):
        _update_editor_empty_state(editor, editor.toPlainText())
        return
    if editor.objectName() == "MailBody":
        return
    original = editor.setPlainText

    def set_plain_text(text: str, *, _original=original, _editor=editor) -> None:
        _original(text)
        _update_editor_empty_state(_editor, text)

    editor.setPlainText = set_plain_text  # type: ignore[method-assign]
    editor.setProperty("emptyStatePatched", True)
    if not editor.placeholderText():
        editor.setPlaceholderText("Arrastra archivos aqui o usa la accion principal para empezar.")
    editor.setProperty("baseLineWrapMode", int(editor.lineWrapMode().value))
    _update_editor_empty_state(editor, editor.toPlainText())


def _update_editor_empty_state(editor: QPlainTextEdit, text: str) -> None:
    normalized = " ".join(text.strip().lower().split())
    empty_markers = (
        "",
        "arrastra ",
        "selecciona ",
        "carga ",
        "aqui se mostraran",
        "aqui se mostrar",
        "la revision ",
        "la salida ",
        "sin incidencias",
        "pulsa ",
        "archivos seleccionados:",
    )
    is_empty = not normalized or any(normalized.startswith(marker) for marker in empty_markers if marker)
    editor.setProperty("emptyState", is_empty)
    if is_empty:
        editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
    else:
        base_mode = editor.property("baseLineWrapMode")
        if isinstance(base_mode, int):
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode(base_mode))
    _refresh_style(editor)


def _update_disabled_tooltip(button: QPushButton, enabled: bool) -> None:
    if not button.property("baseTooltip"):
        button.setProperty("baseTooltip", button.toolTip() or button.text())
    base = str(button.property("baseTooltip") or button.text())
    if enabled:
        button.setToolTip(base)
        button.setAccessibleDescription(base)
        return
    text = button.text().lower()
    if any(word in text for word in ("procesar", "comprobar", "cruzar")):
        reason = "Carga primero los archivos requeridos."
    elif "revalidar" in text:
        reason = "Disponible cuando haya incidencias o cambios pendientes."
    elif any(word in text for word in ("guardar", "pdf", "correo", "enviar")):
        reason = "Procesa datos validos antes de usar esta accion."
    elif "limpiar" in text:
        reason = "Disponible cuando haya archivos o resultados en pantalla."
    else:
        reason = "Completa el paso anterior para activar esta accion."
    button.setToolTip(f"{base}\nNo disponible ahora: {reason}")
    button.setAccessibleDescription(f"No disponible ahora: {reason}")


def _compact_toolbar_button(button: QPushButton, original_text: str) -> None:
    if not _is_toolbar_button(button) or _preserve_button_text(button):
        return
    compact = _compact_button_text(original_text)
    if compact == original_text:
        return
    button.setProperty("fullText", original_text)
    button.setText(compact)
    if not button.toolTip() or button.toolTip() == original_text:
        button.setToolTip(original_text)
    if not button.accessibleName() or button.accessibleName() == compact:
        button.setAccessibleName(original_text)


def _is_toolbar_button(button: QPushButton) -> bool:
    parent = button.parentWidget()
    while parent is not None:
        if parent.objectName() in {"Toolbar", "MailPanel"}:
            return True
        parent = parent.parentWidget()
    return False


def _preserve_button_text(button: QPushButton) -> bool:
    parent = button.parentWidget()
    while parent is not None:
        if parent.property("preserveButtonText"):
            return True
        parent = parent.parentWidget()
    return False


def _compact_button_text(text: str) -> str:
    mapping = {
        "Seleccionar archivos": "Archivos",
        "Seleccionar TXT": "TXT",
        "Seleccionar Excel": "Excel",
        "Cargar CSVs finales": "CSV finales",
        "Cargar origen": "Origen",
        "Cargar TXT/CSV": "TXT/CSV",
        "Cargar Excel oficial": "Excel oficial",
        "Cargar TXT recepcion": "TXT recepcion",
        "Cargar TXT recepción": "TXT recepción",
        "Cargar TXT FAC": "TXT FAC",
        "Cargar SealsReport": "SealsReport",
        "Configurar rangos": "Rangos",
        "Procesar Excel": "Procesar",
        "Procesar archivos": "Procesar",
        "Procesar palets": "Procesar",
        "Procesar cruce": "Procesar",
        "Procesar recepcion": "Procesar",
        "Procesar recepción": "Procesar",
        "Procesar control": "Procesar",
        "Comprobar salida": "Comprobar",
        "Sugerir pallets": "Sugerir",
        "Guardar Excel": "Excel",
        "Guardar CSV": "CSV",
        "Guardar TXT": "TXT",
        "Guardar TXT AX": "TXT AX",
        "Generar PDF diferencias": "PDF dif.",
        "Generar PDF rangos": "PDF rangos",
        "Generar ambos PDFs": "Ambos PDF",
        "Cruzar albaran": "Cruzar",
        "Cruzar albarán": "Cruzar",
        "Enviar correo": "Correo",
        "Guardar plantilla": "Plantilla",
        "Limpiar correcciones": "Restaurar",
        "Limpiar filtro": "Restaurar",
    }
    return mapping.get(text, text)


def confirm_discard_work(widget: QWidget, title: str = "Descartar cambios") -> bool:
    if not _has_pending_work(widget):
        return True
    app = QApplication.instance()
    if app is not None and app.platformName().lower() == "offscreen":
        return True
    if not getattr(widget, "show_dialogs", True):
        return True
    answer = QMessageBox.question(
        widget,
        title,
        "Hay archivos, correcciones o resultados en pantalla.\n\nQuieres continuar y limpiar este trabajo?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


def _install_close_guard(widget: QWidget) -> None:
    if not isinstance(widget, QMainWindow) or widget.property("closeGuardPatched"):
        return
    original_close_event = widget.closeEvent

    def close_event(event, *, _widget=widget, _original=original_close_event) -> None:
        if confirm_discard_work(_widget, "Cerrar ventana"):
            _original(event)
        else:
            event.ignore()

    widget.closeEvent = close_event  # type: ignore[method-assign]
    widget.setProperty("closeGuardPatched", True)


def _has_pending_work(widget: QWidget) -> bool:
    simple_attrs = (
        "paths",
        "final_files",
        "selected_pallets",
        "last_attachments",
        "rutas_txt",
    )
    for attr in simple_attrs:
        value = getattr(widget, attr, None)
        if value:
            return True
    for attr in ("origin_file", "txt_file", "seals_file", "official_excel"):
        if getattr(widget, attr, None) is not None:
            return True
    if getattr(widget, "weight_filter_pending", False):
        return True

    result = getattr(widget, "result", None)
    if result is None:
        return False
    for attr in (
        "precintos",
        "processed_lines",
        "validos",
        "invalidos",
        "duplicados",
        "issues",
        "final_palets",
        "registros_txt",
        "salidas",
        "source_files",
        "selected_files",
    ):
        value = getattr(result, attr, None)
        if value:
            return True
    if getattr(result, "pending_correction", False):
        return True
    dataframe = getattr(result, "dataframe", None)
    if dataframe is not None and hasattr(dataframe, "empty") and not dataframe.empty:
        return True
    return False


def _apply_tab_order(widget: QWidget) -> None:
    focus_widgets = [
        child
        for child in widget.findChildren(QWidget)
        if isinstance(child, (QLineEdit, QComboBox, QPushButton, QPlainTextEdit, QTableWidget))
        and child.focusPolicy() != Qt.NoFocus
        and child.objectName() != "ThemeToggle"
    ]
    for previous, current in zip(focus_widgets, focus_widgets[1:]):
        QWidget.setTabOrder(previous, current)


def _update_context_panel(widget: QWidget) -> None:
    status = widget.findChild(QLabel, "StatusLabel")
    summary = widget.findChild(QLabel, "ResultLabel")
    state_text = status.text() if status is not None and status.text() else "Pendiente"
    summary_text = summary.text() if summary is not None else ""
    state = widget.findChild(QLabel, "ContextStateValue")
    next_action = widget.findChild(QLabel, "ContextNextValue")
    alerts = widget.findChild(QLabel, "ContextAlertsValue")
    if state is None or next_action is None or alerts is None:
        return
    state.setText(_compact_text(_state_summary(state_text, summary_text), 96))
    next_button = _next_action_button(widget)
    next_action.setText(_clean_text(next_button.text()) if next_button is not None else "Completa el paso actual")
    _highlight_next_action(widget, next_button)
    alerts.setText(_alert_text(" ".join([state_text, summary_text])))
    _update_flow_indicator(widget, " ".join([state_text, summary_text]))


def _enable_drag_drop(widget: QWidget) -> None:
    if not isinstance(widget, QMainWindow) or widget.property("dropPatched"):
        return
    widget.setAcceptDrops(True)

    def drag_enter(event, *, _widget=widget) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            show_inline_message(_widget, "info", "Suelta los archivos para cargarlos en esta aplicacion.")
        else:
            event.ignore()

    def drop(event, *, _widget=widget) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        paths = [path for path in paths if path.exists()]
        if not paths:
            event.ignore()
            return
        if _handle_dropped_paths(_widget, paths):
            show_inline_message(_widget, "success", _drop_feedback(paths))
            event.acceptProposedAction()
        else:
            show_inline_message(_widget, "warning", "Esta ventana no reconoce automaticamente esos archivos. Usa los botones de carga para asignarlos.")
            event.ignore()

    widget.dragEnterEvent = drag_enter  # type: ignore[method-assign]
    widget.dropEvent = drop  # type: ignore[method-assign]
    widget.setProperty("dropPatched", True)


def _handle_dropped_paths(widget: QWidget, paths: list[Path]) -> bool:
    if hasattr(widget, "set_files"):
        widget.set_files(paths)  # type: ignore[attr-defined]
        return True
    if hasattr(widget, "set_txt_files"):
        txts = [path for path in paths if path.suffix.lower() == ".txt"]
        if txts:
            widget.set_txt_files(txts)  # type: ignore[attr-defined]
            return True
    if hasattr(widget, "set_final_files") and hasattr(widget, "set_origin_file"):
        csvs = [path for path in paths if path.suffix.lower() == ".csv"]
        excels = [path for path in paths if path.suffix.lower() in {".xlsx", ".xls", ".xlsm"}]
        if csvs:
            widget.set_final_files(csvs)  # type: ignore[attr-defined]
        if excels:
            widget.set_origin_file(excels[0])  # type: ignore[attr-defined]
        return bool(csvs or excels)
    if hasattr(widget, "set_txt_file") or hasattr(widget, "set_seals_file"):
        txts = [path for path in paths if path.suffix.lower() == ".txt"]
        excels = [path for path in paths if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}]
        if txts and hasattr(widget, "set_txt_file"):
            widget.set_txt_file(txts[0])  # type: ignore[attr-defined]
        if excels and hasattr(widget, "set_seals_file"):
            widget.set_seals_file(excels[0])  # type: ignore[attr-defined]
        return bool(txts or excels)
    return False


def _drop_feedback(paths: list[Path]) -> str:
    names = [path.name for path in paths[:3]]
    suffix = "" if len(paths) <= 3 else f" y {len(paths) - 3} mas"
    return f"Archivos cargados por arrastre: {', '.join(names)}{suffix}. Revisa el resumen antes de procesar."


def _update_flow_indicator(widget: QWidget, text: str = "") -> None:
    badges = widget.findChildren(QLabel, "StepBadge")
    if not badges:
        return
    explicit = _explicit_flow_state(widget, len(badges))
    if explicit is not None:
        active_index, warning, complete = explicit
        _apply_stepper_state(badges, active_index, warning=warning, complete=complete)
        return
    if not text:
        status = widget.findChild(QLabel, "StatusLabel")
        summary = widget.findChild(QLabel, "ResultLabel")
        text = " ".join(
            part
            for part in (
                status.text() if status is not None else "",
                summary.text() if summary is not None else "",
            )
            if part
        )
    _update_stepper_from_text(badges, text)


def _explicit_flow_state(widget: QWidget, badge_count: int) -> tuple[int, bool, bool] | None:
    flow_state = getattr(widget, "flow_state", None)
    if not callable(flow_state):
        return None
    try:
        state = flow_state()
    except Exception:
        return None
    if not isinstance(state, tuple) or len(state) < 2:
        return None
    active_index = int(state[0])
    warning = bool(state[1])
    complete = bool(state[2]) if len(state) > 2 else active_index > badge_count
    return active_index, warning, complete


def _update_stepper_from_text(badges: list[QLabel], text: str) -> None:
    normalized = text.lower()
    if "sin archivos" in normalized or "selecciona" in normalized and "empezar" in normalized:
        active_index = 1
        warning = False
        complete = False
    elif any(word in normalized for word in ("error", "no valido", "incidencia", "pendiente")):
        active_index = min(2, len(badges) - 1)
        warning = True
        complete = False
    elif any(word in normalized for word in ("guardado", "enviado", "correctamente")):
        active_index = len(badges)
        warning = False
        complete = True
    elif any(word in normalized for word in ("completado", "finalizado", "listos", "validos", "correcta")):
        active_index = min(3, len(badges))
        warning = False
        complete = False
    elif any(word in normalized for word in ("cargado", "seleccion", "archivos:")):
        active_index = min(2, len(badges))
        warning = False
        complete = False
    else:
        active_index = 1
        warning = False
        complete = False
    _apply_stepper_state(badges, active_index, warning=warning, complete=complete)


def _apply_stepper_state(
    badges: list[QLabel],
    active_index: int,
    *,
    warning: bool = False,
    complete: bool = False,
) -> None:
    active_index = max(1, min(active_index, len(badges)))
    for index, badge in enumerate(badges, start=1):
        if complete:
            state = "complete"
        elif warning and index == active_index:
            state = "warning"
        elif index < active_index:
            state = "complete"
        elif index == active_index:
            state = "active"
        else:
            state = "pending"
        badge.setProperty("stepState", state)
        description = {
            "active": "Paso activo",
            "complete": "Paso completado",
            "warning": "Paso con aviso",
            "pending": "Paso pendiente",
        }[state]
        badge.setToolTip(description)
        badge.setAccessibleDescription(description)
        _refresh_style(badge)


def _next_action_text(widget: QWidget) -> str:
    button = _next_action_button(widget)
    return _clean_text(button.text()) if button is not None else "Completa el paso actual"


def _next_action_button(widget: QWidget) -> QPushButton | None:
    buttons = [
        button
        for button in widget.findChildren(QPushButton)
        if button.objectName() != "ThemeToggle" and _clean_text(button.text())
    ]
    for button in buttons:
        text = _clean_text(button.text())
        if button.isEnabled() and button.property("primary"):
            return button
    for button in buttons:
        text = _clean_text(button.text())
        if not text or text.lower() == "limpiar":
            continue
        if button.isEnabled():
            return button
    return None


def _highlight_next_action(widget: QWidget, next_button: QPushButton | None) -> None:
    for button in widget.findChildren(QPushButton):
        current = button is next_button and button.isEnabled()
        if button.property("nextAction") == current:
            continue
        button.setProperty("nextAction", current)
        _refresh_style(button)


def _state_summary(status_text: str, summary_text: str) -> str:
    combined = " ".join(part for part in (status_text, summary_text) if part)
    normalized = combined.lower()
    if "sin archivos" in normalized:
        return "Esperando archivos"
    if "guardado" in normalized or "enviado" in normalized:
        return "Salida completada"
    if any(word in normalized for word in ("incidencia", "pendiente", "no valido", "error")):
        return "Requiere revision"
    if any(word in normalized for word in ("cargado", "seleccion", "archivos:")):
        return "Archivos preparados"
    if any(word in normalized for word in ("correcta", "validos", "listos", "procesado")):
        return "Datos validados"
    return status_text or "Pendiente"


def _alert_text(text: str) -> str:
    normalized = text.lower()
    if any(word in normalized for word in ("error", "no valido", "incidencia", "pendiente", "no se", "faltan")):
        return "Revisar"
    if any(word in normalized for word in ("guardado", "completado", "finalizado", "correcta", "listos")):
        return "Correcto"
    return "Sin avisos"


def _compact_text(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "..."


def _theme_toggle_button() -> QPushButton:
    button = QPushButton("Claro" if is_dark_mode() else "Oscuro")
    button.setObjectName("ThemeToggle")
    button.setFixedHeight(34)
    button.setMinimumWidth(82)
    button.setCheckable(True)
    button.setChecked(is_dark_mode())
    button.setAccessibleName("Cambiar modo claro oscuro")
    button.setToolTip("Alterna entre modo claro y modo oscuro.")
    button.clicked.connect(lambda checked: _apply_theme_mode("dark" if checked else "light"))
    return button


def _apply_theme_mode(mode: str) -> None:
    set_theme_mode(mode)
    app = QApplication.instance()
    if app is None:
        return
    for top in app.topLevelWidgets():
        top.setProperty("theme", current_theme_mode())
        top.setStyleSheet(base_qss())
        for button in top.findChildren(QPushButton, "ThemeToggle"):
            button.blockSignals(True)
            button.setChecked(is_dark_mode())
            button.setText("Claro" if is_dark_mode() else "Oscuro")
            button.blockSignals(False)
            _refresh_style(button)
        _refresh_style(top)


def _replace_step_bars(widget: QWidget) -> None:
    for label in list(widget.findChildren(QLabel, "StepBar")):
        parent = label.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is None:
            continue
        stepper = _stepper_from_text(label.text())
        layout.replaceWidget(label, stepper)
        label.deleteLater()


def _stepper_from_text(text: str) -> QFrame:
    stepper = QFrame()
    stepper.setObjectName("Stepper")
    layout = make_flow(stepper, margin=0, spacing=8)
    layout.setContentsMargins(8, 6, 8, 6)

    normalized = text.replace("    |    ", "->").replace("  ->  ", "->")
    parts = [part.strip() for part in normalized.split("->") if part.strip()]
    for index, part in enumerate(parts, start=1):
        label_text = part
        if label_text[:1].isdigit():
            label_text = label_text[1:].strip()
        label_text = _compact_step_text(label_text)
        badge = QLabel(str(index))
        badge.setObjectName("StepBadge")
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge)
        step_label = QLabel(label_text)
        step_label.setObjectName("StepText")
        step_label.setWordWrap(True)
        make_widgets_resizable(step_label)
        layout.addWidget(step_label)
        if index < len(parts):
            connector = QLabel(">")
            connector.setObjectName("StepConnector")
            connector.setAlignment(Qt.AlignCenter)
            layout.addWidget(connector)
    return stepper


def _compact_step_text(text: str) -> str:
    replacements = {
        "Cargar TXT/CSV": "Cargar",
        "Cargar TXT": "TXT",
        "Cargar SealsReport": "SealsReport",
        "Cargar Excel": "Excel",
        "Cargar Excel oficial": "Excel oficial",
        "Cargar CSVs finales": "CSV finales",
        "Seleccionar archivos": "Archivos",
        "Seleccionar pallets": "Pallets",
        "Procesar recepcion": "Procesar",
        "Procesar recepción": "Procesar",
        "Procesar": "Procesar",
        "Revisar incidencias": "Revisar",
        "Revisar pesos/correcciones": "Revisar",
        "Guardar/enviar": "Salida",
        "Guardar TXT": "Guardar",
        "Guardar TXT AX": "TXT AX",
        "Generar PDFs": "PDFs",
        "Generar PDF": "PDF",
        "PDF/correo": "Salida",
        "PDF opcional": "PDF",
        "Cruz ar albaran": "Cruzar",
        "Cruzar albaran": "Cruzar",
        "Cruzar albarán": "Cruzar",
    }
    return replacements.get(text, text)


def _icon_for_text(style: QStyle, text: str):
    if any(
        word in text
        for word in (
            "seleccionar",
            "cargar",
            "txt/csv",
            "txt fac",
            "txt recepcion",
            "csvs",
            "fichero",
            "excel oficial",
            "sealsreport",
            "config",
        )
    ):
        return style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
    if any(word in text for word in ("guardar", "csv", "excel", "txt ax")):
        return style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
    if any(word in text for word in ("procesar", "comprobar", "cruzar", "revalidar", "sugerir")):
        return style.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
    if "pdf" in text:
        return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
    if "correo" in text:
        return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
    if "limpiar" in text:
        return style.standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
    fallback = getattr(QStyle.StandardPixmap, "SP_ArrowForward", QStyle.StandardPixmap.SP_DialogOkButton)
    return style.standardIcon(fallback)


def _set_button_role(button: QPushButton, text: str) -> None:
    if button.property("primary"):
        return
    if any(word in text for word in ("limpiar", "borrar", "reset")):
        button.setProperty("role", "danger")
    elif any(
        word in text
        for word in ("seleccionar", "cargar", "txt/csv", "txt fac", "txt recepcion", "fichero", "sealsreport", "config")
    ):
        button.setProperty("role", "open")
    elif any(word in text for word in ("guardar", "csv", "excel", "txt ax")):
        button.setProperty("role", "save")
    elif any(word in text for word in ("procesar", "comprobar", "cruzar", "revalidar", "sugerir")):
        button.setProperty("role", "process")


def _set_shortcut(button: QPushButton, text: str) -> None:
    if button.shortcut().toString():
        return
    shortcut = _shortcut_for_text(text)
    if shortcut:
        button.setShortcut(shortcut)


def _shortcut_for_text(text: str) -> str:
    exact = {
        "cargar csvs finales": "Ctrl+O",
        "cargar origen": "Ctrl+Shift+O",
        "cargar txt/csv": "Ctrl+O",
        "cargar excel oficial": "Ctrl+Shift+O",
        "cargar txt recepcion": "Ctrl+O",
        "cargar txt fac": "Ctrl+O",
        "cargar sealsreport": "Ctrl+Shift+O",
        "guardar txt": "Ctrl+S",
        "guardar txt ax": "Ctrl+S",
        "guardar csv": "Ctrl+Shift+S",
        "guardar excel": "Ctrl+S",
        "configurar rangos": "Ctrl+Shift+G",
    }
    if text in exact:
        return exact[text]
    if any(word in text for word in ("seleccionar", "cargar", "txt/csv", "fichero")):
        return "Ctrl+O"
    if any(word in text for word in ("procesar", "comprobar", "cruzar")):
        return "Ctrl+Return"
    if any(word in text for word in ("guardar", "exportar")):
        return "Ctrl+S"
    if "limpiar" in text:
        return "Esc"
    return ""


def _clean_text(text: str) -> str:
    return " ".join(text.replace("&", "").split())


def _append_shortcut_tooltip(button: QPushButton) -> None:
    shortcut = button.shortcut().toString()
    if not shortcut:
        return
    tooltip = button.toolTip() or button.text()
    if shortcut not in tooltip:
        button.setToolTip(f"{tooltip} ({shortcut})")


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
