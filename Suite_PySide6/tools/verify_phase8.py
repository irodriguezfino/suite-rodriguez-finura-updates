from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.core.recepcion_maquilas import process_recepcion_maquilas
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.recepcion_maquilas_window import RecepcionMaquilasWindow


def write_seals(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["Albaran", "Codigo de articulo", "Nombre del producto", "Numero de lote", "Numero del precinto"])
    ws.append(["ALB1", "FAC1", "Jamon Duroc", "LOT1", "111111111111"])
    ws.append(["ALB1", "FAC1", "Jamon Duroc", "LOT1", "333333333333"])
    wb.save(path)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert app_by_key("recepcion_maquilas").migration_status == "ported"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        txt = tmp_path / "recepcion.txt"
        seals = tmp_path / "SealsReport.xlsx"
        config = tmp_path / "config_articulos.csv"
        pdf_diff = tmp_path / "diferencias.pdf"
        pdf_ranges = tmp_path / "rangos.pdf"
        both_folder = tmp_path / "ambos"

        txt.write_text(
            "\n".join(
                [
                    "PART1;030726;10:00:00;FAC1;111111111111;LOT1;10,50;",
                    "PART1;030726;10:00:01;FAC1;222222222222;LOT1;10,20;",
                ]
            ),
            encoding="utf-8-sig",
        )
        config.write_text("Codigo;Nombre\nFAC1;JAMON DUROC 10-11\n", encoding="utf-8-sig")
        write_seals(seals)

        result = process_recepcion_maquilas(txt, seals, config)
        assert result.partida == "PART1"
        assert len(result.registros_txt) == 2
        assert len(result.registros_oficiales) == 2
        assert len(result.solo_txt) == 1
        assert result.solo_txt[0].precinto == "222222222222"
        assert len(result.solo_oficial) == 1
        assert result.solo_oficial[0].precinto == "333333333333"
        assert len(result.filas_rangos) == 1
        assert result.filas_rangos[0].piezas == 2

        window = RecepcionMaquilasWindow()
        window.show_dialogs = False
        window.config_file = config
        window.set_txt_file(txt)
        window.set_seals_file(seals)
        window.process_files()
        app.processEvents()
        assert len(window.result.filas_rangos) == 1
        window.save_diff_pdf(pdf_diff)
        window.save_ranges_pdf(pdf_ranges)
        both_diff, both_ranges = window.save_both_pdfs(both_folder)
        assert pdf_diff.read_bytes().startswith(b"%PDF")
        assert pdf_ranges.read_bytes().startswith(b"%PDF")
        assert both_diff.read_bytes().startswith(b"%PDF")
        assert both_ranges.read_bytes().startswith(b"%PDF")
        window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("recepcion_maquilas"))
    app.processEvents()
    assert "recepcion_maquilas" in menu.open_windows
    menu.close()

    print("PHASE8_OK")
    print("app_portada=Recepcion Maquilas")
    print("pdfs_test=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
