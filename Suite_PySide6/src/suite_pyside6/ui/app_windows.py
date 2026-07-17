from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from importlib import import_module

from PySide6.QtWidgets import QMainWindow


@dataclass(frozen=True)
class WindowSpec:
    module: str
    class_name: str


_WINDOW_SPECS: dict[str, WindowSpec] = {
    "exportar_precintos_excel": WindowSpec("suite_pyside6.ui.precintos_excel_window", "PrecintosExcelWindow"),
    "txt_csv": WindowSpec("suite_pyside6.ui.txt_csv_window", "TxtCsvWindow"),
    "precintos_txt_ax": WindowSpec("suite_pyside6.ui.precintos_txt_ax_window", "PrecintosTxtAxWindow"),
    "palets": WindowSpec("suite_pyside6.ui.palets_window", "PaletsWindow"),
    "mermas": WindowSpec("suite_pyside6.ui.mermas_window", "MermasWindow"),
    "precintos_expedicion": WindowSpec("suite_pyside6.ui.precintos_expedicion_window", "PrecintosExpedicionWindow"),
    "precintos_jamones": WindowSpec("suite_pyside6.ui.precintos_jamones_window", "PrecintosJamonesWindow"),
    "recepcion_maquilas": WindowSpec("suite_pyside6.ui.recepcion_maquilas_window", "RecepcionMaquilasWindow"),
    "control_recepcion_maquilas": WindowSpec(
        "suite_pyside6.ui.control_recepcion_maquilas_window",
        "ControlRecepcionMaquilasWindow",
    ),
    "pesos": WindowSpec("suite_pyside6.ui.pesos_window", "PesosWindow"),
    "reparto_merma_precintos": WindowSpec(
        "suite_pyside6.ui.reparto_merma_precintos_window",
        "RepartoMermaPrecintosWindow",
    ),
}

_WINDOW_CACHE: dict[str, type[QMainWindow]] = {}


def get_window_class(key: str) -> type[QMainWindow] | None:
    spec = _WINDOW_SPECS.get(key)
    if spec is None:
        return None
    if key not in _WINDOW_CACHE:
        module = import_module(spec.module)
        window_class = getattr(module, spec.class_name)
        _WINDOW_CACHE[key] = window_class
    return _WINDOW_CACHE[key]


class WindowClassRegistry(Mapping[str, type[QMainWindow]]):
    def __iter__(self) -> Iterator[str]:
        return iter(_WINDOW_SPECS)

    def __len__(self) -> int:
        return len(_WINDOW_SPECS)

    def __getitem__(self, key: str) -> type[QMainWindow]:
        window_class = get_window_class(key)
        if window_class is None:
            raise KeyError(key)
        return window_class


WINDOW_CLASSES: Mapping[str, type[QMainWindow]] = WindowClassRegistry()
