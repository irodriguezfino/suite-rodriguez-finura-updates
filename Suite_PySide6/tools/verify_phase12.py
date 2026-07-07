from __future__ import annotations

import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.metric_values["ready"].text() == str(len(APP_REGISTRY))
    assert window.open_processes_panel.findChild(QLabel, "DashboardEmpty") is not None

    first = APP_REGISTRY[1]
    second = APP_REGISTRY[2]
    window.open_app(first)
    window.open_app(second)
    app.processEvents()
    window.show_dashboard()
    app.processEvents()

    open_buttons = [
        button.text()
        for button in window.open_processes_panel.findChildren(QPushButton)
        if button.property("dashboardAction")
    ]
    recent_buttons = [
        button.text()
        for button in window.recent_activity_panel.findChildren(QPushButton)
        if button.property("dashboardAction")
    ]
    assert first.title in open_buttons
    assert second.title in open_buttons
    assert second.title in recent_buttons
    assert int(window.metric_values["recent"].text()) >= 2

    window.close()
    print("PHASE12_OK")
    print("dashboard_operativo=true")
    print(f"procesos_abiertos={len(open_buttons)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
