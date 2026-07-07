from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from suite_pyside6.ui.control_recepcion_maquilas_window import ControlRecepcionMaquilasWindow
from suite_pyside6.ui.mermas_window import MermasWindow
from suite_pyside6.ui.palets_window import PaletsWindow
from suite_pyside6.ui.pesos_window import PesosWindow
from suite_pyside6.ui.precintos_expedicion_window import PrecintosExpedicionWindow
from suite_pyside6.ui.precintos_excel_window import PrecintosExcelWindow
from suite_pyside6.ui.precintos_jamones_window import PrecintosJamonesWindow
from suite_pyside6.ui.recepcion_maquilas_window import RecepcionMaquilasWindow
from suite_pyside6.ui.txt_csv_window import TxtCsvWindow


WINDOW_CLASSES: dict[str, type[QMainWindow]] = {
    "exportar_precintos_excel": PrecintosExcelWindow,
    "txt_csv": TxtCsvWindow,
    "palets": PaletsWindow,
    "mermas": MermasWindow,
    "precintos_expedicion": PrecintosExpedicionWindow,
    "precintos_jamones": PrecintosJamonesWindow,
    "recepcion_maquilas": RecepcionMaquilasWindow,
    "control_recepcion_maquilas": ControlRecepcionMaquilasWindow,
    "pesos": PesosWindow,
}
