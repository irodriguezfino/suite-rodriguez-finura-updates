from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings

from suite_pyside6.core.app_organization import AppOrganization
from suite_pyside6.core.apps import AppDefinition


MAX_RECENTS = 8
MAX_PERSONAL_DESCRIPTION_LENGTH = 500
APP_ORGANIZATION_KEY = "apps/organization"


def settings() -> QSettings:
    return QSettings("RodriguezFinura", "SuitePySide6")


def last_dir(key: str) -> str:
    value = settings().value(f"paths/{key}/last_dir", "")
    return str(value or "")


def remember_paths(key: str, paths: list[Path]) -> None:
    clean = [path for path in paths if path]
    if not clean:
        return
    settings().setValue(f"paths/{key}/last_dir", str(clean[0].parent))
    recent = [str(path) for path in clean] + recent_paths(key)
    settings().setValue(f"paths/{key}/recent", _dedupe_existing(recent))


def remember_export(key: str, path: Path) -> None:
    if not path:
        return
    settings().setValue(f"paths/{key}/last_dir", str(path.parent))
    recent = [str(path)] + recent_paths(key)
    settings().setValue(f"paths/{key}/recent", _dedupe_existing(recent))
    all_exports = [str(path)] + recent_paths("exports")
    settings().setValue("paths/exports/recent", _dedupe_existing(all_exports))


def recent_paths(key: str) -> list[str]:
    value = settings().value(f"paths/{key}/recent", [])
    if isinstance(value, str):
        raw = [value]
    else:
        raw = [str(item) for item in (value or [])]
    return _dedupe_existing(raw)


def favorite_app_keys() -> list[str]:
    value = settings().value("apps/favorites", [])
    if isinstance(value, str):
        return [value]
    return [str(item) for item in (value or [])]


def is_favorite_app(key: str) -> bool:
    return key in favorite_app_keys()


def toggle_favorite_app(key: str) -> bool:
    favorites = favorite_app_keys()
    if key in favorites:
        favorites = [item for item in favorites if item != key]
        enabled = False
    else:
        favorites.append(key)
        enabled = True
    settings().setValue("apps/favorites", favorites)
    return enabled


def remember_app_open(key: str) -> None:
    recent = [key] + recent_app_keys()
    result: list[str] = []
    for item in recent:
        if item not in result:
            result.append(item)
        if len(result) >= MAX_RECENTS:
            break
    settings().setValue("apps/recent", result)


def recent_app_keys() -> list[str]:
    value = settings().value("apps/recent", [])
    if isinstance(value, str):
        return [value]
    return [str(item) for item in (value or [])]


def load_app_organization(apps: tuple[AppDefinition, ...]) -> AppOrganization:
    """Carga una preferencia versionada; datos antiguos o corruptos vuelven al orden estándar."""
    raw = settings().value(APP_ORGANIZATION_KEY, "")
    try:
        data = json.loads(str(raw)) if raw else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    return AppOrganization.from_data(data, apps)


def save_app_organization(organization: AppOrganization) -> None:
    app_settings = settings()
    app_settings.setValue(APP_ORGANIZATION_KEY, json.dumps(organization.to_data(), ensure_ascii=False, separators=(",", ":")))
    app_settings.sync()


def reset_app_organization() -> None:
    app_settings = settings()
    app_settings.remove(APP_ORGANIZATION_KEY)
    app_settings.sync()


def dialog_start_path(key: str, default_name: str = "") -> str:
    directory = last_dir(key)
    if directory and default_name:
        return str(Path(directory) / default_name)
    return directory


def personal_description(feature_key: str) -> str:
    """Devuelve la aclaración privada del perfil actual para una funcionalidad."""
    return str(settings().value(f"preferences/{feature_key}", "") or "")


def save_personal_description(feature_key: str, value: str) -> str:
    """Valida y persiste texto plano en el almacén de preferencias del perfil."""
    clean = _sanitize_plain_text(value)
    if not clean:
        remove_personal_description(feature_key)
        return ""
    if len(clean) > MAX_PERSONAL_DESCRIPTION_LENGTH:
        raise ValueError(f"La aclaración no puede superar {MAX_PERSONAL_DESCRIPTION_LENGTH} caracteres.")
    app_settings = settings()
    app_settings.setValue(f"preferences/{feature_key}", clean)
    app_settings.sync()
    return clean


def remove_personal_description(feature_key: str) -> None:
    app_settings = settings()
    app_settings.remove(f"preferences/{feature_key}")
    app_settings.sync()


def migrate_personal_description(source_key: str, target_key: str) -> None:
    """Mueve una preferencia sólo si la nueva clave aún no tiene valor."""
    if personal_description(target_key):
        return
    value = personal_description(source_key)
    if not value:
        return
    save_personal_description(target_key, value)
    remove_personal_description(source_key)


def _sanitize_plain_text(value: str) -> str:
    # Se muestra siempre como texto plano; se eliminan controles no imprimibles.
    normalized = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return "".join(char for char in normalized if char in {"\n", "\t"} or ord(char) >= 32).strip()


def _dedupe_existing(paths: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in paths:
        if not item:
            continue
        normalized = str(Path(item))
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(normalized)
        if len(result) >= MAX_RECENTS:
            break
    return result
