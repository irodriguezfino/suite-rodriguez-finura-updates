"""State-based waits for real asynchronous operations, not fixed delays."""
import time
from PySide6.QtCore import QEventLoop, QTimer


def wait_for_jobs(window, timeout=15):
    deadline = time.monotonic() + timeout
    while window.property('operationActive') or any(
        timer is not None and timer.isActive()
        for timer in [getattr(window, '_weight_timer', None)]
    ):
        if time.monotonic() >= deadline:
            raise AssertionError('La operación no terminó dentro del plazo')
        loop = QEventLoop()
        QTimer.singleShot(10, loop.quit)
        loop.exec()
