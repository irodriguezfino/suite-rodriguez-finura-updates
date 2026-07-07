from __future__ import annotations

import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QBoxLayout

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.processEvents()

    target = next(item for item in APP_REGISTRY if item.key == "txt_csv")
    window.open_app(target)
    app.processEvents()
    window._update_process_context()

    assert window.process_context.isVisible()
    assert window.process_state.text().startswith("Estado:")
    assert window.process_next.text().startswith("Siguiente:")
    assert window.process_alerts.text().startswith("Avisos:")
    assert window.next_action_button.text()

    window.resize(1024, 700)
    app.processEvents()
    assert window.header_layout.direction() == QBoxLayout.TopToBottom

    window.show_dashboard()
    app.processEvents()
    assert not window.process_context.isVisible()

    window.close()
    print("PHASE13_OK")
    print("contexto_global=true")
    print(f"siguiente={window.next_action_button.text()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
