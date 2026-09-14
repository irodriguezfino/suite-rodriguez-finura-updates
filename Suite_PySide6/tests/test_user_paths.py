from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from suite_pyside6.infrastructure.user_paths import application_config_root


class UserPathsTests(unittest.TestCase):
    def test_application_config_root_preserves_the_windows_appdata_contract(self) -> None:
        with patch.dict("os.environ", {"APPDATA": r"C:\\Users\\operario\\AppData\\Roaming"}, clear=True):
            self.assertEqual(
                application_config_root("RodriguezFinura", "SuitePySide6"),
                Path(r"C:\\Users\\operario\\AppData\\Roaming/RodriguezFinura/SuitePySide6"),
            )


    def test_application_config_root_has_a_deterministic_non_windows_fallback(self) -> None:
        with patch.dict("os.environ", {}, clear=True), patch("suite_pyside6.infrastructure.user_paths.Path.home", return_value=Path("/perfil")):
            self.assertEqual(
                application_config_root("RodriguezFinura", "SuitePySide6"),
                Path("/perfil/.config/RodriguezFinura/SuitePySide6"),
            )
