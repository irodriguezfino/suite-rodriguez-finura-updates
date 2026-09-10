from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from importlib import import_module
from threading import Lock

from PySide6.QtWidgets import QMainWindow

from suite_pyside6.core.apps import resolve_app_key


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
    "control_recepcion_precintos": WindowSpec(
        "suite_pyside6.ui.control_recepcion_maquilas_window",
        "ControlRecepcionPrecintosWindow",
    ),
    "pesos": WindowSpec("suite_pyside6.ui.pesos_window", "PesosWindow"),
    "reparto_merma_precintos": WindowSpec(
        "suite_pyside6.ui.reparto_merma_precintos_window",
        "RepartoMermaPrecintosWindow",
    ),
    "file_compare": WindowSpec("suite_pyside6.ui.file_compare_window", "FileCompareWindow"),
    "numerador_etiquetas": WindowSpec("suite_pyside6.ui.numerador_etiquetas_window", "NumeradorEtiquetasWindow"),
}

_WINDOW_CACHE: dict[str, type[QMainWindow]] = {}
_PRELOAD_LOCK = Lock()


def _load_window_class(key: str) -> type[QMainWindow] | None:
    key = resolve_app_key(key)
    with _PRELOAD_LOCK:
        cached = _WINDOW_CACHE.get(key)
    if cached is not None:
        return cached
    spec = _WINDOW_SPECS.get(key)
    if spec is None:
        return None
    module = import_module(spec.module)
    window_class = getattr(module, spec.class_name)
    with _PRELOAD_LOCK:
        return _WINDOW_CACHE.setdefault(key, window_class)


def get_window_class(key: str) -> type[QMainWindow] | None:
    return _load_window_class(key)


def preload_window_class(key: str) -> bool:
    """Indica si una ventana ya está disponible sin importar módulos desde otro hilo.

    Importar módulos que dependen de Qt desde un ``ThreadPoolExecutor`` no es
    una operación garantizada por Qt y podía dejar la navegación esperando para
    siempre. La importación real se hace al completar la navegación, en el hilo
    principal, una sola vez y con manejo de error visible.
    """
    key = resolve_app_key(key)
    if key not in _WINDOW_SPECS:
        return False
    with _PRELOAD_LOCK:
        if key in _WINDOW_CACHE:
            return True
    return False


def preloaded_window_class(key: str) -> type[QMainWindow] | None:
    """Carga la clase de forma determinista en el hilo de interfaz."""
    return _load_window_class(key)


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
