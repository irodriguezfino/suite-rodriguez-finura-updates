from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings

from suite_pyside6.core.app_organization import AppOrganization, system_category_id
from suite_pyside6.core.apps import APP_REGISTRY, app_by_key
from suite_pyside6.ui.session import load_app_organization, reset_app_organization, save_app_organization


class AppOrganizationTests(unittest.TestCase):
    def test_crear_renombrar_y_rechazar_nombres_invalidos(self) -> None:
        organization = AppOrganization()
        category = organization.add_category("  Merma  ", APP_REGISTRY)
        self.assertEqual(category.name, "Merma")
        with self.assertRaises(ValueError):
            organization.add_category("   ", APP_REGISTRY)
        with self.assertRaises(ValueError):
            organization.add_category("merma", APP_REGISTRY)
        with self.assertRaises(ValueError):
            organization.add_category("  JAMONES ", APP_REGISTRY)
        organization.rename_category(category.id, "Mermas especiales", APP_REGISTRY)
        self.assertEqual(organization.custom_categories[0].name, "Mermas especiales")

    def test_asignacion_unica_eliminacion_y_restauracion(self) -> None:
        organization = AppOrganization()
        category = organization.add_category("Merma", APP_REGISTRY)
        app = app_by_key("reparto_merma_precintos")
        organization.assign(app, category.id, APP_REGISTRY)
        self.assertEqual(organization.category_for(app, APP_REGISTRY), category.id)
        self.assertEqual(
            [item for item in APP_REGISTRY if organization.category_for(item, APP_REGISTRY) == category.id],
            [app],
        )
        affected = organization.delete_category(category.id)
        self.assertEqual(affected, [app.key])
        self.assertEqual(organization.category_for(app, APP_REGISTRY), system_category_id(app.category))
        organization.add_category("Merma", APP_REGISTRY)
        organization.reset()
        self.assertFalse(organization.custom_categories)
        self.assertFalse(organization.assignments)

    def test_persistencia_migracion_y_datos_incompletos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "perfil.ini"), QSettings.IniFormat)
            with patch("suite_pyside6.ui.session.settings", return_value=settings):
                organization = AppOrganization()
                category = organization.add_category("Merma", APP_REGISTRY)
                organization.assign(app_by_key("mermas"), category.id, APP_REGISTRY)
                save_app_organization(organization)
                recovered = load_app_organization(APP_REGISTRY)
                self.assertEqual(recovered.custom_categories[0].name, "Merma")
                self.assertEqual(recovered.assignments["mermas"], category.id)

                settings.setValue("apps/organization", "{not-json")
                self.assertFalse(load_app_organization(APP_REGISTRY).assignments)
                settings.setValue(
                    "apps/organization",
                    '{"custom_categories":[{"id":"custom:x","name":"  Merma  "}],"assignments":{"missing":"custom:x","mermas":"missing"}}',
                )
                recovered = load_app_organization(APP_REGISTRY)
                self.assertEqual(recovered.custom_categories[0].name, "Merma")
                self.assertFalse(recovered.assignments)
                reset_app_organization()
                self.assertFalse(load_app_organization(APP_REGISTRY).custom_categories)


if __name__ == "__main__":
    unittest.main()
