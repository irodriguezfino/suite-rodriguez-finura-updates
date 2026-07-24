"""Modelo puro de la organización personal de aplicaciones.

La definición de aplicaciones no se altera: esta capa sólo guarda las
preferencias del perfil y resuelve cómo se muestran las categorías.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from uuid import uuid4

from suite_pyside6.core.apps import AppDefinition


ORGANIZATION_FORMAT_VERSION = 1
CUSTOM_CATEGORY_PREFIX = "custom:"
SYSTEM_CATEGORY_PREFIX = "system:"


def normalize_category_name(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def system_category_id(name: str) -> str:
    normalized = normalize_category_name(name)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return f"{SYSTEM_CATEGORY_PREFIX}{slug or 'general'}"


@dataclass(frozen=True)
class CategoryDefinition:
    id: str
    name: str
    is_custom: bool = False


@dataclass
class AppOrganization:
    version: int = ORGANIZATION_FORMAT_VERSION
    custom_categories: list[CategoryDefinition] = field(default_factory=list)
    category_order: list[str] = field(default_factory=list)
    assignments: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_data(cls, raw: object, apps: tuple[AppDefinition, ...]) -> "AppOrganization":
        if not isinstance(raw, dict):
            return cls()
        app_keys = {app.key for app in apps}
        custom_categories: list[CategoryDefinition] = []
        used_names: set[str] = {normalize_category_name(app.category) for app in apps}
        used_ids: set[str] = set()
        items = raw.get("custom_categories", [])
        if not isinstance(items, list):
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            category_id = str(item.get("id", "")).strip()
            name = " ".join(str(item.get("name", "")).split())
            normalized = normalize_category_name(name)
            if (
                not category_id.startswith(CUSTOM_CATEGORY_PREFIX)
                or not name
                or not normalized
                or category_id in used_ids
                or normalized in used_names
            ):
                continue
            used_ids.add(category_id)
            used_names.add(normalized)
            custom_categories.append(CategoryDefinition(category_id, name, True))

        valid_ids = {system_category_id(app.category) for app in apps} | used_ids
        assignments_raw = raw.get("assignments", {})
        assignments: dict[str, str] = {}
        if isinstance(assignments_raw, dict):
            for app_key, category_id in assignments_raw.items():
                key = str(app_key)
                target = str(category_id)
                if key in app_keys and target in valid_ids:
                    assignments[key] = target
        order_raw = raw.get("category_order", [])
        order = [str(item) for item in order_raw] if isinstance(order_raw, list) else []
        return cls(ORGANIZATION_FORMAT_VERSION, custom_categories, order, assignments)

    def to_data(self) -> dict[str, object]:
        return {
            "version": ORGANIZATION_FORMAT_VERSION,
            "custom_categories": [{"id": item.id, "name": item.name} for item in self.custom_categories],
            "category_order": list(self.category_order),
            "assignments": dict(self.assignments),
        }

    def categories(self, apps: tuple[AppDefinition, ...]) -> list[CategoryDefinition]:
        system: list[CategoryDefinition] = []
        known: set[str] = set()
        for app in apps:
            category_id = system_category_id(app.category)
            if category_id not in known:
                known.add(category_id)
                system.append(CategoryDefinition(category_id, app.category))
        by_id = {item.id: item for item in [*system, *self.custom_categories]}
        ordered = [by_id.pop(category_id) for category_id in self.category_order if category_id in by_id]
        return [*ordered, *by_id.values()]

    def category_for(self, app: AppDefinition, apps: tuple[AppDefinition, ...]) -> str:
        available = {item.id for item in self.categories(apps)}
        target = self.assignments.get(app.key)
        if target is not None and (target in available or any(item.id == target for item in self.custom_categories)):
            return target
        return system_category_id(app.category)

    def add_category(self, name: str, apps: tuple[AppDefinition, ...]) -> CategoryDefinition:
        clean = " ".join(str(name or "").split())
        if not clean:
            raise ValueError("El nombre de la categoría no puede estar vacío.")
        if normalize_category_name(clean) in {normalize_category_name(item.name) for item in self.categories(apps)}:
            raise ValueError("Ya existe una categoría con ese nombre.")
        category = CategoryDefinition(f"{CUSTOM_CATEGORY_PREFIX}{uuid4()}", clean, True)
        self.custom_categories.append(category)
        self.category_order.append(category.id)
        return category

    def rename_category(self, category_id: str, name: str, apps: tuple[AppDefinition, ...]) -> None:
        category = self._custom_category(category_id)
        clean = " ".join(str(name or "").split())
        if not clean:
            raise ValueError("El nombre de la categoría no puede estar vacío.")
        names = [item.name for item in self.categories(apps) if item.id != category.id]
        if normalize_category_name(clean) in {normalize_category_name(item) for item in names}:
            raise ValueError("Ya existe una categoría con ese nombre.")
        index = self.custom_categories.index(category)
        self.custom_categories[index] = CategoryDefinition(category.id, clean, True)

    def delete_category(self, category_id: str) -> list[str]:
        self._custom_category(category_id)
        affected = [key for key, value in self.assignments.items() if value == category_id]
        self.custom_categories = [item for item in self.custom_categories if item.id != category_id]
        self.category_order = [item for item in self.category_order if item != category_id]
        for key in affected:
            self.assignments.pop(key, None)
        return affected

    def assign(self, app: AppDefinition, category_id: str, apps: tuple[AppDefinition, ...]) -> None:
        if category_id not in {item.id for item in self.categories(apps)}:
            raise ValueError("La categoría seleccionada ya no existe.")
        default = system_category_id(app.category)
        if category_id == default:
            self.assignments.pop(app.key, None)
        else:
            self.assignments[app.key] = category_id

    def move_category(self, category_id: str, direction: int, apps: tuple[AppDefinition, ...]) -> None:
        identifiers = [item.id for item in self.categories(apps)]
        if category_id not in identifiers:
            return
        old_index = identifiers.index(category_id)
        new_index = max(0, min(len(identifiers) - 1, old_index + direction))
        if new_index == old_index:
            return
        identifiers.insert(new_index, identifiers.pop(old_index))
        self.category_order = identifiers

    def reset(self) -> None:
        self.custom_categories.clear()
        self.category_order.clear()
        self.assignments.clear()

    def _custom_category(self, category_id: str) -> CategoryDefinition:
        for category in self.custom_categories:
            if category.id == category_id:
                return category
        raise ValueError("Sólo se pueden modificar categorías personalizadas.")
