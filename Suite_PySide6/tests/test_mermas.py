from __future__ import annotations

import tempfile
import unittest
from qt_jobs import wait_for_jobs
from pathlib import Path

from suite_pyside6.core.mermas import process_mermas


class MermasTests(unittest.TestCase):
    def test_ventana_vacia_y_procesamiento_en_segundo_plano(self):
        import time
        from unittest.mock import patch
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from suite_pyside6.ui.mermas_window import MermasWindow
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            final = base / "final.csv"
            origin = base / "origen.csv"
            final.write_text("340224;27/7/2026;10:37:34;157528405029;11.15;7.55;32.28;SI\n", encoding="utf-8")
            origin.write_text("340224;20/08/2024;10:37:11;60727;157528405029;34242702020;11,89;\n", encoding="utf-8")
            window = MermasWindow()
            window.show_dialogs = False
            self.assertIsNone(window.result)
            self.assertFalse(window.save_button.isEnabled())
            window.set_final_files([final])
            window.set_origin_file(origin)
            window.process_files()
            deadline = time.monotonic() + 15
            while window.property("operationActive") and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertFalse(window.property("operationActive"))
            self.assertTrue(window._has_result, window.status.text())
            self.assertEqual(window.result.dataframe.iloc[0]["LOTE ORIGEN"], "34242702020")
            window.save_path(base / "salida.xlsx")
            wait_for_jobs(window)
            self.assertTrue((base / "salida.xlsx").exists())
            with patch("suite_pyside6.ui.mermas_window.confirm_discard_work", return_value=True):
                window.clear()
            self.assertIsNone(window.result)
            window.close()

    def test_descarta_registros_sin_los_identificadores_obligatorios(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            final = base / "340224M.csv"
            origin = base / "340224.CSV"
            final.write_text(
                "340224;27/7/2026;10:37:34;157528405029;11.15;7.55;32.28;SI\n"
                "            ;27/7/2026;10:37:43;            ;1.0;7.68;-668.;NO\n",
                encoding="utf-8",
            )
            origin.write_text(
                "340224;20/08/2024;10:37:11;60727;157528405029;34242702020;11,89;\n",
                encoding="utf-8",
            )

            result = process_mermas([final], origin, "TODOS")

        self.assertEqual(result.summary.filas_leidas, 1)
        self.assertEqual(result.summary.precintos_unicos, 1)
        self.assertEqual(len(result.dataframe), 1)
        self.assertEqual(result.dataframe.iloc[0]["Fichero FAC"], "340224")
        self.assertEqual(result.dataframe.iloc[0]["Precinto"], "157528405029")


if __name__ == "__main__":
    unittest.main()
