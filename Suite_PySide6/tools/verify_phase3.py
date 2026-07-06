from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.precintos_excel_window import PrecintosExcelWindow

from verify_phase1 import crear_xlsx_minimo


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert app_by_key("exportar_precintos_excel").migration_status == "ported"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        xlsx = tmp_path / "precintos.xlsx"
        csv_path = tmp_path / "precintos.csv"
        ignored = tmp_path / "documento.pdf"
        ignored.write_text("no excel", encoding="utf-8")
        crear_xlsx_minimo(xlsx)

        window = PrecintosExcelWindow()
        window.set_files([xlsx, ignored])
        window.process_selected_files()
        app.processEvents()
        assert window.result.precintos == ["123456789012", "987654321000"]
        assert len(window.result.ignored_files) == 1
        assert "2 precintos" in window.status.text()
        window.save_csv_path(csv_path)
        assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
        assert csv_path.read_text(encoding="utf-8-sig") == "123456789012\n987654321000\n"
        window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("exportar_precintos_excel"))
    app.processEvents()
    assert "exportar_precintos_excel" in menu.open_windows
    menu.close()

    print("PHASE3_OK")
    print("app_portada=Precintos Excel a CSV")
    print("precintos_test=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

