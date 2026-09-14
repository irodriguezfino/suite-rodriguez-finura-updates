"""Owned jobs with UI-thread finalization and explicit lifecycle."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Slot, Signal
from PySide6.QtWidgets import QWidget, QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QAbstractButton
from shiboken6 import isValid
from suite_pyside6.core.jobs import JobContext, JobState, JobCancelled, job_scope
from suite_pyside6.ui.job_display import install_job_display

LOGGER = logging.getLogger(__name__)


def operation_active(owner: QWidget) -> bool:
    return bool(owner.property("operationActive"))


class _FunctionWorker(QObject):
    progress = Signal(object)

    def __init__(self, operation: Callable[[], Any], *, cancellable=True) -> None:
        super().__init__()
        self.operation = operation
        self.value: Any = None
        self.error: str | None = None
        self.cancelled = False
        self.context = JobContext(self.progress.emit, cancellable=cancellable)

    @Slot()
    def run(self) -> None:
        try:
            with job_scope(self.context):
                self.context.emit('Procesando — total global aún no disponible', force=True)
                self.value = self.operation()
        except JobCancelled as exc:
            self.cancelled = True
            self.error = str(exc)
        except Exception as exc:
            LOGGER.error("Background operation failed: %s", type(exc).__name__)
            self.error = str(exc) or exc.__class__.__name__
        finally:
            now = time.monotonic()
            context = self.context
            if context.last_phase:
                context.timings[context.last_phase] = context.timings.get(context.last_phase, 0) + now - context.phase_started
            QThread.currentThread().quit()


class _CompletionBridge(QObject):
    """Publish only after thread.finished, clearing busy before callbacks."""
    def __init__(self, owner, thread, worker, succeeded, failed):
        super().__init__(owner)
        self.owner, self.thread, self.worker = owner, thread, worker
        self.succeeded, self.failed = succeeded, failed
        self.started = time.perf_counter()
        self.fields = [(field, field.isEnabled()) for field in owner.findChildren(QWidget)
                       if isinstance(field, (QLineEdit, QComboBox, QAbstractSpinBox)) or
                       isinstance(field, QPlainTextEdit) and not field.isReadOnly() or
                       isinstance(field, QAbstractButton) and "cancel" not in field.text().lower()]
        for field, _enabled in self.fields:
            field.setEnabled(False)

    @Slot(object)
    def progress(self, value):
        if not value.cancellable and self.owner.property('jobState') != 'cancelling':
            self.owner.setProperty('jobState', JobState.COMMITTING.value)
        display = getattr(self.owner, '_job_display', None)
        if display:
            display.progress(value)
        callback = getattr(self.owner, '_update_job_progress', None)
        if callable(callback):
            callback(value)

    @Slot()
    def finish(self) -> None:
        owner, worker, thread = self.owner, self.worker, self.thread
        owner._background_threads = [item for item in owner._background_threads if item is not thread]
        owner.setProperty("operationActive", bool(owner._background_threads))
        owner.setProperty("lastOperationSeconds", time.perf_counter() - self.started)
        owner.setProperty("jobState", JobState.CANCELLED.value if worker.cancelled else JobState.SUCCEEDED.value if worker.error is None else JobState.FAILED.value)
        from suite_pyside6.core.performance_metrics import record_duration
        record_duration(type(owner).__name__, time.perf_counter() - self.started, owner.property("jobState"))
        from suite_pyside6.core.performance_metrics import record_job_details
        record_job_details(type(owner).__name__, worker.context)
        for field, enabled in self.fields:
            if isValid(field):
                field.setEnabled(enabled)
        try:
            if worker.error is None:
                self.succeeded(worker.value)
            else:
                self.failed(worker.error)
        except Exception as exc:
            owner.setProperty('jobState', JobState.FAILED.value)
            LOGGER.error("Operation completion failed: %s", type(exc).__name__)
            from suite_pyside6.ui.polish import show_inline_message
            show_inline_message(owner, "error", f"No se pudo presentar el resultado: {exc}")
        finally:
            display = getattr(owner, '_job_display', None)
            if display:
                display.finish(owner.property('jobState'))
            owner._job_context = None
            worker.context.report = None
            worker.value = None
            worker.operation = None
            self.succeeded = self.failed = None
            thread.deleteLater()
            self.deleteLater()


def run_background(owner: QWidget, operation: Callable[[], Any],
                   succeeded: Callable[[Any], None], failed: Callable[[str], None], *, cancellable=True) -> bool:
    if operation_active(owner):
        return False
    thread = QThread(owner)
    worker = _FunctionWorker(operation, cancellable=cancellable)
    display = install_job_display(owner)
    bridge = _CompletionBridge(owner, thread, worker, succeeded, failed)
    owner._job_context = worker.context
    worker.progress.connect(bridge.progress)
    if display:
        display.start(cancellable)
    thread._suite_worker = worker
    worker.moveToThread(thread)
    owner.setProperty("operationActive", True)
    owner.setProperty("jobState", JobState.RUNNING.value)
    owner._background_threads = [thread]
    thread.started.connect(worker.run)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(bridge.finish)
    thread.start()
    return True

def run_export(owner, operation, completed=None, *, label="Guardando resultado…"):
    """One consistent error boundary; writers receive captured data, never widgets."""
    from suite_pyside6.ui.polish import show_inline_message
    if operation_active(owner):
        show_inline_message(owner, "info", "Ya hay una operación en curso.")
        return False
    owner.status.setText(label)
    def succeeded(value):
        if completed is not None:
            completed(value)
        else:
            owner.status.setText("Resultado guardado correctamente.")
            show_inline_message(owner, "success", "Resultado guardado correctamente.")
        refresh = getattr(owner, "_refresh", None)
        if callable(refresh):
            refresh()
    def failed(message):
        owner.status.setText(f"No se pudo guardar: {message}")
        show_inline_message(owner, "error", "No se guardó el resultado. Conservas los datos para reintentar o elegir otro destino. " + message)
    return run_background(owner, operation, succeeded, failed, cancellable=False)
