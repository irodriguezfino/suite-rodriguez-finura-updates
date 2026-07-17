from __future__ import annotations

import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import APP_REGISTRY, categories
from suite_pyside6.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.processEvents()
    assert len(APP_REGISTRY) == 10
    assert categories() == ("Todas", "Jamones", "Excel / CSV", "Palets y PDA", "Pesos")
    assert window.result_label.text() == "10 procesos disponibles en Todas"
    assert window.category_buttons["Todas"].isChecked()
    window.search.setText("maquilas")
    app.processEvents()
    assert window.result_label.text() == "2 procesos encontrados en Todas"
    window.close()
    print("PHASE2_OK")
    print(f"apps_renderizadas={len(APP_REGISTRY)}")
    print(f"categorias={', '.join(categories())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
