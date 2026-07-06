from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import Workbook
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import app_by_key
from suite_pyside6.core.precintos_expedicion import (
    cargar_excels,
    filtrar_precintos_por_pallets,
    generar_txts_expedicion,
    guardar_txts_expedicion,
    pallets_disponibles,
)
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.precintos_expedicion_window import PrecintosExpedicionWindow


def write_entrada(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "Codigo de articulo",
            "Codigo de articulo externo",
            "Numero de lote",
            "Numero de lote del proveedor",
            "Peso neto",
            "Precinto",
            "Id de pallet",
        ]
    )
    ws.append(["ART1", "EXT1", "L001", "PROV1", 10.2, "00000000000000000001", "PALLET-A"])
    ws.append(["ART1", "EXT1", "L001", "PROV1", 10.3, "00000000000000000002", "PALLET-A"])
    ws.append(["ART2", "EXT2", "L002", "PROV2", 8.0, "00000000000000000003", "PALLET-B"])
    wb.save(path)


def write_salida(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["Codigo de articulo", "Id de pallet", "Unidades", "Kilos"])
    ws.append(["ART1", "JUMBO-1", 2, 20.001])
    wb.save(path)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    assert app_by_key("precintos_expedicion").migration_status == "ported"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        entrada = tmp_path / "Entrada AX.xlsx"
        salida = tmp_path / "Salida 123456.xlsx"
        destino = tmp_path / "txt"
        write_entrada(entrada)
        write_salida(salida)

        carga = cargar_excels([entrada, salida])
        assert carga.entrada is not None
        assert len(carga.salidas) == 1
        entrada_filas = carga.entrada.filas
        assert pallets_disponibles(entrada_filas) == ["PALLET-A", "PALLET-B"]  # type: ignore[arg-type]
        filtradas = filtrar_precintos_por_pallets(entrada_filas, ["PALLET-A"])  # type: ignore[arg-type]
        result = generar_txts_expedicion(filtradas, carga.salidas, inicio=datetime(2026, 7, 3, 10, 0, 0))
        assert result.precintos_usados == 2
        assert result.unidades_salida == 2
        assert result.salidas[0].nombre_txt == "SC123456.TXT"
        assert result.lineas[0] == "PROV1;03/07/2026;10:00:00;EXT1;00000000000000000001;L001;10,001;"
        assert result.lineas[1] == "PROV1;03/07/2026;10:00:01;EXT1;00000000000000000002;L001;10,000;"
        saved = guardar_txts_expedicion(result, destino)
        assert saved[0].name == "SC123456.TXT"
        assert saved[0].read_text(encoding="cp1252").splitlines() == result.lineas

        salida_sin_nombre = tmp_path / "Salida sin numero.xlsx"
        write_salida(salida_sin_nombre)
        carga_sin_nombre = cargar_excels([entrada, salida_sin_nombre])
        result_sin_nombre = generar_txts_expedicion(filtradas, carga_sin_nombre.salidas, inicio=datetime(2026, 7, 3, 10, 0, 0))
        assert result_sin_nombre.salidas[0].nombre_txt is None
        try:
            guardar_txts_expedicion(result_sin_nombre, tmp_path / "sin_nombre")
            raise AssertionError("guardar_txts_expedicion debia exigir nombre manual")
        except ValueError as exc:
            assert "Falta nombre TXT" in str(exc)
        saved_manual = guardar_txts_expedicion(
            result_sin_nombre,
            tmp_path / "manual",
            {str(salida_sin_nombre): "SC654321.TXT"},
        )
        assert saved_manual[0].name == "SC654321.TXT"

        window = PrecintosExpedicionWindow()
        window.show_dialogs = False
        window.set_files([entrada, salida])
        app.processEvents()
        assert window.selected_pallets == {"PALLET-A"}
        window.process_files()
        app.processEvents()
        assert window.result is not None
        assert window.result.precintos_usados == 2
        saved_from_window = window.save_to_directory(tmp_path / "window_txt")
        assert saved_from_window[0].exists()
        window.close()

    menu = MainWindow()
    menu.show()
    menu.open_app(app_by_key("precintos_expedicion"))
    app.processEvents()
    assert "precintos_expedicion" in menu.open_windows
    menu.close()

    print("PHASE7_OK")
    print("app_portada=Precintos Expedicion")
    print("txt_generados_test=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
