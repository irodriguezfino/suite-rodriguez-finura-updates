from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from suite_pyside6.core.apps import APP_REGISTRY, app_by_key
from suite_pyside6.core.paths import LEGACY_SOURCE_DIR
from suite_pyside6.core.precintos_excel import leer_precintos_excel


def crear_xlsx_minimo(ruta: Path) -> None:
    ns_main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ns_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>")
        zf.writestr(
            "xl/workbook.xml",
            f"<workbook xmlns=\"{ns_main}\" xmlns:r=\"{ns_rel}\"><sheets><sheet name=\"Datos\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"worksheet\" Target=\"worksheets/sheet1.xml\"/></Relationships>",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            f"""
            <worksheet xmlns=\"{ns_main}\">
              <sheetData>
                <row r=\"1\"><c r=\"A1\" t=\"inlineStr\"><is><t>Identificacion</t></is></c></row>
                <row r=\"2\"><c r=\"A2\"><v>123456789012</v></c></row>
                <row r=\"3\"><c r=\"A3\"><v>987654321000.0</v></c></row>
              </sheetData>
            </worksheet>
            """,
        )


def main() -> int:
    assert LEGACY_SOURCE_DIR.exists(), f"No existe fuente legacy: {LEGACY_SOURCE_DIR}"
    assert app_by_key("exportar_precintos_excel").migration_status in {"core-started", "ported"}
    assert len(APP_REGISTRY) >= 8
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "precintos.xlsx"
        crear_xlsx_minimo(ruta)
        precintos, hoja = leer_precintos_excel(ruta)
    assert hoja == "Datos"
    assert precintos == ["123456789012", "987654321000"]
    print("PHASE1_OK")
    print(f"apps_registradas={len(APP_REGISTRY)}")
    print(f"fuente_legacy={LEGACY_SOURCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
