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

    intro = window.findChild(QFrame, "DashboardIntro")
    command_card = window.findChild(QFrame, "DashboardCommandCard")
    drop_target = window.findChild(QFrame, "DashboardDropTarget")
    resume_card = window.findChild(QFrame, "DashboardResumeCard")
    activity_panels = window.findChildren(QFrame, "ActivityPanel")
    assert intro is not None, "Falta la introducción operativa de Bandeja"
    assert command_card is not None and drop_target is not None, "Falta el punto principal de carga de archivos"
    assert resume_card is not None, "Falta el área para retomar trabajo"
    assert len(activity_panels) == 2, "Bandeja debe separar actividad reciente y salidas"

    chips = window.findChildren(QFrame, "DsMetric")
    assert len(chips) >= 3, f"El centro operativo debe tener metricas, tiene {len(chips)}"
    rows = window.findChildren(QFrame, "DashboardProcessCard")
    assert 1 <= len(rows) <= 3, f"Bandeja debe mostrar una selección breve de procesos frecuentes, tarjetas={len(rows)}"
    assert window.command_open_value.text() == "0"
    assert window.result_label.accessibleDescription()

    window.open_app(APP_REGISTRY[0])
    app.processEvents()
    assert window.command_open_value.text() == "1", "El contador de abiertos debe reaccionar al abrir un proceso"
    assert window.command_title.text(), "La Bandeja debe conservar un título operativo al abrir un proceso"

    window.show_dashboard()
    window.resize(900, 700)
    app.processEvents()
    assert not window.command_detail.isVisible(), "El detalle del centro operativo debe compactarse"

    window.show_view("procesos")
    app.processEvents()
    module_rows = window.findChildren(QFrame, "ModuleRow")
    assert len(module_rows) == len(APP_REGISTRY), f"El catálogo debe mostrar todos los procesos, filas={len(module_rows)}"

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
    print("operational_inbox=true")
    print(f"dashboard_cards={len(rows)}")
    print(f"module_rows={len(module_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
