from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import APP_REGISTRY, app_by_key
from suite_pyside6.core.precintos_jamones import (
    correction_text,
    gtin12_valido,
    process_precintos_jamones,
    revalidate_corrections,
    save_precintos_csv,
    save_precintos_txt,
    sugerir_precintos,
    weight_filter_text,
)
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.precintos_jamones_window import PrecintosJamonesWindow


def write_official(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["Numero del precinto"])
    ws.append(["123456789012"])
    ws.append(["222222222222"])
    wb.save(path)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert all(item.migration_status == "ported" for item in APP_REGISTRY)
    assert app_by_key("precintos_jamones").migration_status == "ported"
    assert gtin12_valido("123456789012")
    assert gtin12_valido("111111111117")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        txt = tmp_path / "precintos.txt"
        official = tmp_path / "oficial.xlsx"
        csv_path = tmp_path / "precintos.csv"
        txt_path = tmp_path / "precintos_salida.txt"

        txt.write_text(
            "\n".join(
                [
                    "123456;03/07/2026;10:00:00;ART1;123456789012;LOT1;10,5;",
                    "123456;03/07/2026;10:01:00;ART1;123456789012;LOT1;10,6;",
                    "123456;03/07/2026;10:02:00;ART1;111111111117;LOT1;9,5;",
                ]
            ),
            encoding="utf-8-sig",
        )
        write_official(official)

        result = process_precintos_jamones([txt], "Iberico", official)
        assert len(result.validos) == 2
        assert len(result.duplicados) == 1
        assert not result.invalidos
        assert sugerir_precintos("123456789013", result.oficiales)[0] == "123456789012"

        bad_txt = tmp_path / "precintos_bad.txt"
        bad_txt.write_text("ABC;03/07/2026;10:00:00;ART1;111111111117;LOT1;9,5;\n", encoding="utf-8-sig")
        bad_result = process_precintos_jamones([bad_txt], "Iberico")
        assert len(bad_result.invalidos) == 1
        fixed_text = correction_text(bad_result).replace("ABC;", "123456;")
        fixed_result = revalidate_corrections(bad_result, fixed_text)
        assert not fixed_result.invalidos
        assert len(fixed_result.validos) == 1

        assert result.validos[0].hora == "10:01:00"
        extra, missing = result.differences()
        assert extra == {"111111111117"}
        assert missing == {"222222222222"}
        editor, weight_summary, pending = weight_filter_text(result, "10,55", "")
        assert pending
        assert "111111111117" in editor
        assert "Peso minimo: 10,55" in weight_summary

        save_precintos_txt(txt_path, result)
        assert "10:01:00" in txt_path.read_text(encoding="utf-8")
        summary = save_precintos_csv(csv_path, result)
        assert summary is not None and summary.exists()
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        assert "123456789012" in csv_text
        assert "111111111117" in csv_text

        window = PrecintosJamonesWindow()
        window.show_dialogs = False
        window.type_combo.setCurrentText("Iberico")
        window.official_excel = official
        window.set_files([txt])
        app.processEvents()
        assert len(window.result.validos) == 2
        window.weight_min.setText("10,55")
        window.apply_weight_filter()
        app.processEvents()
        assert window.weight_filter_pending
        window.clear_weight_filter()
        app.processEvents()
        assert not window.weight_filter_pending
        attachments = window.save_csv(tmp_path / "window_precintos.csv")
        assert len(attachments) == 2
        window.close()

        correction_window = PrecintosJamonesWindow()
        correction_window.show_dialogs = False
        correction_window.type_combo.setCurrentText("Iberico")
        correction_window.set_files([bad_txt])
        app.processEvents()
        assert correction_window.result.invalidos
        correction_window.preview.setPlainText(correction_text(correction_window.result).replace("ABC;", "123456;"))
        correction_window.revalidate()
        app.processEvents()
        assert not correction_window.result.invalidos
        correction_window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("precintos_jamones"))
    app.processEvents()
    assert "precintos_jamones" in menu.open_windows
    menu.close()

    print("PHASE10_OK")
    print("app_portada=Precintos Jamones")
    print("suite_pyside6_portada=8/8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
