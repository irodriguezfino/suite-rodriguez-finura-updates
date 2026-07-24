from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QGuiApplication, QPainter, QPalette, QPen, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class ModernSelect(QComboBox):
    """Selector nativo con popup y teclado de Qt, unificado para toda la Suite."""

    def __init__(self, parent: QWidget | None = None, *, placeholder: str = "Selecciona una opción") -> None:
        super().__init__(parent)
        self.setObjectName("ModernSelect")
        self.setProperty("modernSelect", True)
        self.setProperty("chevronVisible", True)
        self.setProperty("popupOpen", False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setMaxVisibleItems(9)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setPlaceholderText(placeholder)
        self.setAccessibleDescription("Selector desplegable. Usa Espacio o Enter para abrir las opciones.")
        view = QListView(self)
        view.setObjectName("ModernSelectPopup")
        view.setUniformItemSizes(True)
        view.setSpacing(2)
        view.setVerticalScrollMode(QListView.ScrollPerPixel)
        view.setTextElideMode(Qt.ElideRight)
        self.setView(view)

    def add_option(self, text: str, data: object = None, *, enabled: bool = True, description: str = "") -> None:
        self.addItem(text, data)
        index = self.count() - 1
        item = self.model().item(index)
        if item is not None:
            item.setEnabled(enabled)
            item.setToolTip(description or text)

    def chevron_rect(self):
        """Zona reservada para el indicador; útil para pintura y pruebas."""
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        return self.style().subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, self)

    def _set_popup_open(self, is_open: bool) -> None:
        self.setProperty("popupOpen", is_open)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def showPopup(self) -> None:  # noqa: N802 - API de Qt
        if not self.isEnabled():
            return
        self._set_popup_open(True)
        super().showPopup()
        popup = self.view().window()
        anchor = self.mapToGlobal(self.rect().bottomLeft())
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        content_width = self.view().sizeHintForColumn(0) + 42
        width = min(max(self.width(), self.minimumWidth(), content_width), max(120, available.width() - 16))
        height = min(360, max(160, popup.sizeHint().height()))
        height = min(height, max(100, available.height() - 16))
        below = available.bottom() - anchor.y()
        above = self.mapToGlobal(self.rect().topLeft()).y() - available.top()
        y = anchor.y() if below >= min(height, 160) or below >= above else self.mapToGlobal(self.rect().topLeft()).y() - height
        y = max(available.top() + 8, min(y, available.bottom() - height + 1))
        x = max(available.left() + 8, min(anchor.x(), available.right() - width + 1))
        popup.setGeometry(x, y, width, height)

    def hidePopup(self) -> None:  # noqa: N802 - API de Qt
        super().hidePopup()
        self._set_popup_open(False)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        rect = self.chevron_rect()
        if not rect.isValid():
            return
        color = self.palette().text().color()
        if not self.isEnabled():
            color = self.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        center = rect.center()
        points = (
            (QPoint(center.x() - 4, center.y() + 2), QPoint(center.x(), center.y() - 2), QPoint(center.x() + 4, center.y() + 2))
            if self.property("popupOpen")
            else (QPoint(center.x() - 4, center.y() - 2), QPoint(center.x(), center.y() + 2), QPoint(center.x() + 4, center.y() - 2))
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(points[0], points[1])
        painter.drawLine(points[1], points[2])
        painter.end()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in {Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter} and not self.view().isVisible():
            self.showPopup()
            event.accept()
            return
        if event.key() == Qt.Key_Escape and self.view().isVisible():
            self.hidePopup()
            self.setFocus(Qt.ShortcutFocusReason)
            event.accept()
            return
        super().keyPressEvent(event)


class SearchableComboBox(ModernSelect):
    """Combobox para listas que pueden crecer, con búsqueda nativa por texto."""

    def __init__(self, parent: QWidget | None = None, *, placeholder: str = "Busca una opción") -> None:
        super().__init__(parent, placeholder=placeholder)
        self.setObjectName("SearchableComboBox")
        self.setProperty("searchable", True)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        line_edit = self.lineEdit()
        if line_edit is None:  # Protección para stubs de Qt; el combobox ya es editable.
            raise RuntimeError("No se pudo crear el campo de búsqueda")
        line_edit.setCursor(Qt.CursorShape.IBeamCursor)
        line_edit.setClearButtonEnabled(True)
        line_edit.setPlaceholderText(placeholder)
        line_edit.setAccessibleDescription("Escribe para buscar; usa las flechas y Enter para seleccionar.")
        self._completer = QCompleter(self.model(), self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.activated[str].connect(self._select_completion)
        self.setCompleter(self._completer)
        self._empty_model = QStandardItemModel(self)
        empty_item = QStandardItem("No se encontraron opciones")
        empty_item.setFlags(Qt.NoItemFlags)
        self._empty_model.appendRow(empty_item)
        line_edit.textEdited.connect(self._update_search_feedback)

    def _select_completion(self, text: str) -> None:
        index = self.findText(text, Qt.MatchFixedString)
        if index >= 0:
            self.setCurrentIndex(index)

    def _update_search_feedback(self, text: str) -> None:
        query = text.strip().casefold()
        matches = any(query in self.itemText(index).casefold() for index in range(self.count()))
        self._completer.setModel(self.model() if not query or matches else self._empty_model)
        self._completer.setCompletionPrefix(query if matches else "")
        if query:
            self._completer.complete()


class ActionMenuButton(QToolButton):
    """Botón de acciones no seleccionables; evita confundir menús con selects."""

    def __init__(self, parent: QWidget | None = None, *, accessible_name: str = "Más acciones") -> None:
        super().__init__(parent)
        self.setObjectName("ActionMenuButton")
        self.setText("Más acciones  ⋯")
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.setPopupMode(QToolButton.InstantPopup)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(accessible_name)
        self.setToolTip(accessible_name)
        self._menu = QMenu(self)
        self._menu.setObjectName("ActionDropdownMenu")
        self.setMenu(self._menu)

    def add_action(self, text: str, callback, *, destructive: bool = False) -> QAction:
        action = self._menu.addAction(text)
        action.setProperty("destructive", destructive)
        action.triggered.connect(callback)
        return action


def labeled_field(label_text: str, field: QWidget, *, compact: bool = False) -> QWidget:
    group = QWidget()
    group.setObjectName("FieldGroup")
    group.setProperty("compact", compact)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    label = QLabel(label_text)
    label.setObjectName("FieldLabel")
    label.setBuddy(field)
    layout.addWidget(label)
    layout.addWidget(field)

    field.setAccessibleName(label_text)
    if not field.toolTip():
        field.setToolTip(label_text)
    return group


def configure_header_action(button: QPushButton) -> QPushButton:
    """Aplica la variante compartida para acciones de la cabecera principal."""
    button.setProperty("headerAction", True)
    button.setMinimumHeight(36)
    button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
    return button


def page_header(title: str, subtitle: str = "", actions: list[QWidget] | None = None) -> QFrame:
    header = QFrame()
    header.setObjectName("ConsoleHeader")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(12)

    copy = QVBoxLayout()
    copy.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("ShellTitle")
    copy.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("ShellSubtitle")
        subtitle_label.setWordWrap(True)
        copy.addWidget(subtitle_label)
    layout.addLayout(copy, 1)

    for action in actions or []:
        layout.addWidget(action, 0, Qt.AlignVCenter)
    return header


def panel(title: str = "", subtitle: str = "", *, name: str = "Panel") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(10)
    if title:
        header = QVBoxLayout()
        header.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("PanelTitle")
        header.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("PanelSubtitle")
            subtitle_label.setWordWrap(True)
            header.addWidget(subtitle_label)
        layout.addLayout(header)
    return frame, layout


def metric(label: str, value: str, detail: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("DsMetric")
    frame.setAccessibleName(label)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    frame.setMinimumWidth(0)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(2)

    value_label = QLabel(value)
    value_label.setObjectName("DsMetricValue")
    value_label.setAccessibleName(label)
    value_label.setMinimumWidth(0)
    label_widget = QLabel(label)
    label_widget.setObjectName("DsMetricLabel")
    label_widget.setWordWrap(True)
    label_widget.setMinimumWidth(0)
    layout.addWidget(value_label)
    layout.addWidget(label_widget)
    if detail:
        detail_label = QLabel(detail)
        detail_label.setObjectName("DsMetricDetail")
        detail_label.setWordWrap(True)
        detail_label.setMinimumWidth(0)
        layout.addWidget(detail_label)
    frame.setProperty("valueLabel", value_label)
    return frame


def control_metric_pair(layout: QGridLayout, column: int, label: str, value: str) -> QLabel:
    value_label = QLabel(value)
    value_label.setObjectName("ControlMetricValue")
    value_label.setAccessibleName(label)
    value_label.setAccessibleDescription(f"{label}: {value}")
    text_label = QLabel(label)
    text_label.setObjectName("ControlMetricLabel")
    layout.addWidget(value_label, 0, column)
    layout.addWidget(text_label, 1, column)
    return value_label


def control_pill(text: str, *, issue: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName("ControlIssuePill" if issue else "ControlCountPill")
    label.setAccessibleName(text)
    return label


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionLabel")
    label.setWordWrap(True)
    label.setAccessibleName(text)
    return label


def control_rail_label(text: str, *, role: str = "detail") -> QLabel:
    names = {
        "action": "ControlRailAction",
        "detail": "ControlRailDetail",
        "state": "ControlRailState",
    }
    label = QLabel(text)
    label.setObjectName(names.get(role, names["detail"]))
    label.setWordWrap(True)
    label.setAccessibleName(text)
    return label


def step_bar(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("StepBar")
    label.setWordWrap(True)
    label.setAccessibleName("Progreso del flujo")
    label.setAccessibleDescription(text)
    return label


def badge(text: str, *, tone: str = "neutral") -> QLabel:
    label = QLabel(text)
    label.setObjectName("DsBadge")
    label.setProperty("tone", tone)
    label.setAlignment(Qt.AlignCenter)
    label.setAccessibleName(text)
    return label


def empty_state(title: str, body: str = "", action: QPushButton | None = None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Dropzone")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("PanelTitle")
    title_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(title_label)
    if body:
        body_label = QLabel(body)
        body_label.setObjectName("DashboardEmpty")
        body_label.setAlignment(Qt.AlignCenter)
        body_label.setWordWrap(True)
        layout.addWidget(body_label)
    if action is not None:
        layout.addWidget(action, 0, Qt.AlignCenter)
    return frame


def dropzone(title: str, body: str, action: QPushButton | None = None) -> QFrame:
    return empty_state(title, body, action)


def module_row(
    title: str,
    description: str,
    category: str,
    status: str,
    shortcut: str,
    action: QPushButton,
    description_control: QWidget | None = None,
) -> QFrame:
    row = QFrame()
    row.setObjectName("ModuleRow")
    row.setAccessibleName(title)
    shortcut_hint = f" Atajo: {shortcut}." if shortcut else ""
    row.setToolTip(f"{description}{shortcut_hint}")
    row.setAccessibleDescription(f"{description}{shortcut_hint}")
    row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(12)

    icon = QLabel(_initials(title))
    icon.setObjectName("ModuleIcon")
    icon.setAlignment(Qt.AlignCenter)
    layout.addWidget(icon, 0, Qt.AlignTop)

    text_layout = QVBoxLayout()
    text_layout.setSpacing(4)
    title_label = QLabel(title)
    title_label.setObjectName("ModuleTitle")
    title_label.setWordWrap(True)
    desc_label = description_control or QLabel(description)
    if description_control is None:
        desc_label.setObjectName("ModuleDescription")
        desc_label.setWordWrap(True)
    text_layout.addWidget(title_label)
    text_layout.addWidget(desc_label)

    meta = QHBoxLayout()
    meta.setSpacing(6)
    meta.addWidget(badge(category))
    meta.addWidget(badge(status, tone="success" if status == "Disponible" else "neutral"))
    if shortcut:
        shortcut_label = QLabel(shortcut)
        shortcut_label.setObjectName("ModuleShortcut")
        shortcut_label.setToolTip(f"Atajo para abrir {title}: {shortcut}")
        shortcut_label.setAccessibleName(f"Atajo {shortcut}")
        meta.addWidget(shortcut_label)
    meta.addStretch(1)
    text_layout.addLayout(meta)
    layout.addLayout(text_layout, 1)

    action.setObjectName("PrimaryButton")
    action.setProperty("primary", True)
    action.setMinimumWidth(96)
    action.setToolTip(f"Abrir {title}{f' ({shortcut})' if shortcut else ''}")
    if not action.accessibleName():
        action.setAccessibleName(f"Abrir {title}")
    action.setAccessibleDescription(f"Abre {title}.{shortcut_hint}")
    layout.addWidget(action, 0, Qt.AlignVCenter)
    return row


def work_item(title: str, detail: str, status: str, action: QPushButton | None = None) -> QFrame:
    item = QFrame()
    item.setObjectName("WorkItem")
    layout = QHBoxLayout(item)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(10)

    copy = QVBoxLayout()
    copy.setSpacing(3)
    title_label = QLabel(title)
    title_label.setObjectName("ModuleTitle")
    detail_label = QLabel(detail)
    detail_label.setObjectName("ModuleDescription")
    detail_label.setWordWrap(True)
    copy.addWidget(title_label)
    copy.addWidget(detail_label)
    layout.addLayout(copy, 1)
    status_badge = badge(status, tone=_status_tone(status))
    status_badge.setToolTip(f"Estado: {status}")
    layout.addWidget(status_badge)
    if action is not None:
        if not action.toolTip():
            action.setToolTip(title)
        if not action.accessibleName():
            action.setAccessibleName(f"{action.text()}: {title}")
        if not action.accessibleDescription():
            action.setAccessibleDescription(f"Ejecuta {action.text().lower()} para {title}.")
        layout.addWidget(action)
    return item


def metrics_grid(items: list[tuple[str, str, str]]) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Panel")
    layout = QGridLayout(frame)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)
    for index, (label, value, detail) in enumerate(items):
        layout.addWidget(metric(label, value, detail), 0, index)
    return frame


def _status_tone(status: str) -> str:
    text = status.lower()
    if "error" in text or "incid" in text:
        return "danger"
    if "listo" in text or "valid" in text or "gener" in text:
        return "success"
    if "pend" in text or "revis" in text:
        return "warning"
    return "neutral"


def _initials(title: str) -> str:
    words = [word for word in title.split() if word]
    if not words:
        return "SR"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()
