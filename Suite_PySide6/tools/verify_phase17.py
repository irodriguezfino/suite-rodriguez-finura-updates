from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.main_window import MainWindow


def main() -> int:
    source = (Path(__file__).resolve().parents[1] / "src" / "suite_pyside6" / "ui" / "main_window.py").read_text(
        encoding="utf-8-sig"
    )
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.resize(1180, 740)
    window.show()
    app.processEvents()

    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Inicio"
    assert not window.process_context.isVisible()
    assert window.sidebar_summary.isVisible()
    assert "_metric_card" not in source
    assert "QTabWidget" in source

    first = APP_REGISTRY[0]
    second = APP_REGISTRY[1]
    window.open_app(first)
    window.open_app(second)
    app.processEvents()

    assert window.tabs.count() == 3
    assert window.tabs.tabText(1) == first.title
    assert window.tabs.tabText(2) == second.title
    assert window.process_context.isVisible()
    assert window.context_app_title.text() == second.title
    assert window.search.isHidden()

    window._close_current_tab()
    app.processEvents()
    assert window.tabs.count() == 2
    assert second.key not in window.app_pages

    window.show_dashboard()
    app.processEvents()
    assert window.tabs.currentIndex() == 0
    assert window.search.isVisible()

    window.close()
    print("PHASE17_OK")
    print("tabbed_shell=true")
    print("top_metrics_removed=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
