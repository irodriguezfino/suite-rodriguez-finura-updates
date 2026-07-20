from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from suite_pyside6.core.apps import APP_REGISTRY, app_by_key
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.control_recepcion_maquilas_window import (
    PERSONAL_DESCRIPTION_KEY,
    ControlRecepcionPrecintosWindow,
)
from suite_pyside6.ui.session import (
    MAX_PERSONAL_DESCRIPTION_LENGTH,
    personal_description,
    remove_personal_description,
    save_personal_description,
)


class ControlRecepcionPrecintosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_registro_unificado_y_compatibilidad_de_claves_anteriores(self) -> None:
        app = app_by_key("control_recepcion_precintos")
        self.assertEqual(app.title, "Control y Recepción Precintos")
        self.assertIs(app_by_key("control_recepcion_maquilas"), app)
        self.assertIs(app_by_key("recepcion_maquilas"), app)
        self.assertNotIn("recepcion_maquilas", {item.key for item in APP_REGISTRY})
        self.assertNotIn("control_recepcion_maquilas", {item.key for item in APP_REGISTRY})
        self.assertNotIn("Control Precintos", {item.title for item in APP_REGISTRY})
        self.assertIs(get_window_class(app.key), ControlRecepcionPrecintosWindow)
        self.assertIs(get_window_class("recepcion_maquilas"), ControlRecepcionPrecintosWindow)

    def test_aclaracion_privada_persistente_validada_y_texto_plano(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings_a = QSettings(str(Path(directory) / "usuario-a.ini"), QSettings.IniFormat)
            settings_b = QSettings(str(Path(directory) / "usuario-b.ini"), QSettings.IniFormat)
            with patch("suite_pyside6.ui.session.settings", return_value=settings_a):
                saved = save_personal_description(PERSONAL_DESCRIPTION_KEY, "Nota <script>alert(1)</script>")
                self.assertEqual(saved, "Nota <script>alert(1)</script>")
                self.assertEqual(personal_description(PERSONAL_DESCRIPTION_KEY), saved)
                self.assertEqual(app_by_key("control_recepcion_precintos").title, "Control y Recepción Precintos")
                with self.assertRaises(ValueError):
                    save_personal_description(PERSONAL_DESCRIPTION_KEY, "x" * (MAX_PERSONAL_DESCRIPTION_LENGTH + 1))
                window = ControlRecepcionPrecintosWindow()
                window._refresh_personal_description()
                self.assertEqual(window.personal_description_note.text(), saved)
                self.assertEqual(window.personal_description_note.textFormat(), Qt.PlainText)
                self.assertFalse(window.personal_description_note.isHidden())
                window.close()

            with patch("suite_pyside6.ui.session.settings", return_value=settings_b):
                self.assertEqual(personal_description(PERSONAL_DESCRIPTION_KEY), "")
                window = ControlRecepcionPrecintosWindow()
                self.assertFalse(window.standard_description.isHidden())
                self.assertTrue(window.personal_description_note.isHidden())
                window.close()

            with patch("suite_pyside6.ui.session.settings", return_value=settings_a):
                remove_personal_description(PERSONAL_DESCRIPTION_KEY)
                self.assertEqual(personal_description(PERSONAL_DESCRIPTION_KEY), "")


if __name__ == "__main__":
    unittest.main()
