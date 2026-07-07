from __future__ import annotations

import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.app_windows import WINDOW_CLASSES
from suite_pyside6.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.resize(1024, 700)
    window.show()
    app.processEvents()

    assert len(WINDOW_CLASSES) == len(APP_REGISTRY)
    assert window.sidebar.maximumWidth() <= 176
    assert window.nav_title.text() == "SRF"
    assert window.category_buttons["Excel / CSV"].text().startswith("CSV")

    window.open_app(APP_REGISTRY[0])
    app.processEvents()
    assert window.app_pages[APP_REGISTRY[0].key].minimumWidth() == 0
    assert window._column_count() <= 2

    window.close()
    print("PHASE14_OK")
    print("responsive_profesional=true")
    print(f"ventanas_registradas={len(WINDOW_CLASSES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
