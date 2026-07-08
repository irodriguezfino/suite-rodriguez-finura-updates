from __future__ import annotations

import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.resize(1180, 740)
    window.show()
    app.processEvents()

    command_center = window.findChild(QFrame, "CommandCenter")
    priority_panel = window.findChild(QFrame, "PriorityPanel")
    assert command_center is not None, "Falta centro operativo SaaS en Inicio"
    assert command_center.accessibleName() == "Centro operativo"
    assert priority_panel is not None, "Falta panel compacto de procesos criticos"
    assert priority_panel.accessibleName() == "Procesos criticos"
    assert len(window.findChildren(QPushButton, "PriorityButton")) == 3

    chips = window.findChildren(QFrame, "CommandChip")
    assert len(chips) == 3, f"El centro operativo debe tener 3 chips, tiene {len(chips)}"
    assert window.command_open_value.text() == "0"
    assert window.result_label.accessibleDescription()

    window.open_app(APP_REGISTRY[0])
    app.processEvents()
    assert window.command_open_value.text() == "1", "El contador de abiertos debe reaccionar al abrir un proceso"
    assert window.command_title.text() == "Operacion en curso"

    window.show_dashboard()
    window.resize(900, 700)
    app.processEvents()
    assert not window.priority_panel.isVisible(), "Los accesos criticos deben ocultarse en ancho estrecho"
    assert not window.command_detail.isVisible(), "El detalle del centro operativo debe compactarse"

    window.close()
    print("PHASE21_OK")
    print("saas_dashboard=true")
    print("priority_actions=3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
