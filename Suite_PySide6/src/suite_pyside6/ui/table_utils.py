from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from PySide6.QtWidgets import QLabel, QTableWidget


@contextmanager
def bulk_table_update(table: QTableWidget, *, block_signals: bool = True) -> Iterator[None]:
    updates_enabled = table.updatesEnabled()
    signals_blocked = table.signalsBlocked()
    sorting_enabled = table.isSortingEnabled()
    table.setSortingEnabled(False)
    table.setUpdatesEnabled(False)
    if block_signals:
        table.blockSignals(True)
    try:
        yield
    finally:
        table.setSortingEnabled(sorting_enabled)
        if block_signals:
            table.blockSignals(signals_blocked)
        table.setUpdatesEnabled(updates_enabled)
        update_table_accessibility(table)
        table.viewport().update()


def update_table_accessibility(table: QTableWidget) -> None:
    row_count = table.rowCount()
    column_count = table.columnCount()
    headers = [
        table.horizontalHeaderItem(index).text()
        for index in range(column_count)
        if table.horizontalHeaderItem(index) is not None and table.horizontalHeaderItem(index).text()
    ]
    row_text = "sin filas" if row_count == 0 else f"{row_count} fila{'s' if row_count != 1 else ''}"
    column_text = f"{column_count} columna{'s' if column_count != 1 else ''}"
    header_text = f" Columnas: {', '.join(headers[:8])}." if headers else ""
    if table.property("allowCellEditing"):
        suffix = " Usa Tab para entrar en la tabla, las flechas para recorrer filas, Mayús o Ctrl para ampliar selección, Ctrl+C para copiar y Enter o doble clic para editar celdas editables."
        kind = "Tabla editable"
    else:
        suffix = " Usa Tab para entrar en la tabla, las flechas para recorrer filas, Mayús o Ctrl para ampliar selección y Ctrl+C para copiar."
        kind = "Tabla de revisión"
    table.setAccessibleDescription(f"{kind} con {row_text} y {column_text}.{header_text}{suffix}")


def visible_count_text(shown: int, total: int, unit: str) -> str:
    unit_text = unit[:-1] if total == 1 and unit.endswith("s") else unit
    if total <= 0:
        return f"0 {unit}"
    if shown >= total:
        return f"{total} {unit_text}"
    return f"{shown} de {total} {unit}"


def update_count_label(label: QLabel, shown: int, total: int, unit: str) -> None:
    text = visible_count_text(shown, total, unit)
    unit_text = unit[:-1] if total == 1 and unit.endswith("s") else unit
    label.setText(text)
    if total > shown:
        detail = f"Vista parcial: se muestran {shown} de {total} {unit} para mantener la interfaz fluida."
    else:
        detail = f"Vista completa: {total} {unit_text}."
    label.setToolTip(detail)
    label.setAccessibleName(text)
    label.setAccessibleDescription(detail)
