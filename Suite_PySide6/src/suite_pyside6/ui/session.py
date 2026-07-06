from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings


MAX_RECENTS = 8


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


def dialog_start_path(key: str, default_name: str = "") -> str:
    directory = last_dir(key)
    if directory and default_name:
        return str(Path(directory) / default_name)
    return directory


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
