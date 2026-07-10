from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame

from suite_pyside6.core.apps import APP_REGISTRY
from suite_pyside6.core.pesos import OLD_EXCEL_EXTENSIONS, SUPPORTED_EXTENSIONS
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.pesos_window import PesosWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.resize(1180, 740)
    window.show()
    app.processEvents()

    hero_panel = window.findChild(QFrame, "HeroPanel")
    modules_panel = window.findChild(QFrame, "ModulesPanel")
    activity_panel = window.findChild(QFrame, "ActivityPanel")
    assert hero_panel is not None, "Falta hero operativo SaaS en Inicio"
    assert modules_panel is not None, "Falta panel de modulos como workspace"
    assert activity_panel is not None, "Falta panel lateral de actividad"

    chips = window.findChildren(QFrame, "DsMetric")
    assert len(chips) >= 3, f"El centro operativo debe tener metricas, tiene {len(chips)}"
    rows = window.findChildren(QFrame, "ModuleRow")
    assert len(rows) == len(APP_REGISTRY), f"Debe mostrar los modulos como filas operativas, filas={len(rows)}"
    assert window.command_open_value.text() == "0"
    assert window.result_label.accessibleDescription()

    window.open_app(APP_REGISTRY[0])
    app.processEvents()
    assert window.command_open_value.text() == "1", "El contador de abiertos debe reaccionar al abrir un proceso"
    assert window.command_title.text() == "Operación en curso"

    window.show_dashboard()
    window.resize(900, 700)
    app.processEvents()
    assert not window.command_detail.isVisible(), "El detalle del centro operativo debe compactarse"

    window.close()

    assert ".xls" in SUPPORTED_EXTENSIONS, "Pesos debe aceptar archivos .xls"
    assert ".xls" not in OLD_EXCEL_EXTENSIONS, "Pesos no debe tratar .xls como formato ignorado"
    with tempfile.TemporaryDirectory() as tmp:
        xls = Path(tmp) / "pesos.xls"
        xls.write_bytes(b"placeholder")
        pesos = PesosWindow()
        pesos.set_files([xls])
        app.processEvents()
        assert "Excel procesables: 1" in pesos.summary.text()
        pesos.close()

    print("PHASE21_OK")
    print("saas_workspace=true")
    print(f"module_rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
