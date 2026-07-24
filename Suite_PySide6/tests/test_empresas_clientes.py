from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from suite_pyside6.core.empresas_clientes import empresas_clientes_template_path, load_empresas_clientes


class EmpresasClientesTests(unittest.TestCase):
    def test_plantilla_del_proyecto_contiene_las_empresas_iniciales_en_orden(self) -> None:
        lines = empresas_clientes_template_path().read_text(encoding="utf-8").splitlines()
        companies = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(
            companies,
            ["JAMONES DURIBER, S.L.", "EMBUTIDOS RODRIGUEZ, S.L.U.", "VALL TRADICION IBERICA, S.L."],
        )

    def test_crea_el_archivo_configurable_desde_la_plantilla(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            template = base / "plantilla.txt"
            target = base / "config" / "empresas_clientes.txt"
            template.write_text(
                "JAMONES DURIBER, S.L.\nEMBUTIDOS RODRIGUEZ, S.L.U.\nVALL TRADICION IBERICA, S.L.\n",
                encoding="utf-8",
            )
            result = load_empresas_clientes(target, template_path=template)
            self.assertTrue(target.exists())
            self.assertEqual(
                result.companies,
                ("JAMONES DURIBER, S.L.", "EMBUTIDOS RODRIGUEZ, S.L.U.", "VALL TRADICION IBERICA, S.L."),
            )

    def test_limpia_espacios_vacios_comentarios_y_duplicados_sin_reordenar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "empresas_clientes.txt"
            target.write_text(
                "# Comentario\n  Jamones Duriber, S.L.  \n\nJAMONES DURIBER, S.L.\n Cliente Ñ, S.A. \n",
                encoding="utf-8",
            )
            result = load_empresas_clientes(target)
            self.assertEqual(result.companies, ("Jamones Duriber, S.L.", "Cliente Ñ, S.A."))

    def test_archivo_existente_sin_valores_no_se_sobrescribe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "empresas_clientes.txt"
            target.write_text(" \n# Sin empresas\n", encoding="utf-8")
            result = load_empresas_clientes(target)
            self.assertEqual(result.companies, ())
            self.assertEqual(target.read_text(encoding="utf-8"), " \n# Sin empresas\n")

    def test_error_de_codificacion_devuelve_un_estado_controlado(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "empresas_clientes.txt"
            target.write_bytes(b"\xff\xfe\x00")
            result = load_empresas_clientes(target)
            self.assertEqual(result.companies, ())
            self.assertIsNotNone(result.error_message)


if __name__ == "__main__":
    unittest.main()
