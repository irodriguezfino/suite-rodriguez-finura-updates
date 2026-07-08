from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def labeled_field(label_text: str, field: QWidget, *, compact: bool = False) -> QWidget:
    group = QWidget()
    group.setObjectName("FieldGroup")
    group.setProperty("compact", compact)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    label = QLabel(label_text)
    label.setObjectName("FieldLabel")
    label.setBuddy(field)
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    layout.addWidget(label)
    layout.addWidget(field)

    field.setAccessibleName(label_text)
    if not field.toolTip():
        field.setToolTip(label_text)
    return group


def panel(title: str = "", subtitle: str = "", *, name: str = "DsPanel") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(10)
    if title:
        header = QVBoxLayout()
        header.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("DsPanelTitle")
        header.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("DsPanelSubtitle")
            subtitle_label.setWordWrap(True)
            header.addWidget(subtitle_label)
        layout.addLayout(header)
    return frame, layout


def metric(label: str, value: str, detail: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("DsMetric")
    frame.setAccessibleName(label)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 9, 12, 9)
    layout.setSpacing(2)
    value_label = QLabel(value)
    value_label.setObjectName("DsMetricValue")
    value_label.setAccessibleName(label)
    value_label.setAccessibleDescription(f"{label}: {value}")
    label_widget = QLabel(label)
    label_widget.setObjectName("DsMetricLabel")
    layout.addWidget(value_label)
    layout.addWidget(label_widget)
    if detail:
        detail_label = QLabel(detail)
        detail_label.setObjectName("DsMetricDetail")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)
    frame.setProperty("valueLabel", value_label)
    return frame


def badge(text: str, *, tone: str = "neutral") -> QLabel:
    label = QLabel(text)
    label.setObjectName("DsBadge")
    label.setProperty("tone", tone)
    label.setAlignment(Qt.AlignCenter)
    label.setAccessibleName(text)
    return label


def empty_state(title: str, body: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("DsEmpty")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(6)
    title_label = QLabel(title)
    title_label.setObjectName("DsEmptyTitle")
    title_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(title_label)
    if body:
        body_label = QLabel(body)
        body_label.setObjectName("DsEmptyBody")
        body_label.setAlignment(Qt.AlignCenter)
        body_label.setWordWrap(True)
        layout.addWidget(body_label)
    return frame


def module_row(title: str, description: str, category: str, status: str, shortcut: str, action: QPushButton) -> QFrame:
    row = QFrame()
    row.setObjectName("ModuleRow")
    row.setAccessibleName(title)
    row.setToolTip(description)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(12)

    icon = QLabel(_initials(title))
    icon.setObjectName("ModuleIcon")
    icon.setAlignment(Qt.AlignCenter)
    layout.addWidget(icon, 0, Qt.AlignVCenter)

    text_layout = QVBoxLayout()
    text_layout.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("ModuleTitle")
    title_label.setWordWrap(True)
    desc_label = QLabel(description)
    desc_label.setObjectName("ModuleDescription")
    desc_label.setWordWrap(True)
    meta = QHBoxLayout()
    meta.setSpacing(6)
    meta.addWidget(badge(category))
    meta.addWidget(badge(status, tone="success" if status == "Disponible" else "neutral"))
    shortcut_label = QLabel(shortcut)
    shortcut_label.setObjectName("ModuleShortcut")
    meta.addWidget(shortcut_label)
    meta.addStretch(1)
    text_layout.addWidget(title_label)
    text_layout.addWidget(desc_label)
    text_layout.addLayout(meta)
    layout.addLayout(text_layout, 1)

    action.setObjectName("ModuleAction")
    action.setProperty("primary", True)
    action.setMinimumWidth(72)
    layout.addWidget(action, 0, Qt.AlignVCenter)
    return row


def _initials(title: str) -> str:
    words = [word for word in title.split() if word]
    if not words:
        return "SR"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()
