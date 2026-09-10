from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QLayout,
    QLayoutItem,
    QSizePolicy,
    QWidget,
    QWidgetItem,
)


class FlowLayout(QLayout):
    """Simple wrapping layout for toolbars, chips and compact forms."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802 - Qt API
        self._items.append(item)

    def addWidget(self, widget: QWidget, *_args) -> None:  # noqa: N802 - Qt API
        self.addChildWidget(widget)
        self.addItem(QWidgetItem(widget))

    def addLayout(self, layout: QLayout, *_args) -> None:  # noqa: N802 - Qt API
        self.addChildLayout(layout)
        self.addItem(layout)

    def addStretch(self, _stretch: int = 0) -> None:  # noqa: N802 - compatibility with box layouts
        return

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - Qt API
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802 - Qt API
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:  # noqa: N802 - Qt API
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802 - Qt API
        super().setGeometry(rect)
        required_height = self._do_layout(rect, test_only=False) + 14
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()
        if parent is not None and parent.property("lockFlowMinimumHeight") and parent.minimumHeight() != required_height:
            parent.setMinimumHeight(required_height)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        parent = self.parentWidget()
        width = parent.width() if parent is not None and parent.width() > 0 else self._preferred_width()
        return QSize(width, self.heightForWidth(width))

    def minimumSize(self) -> QSize:  # noqa: N802 - Qt API
        size = QSize()
        for item in self._items:
            widget = item.widget()
            minimum = item.minimumSize()
            if widget is not None and widget.property("flowCanShrink"):
                minimum.setWidth(0)
            size = size.expandedTo(minimum)
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _preferred_width(self) -> int:
        left, _top, right, _bottom = self.getContentsMargins()
        visible_items = [
            item
            for item in self._items
            # A page is usually laid out before its top-level window is shown.
            # isVisible() is false in that moment even for normal controls;
            # only explicitly hidden widgets should be skipped.
            if item.widget() is None or not item.widget().isHidden()
        ]
        if not visible_items:
            return left + right
        spacing = self.spacing() * max(0, len(visible_items) - 1)
        return sum(item.sizeHint().width() for item in visible_items) + spacing + left + right

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        spacing = self.spacing()
        rows: list[list[tuple[QLayoutItem, int, int]]] = []
        row: list[tuple[QLayoutItem, int, int]] = []
        row_width = 0
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            hint = item.sizeHint()
            item_width = min(hint.width(), max(1, effective.width()))
            item_height = item.heightForWidth(item_width) if item.hasHeightForWidth() else hint.height()
            required_width = item_width if not row else row_width + spacing + item_width
            if row and required_width > effective.width():
                rows.append(row)
                row = []
                row_width = 0
            row.append((item, item_width, item_height))
            row_width = item_width if len(row) == 1 else row_width + spacing + item_width
        if row:
            rows.append(row)

        # Items such as a 50 px action summary and 34 px buttons frequently
        # share one wrapping row.  Center them on the row's vertical axis so
        # the toolbar and the stepper look intentional rather than top-heavy.
        y = effective.y()
        for row in rows:
            line_height = max(item_height for _item, _item_width, item_height in row)
            x = effective.x()
            for item, item_width, item_height in row:
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y + (line_height - item_height) // 2), QSize(item_width, item_height)))
                x += item_width + spacing
            y += line_height + spacing
        content_height = 0 if not rows else y - spacing - effective.y()
        return top + content_height + bottom


@dataclass
class AdaptiveLayout:
    layout: QBoxLayout
    breakpoint_width: int = 860
    wide_direction: QBoxLayout.Direction = QBoxLayout.LeftToRight
    narrow_direction: QBoxLayout.Direction = QBoxLayout.TopToBottom


def make_flow(parent: QWidget | None = None, *, margin: int = 0, spacing: int = 8) -> FlowLayout:
    return FlowLayout(parent, margin=margin, spacing=spacing)


def register_adaptive_layout(
    widget: QWidget,
    layout: QBoxLayout,
    *,
    breakpoint_width: int = 860,
    wide_direction: QBoxLayout.Direction = QBoxLayout.LeftToRight,
    narrow_direction: QBoxLayout.Direction = QBoxLayout.TopToBottom,
) -> None:
    layouts: list[AdaptiveLayout] = getattr(widget, "_adaptive_layouts", [])
    layouts.append(
        AdaptiveLayout(
            layout=layout,
            breakpoint_width=breakpoint_width,
            wide_direction=wide_direction,
            narrow_direction=narrow_direction,
        )
    )
    setattr(widget, "_adaptive_layouts", layouts)
    _patch_resize_event(widget)
    apply_adaptive_layouts(widget)


def apply_adaptive_layouts(widget: QWidget) -> None:
    for item in getattr(widget, "_adaptive_layouts", []):
        direction = item.narrow_direction if widget.width() < item.breakpoint_width else item.wide_direction
        if item.layout.direction() != direction:
            item.layout.setDirection(direction)


def make_widgets_resizable(*widgets: QWidget) -> None:
    for widget in widgets:
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


def _patch_resize_event(widget: QWidget) -> None:
    if getattr(widget, "_adaptive_resize_patched", False):
        return
    original_resize_event = widget.resizeEvent

    def resize_event(event, *, _widget=widget, _original=original_resize_event) -> None:
        _original(event)
        apply_adaptive_layouts(_widget)

    widget.resizeEvent = resize_event  # type: ignore[method-assign]
    setattr(widget, "_adaptive_resize_patched", True)
