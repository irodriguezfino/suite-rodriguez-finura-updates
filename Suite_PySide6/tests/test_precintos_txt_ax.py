from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from suite_pyside6.core.precintos_txt_ax import (
    AX_ENCODING,
    AX_DELIMITER,
    AX_LINE_ENDING,
    SOURCE_DELIMITER,
    csv_filename_from_source,
    ensure_csv_extension,
    extract_precintos,
    process_txt_files,
    process_txt_file,
    render_ax_csv,
)


class PrecintosTxtAxTests(unittest.TestCase):
    def test_delimitador_real_y_variantes_de_espaciado(self):
        self.assertEqual(SOURCE_DELIMITER, "->")
        result = extract_precintos("origen -> 1001\ntexto\t\u2192\t2002\nA=>3003\nB\u00e2\u2020\u20194004")
        self.assertEqual(result.precintos, ["100", "200", "300", "400"])
        self.assertEqual(result.lines_read, 4)
        self.assertEqual(result.skipped_lines, 0)

    def test_ejemplo_real_elimina_parte_izquierda_flecha_y_ultimo_digito(self):
        result = extract_precintos(
            "2052803115175 -> 2052803108191\n"
            "2052803115175 -> 2052803113133\n"
            "2052803115175 -> 2052803108290\n"
        )
        self.assertEqual(
            result.precintos,
            ["205280310819", "205280311313", "205280310829"],
        )

    def test_ignora_vacias_e_invalidas_y_conserva_duplicados(self):
        result = extract_precintos("\r\nA -> 1234\r\nSin flecha\r\nB ->   \r\nC -> 1234\r\n")
        self.assertEqual(result.precintos, ["123"])
        self.assertEqual(result.lines_read, 5)
        self.assertEqual(result.skipped_lines, 3)
        self.assertEqual(result.valid_lines, 2)
        self.assertEqual(result.exported_count, 1)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(
            [(line.line_number, line.original_content, line.reason) for line in result.ignored_lines],
            [
                (1, "", "Línea vacía"),
                (3, "Sin flecha", "Separador no encontrado"),
                (4, "B ->   ", "Segunda columna vacía"),
            ],
        )

    def test_saltos_windows_unix_y_contenido_exactamente_recortado_en_extremos(self):
        result = extract_precintos("A ->  1234  \r\nB ->\t\ufeff0001\u200b\nC -> 9876\n")
        self.assertEqual(result.precintos, ["123", "000", "987"])
        self.assertEqual(result.skipped_lines, 0)

    def test_precinto_vacio_y_caracteres_no_permitidos_se_registran_con_motivo(self):
        result = extract_precintos("A -> \ufeff\nB -> COD\x00IGO\nC -> ABC4\nD -> 1234\n")
        self.assertEqual(result.precintos, ["123"])
        self.assertEqual(result.skipped_lines, 3)
        self.assertEqual(
            [line.reason for line in result.ignored_lines],
            ["Precinto vacío", "Caracteres no permitidos en el precinto", "El valor después de la flecha no es numérico"],
        )

    def test_rechaza_columnas_adicionales_para_no_generar_un_precinto_incorrecto(self):
        result = extract_precintos("A -> 1234 -> detalle\n")
        self.assertEqual(result.precintos, [])
        self.assertEqual(result.skipped_lines, 1)

    def test_archivo_sin_precintos_registra_todas_las_lineas_ignoradas(self):
        result = extract_precintos("\nSIN FLECHA\nA -> \n")
        self.assertEqual(result.precintos, [])
        self.assertEqual(result.skipped_lines, 3)
        self.assertEqual(len(result.ignored_lines), result.skipped_lines)

    def test_archivo_cp1252_y_archivo_sin_datos_validos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "origen especial.txt"
            path.write_bytes("lote ñ -> 1234\r\nincorrecta\r\n".encode("cp1252"))
            result = process_txt_file(path)
        self.assertEqual(result.source_encoding, "cp1252")
        self.assertEqual(result.precintos, ["123"])
        empty = extract_precintos("\nSIN FLECHA\nA -> \t\n")
        self.assertEqual(empty.precintos, [])
        self.assertEqual(empty.skipped_lines, 3)

    def test_archivo_utf8_con_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.txt"
            path.write_bytes("lote -> 1234\r\n".encode("utf-8-sig"))
            result = process_txt_file(path)
        self.assertEqual(result.source_encoding, "utf-8-sig")
        self.assertEqual(result.precintos, ["123"])

    def test_archivo_utf16_de_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "utf16.txt"
            path.write_bytes("lote \u2192 0000123\r\n".encode("utf-16"))
            result = process_txt_file(path)
        self.assertEqual(result.source_encoding, "utf-16")
        self.assertEqual(result.precintos, ["000012"])

    def test_unifica_varios_archivos_y_mantiene_el_orden(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "primero.txt"
            second = Path(directory) / "segundo.txt"
            first.write_text("A -> 2052803108191\n", encoding="utf-8")
            second.write_text("B -> 2052803113133\nC -> 2052803108290\n", encoding="utf-8")
            result = process_txt_files([first, second])
        self.assertEqual(result.precintos, ["205280310819", "205280311313", "205280310829"])
        self.assertEqual(result.lines_read, 3)
        self.assertEqual(result.source_paths, [first, second])

    def test_archivos_repetidos_no_duplican_las_filas_del_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "original.txt"
            copy = Path(directory) / "copia.txt"
            content = "A -> 2052803108191\nB -> 2052803113133\n"
            first.write_text(content, encoding="utf-8")
            copy.write_text(content, encoding="utf-8")
            result = process_txt_files([first, copy])
        self.assertEqual(result.detected_count, 4)
        self.assertEqual(result.valid_lines, 4)
        self.assertEqual(result.duplicate_count, 2)
        self.assertEqual(result.exported_count, 2)
        self.assertEqual(result.precintos, ["205280310819", "205280311313"])
        self.assertIn("Precintos finales para el CSV: 2", result.summary())

    def test_csv_ax_una_columna_crlf_cp1252_sin_cabecera(self):
        content = render_ax_csv(["P001", "P001", "PRECINTO-Ñ"])
        self.assertEqual(content.decode(AX_ENCODING), "P001\r\nP001\r\nPRECINTO-Ñ\r\n")
        self.assertTrue(content.endswith(AX_LINE_ENDING.encode(AX_ENCODING)))
        self.assertFalse(content.startswith(b"\xef\xbb\xbf"))

    def test_csv_ax_usa_punto_y_coma_y_comillas_solo_si_son_necesarias(self):
        content = render_ax_csv(["normal", "A,1", "A;1", '"texto"'])
        self.assertEqual(AX_DELIMITER, ";")
        self.assertEqual(content.decode(AX_ENCODING), 'normal\r\nA,1\r\n"A;1"\r\n"""texto"""\r\n')

    def test_nombre_csv_conserva_referencia_y_sanea(self):
        self.assertEqual(csv_filename_from_source(Path("listado precintos.txt")), "listado precintos.csv")
        self.assertEqual(csv_filename_from_source(Path("CON.txt")), "precintos.csv")
        self.assertEqual(csv_filename_from_source(Path("  .txt")), "precintos.csv")
        self.assertEqual(ensure_csv_extension(Path("resultado")), Path("resultado.csv"))
        self.assertEqual(ensure_csv_extension(Path("resultado.txt")), Path("resultado.csv"))


if __name__ == "__main__":
    unittest.main()
