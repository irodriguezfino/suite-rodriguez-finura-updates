"""Safe, small QThread wrapper for file, network and printer operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QWidget


class _FunctionWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self._operation())
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
        finally:
            # The worker owns the execution path, so stopping from this thread
            # does not depend on delivery of a cross-thread Python callback.
            QThread.currentThread().quit()


class _CompletionBridge(QObject):
    """A QObject receiver guarantees that UI callbacks run on the UI thread."""

    def __init__(self, succeeded: Callable[[Any], None], failed: Callable[[str], None], parent: QWidget) -> None:
        super().__init__(parent)
        self._succeeded = succeeded
        self._failed = failed

    @Slot(object)
    def deliver_success(self, value: Any) -> None:
        self._succeeded(value)

    @Slot(str)
    def deliver_failure(self, message: str) -> None:
        self._failed(message)


def run_background(
    owner: QWidget,
    operation: Callable[[], Any],
    succeeded: Callable[[Any], None],
    failed: Callable[[str], None],
) -> bool:
    """Run one operation and keep its Qt objects alive until they terminate.

    The owner exposes the thread list to the shared close guard, so a page can
    never be detached while its worker is running.
    """
    threads = list(getattr(owner, "_background_threads", ()))
    if any(thread.isRunning() for thread in threads):
        return False
    thread = QThread(owner)
    worker = _FunctionWorker(operation)
    bridge = _CompletionBridge(succeeded, failed, owner)
    # Qt owns the C++ object after moveToThread, but Python can otherwise
    # collect its wrapper before ``started`` is delivered.
    setattr(thread, "_suite_worker", worker)
    worker.moveToThread(thread)
    owner.setProperty("operationActive", True)
    threads.append(thread)
    setattr(owner, "_background_threads", threads)
    thread.started.connect(worker.run)
    worker.succeeded.connect(bridge.deliver_success)
    worker.failed.connect(bridge.deliver_failure)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    def settle() -> None:
        active = [item for item in getattr(owner, "_background_threads", ()) if item is not thread and item.isRunning()]
        setattr(owner, "_background_threads", active)
        owner.setProperty("operationActive", bool(active))

    thread.finished.connect(settle)
    thread.start()
    return True
