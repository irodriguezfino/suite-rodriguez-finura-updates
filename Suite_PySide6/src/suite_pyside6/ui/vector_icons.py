"""Small code-drawn icons, independent of font glyphs and SVG plugins."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPen, QPixmap


class _VectorEngine(QIconEngine):
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol

    def clone(self):
        return _VectorEngine(self.symbol)

    def paint(self, painter, rect, mode, state):
        from .theme import palette
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        from PySide6.QtGui import QColor
        color = QColor(palette()['text_secondary'])
        painter.setPen(QPen(color, 1.8))
        painter.translate(rect.x(), rect.y())
        painter.scale(rect.width()/24, rect.height()/24)
        if self.symbol == 'more':
            painter.setBrush(color)
            for x in (5, 12, 19):
                painter.drawEllipse(QRectF(x-1, 11, 2, 2))
        elif self.symbol == 'back':
            painter.drawLine(5, 12, 19, 12)
            painter.drawLine(5, 12, 11, 6)
            painter.drawLine(5, 12, 11, 18)
        elif self.symbol == 'tag':
            from PySide6.QtGui import QPolygonF
            from PySide6.QtCore import QPointF
            painter.drawPolygon(QPolygonF([QPointF(4, 4), QPointF(13, 4), QPointF(21, 12), QPointF(12, 21), QPointF(4, 13)]))
            painter.drawEllipse(QRectF(7, 7, 2, 2))
        elif self.symbol == 'compare':
            painter.drawRect(QRectF(3, 4, 7, 16))
            painter.drawRect(QRectF(14, 4, 7, 16))
            painter.drawLine(6, 8, 8, 8)
            painter.drawLine(16, 8, 18, 8)
        elif self.symbol == 'scale':
            painter.drawRoundedRect(QRectF(4, 4, 16, 17), 2, 2)
            painter.drawArc(QRectF(7, 7, 10, 8), 0, 180 * 16)
            painter.drawLine(12, 11, 15, 8)
        elif self.symbol == 'grid':
            for x in (4, 13):
                for y in (4, 13):
                    painter.drawRect(QRectF(x, y, 7, 7))
        else:
            painter.drawRoundedRect(QRectF(5, 3, 14, 18), 1, 1)
            for y in (8, 12, 16):
                painter.drawLine(8, y, 16, y)
        painter.restore()

    def pixmap(self, size, mode, state):
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter=QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


def vector_icon(symbol):
    return QIcon(_VectorEngine(symbol))
