from __future__ import annotations

import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.metric_values["ready"].text() == str(len(APP_REGISTRY))
    assert hasattr(window, "continue_strip")
    assert not hasattr(window, "open_processes_panel")

    first = APP_REGISTRY[1]
    second = APP_REGISTRY[2]
    window.open_app(first)
    window.open_app(second)
    app.processEvents()
    window.show_dashboard()
    app.processEvents()

    assert window.continue_strip.isVisible()
    assert second.title in window.continue_title.text()
    assert window._continue_app_key == second.key
    assert "Abiertos 2" in window.continue_activity.text()
    assert int(window.metric_values["recent"].text()) >= 2

    window.close()
    print("PHASE12_OK")
    print("dashboard_compacto=true")
    print(f"continuar={window._continue_app_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
