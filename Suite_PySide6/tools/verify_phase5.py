from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.core.palets import clean_and_dedupe, is_valid_code, process_palets_files, validate_corrected_codes
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.palets_window import PaletsWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert app_by_key("palets").migration_status == "ported"
    assert is_valid_code("00781234567890123456")
    assert not is_valid_code("781234567890123456")
    assert clean_and_dedupe(["00111111117890123456", "00222222227890123456"]) == ["222222227890123456"]
    valid, invalid = validate_corrected_codes("# info\n00481234567890123450\n12345678901\n")
    assert valid == ["00481234567890123450"]
    assert invalid == ["12345678901"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        txt = tmp_path / "palets.txt"
        csv_path = tmp_path / "Stock01.csv"
        txt.write_text("00781234567890123456\nCODIGO MALO\n", encoding="utf-8-sig")

        result = process_palets_files([txt])
        assert result.pending_correction
        assert len(result.valid_base) == 1
        assert len(result.issues) == 1

        window = PaletsWindow()
        window.show_dialogs = False
        window.set_files([txt])
        window.process_selected_files()
        app.processEvents()
        assert window.result.pending_correction
        window.review.setPlainText("00481234567890123450")
        window.revalidate()
        app.processEvents()
        assert not window.result.pending_correction
        assert window.result.final_palets == ["781234567890123456", "481234567890123450"]
        window.save_csv_path(csv_path)
        data = csv_path.read_bytes()
        assert data.startswith(b"\xef\xbb\xbf")
        assert b"781234567890123456\r\n" in data
        assert b"481234567890123450\r\n" in data
        window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("palets"))
    app.processEvents()
    assert "palets" in menu.open_windows
    menu.close()

    print("PHASE5_OK")
    print("app_portada=Palets PDA a CSV")
    print("palets_test=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
