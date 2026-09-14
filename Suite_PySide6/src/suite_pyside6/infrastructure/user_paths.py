"""Rutas persistentes del usuario, independientes de Qt y de la interfaz."""

from __future__ import annotations

import os
from pathlib import Path


def application_config_root(organization: str, application: str) -> Path:
    """Devuelve una ruta estable de configuración sin importar componentes UI.

    En Windows se conserva la convención de ``%APPDATA%`` usada por las
    versiones publicadas. En otros entornos (incluidos los tests) se emplea
    una alternativa predecible en el perfil del usuario.
    """

    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / organization / application
    return Path.home() / ".config" / organization / application
