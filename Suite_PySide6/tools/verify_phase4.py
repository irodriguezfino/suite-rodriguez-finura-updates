from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.core.txt_csv import format_decimal_2, process_line, process_txt_files
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.txt_csv_window import TxtCsvWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert app_by_key("txt_csv").migration_status == "ported"
    assert format_decimal_2("1,2") == "1,20"
    assert format_decimal_2("texto") == "texto"
    assert process_line("A;B;1,2;") == "A;B;1,20;"
    assert process_line("A;B;1.234") == "A;B;1,23"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        txt = tmp_path / "entrada.txt"
        csv_path = tmp_path / "salida.csv"
        txt.write_text("A;B;1,2;\n\n;;;;\nC;D;3.456\n", encoding="utf-8-sig")

        result = process_txt_files([txt])
        assert result.processed_lines == ["A;B;1,20;", "C;D;3,46"]

        window = TxtCsvWindow()
        window.set_files([txt])
        window.process_selected_files()
        app.processEvents()
        assert window.result.processed_lines == result.processed_lines
        assert "2 linea" in window.status.text()
        window.save_csv_path(csv_path)
        assert csv_path.read_text(encoding="utf-8") == "A;B;1,20;\nC;D;3,46\n"
        window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("txt_csv"))
    app.processEvents()
    assert "txt_csv" in menu.open_windows
    menu.close()

    print("PHASE4_OK")
    print("app_portada=Procesador TXT a CSV")
    print("lineas_test=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

