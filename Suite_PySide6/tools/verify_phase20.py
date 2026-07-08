from __future__ import annotations

import os
from pathlib import Path
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QTabWidget, QTableWidget

from suite_pyside6.core.precintos_jamones import PrecintosJamonesResult, RegistroJamones
from suite_pyside6.ui.precintos_jamones_window import PrecintosJamonesWindow


def make_registro(linea: int, precinto: str, peso: str = "88,50") -> RegistroJamones:
    return RegistroJamones(
        archivo="precintos.txt",
        linea=linea,
        campos=["P001", "08/07/2026", "09:15:00", "JM001234", precinto, "L001", peso],
        orden=linea,
    )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = PrecintosJamonesWindow()
    window.show()
    app.processEvents()

    assert window.findChild(QTabWidget, "WorkTabs") is None, "Precintos Jamones no debe volver a tabs"
    assert window.findChild(QFrame, "ContextPanel") is None, "El modulo ya tiene rail propio; no debe duplicar contexto"
    table = window.findChild(QTableWidget, "ControlPreviewTable")
    assert table is not None, "Falta tabla operativa de vista previa"
    assert table.accessibleName(), "La tabla necesita nombre accesible"
    progress = window.findChild(QProgressBar, "ControlProgress")
    assert progress is not None, "Falta progreso del flujo"
    assert progress.accessibleName(), "La barra de progreso necesita nombre accesible"

    valid = make_registro(1, "123456789012")
    invalid = make_registro(2, "")
    window.paths = [Path("precintos.txt")]
    window.result = PrecintosJamonesResult(
        selected_files=window.paths,
        tipo_jamon="Blanco",
        validos=[valid],
        invalidos=[(invalid, "Precinto vacio")],
        duplicados=[valid],
    )
    window._refresh()
    app.processEvents()

    assert table.rowCount() == 2, f"La tabla debe reflejar validos e incidencias, filas={table.rowCount()}"
    assert table.item(0, 5).text() == "Valido", "La primera fila debe marcarse como valida"
    assert table.item(1, 5).text().startswith("Pendiente"), "La incidencia debe aparecer como pendiente"
    state = window.findChild(QLabel, "ControlRailState")
    assert state is not None and "Revision" in state.text(), "El rail debe mostrar revision pendiente"
    assert window.issues.isVisible(), "Las incidencias deben estar visibles cuando hay errores"
    assert window.preview.isVisible(), "El editor de correcciones debe estar visible cuando hay errores"

    window.close()
    print("PHASE20_OK")
    print("precintos_jamones_pilot=locked")
    print("table_rows=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
