from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.core.control_recepcion_maquilas import (
    correction_text,
    parsear_destinatarios,
    process_control_txt,
    revalidate_corrections,
    run_recepcion_with_seals,
    save_pdf_rangos,
    save_txt_ax,
    validar_destinatarios,
    weight_filter_text,
)
from suite_pyside6.ui.control_recepcion_maquilas_window import ControlRecepcionMaquilasWindow
from suite_pyside6.ui.main_window import MainWindow


def write_seals(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["Albaran", "Codigo de articulo", "Nombre del producto", "Numero de lote", "Numero del precinto"])
    ws.append(["ALB1", "FAC1", "Jamon Duroc", "LOT1", "111111111111"])
    ws.append(["ALB1", "FAC1", "Jamon Duroc", "LOT1", "222222222222"])
    wb.save(path)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert app_by_key("control_recepcion_maquilas").migration_status == "ported"
    assert parsear_destinatarios("a@test.com; b@test.com a@test.com") == ["a@test.com", "b@test.com"]
    assert validar_destinatarios(["ok@test.com", "mal"]) == ["mal"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        txt = tmp_path / "fac.txt"
        txt_ax = tmp_path / "fac_ax.txt"
        seals = tmp_path / "SealsReport.xlsx"
        config = tmp_path / "config_articulos.csv"
        pdf = tmp_path / "rangos.pdf"

        txt.write_text(
            "\n".join(
                [
                    "123456;030726;10:00:00;FAC1;111111111111;LOT1;10,50;",
                    "123456;030726;10:00:01;FAC1;222222222222;LOT1;10,20;",
                    "123456;030726;10:00:02;FAC1;222222222222;LOT1;10,20;",
                ]
            ),
            encoding="utf-8-sig",
        )
        config.write_text("Codigo;Nombre\nFAC1;JAMON DUROC 10-11\n", encoding="utf-8-sig")
        write_seals(seals)

        result = process_control_txt([txt])
        assert len(result.validos) == 2
        assert len(result.duplicados) == 1
        assert not result.invalidos
        editor, weight_summary, pending = weight_filter_text(result, "10,30", "")
        assert pending
        assert "222222222222" in editor
        assert "Peso minimo: 10,3" in weight_summary

        bad_txt = tmp_path / "fac_bad.txt"
        bad_txt.write_text("123456;030726;10:00:00;FAC1;111111111111;;10,50;\n", encoding="utf-8-sig")
        bad_result = process_control_txt([bad_txt])
        assert len(bad_result.invalidos) == 1
        fixed_text = correction_text(bad_result).replace(";;10,50;", ";LOT1;10,50;")
        fixed_result = revalidate_corrections(bad_result, fixed_text)
        assert not fixed_result.invalidos
        assert len(fixed_result.validos) == 1

        iberico_txt = tmp_path / "fac_iberico.txt"
        iberico_config = tmp_path / "config_iberico.csv"
        iberico_txt.write_text("123456;030726;10:00:00;IB1;111111111111;LOT1;10,50;\n", encoding="utf-8-sig")
        iberico_config.write_text("Codigo;Nombre\nIB1;JAMON IBERICO CEBO 10-11\n", encoding="utf-8-sig")
        iberico_result = process_control_txt([iberico_txt], iberico_config)
        assert iberico_result.tipo.tipo == "Iberico"
        assert iberico_result.invalidos and "GTIN-12 incorrecto" in iberico_result.invalidos[0][1]

        save_txt_ax(txt_ax, result)
        assert txt_ax.read_text(encoding="cp1252").count("222222222222") == 1
        recepcion = run_recepcion_with_seals(result, seals, config)
        assert len(recepcion.filas_rangos) == 1
        save_pdf_rangos(pdf, result)
        assert pdf.read_bytes().startswith(b"%PDF")

        window = ControlRecepcionMaquilasWindow()
        window.show_dialogs = False
        window.config_file = config
        window.set_txt_files([txt])
        app.processEvents()
        assert len(window.result.validos) == 2
        window.weight_min.setText("10,30")
        window.apply_weight_filter()
        app.processEvents()
        assert window.weight_filter_pending
        window.clear_corrections()
        app.processEvents()
        assert not window.weight_filter_pending
        window.save_txt_ax(tmp_path / "window_ax.txt")
        window.seals_file = seals
        window.process_seals()
        window.save_pdf(tmp_path / "window_rangos.pdf")
        assert window.result.pdf_rangos is not None
        window.close()

        correction_window = ControlRecepcionMaquilasWindow()
        correction_window.show_dialogs = False
        correction_window.set_txt_files([bad_txt])
        app.processEvents()
        assert correction_window.result.invalidos
        correction_window.preview.setPlainText(correction_text(correction_window.result).replace(";;10,50;", ";LOT1;10,50;"))
        correction_window.revalidate()
        app.processEvents()
        assert not correction_window.result.invalidos
        correction_window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("control_recepcion_maquilas"))
    app.processEvents()
    assert "control_recepcion_maquilas" in menu.open_windows
    menu.close()

    print("PHASE9_OK")
    print("app_portada=Control y Recepcion Maquilas")
    print("txt_ax_pdf_test=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
