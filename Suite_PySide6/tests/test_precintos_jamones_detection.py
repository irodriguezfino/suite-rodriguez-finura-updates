from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from suite_pyside6.core.precintos_jamones import (
    PrecintosJamonesResult,
    RegistroJamones,
    calcular_control_resumen,
    clasificar_precinto,
    gtin12_valido,
    leer_resumen_partida,
    parsear_resumen_partida,
    process_precintos_jamones,
    save_precintos_csv,
    save_precintos_txt,
    seleccionar_registros_por_peso,
    texto_control_resumen,
)


VALID_GTIN = "036000291452"  # UPC-A/GTIN-12 con dígito de control verificado.
INVALID_GTIN = "036000291453"


def source_line(seal: str) -> str:
    return f"123456;01/01/2026;10:00:00;ART;{seal};LOTE;12,5;\n"


RESUMEN_PARTIDA = """Nº PARTIDA
460126

PROVEEDOR    Nº LOTE
98           46012698021

FECHA        HORA
06/11/2026   12:07:20

TOTAL PIEZAS TOTAL PESO
972          13000,65

RANGO DE PESOS
MIN. MAX. PIEZAS PESO
10,5 12 14 164,64
12 13 422 5281,859
13 14 287 3866
14 16 236 3479,012
16 18 13 209,14
18 0 0 0
0 0 0 0
"""


def registro_con_peso(numero: int, peso: str) -> RegistroJamones:
    return RegistroJamones(
        archivo="prueba.txt",
        linea=numero,
        campos=["460126", "06/11/2026", "12:07:20", "5728", f"46698011{numero:04d}", "46012698021", peso],
        orden=numero,
    )


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

    def test_resumen_recalcula_tramos_sin_doblar_los_limites(self) -> None:
        resumen = parsear_resumen_partida(RESUMEN_PARTIDA)
        self.assertEqual(resumen.partida, "460126")
        self.assertEqual(resumen.total_piezas, 972)
        self.assertEqual(resumen.total_peso, Decimal("13000.65"))
        self.assertEqual(len(resumen.rangos), 5)

        pesos = ["10,5", "11,99", "12", "12,5", "13", "15", "17,99"]
        result = PrecintosJamonesResult(validos=[registro_con_peso(i, peso) for i, peso in enumerate(pesos, 1)])
        control = calcular_control_resumen(result, resumen)

        self.assertEqual([item.piezas_validas for item in control.rangos], [2, 2, 1, 1, 1])
        self.assertEqual(control.piezas_en_rangos, 7)
        self.assertTrue(control.cuadra_con_validos)
        texto = texto_control_resumen(control)
        self.assertIn("Total en rangos: 7 de 7 válidos", texto)
        self.assertIn("10,5 ≤ kg < 12: 2 uds", texto)

    def test_resumen_se_carga_desde_archivo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resumen_partida.txt"
            path.write_text(RESUMEN_PARTIDA, encoding="cp1252")
            resumen = leer_resumen_partida(path)
            self.assertEqual(resumen.partida, "460126")
            self.assertEqual(len(resumen.rangos), 5)
            with self.assertRaises(ValueError):
                leer_resumen_partida(path.with_suffix(".xlsx"))

    def test_resumen_solo_necesita_la_tabla_de_rangos(self) -> None:
        resumen = parsear_resumen_partida(
            """RANGO DE PESOS
MIN. MAX. PIEZAS PESO
8 10,5 4 38,20
10,5 12 6 67,50
12 14 8 103,40
"""
        )
        self.assertEqual(resumen.partida, "")
        self.assertEqual(resumen.total_piezas, 18)
        self.assertEqual(resumen.total_peso, Decimal("209.10"))
        self.assertEqual([(r.minimo, r.maximo) for r in resumen.rangos], [
            (Decimal("8"), Decimal("10.5")),
            (Decimal("10.5"), Decimal("12")),
            (Decimal("12"), Decimal("14")),
        ])

    def test_resumen_avisa_si_un_valido_esta_fuera_de_los_tramos(self) -> None:
        resumen = parsear_resumen_partida(RESUMEN_PARTIDA)
        result = PrecintosJamonesResult(validos=[registro_con_peso(1, "9,9"), registro_con_peso(2, "18")])
        control = calcular_control_resumen(result, resumen)
        self.assertFalse(control.cuadra_con_validos)
        self.assertEqual(len(control.fuera_de_rango), 2)

    def test_filtro_selecciona_entre_minimo_y_maximo_incluidos(self) -> None:
        pesos = ["10,49", "10,5", "11", "12", "12,01"]
        result = PrecintosJamonesResult(validos=[registro_con_peso(i, peso) for i, peso in enumerate(pesos, 1)])
        seleccion = seleccionar_registros_por_peso(result, "10,5", "12")
        self.assertEqual([registro.peso for registro in seleccion.registros], ["10,5", "11", "12"])
        seleccion_con_punto = seleccionar_registros_por_peso(result, "10.5", "12.0")
        self.assertEqual([registro.peso for registro in seleccion_con_punto.registros], ["10,5", "11", "12"])
        with self.assertRaises(ValueError):
            seleccionar_registros_por_peso(result, "13", "12")


if __name__ == "__main__":
    unittest.main()
