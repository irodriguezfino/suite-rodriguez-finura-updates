from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


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
