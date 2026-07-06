from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.core.mermas import process_mermas
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.mermas_window import MermasWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert app_by_key("mermas").migration_status == "ported"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        final_csv = tmp_path / "final_fac.csv"
        origin_csv = tmp_path / "origen.csv"
        excel_path = tmp_path / "resultado_mermas.xlsx"

        final_csv.write_text(
            "\n".join(
                [
                    "FAC1;1/2/26;1:2:3;P001;10.5;9.5;1.0;NO",
                    "FAC2;2026-02-02;2:3:4;P001;10.7;9.7;1.0;SI",
                    "FAC3;03-02-2026;3:4:5;P002;20.0;18.0;2.0;NO",
                ]
            ),
            encoding="utf-8-sig",
        )
        origin_csv.write_text(
            "\n".join(
                [
                    "a;b;c;d;P001;LOTE-A",
                    "a;b;c;d;P002;LOTE-B",
                ]
            ),
            encoding="utf-8",
        )

        result = process_mermas([final_csv], origin_csv, "SI")
        assert len(result.dataframe) == 1
        row = result.dataframe.iloc[0]
        assert row["Precinto"] == "P001"
        assert row["Fecha"] == "02/02/2026"
        assert row["Hora"] == "02:03:04"
        assert row["Peso Origen"] == "10,7"
        assert row["LOTE ORIGEN"] == "LOTE-A"
        assert result.summary.filas_leidas == 3
        assert result.summary.precintos_unicos == 2
        assert result.summary.duplicados_detectados == 1
        assert result.summary.total_piezas_si == 1
        assert result.summary.total_piezas_no == 1
        assert result.summary.piezas_resultado_final == 1

        window = MermasWindow()
        window.show_dialogs = False
        window.set_final_files([final_csv])
        window.set_origin_file(origin_csv)
        window.process_files()
        app.processEvents()
        assert len(window.result.dataframe) == 1
        window.save_path(excel_path)
        assert excel_path.exists()
        exported = pd.read_excel(excel_path, sheet_name="Resultado", dtype=str)
        assert exported.iloc[0]["Precinto"] == "P001"
        assert exported.iloc[0]["LOTE ORIGEN"] == "LOTE-A"
        window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("mermas"))
    app.processEvents()
    assert "mermas" in menu.open_windows
    menu.close()

    print("PHASE6_OK")
    print("app_portada=Merma Jamones FAC")
    print("registros_test=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
