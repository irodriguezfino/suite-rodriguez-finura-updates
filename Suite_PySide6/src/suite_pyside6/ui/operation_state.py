"""Operation lifecycle, close protection and desktop input affordances."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget, QMainWindow, QDialog, QMessageBox, QLineEdit, QComboBox, QPlainTextEdit, QTableWidget, QPushButton, QMenu

def _mark_work_in_progress(widget: QWidget) -> None:
    revision = int(widget.property("closeWorkRevision") or 0) + 1
    widget.setProperty("closeWorkRevision", revision)


def _guard_input_changes(widget: QWidget) -> None:
    from .polish import show_inline_message
    """The same busy policy for direct calls, drops and toolbar actions."""
    if widget.property("inputChangesGuarded"):
        return
    widget.setProperty("inputChangesGuarded", True)
    names = ("set_files", "set_txt_files", "set_final_files", "set_origin_file",
             "set_txt_file", "set_seals_file", "load_path", "select_official",
             "select_seals", "add_fac_paths", "remove_fac_path", "revalidate",
             "apply_weight_filter", "clear_corrections", "clear", "clear_fac", "clear_weight_filter")
    for name in names:
        original = getattr(widget, name, None)
        if not callable(original):
            continue
        def guarded(*args, _original=original, **kwargs):
            if widget.property("operationActive") or _has_running_worker(widget):
                show_inline_message(widget, "info", "Espera a que termine la operación antes de cambiar sus datos.")
                return None
            widget.setProperty("jobState", "idle")
            display = getattr(widget, "_job_display", None)
            if display:
                display.hide()
            return _original(*args, **kwargs)
        setattr(widget, name, guarded)


def _patch_button_work_state(button: QPushButton, widget: QWidget) -> None:
    if button.property("workStatePatched"):
        return
    button.setProperty("workStatePatched", True)


def _patch_field_work_state(field: QWidget, widget: QWidget) -> None:
    if field.property("workStatePatched"):
        return
    if isinstance(field, QLineEdit):
        field.textEdited.connect(lambda _text, _widget=widget: _mark_work_in_progress(_widget))
    elif isinstance(field, QComboBox):
        field.activated.connect(lambda _index, _widget=widget: _mark_work_in_progress(_widget))
    elif isinstance(field, QPlainTextEdit) and not field.isReadOnly():
        field.textChanged.connect(lambda _widget=widget: _mark_work_in_progress(_widget))
    elif isinstance(field, QTableWidget) and field.property("allowCellEditing"):
        field.itemChanged.connect(lambda _item, _widget=widget: _mark_work_in_progress(_widget))
    field.setProperty("workStatePatched", True)

def _install_table_desktop_affordances(table: QTableWidget, widget: QWidget) -> None:
    if table.property("desktopAffordancesPatched"):
        return
    table.setContextMenuPolicy(Qt.CustomContextMenu)
    table.setToolTip("Selecciona filas con Mayús o Ctrl. Copia la selección con Ctrl+C.")

    copy_action = QAction("Copiar selección", table)
    copy_action.setShortcut(QKeySequence.Copy)
    copy_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
    copy_action.triggered.connect(lambda _checked=False, _table=table, _widget=widget: _copy_table_selection(_table, _widget))
    table.addAction(copy_action)

    def show_menu(position, *, _table=table, _widget=widget) -> None:
        menu = QMenu(_table)
        action = menu.addAction("Copiar selección")
        action.setEnabled(bool(_table.selectedIndexes()) or _table.currentRow() >= 0)
        action.triggered.connect(lambda _checked=False: _copy_table_selection(_table, _widget))
        menu.exec(_table.viewport().mapToGlobal(position))

    table.customContextMenuRequested.connect(show_menu)
    table.setProperty("desktopAffordancesPatched", True)


def _copy_table_selection(table: QTableWidget, widget: QWidget) -> None:
    from .polish import show_inline_message
    text = _table_selection_text(table)
    if not text:
        return
    app = QApplication.instance()
    if app is None:
        return
    app.clipboard().setText(text)
    show_inline_message(widget, "info", "Selección copiada al portapapeles.")


def _table_selection_text(table: QTableWidget) -> str:
    indexes = table.selectedIndexes()
    if not indexes and table.currentRow() >= 0:
        row = table.currentRow()
        indexes = [table.model().index(row, column) for column in range(table.columnCount())]
    if not indexes:
        return ""
    rows = sorted({index.row() for index in indexes})
    columns = sorted({index.column() for index in indexes})
    selected = {(index.row(), index.column()) for index in indexes}
    lines: list[str] = []
    for row in rows:
        values: list[str] = []
        for column in columns:
            if (row, column) not in selected:
                values.append("")
                continue
            item = table.item(row, column)
            values.append("" if item is None else item.text())
        lines.append("\t".join(values))
    return "\n".join(lines)

def confirm_discard_work(widget: QWidget, title: str = "Descartar cambios") -> bool:
    reason = close_risk_reason(widget)
    if not reason:
        return True
    app = QApplication.instance()
    if app is not None and app.platformName().lower() == "offscreen":
        return True
    if not getattr(widget, "show_dialogs", True):
        return True
    dialog = QMessageBox(QMessageBox.Warning, title, reason, parent=widget)
    safe = dialog.addButton("Seguir trabajando", QMessageBox.RejectRole)
    discard_label = "Cerrar sin guardar" if title == "Cerrar ventana" else "Descartar trabajo"
    discard = dialog.addButton(discard_label, QMessageBox.DestructiveRole)
    dialog.setDefaultButton(safe)
    dialog.exec()
    return dialog.clickedButton() is discard


def _install_close_guard(widget: QWidget) -> None:
    if not isinstance(widget, (QMainWindow, QDialog)) or widget.property("closeGuardPatched"):
        return
    original_close_event = widget.closeEvent

    def close_event(event, *, _widget=widget, _original=original_close_event) -> None:
        if _widget.property("operationActive") or _has_running_worker(_widget):
            # Never detach a QMainWindow which owns a running QThread.  Qt will
            # abort the entire process if the thread is destroyed underneath it.
            if getattr(_widget, "show_dialogs", True) and QApplication.instance() is not None and QApplication.instance().platformName().lower() != "offscreen":
                QMessageBox.information(
                    _widget,
                    "Operación en curso",
                    "La operación actual sigue trabajando. Espera a que finalice o usa Cancelar cuando esté disponible.",
                )
            event.ignore()
            return
        if confirm_discard_work(_widget, "Cerrar ventana"):
            flush = getattr(_widget, "flush_pending_preferences", None)
            if callable(flush):
                flush()
            _original(event)
        else:
            event.ignore()

    widget.closeEvent = close_event  # type: ignore[method-assign]
    widget.setProperty("closeGuardPatched", True)


def _has_running_worker(widget: QWidget) -> bool:
    """Detect worker threads without coupling the shared close guard to each app."""
    thread = getattr(widget, "_thread", None)
    if thread is not None and hasattr(thread, "isRunning") and thread.isRunning():
        return True
    threads = getattr(widget, "_background_threads", ())
    return any(thread is not None and hasattr(thread, "isRunning") and thread.isRunning() for thread in threads)


def _install_desktop_shortcuts(widget: QWidget) -> None:
    if widget.property("desktopShortcutsPatched"):
        return
    cancel_action = QAction(widget)
    cancel_action.setShortcut("Esc")
    cancel_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
    cancel_action.triggered.connect(lambda _checked=False, _widget=widget: _cancel_transient_state(_widget))
    widget.addAction(cancel_action)
    widget.setProperty("desktopShortcutsPatched", True)


def _cancel_transient_state(widget: QWidget) -> None:
    from .polish import clear_inline_message, focus_next_action
    from suite_pyside6.ui.job_display import request_cancel
    if request_cancel(widget):
        return
    focused = QApplication.focusWidget()
    if focused is not None and (focused is widget or widget.isAncestorOf(focused)):
        focused.clearFocus()
    clear_inline_message(widget)
    focus_next_action(widget)


def close_risk_reason(widget: QWidget) -> str:
    """Describe el riesgo real de cierre; un archivo sólo seleccionado no basta."""
    if widget.property("operationActive") or _has_running_worker(widget):
        return "Hay una operación en curso. Cerrar ahora puede dejarla incompleta."
    snapshot = _pending_work_snapshot(widget)
    if not snapshot or snapshot == str(widget.property("closeSafeSnapshot") or ""):
        return ""
    if getattr(widget, "weight_filter_pending", False) or _has_editable_correction(widget):
        return "Hay correcciones o cambios sin guardar. Si cierras ahora, se perderán."
    return "Los datos procesados todavía no se han exportado. Si cierras ahora, tendrás que procesarlos de nuevo."


def _pending_work_snapshot(widget: QWidget) -> str:
    parts: list[str] = []
    result = getattr(widget, "result", None)
    if _result_has_work(result):
        parts.append(f"result:{id(result)}")
    adjustment = getattr(widget, "adjustment", None)
    if adjustment is not None:
        # En Reparto, el análisis inicial es una vista previa reproducible. Solo
        # pasa a ser trabajo pendiente cuando ya hay un ajuste calculado.
        source_result = getattr(widget, "source_result", None)
        if _result_has_work(source_result):
            parts.append(f"source:{id(source_result)}")
        parts.append(f"adjustment:{id(adjustment)}")
    if getattr(widget, "weight_filter_pending", False):
        parts.append("weight-filter")
    if _has_editable_correction(widget):
        parts.append(f"revision:{int(widget.property('closeWorkRevision') or 0)}")
    return "|".join(parts)


def _result_has_work(result: object) -> bool:
    if result is None:
        return False
    for attr in (
        "precintos", "processed_lines", "validos", "invalidos", "duplicados", "issues",
        "final_palets", "registros_txt", "salidas", "records", "processed_excels", "results",
        "valid_base", "detected", "log_lines",
    ):
        if getattr(result, attr, None):
            return True
    if getattr(result, "pending_correction", False):
        return True
    dataframe = getattr(result, "dataframe", None)
    return dataframe is not None and hasattr(dataframe, "empty") and not dataframe.empty


def _has_editable_correction(widget: QWidget) -> bool:
    result = getattr(widget, "result", None)
    correction_expected = bool(
        getattr(result, "invalidos", None)
        or getattr(result, "issues", None)
        or getattr(result, "pending_correction", False)
    )
    if not correction_expected:
        return False
    return any(not editor.isReadOnly() and editor.toPlainText().strip() for editor in widget.findChildren(QPlainTextEdit))


def _has_pending_work(widget: QWidget) -> bool:
    """Compatibilidad interna para consumidores anteriores del guard."""
    return bool(close_risk_reason(widget))

