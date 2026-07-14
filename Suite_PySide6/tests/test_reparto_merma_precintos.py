from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from suite_pyside6.core.reparto_merma_precintos import (
    AX_CSV_FORMAT,
    DomainValidationError,
    build_preview,
    calculate_adjustment,
    read_source_file,
    render_ax_csv,
    validate_ax_csv_content,
    validate_final_weight,
)


class RepartoMermaPrecintosTests(unittest.TestCase):
    def read(self, text: str, encoding: str = "utf-8"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "origen.txt"
            path.write_bytes(text.encode(encoding))
            return read_source_file(path)

    def result(self, text: str, final_weight: str):
        return calculate_adjustment(self.read(text), final_weight)

    def test_calculos_normales_ausencia_merma_y_ganancia(self):
        source = "A;X;10,00\r\nB;X;20,00\r\n"
        for final, loss, percentage, factor, warning in (
            ("27,00", Decimal("3.00"), Decimal("10.0"), Decimal("0.9"), False),
            ("30,00", Decimal("0.00"), Decimal("0"), Decimal("1"), False),
            ("33,00", Decimal("-3.00"), Decimal("-10.0"), Decimal("1.1"), True),
        ):
            with self.subTest(final=final):
                result = self.result(source, final)
                self.assertEqual(result.absolute_loss, loss)
                self.assertEqual(result.loss_percentage, percentage)
                self.assertEqual(result.adjustment_factor, factor)
                self.assertEqual(bool(result.warnings), warning)
                self.assertEqual(result.adjusted_total, Decimal(final.replace(",", ".")))

    def test_un_precinto_varios_precintos_y_decimales(self):
        one = self.result("UNO;X;10,25\r\n", "9,99")
        self.assertEqual(one.rows[0].adjusted_weight, Decimal("9.99"))
        many = self.result("A;X;1,11\r\nB;X;2,22\r\nC;X;6,67\r\n", "8,50")
        self.assertEqual([row.source.precinto for row in many.rows], ["A", "B", "C"])
        self.assertEqual(many.adjusted_total, Decimal("8.50"))

    def test_coma_punto_y_aviso_inconsistente(self):
        comma = self.read("A;X;1,25\r\n")
        point = self.read("A;X;1.25\r\n")
        mixed = self.read("A;X;1,25\r\nB;X;2.50\r\n")
        self.assertEqual(comma.total_weight, Decimal("1.25"))
        self.assertEqual(point.total_weight, Decimal("1.25"))
        self.assertIn("INCONSISTENT_DECIMAL_SEPARATOR", [issue.code for issue in mixed.warnings])

    def test_residuo_positivo_y_negativo_se_concilian(self):
        positive = self.result("A;X;1\r\nB;X;1\r\nC;X;1\r\n", "1,00")
        negative = self.result("A;X;1\r\nB;X;1\r\nC;X;1\r\n", "2,00")
        self.assertEqual([row.adjusted_weight for row in positive.rows], [Decimal("0.34"), Decimal("0.33"), Decimal("0.33")])
        self.assertEqual([row.adjusted_weight for row in negative.rows], [Decimal("0.66"), Decimal("0.67"), Decimal("0.67")])
        self.assertEqual(positive.adjusted_total, Decimal("1.00"))
        self.assertEqual(negative.adjusted_total, Decimal("2.00"))

    def test_distribucion_equitativa_y_pesos_muy_diferentes(self):
        equal = self.result("C;X;1\r\nA;X;1\r\nB;X;1\r\n", "1,00")
        self.assertEqual([row.adjusted_weight for row in equal.rows], [Decimal("0.33"), Decimal("0.34"), Decimal("0.33")])
        uneven = self.result("A;X;0,01\r\nB;X;999,99\r\n", "500,00")
        self.assertEqual(uneven.adjusted_total, Decimal("500.00"))
        self.assertGreater(uneven.rows[1].adjusted_weight, uneven.rows[0].adjusted_weight)

    def test_duplicados_y_validaciones_de_registro(self):
        cases = {
            "A;X;1\r\nA;X;2\r\n": "DUPLICATE_SEAL",
            ";X;1\r\n": "EMPTY_SEAL",
            "A;X;\r\n": "EMPTY_WEIGHT",
            "A;X;abc\r\n": "INVALID_WEIGHT",
            "A;X;-1\r\n": "NEGATIVE_WEIGHT",
            "A;X;0\r\n": "ZERO_SOURCE_TOTAL",
            "A;X\r\n": "TOO_FEW_FIELDS",
        }
        for text, code in cases.items():
            with self.subTest(code=code):
                result = self.read(text)
                self.assertIn(code, [issue.code for issue in result.issues])
                with self.assertRaises(DomainValidationError):
                    calculate_adjustment(result, "0,00")

    def test_cabecera_sin_cabecera_vacias_y_totales(self):
        with_header = self.read("Precinto;Clase;Peso\r\nA;X;1,00\r\n\r\nTOTAL;;1,00\r\n")
        without_header = self.read("A;X;1,00\r\n")
        self.assertTrue(with_header.source_format and with_header.source_format.has_header)
        self.assertFalse(without_header.source_format and without_header.source_format.has_header)
        self.assertEqual(len(with_header.records), 1)
        self.assertEqual([row.reason for row in with_header.ignored_rows], ["encabezado", "fila vacia", "fila total o tecnica"])

    def test_formato_codificacion_crlf_y_caracteres_espanoles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "origen.csv"
            path.write_bytes("Precinto;Clase;Peso\r\nAÑO;ñ;1,50\r\n".encode("cp1252"))
            result = read_source_file(path)
        self.assertEqual(result.source_format.encoding, "cp1252")
        self.assertEqual(result.source_format.line_ending, "CRLF")
        self.assertEqual(result.records[0].precinto, "AÑO")
        self.assertEqual(result.records[0].peso_original, Decimal("1.50"))

    def test_formatos_no_soportados_vacio_y_codificacion_incorrecta(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            unsupported = base / "origen.xlsx"
            unsupported.write_bytes(b"x")
            empty = base / "vacio.txt"
            empty.write_bytes(b"")
            invalid = base / "invalido.txt"
            invalid.write_bytes(b"A;X;1\x00")
            for path, code in ((unsupported, "UNSUPPORTED_FORMAT"), (empty, "EMPTY_FILE"), (invalid, "INVALID_ENCODING")):
                with self.subTest(code=code):
                    self.assertEqual(read_source_file(path).issues[0].code, code)

    def test_validacion_peso_final(self):
        total = Decimal("10.00")
        cases = ((None, "EMPTY_FINAL_WEIGHT"), ("abc", "INVALID_FINAL_WEIGHT"), ("-1", "NEGATIVE_FINAL_WEIGHT"), ("1,001", "FINAL_WEIGHT_PRECISION"))
        for value, code in cases:
            with self.subTest(value=value):
                self.assertEqual(validate_final_weight(value, total).issues[0].code, code)
        gain = validate_final_weight("11,00", total)
        self.assertTrue(gain.is_valid)
        self.assertEqual(gain.issues[0].code, "WEIGHT_GAIN")

    def test_csv_ax_dos_columnas_suma_orden_y_bytes(self):
        result = self.result("B;X;2,00\r\nA;X;1,00\r\n", "2,00")
        content = render_ax_csv(result)
        self.assertFalse(content.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(content.endswith(b"\r\n"))
        self.assertEqual(content.decode("cp1252"), "B;1,33\r\nA;0,67\r\n")
        validate_ax_csv_content(content, result)
        rows = content.decode("cp1252").split("\r\n")[:-1]
        self.assertTrue(all(len(row.split(";")) == 2 for row in rows))
        self.assertEqual(len(rows), len(result.rows))

    def test_modelo_de_vista_previa_conserva_pesos_y_orden(self):
        result = self.result("B;X;2,00\r\nA;X;1,00\r\n", "2,00")
        preview = build_preview(result)
        self.assertEqual(preview.source_total, Decimal("3.00"))
        self.assertEqual(preview.final_weight, Decimal("2.00"))
        self.assertEqual([row.precinto for row in preview.rows], ["B", "A"])
        self.assertEqual(sum((row.peso_ajustado for row in preview.rows), Decimal("0")), Decimal("2.00"))

    def test_csv_injection_se_rechaza_sin_mutar_el_identificador(self):
        result = self.result("=1+1;X;1,00\r\n", "1,00")
        with self.assertRaises(DomainValidationError) as raised:
            render_ax_csv(result)
        self.assertEqual(raised.exception.issues[0].code, "CSV_INJECTION_RISK")

    def test_formato_ax_centralizado(self):
        self.assertEqual(AX_CSV_FORMAT.encoding, "cp1252")
        self.assertEqual(AX_CSV_FORMAT.delimiter, ";")
        self.assertEqual(AX_CSV_FORMAT.decimal_separator, ",")
        self.assertEqual(AX_CSV_FORMAT.precision, 2)
        self.assertEqual(AX_CSV_FORMAT.line_ending, "\r\n")
        self.assertFalse(AX_CSV_FORMAT.include_header)


if __name__ == "__main__":
    unittest.main()
