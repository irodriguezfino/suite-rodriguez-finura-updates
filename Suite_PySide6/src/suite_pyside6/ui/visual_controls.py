"""Native Qt interactions with explicit, theme-aware control indicators."""
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QSpinBox, QDoubleSpinBox, QStyle, QStyleOptionButton, QStyleOptionSpinBox


class ModernCheckBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, self)
        from .theme import palette
        colors = palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.checkState() != Qt.Unchecked:
            color = colors['background'] if self.isEnabled() else colors['text_muted']
            pen = QPen(QColor(color), 2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            center = rect.center()
            if self.checkState() == Qt.PartiallyChecked:
                painter.drawLine(center.x()-4, center.y(), center.x()+4, center.y())
            else:
                painter.drawLine(QPointF(rect.left()+3, center.y()), QPointF(center.x()-1, rect.bottom()-4))
                painter.drawLine(QPointF(center.x()-1, rect.bottom()-4), QPointF(rect.right()-3, rect.top()+4))
        if self.hasFocus():
            painter.setPen(QPen(QColor(colors['focus_ring']), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 4, 4)
        painter.end()


class _SpinAppearance:
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('modernSpin', True)

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.palette().text().color(), 1.6))
        for control, direction in ((QStyle.SC_SpinBoxUp, -1), (QStyle.SC_SpinBoxDown, 1)):
            rect = self.style().subControlRect(QStyle.CC_SpinBox, option, control, self)
            c = rect.center()
            painter.drawLine(c.x()-3, c.y()-direction, c.x(), c.y()+direction)
            painter.drawLine(c.x(), c.y()+direction, c.x()+3, c.y()-direction)
        painter.end()


class ModernSpinBox(_SpinAppearance, QSpinBox):
    """Integer range and step behaviour remain owned by QSpinBox."""


class ModernDoubleSpinBox(_SpinAppearance, QDoubleSpinBox):
    """Decimal precision, suffixes and stepping remain owned by Qt."""
