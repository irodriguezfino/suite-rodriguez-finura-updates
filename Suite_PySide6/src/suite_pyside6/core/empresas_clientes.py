"""Configuracion editable de empresas cliente para Control y Recepcion."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from suite_pyside6.core.paths import resource_path


LOGGER = logging.getLogger(__name__)
EMPRESAS_CLIENTES_FILENAME = "empresas_clientes.txt"


@dataclass(frozen=True)
class EmpresasClientesLoadResult:
    path: Path
    companies: tuple[str, ...]
    error_message: str | None = None


def empresas_clientes_config_path() -> Path:
    """Ruta persistente editable, independiente de la carpeta de instalacion."""

    app_data = os.environ.get("APPDATA")
    if app_data:
        config_dir = Path(app_data) / "RodriguezFinura" / "SuitePySide6"
    else:
        standard_path = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        config_dir = Path(standard_path or Path.home() / ".config") / "RodriguezFinura" / "SuitePySide6"
    return config_dir / "control_recepcion_precintos" / EMPRESAS_CLIENTES_FILENAME


def empresas_clientes_template_path() -> Path:
    """Plantilla distribuida con la Suite para crear la configuracion inicial."""

    return resource_path(EMPRESAS_CLIENTES_FILENAME)


def load_empresas_clientes(
    path: Path | None = None,
    *,
    template_path: Path | None = None,
) -> EmpresasClientesLoadResult:
    """Carga empresas validas en orden y crea la configuracion inicial si falta."""

    target = path or empresas_clientes_config_path()
    template = template_path or empresas_clientes_template_path()
    if not target.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        except (OSError, UnicodeError) as exc:
            LOGGER.warning("No se pudo crear la configuracion de empresas cliente en %s: %s", target, exc)
            return EmpresasClientesLoadResult(
                target,
                (),
                "No se pudo preparar el archivo de empresas cliente. Revisa sus permisos e intenta de nuevo.",
            )
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        LOGGER.warning("No se pudo leer la configuracion de empresas cliente en %s: %s", target, exc)
        return EmpresasClientesLoadResult(
            target,
            (),
            "No se pudo leer el archivo de empresas cliente. Revisa el archivo y su codificacion UTF-8.",
        )
    return EmpresasClientesLoadResult(target, _clean_companies(content.splitlines()))


def _clean_companies(lines: list[str]) -> tuple[str, ...]:
    companies: list[str] = []
    seen: set[str] = set()
    for raw_line in lines:
        value = raw_line.strip()
        if not value or value.startswith("#"):
            continue
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        companies.append(value)
    return tuple(companies)
