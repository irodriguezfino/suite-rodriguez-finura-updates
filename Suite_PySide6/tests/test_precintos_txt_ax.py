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
    process_txt_file,
    render_ax_csv,
)


class PrecintosTxtAxTests(unittest.TestCase):
    def test_delimitador_real_y_variantes_de_espaciado(self):
        self.assertEqual(SOURCE_DELIMITER, "->")
        result = extract_precintos("origen -> P001\ntexto\t→\tP002\nA=>P003")
        self.assertEqual(result.precintos, ["P001", "P002", "P003"])
        self.assertEqual(result.lines_read, 3)
        self.assertEqual(result.skipped_lines, 0)

    def test_ignora_vacias_e_invalidas_y_conserva_duplicados(self):
        result = extract_precintos("\r\nA -> DUP\r\nSin flecha\r\nB ->   \r\nC -> DUP\r\n")
        self.assertEqual(result.precintos, ["DUP", "DUP"])
        self.assertEqual(result.lines_read, 5)
        self.assertEqual(result.skipped_lines, 3)

    def test_saltos_windows_unix_y_contenido_exactamente_recortado_en_extremos(self):
        result = extract_precintos("A ->  precinto con espacios  \r\nB ->\tX-01\nC -> uno -> dos\n")
        self.assertEqual(result.precintos, ["precinto con espacios", "X-01", "uno -> dos"])

    def test_archivo_cp1252_y_archivo_sin_datos_validos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "origen especial.txt"
            path.write_bytes("lote -> PRECINTO-Ñ\r\nincorrecta\r\n".encode("cp1252"))
            result = process_txt_file(path)
        self.assertEqual(result.source_encoding, "cp1252")
        self.assertEqual(result.precintos, ["PRECINTO-Ñ"])
        empty = extract_precintos("\nSIN FLECHA\nA -> \t\n")
        self.assertEqual(empty.precintos, [])
        self.assertEqual(empty.skipped_lines, 3)

    def test_archivo_utf8_con_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.txt"
            path.write_bytes("lote -> P001\r\n".encode("utf-8-sig"))
            result = process_txt_file(path)
        self.assertEqual(result.source_encoding, "utf-8-sig")
        self.assertEqual(result.precintos, ["P001"])

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
