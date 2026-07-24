from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from suite_pyside6.core.precintos_jamones import (
    clasificar_precinto,
    gtin12_valido,
    process_precintos_jamones,
    save_precintos_csv,
    save_precintos_txt,
)


VALID_GTIN = "036000291452"  # UPC-A/GTIN-12 con dígito de control verificado.
INVALID_GTIN = "036000291453"


def source_line(seal: str) -> str:
    return f"123456;01/01/2026;10:00:00;ART;{seal};LOTE;12,5;\n"


class PrecintosJamonesDetectionTests(unittest.TestCase):
    def test_validacion_gtin12_real_y_ceros_iniciales(self) -> None:
        self.assertTrue(gtin12_valido(VALID_GTIN))
        self.assertTrue(gtin12_valido(f"  {VALID_GTIN}  "))
        self.assertFalse(gtin12_valido(INVALID_GTIN))
        self.assertFalse(gtin12_valido("ABC000291452"))
        self.assertFalse(gtin12_valido("36000291452"))
        self.assertFalse(gtin12_valido(VALID_GTIN + "0"))
        self.assertEqual(clasificar_precinto(VALID_GTIN), "Iberico")
        self.assertEqual(clasificar_precinto(INVALID_GTIN), "Blanco")

    def test_lotes_automaticos_mixtos_y_conservacion_del_texto(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            iberico = base / "iberico.txt"
            blanco = base / "blanco.txt"
            mixto = base / "mixto.txt"
            iberico.write_text(source_line(f"  {VALID_GTIN}  "), encoding="utf-8")
            blanco.write_text(source_line(INVALID_GTIN), encoding="utf-8")
            mixto.write_text(source_line(VALID_GTIN) + source_line(INVALID_GTIN), encoding="utf-8")

            result_iberico = process_precintos_jamones([iberico])
            self.assertEqual(result_iberico.tipo_jamon, "Iberico")
            self.assertIn(f"  {VALID_GTIN}  ", result_iberico.validos[0].a_linea())
            self.assertEqual(result_iberico.validos[0].precinto, VALID_GTIN)

            result_blanco = process_precintos_jamones([blanco])
            self.assertEqual(result_blanco.tipo_jamon, "Blanco")
            self.assertFalse(result_blanco.invalidos)

            result_mixto = process_precintos_jamones([mixto])
            self.assertEqual(result_mixto.tipo_jamon, "Mixto")
            self.assertTrue(result_mixto.es_lote_mixto())
            self.assertEqual([result_mixto.tipo_registro(row) for row in result_mixto.validos], ["Iberico", "Blanco"])
            self.assertTrue(any("mezcla" in message for message in result_mixto.detection_messages()))
            with self.assertRaises(ValueError):
                save_precintos_csv(base / "mixto.csv", result_mixto)
            save_precintos_txt(base / "mixto.txt.out", result_mixto)
            self.assertTrue((base / "mixto.txt.out").exists())

    def test_registro_malformado_se_mantiene_y_se_clasifica_sin_fallo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformado.txt"
            path.write_text("123456;01/01/2026;10:00:00;ART;ABC;\n", encoding="utf-8")
            result = process_precintos_jamones([path])
            self.assertEqual(result.tipo_jamon, "Blanco")
            self.assertEqual(len(result.invalidos), 1)
            self.assertEqual(result.tipo_registro(result.invalidos[0][0]), "Blanco")


if __name__ == "__main__":
    unittest.main()
