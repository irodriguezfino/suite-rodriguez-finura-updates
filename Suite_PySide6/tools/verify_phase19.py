from __future__ import annotations

import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLineEdit, QPushButton

from suite_pyside6.ui.app_windows import WINDOW_CLASSES


MAX_INITIAL_VISIBLE_BUTTONS = {
    "control_recepcion_maquilas": 4,
    "precintos_jamones": 5,
    "recepcion_maquilas": 5,
}


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    checked = 0
    for key, window_class in WINDOW_CLASSES.items():
        window = window_class()
        window.show()
        app.processEvents()
        toolbar = window.findChild(QFrame, "Toolbar")
        assert toolbar is not None, f"{key} no tiene toolbar"
        visible_buttons = [button for button in toolbar.findChildren(QPushButton) if button.isVisible()]
        visible_disabled = [button.text() for button in visible_buttons if not button.isEnabled()]
        assert len(visible_buttons) <= MAX_INITIAL_VISIBLE_BUTTONS.get(key, 6), (
            f"{key} tiene demasiados botones visibles iniciales: "
            + ", ".join(button.text() for button in visible_buttons)
        )
        assert len(visible_disabled) <= 1, f"{key} muestra demasiados botones bloqueados: {visible_disabled}"
        floating_fields = [field.placeholderText() for field in toolbar.findChildren(QLineEdit) if field.isVisible()]
        assert len(floating_fields) <= 1, f"{key} muestra demasiados campos sueltos en toolbar: {floating_fields}"
        checked += 1
    print("PHASE19_OK")
    print("initial_toolbar_noise=controlled")
    print(f"windows_checked={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
