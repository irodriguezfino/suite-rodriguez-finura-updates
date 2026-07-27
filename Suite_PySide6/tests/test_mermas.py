from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from suite_pyside6.core.mermas import process_mermas


class MermasTests(unittest.TestCase):
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
