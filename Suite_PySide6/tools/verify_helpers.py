"""Utilidades compartidas por los verificadores de interfaz.

Las pantallas ejecutan operaciones de archivo en segundo plano. Los
verificadores deben esperar su finalización en vez de asumir que un solo
``processEvents`` convierte el flujo en síncrono.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtWidgets import QApplication


def wait_for(app: QApplication, condition: Callable[[], bool], *, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("La operación en segundo plano no terminó a tiempo")
