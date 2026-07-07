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

    for target in APP_REGISTRY:
        window.open_app(target)
        app.processEvents()

        embedded = window.app_pages[target.key]
        assert window.stack.currentWidget() is embedded
        assert embedded.parentWidget() is window.stack
        assert not embedded.isWindow()
        assert window.home_button.isVisible()
        assert window.workspace_title.text() == target.title

        window.show_dashboard()
        app.processEvents()
        assert window.stack.currentWidget() is window.dashboard_page
        assert not window.home_button.isVisible()

    window.close()
    print("PHASE11_OK")
    print(f"apps_integradas={len(APP_REGISTRY)}")
    print("ventana_unica=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
