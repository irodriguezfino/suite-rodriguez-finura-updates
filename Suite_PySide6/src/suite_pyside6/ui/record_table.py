"""Virtual rows: data stays in Python; Qt paints only the visible cells."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QEvent
from PySide6.QtGui import QKeySequence, QPainter
from PySide6.QtWidgets import QTableView, QStyledItemDelegate, QStyleOptionButton, QStyle, QAbstractItemView, QApplication


class RecordModel(QAbstractTableModel):
    def __init__(self, view, columns):
        super().__init__(view)
        self.view, self.columns, self.rows, self.keys = view, columns, [], []
        self.checks = {}
        self.actions = {}
        self.editable = lambda key: True

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self.columns[section] if orientation == Qt.Horizontal else str(section + 1)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        key = self.keys[row]
        if role in (Qt.DisplayRole, Qt.AccessibleTextRole):
            return self.rows[row][column]
        if role == Qt.UserRole:
            return str(key)
        if role == Qt.ToolTipRole:
            return str(key) if column == 0 else self.rows[row][column]
        if role == Qt.CheckStateRole and column in self.checks:
            return Qt.Checked if self.checks[column][0](key) else Qt.Unchecked

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() in self.checks and self.editable(self.keys[index.row()]) and not self.view.busy():
            flags |= Qt.ItemIsUserCheckable
        return flags

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.CheckStateRole or not (self.flags(index) & Qt.ItemIsUserCheckable):
            return False
        self.checks[index.column()][1](self.keys[index.row()], value == Qt.Checked or value == Qt.Checked.value)
        self.dataChanged.emit(self.index(index.row(), 0), self.index(index.row(), len(self.columns)-1))
        return True


class ActionDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        button = QStyleOptionButton()
        button.rect = option.rect.adjusted(6, 4, -6, -4)
        button.text = index.data()
        button.palette = option.palette
        button.state = QStyle.State_Enabled if not index.model().view.busy() else QStyle.State_None
        if option.state & QStyle.State_HasFocus:
            button.state |= QStyle.State_HasFocus
        QApplication.style().drawControl(QStyle.CE_PushButton, button, painter)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and option.rect.contains(event.position().toPoint()):
            return model.view.activate(index)
        return False


class RecordTable(QTableView):
    def __init__(self, columns, owner):
        super().__init__(owner)
        self.owner = owner
        self.records = RecordModel(self, columns)
        self.setModel(self.records)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setTabKeyNavigation(True)
        self.setWordWrap(False)
        self.setShowGrid(False)
        self.setTextElideMode(Qt.ElideMiddle)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(42)
        self.horizontalHeader().setResizeContentsPrecision(50)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.records.rowCount():
            painter = QPainter(self.viewport())
            painter.setPen(self.palette().text().color())
            painter.drawText(self.viewport().rect().adjusted(24, 16, -24, -16),
                             Qt.AlignCenter | Qt.TextWordWrap,
                             self.property('emptyText') or 'No hay registros para mostrar.')
            painter.end()

    def busy(self):
        return bool(self.owner.property('operationActive'))

    def set_records(self, keys, rows):
        selected = {self.records.keys[index.row()] for index in self.selectionModel().selectedRows()}
        current = self.currentIndex()
        current_key = self.records.keys[current.row()] if current.isValid() else None
        scroll = self.verticalScrollBar().value()
        self.records.beginResetModel()
        self.records.keys, self.records.rows = list(keys), list(rows)
        self.records.endResetModel()
        from PySide6.QtCore import QItemSelectionModel
        for row, key in enumerate(self.records.keys):
            index = self.records.index(row, max(0, current.column()))
            if key == current_key:
                self.selectionModel().setCurrentIndex(index, QItemSelectionModel.NoUpdate)
            if key in selected:
                self.selectionModel().select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        self.verticalScrollBar().setValue(scroll)

    def set_action(self, column, callback):
        self.records.actions[column] = callback
        self.setItemDelegateForColumn(column, ActionDelegate(self))

    def activate(self, index):
        if not index.isValid() or self.busy():
            return False
        action = self.records.actions.get(index.column())
        if action:
            action(self.records.keys[index.row()])
            return True
        if index.column() in self.records.checks:
            value = Qt.Unchecked if index.data(Qt.CheckStateRole) == Qt.Checked else Qt.Checked
            return self.records.setData(index, value, Qt.CheckStateRole)
        return False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter) and self.activate(self.currentIndex()):
            event.accept()
            return
        if event.matches(QKeySequence.Copy):
            indexes = self.selectedIndexes()
            rows = sorted({index.row() for index in indexes})
            QApplication.clipboard().setText('\n'.join('\t'.join(str(v) for v in self.records.rows[row]) for row in rows))
            return
        super().keyPressEvent(event)

    # Read-only accessors used by the shared count/selection helpers.
    def rowCount(self):
        return self.records.rowCount()

    def columnCount(self):
        return self.records.columnCount()

    def currentRow(self):
        return self.currentIndex().row()

    def item(self, row, column):
        index = self.records.index(row, column)
        if not index.isValid():
            return None
        return _Cell(index)


class _Cell:
    def __init__(self, index):
        self.index = index

    def text(self):
        return str(self.index.data() or '')

    def data(self, role):
        return self.index.data(role)
