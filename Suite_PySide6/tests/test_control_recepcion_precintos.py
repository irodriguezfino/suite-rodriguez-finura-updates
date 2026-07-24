from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QFrame, QPlainTextEdit, QScrollArea, QToolButton

from suite_pyside6.core.apps import APP_REGISTRY, app_by_key
from suite_pyside6.core.empresas_clientes import EmpresasClientesLoadResult
from suite_pyside6.core.recepcion_maquilas import (
    FilaRango,
    RecepcionResult,
    RegistroMaquila,
    RegistroOficial,
    generar_pdf_rangos,
    nombre_base_articulo,
    nombres_articulo_informe,
)
from suite_pyside6.ui.app_windows import get_window_class
from suite_pyside6.ui.control_recepcion_maquilas_window import ControlRecepcionPrecintosWindow
from suite_pyside6.ui.components import ModernSelect, SearchableComboBox
from suite_pyside6.ui.main_window import MainWindow
from suite_pyside6.ui.personalized_descriptions import (
    PersonalizedDescriptionControl,
    header_description_key,
    migrate_control_recepcion_precintos_header,
    process_description_key,
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
        self.assertIs(get_window_class(app.key), ControlRecepcionPrecintosWindow)

    def test_empresa_cliente_es_selector_y_se_conserva_como_campo_manual(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user = QSettings(str(Path(directory) / "usuario.ini"), QSettings.IniFormat)
            companies = ("JAMONES DURIBER, S.L.", "EMBUTIDOS RODRIGUEZ, S.L.U.", "VALL TRADICION IBERICA, S.L.")
            loaded = EmpresasClientesLoadResult(Path(directory) / "empresas_clientes.txt", companies)
            with (
                patch("suite_pyside6.ui.control_recepcion_maquilas_window.settings", return_value=user),
                patch("suite_pyside6.ui.control_recepcion_maquilas_window.load_empresas_clientes", return_value=loaded),
            ):
                window = ControlRecepcionPrecintosWindow()
                self.assertIsInstance(window.empresa_cliente, ModernSelect)
                self.assertNotIsInstance(window.empresa_cliente, SearchableComboBox)
                self.assertFalse(window.empresa_cliente.isEditable())
                self.assertEqual(window.empresa_cliente.currentIndex(), -1)
                self.assertEqual([window.empresa_cliente.itemText(index) for index in range(window.empresa_cliente.count())], list(companies))
                window.empresa_cliente.setCurrentIndex(1)
                self.assertEqual(window._metadata()["empresa_cliente"], "EMBUTIDOS RODRIGUEZ, S.L.U.")
                window.close()

    def test_recarga_empresas_conserva_o_limpia_la_seleccion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "empresas_clientes.txt"
            first = EmpresasClientesLoadResult(config, ("Cliente A", "Cliente B"))
            with patch("suite_pyside6.ui.control_recepcion_maquilas_window.load_empresas_clientes", return_value=first):
                window = ControlRecepcionPrecintosWindow()
            window.empresa_cliente.setCurrentIndex(1)
            with patch(
                "suite_pyside6.ui.control_recepcion_maquilas_window.load_empresas_clientes",
                return_value=EmpresasClientesLoadResult(config, ("Cliente B", "Cliente C")),
            ):
                window.reload_empresas_clientes()
            self.assertEqual(window._metadata()["empresa_cliente"], "Cliente B")
            with patch(
                "suite_pyside6.ui.control_recepcion_maquilas_window.load_empresas_clientes",
                return_value=EmpresasClientesLoadResult(config, ("Cliente C",)),
            ):
                window.reload_empresas_clientes()
            self.assertEqual(window.empresa_cliente.currentIndex(), -1)
            self.assertEqual(window._metadata()["empresa_cliente"], "")
            window.close()

    def test_empresa_cliente_es_obligatoria_para_el_informe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            loaded = EmpresasClientesLoadResult(Path(directory) / "empresas_clientes.txt", ("Cliente A",))
            with patch("suite_pyside6.ui.control_recepcion_maquilas_window.load_empresas_clientes", return_value=loaded):
                window = ControlRecepcionPrecintosWindow()
            window.show_dialogs = False
            self.assertFalse(window._validate_empresa_cliente())
            self.assertIn("Selecciona una empresa cliente", window.status.text())
            window.empresa_cliente.setCurrentIndex(0)
            self.assertTrue(window._validate_empresa_cliente())
            window.close()

    def test_destinatarios_habituales_dinamicos_se_guardan_y_cargan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user = QSettings(str(Path(directory) / "usuario.ini"), QSettings.IniFormat)
            with patch("suite_pyside6.ui.control_recepcion_maquilas_window.settings", return_value=user):
                window = ControlRecepcionPrecintosWindow()
                self.assertEqual(len(window.recipient_fields), 1)
                window.recipient_fields[0].setText(" a@test.com, b@test.com\nc@test.com ")
                window._normalize_recipient_fields()
                self.assertEqual([field.text() for field in window.recipient_fields], ["a@test.com", "b@test.com", "c@test.com"])
                window._remove_recipient_field(window.recipient_fields[1])
                window._add_recipient_field("d@test.com")
                window.save_email_template()
                window.close()

                reopened = ControlRecepcionPrecintosWindow()
                self.assertEqual([field.text() for field in reopened.recipient_fields], ["a@test.com", "c@test.com", "d@test.com"])
                reopened._add_recipient_field("temporal@test.com")
                self.assertEqual(reopened._validated_recipients(), ["a@test.com", "c@test.com", "d@test.com", "temporal@test.com"])
                reopened.close()

                restored = ControlRecepcionPrecintosWindow()
                self.assertEqual([field.text() for field in restored.recipient_fields], ["a@test.com", "c@test.com", "d@test.com"])
                restored.close()

    def test_destinatarios_migran_campos_anteriores_y_validan_entradas_individuales(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user = QSettings(str(Path(directory) / "usuario.ini"), QSettings.IniFormat)
            user.setValue("mail/control_recepcion_precintos/recipient_1", " a@test.com ")
            user.setValue("mail/control_recepcion_precintos/recipient_2", "b@test.com")
            with patch("suite_pyside6.ui.control_recepcion_maquilas_window.settings", return_value=user):
                window = ControlRecepcionPrecintosWindow()
                self.assertEqual([field.text() for field in window.recipient_fields], ["a@test.com", "b@test.com"])
                self.assertEqual(user.value("mail/control_recepcion_precintos/recipients"), ["a@test.com", "b@test.com"])
                window._add_recipient_field(" A@TEST.COM ")
                self.assertEqual(window._validated_recipients(), ["a@test.com", "b@test.com"])
                self.assertEqual(len(window.recipient_fields), 2)
                window._add_recipient_field("correo inválido")
                self.assertIsNone(window._validated_recipients())
                self.assertTrue(window.recipient_fields[-1].property("error"))
                window._remove_recipient_field(window.recipient_fields[-1])
                for field in tuple(window.recipient_fields):
                    window._remove_recipient_field(field)
                self.assertIsNone(window._validated_recipients())
                window.close()

    def test_paneles_auxiliares_son_exclusivos_y_no_usan_scroll_horizontal(self) -> None:
        window = ControlRecepcionPrecintosWindow()
        metadata_header = window.metadata_section.findChild(QToolButton, "CollapsibleHeader")
        email_header = window.email_section.findChild(QToolButton, "CollapsibleHeader")
        self.assertIsNotNone(metadata_header)
        self.assertIsNotNone(email_header)
        self.assertEqual(window.metadata_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)
        self.assertEqual(window.email_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarAlwaysOff)
        self.assertIsNotNone(window.findChild(QFrame, "ContextPanel"))
        self.assertIs(window.output.parentWidget(), window.output_section)
        self.assertEqual(window.rail_layout.indexOf(window.output), -1)
        self.assertIsNone(window.findChild(QScrollArea, "WindowScroll"))
        window.resize(1400, 900)
        window.show()
        self.application.processEvents()

        metadata_header.setChecked(True)  # type: ignore[union-attr]
        self.application.processEvents()
        self.assertTrue(metadata_header.isChecked())  # type: ignore[union-attr]
        self.assertFalse(email_header.isChecked())  # type: ignore[union-attr]
        expanded_height = window.metadata_scroll.height()
        selected_company = window.empresa_cliente.itemText(0)
        window.empresa_cliente.setCurrentIndex(0)

        window.resize(900, 700)
        self.application.processEvents()
        self.assertLessEqual(window.metadata_scroll.height(), expanded_height)
        self.assertEqual(window.metadata_scroll.horizontalScrollBar().maximum(), 0)
        self.assertLessEqual(window.empresa_cliente.width(), window.metadata_scroll.viewport().width())
        self.assertEqual(window.metadata_section.width(), window.email_section.width())
        self.assertGreater(window.metadata_section.width(), window.centralWidget().width() * 0.3)

        email_header.setChecked(True)  # type: ignore[union-attr]
        self.application.processEvents()
        self.assertFalse(metadata_header.isChecked())  # type: ignore[union-attr]
        self.assertTrue(email_header.isChecked())  # type: ignore[union-attr]
        self.assertEqual(window.empresa_cliente.currentText(), selected_company)
        self.assertTrue(window.add_recipient_button.isVisible())
        self.assertTrue(window.save_template_button.isVisible())
        self.assertTrue(window.email_actions.isVisible())
        for index in range(6):
            window._add_recipient_field(f"extra{index}@test.com")
        self.application.processEvents()
        self.assertEqual(window.email_scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual(window.email_scroll.verticalScrollBarPolicy(), Qt.ScrollBarAsNeeded)
        self.assertLessEqual(window.recipients_editor.width(), window.email_scroll.viewport().width())
        self.assertLess(window.rail_layout.indexOf(window.metadata_section), window.rail_layout.indexOf(window.email_section))
        output_header = window.output_section.findChild(QToolButton, "CollapsibleHeader")
        self.assertIsNotNone(output_header)
        output_header.setChecked(True)  # type: ignore[union-attr]
        self.application.processEvents()
        self.assertTrue(window.output.isVisible())
        self.assertGreaterEqual(window.output.height(), window.output.minimumHeight())
        self.assertEqual(len(window.findChildren(QPlainTextEdit, "OutputText")), 1)
        window.output.setPlainText("AX0001\nAX0002")
        output_header.setChecked(False)  # type: ignore[union-attr]
        output_header.setChecked(True)  # type: ignore[union-attr]
        self.assertEqual(window.output.toPlainText(), "AX0001\nAX0002")

        email_header.setChecked(False)  # type: ignore[union-attr]
        self.assertFalse(metadata_header.isChecked())  # type: ignore[union-attr]
        self.assertFalse(email_header.isChecked())  # type: ignore[union-attr]
        window.close()

    def test_nombre_articulo_del_informe_usa_configuracion_y_tiene_respaldo(self) -> None:
        filas = [
            FilaRango(
                lote="L1",
                etiqueta_rango="7-8",
                producto_corto="Jamón",
                piezas=1,
                peso_total=1,
                peso_medio=1,
                codigo_fac="FAC-1",
                producto_completo="Jamón de cebo 50% ibérico",
            )
        ]
        oficiales = [
            RegistroOficial("A1", "FAC-2", "Paleta curada", "L2", "123"),
        ]
        self.assertEqual(nombres_articulo_informe(filas, oficiales, "FAC-1"), "Jamón de cebo 50% ibérico")
        self.assertEqual(nombres_articulo_informe([], oficiales, "FAC-2"), "Paleta curada")
        self.assertEqual(nombres_articulo_informe([], [], "FAC-3"), "")

    def test_articulo_del_informe_elimina_rangos_finales_y_duplicados(self) -> None:
        self.assertEqual(nombre_base_articulo("JAMON CEBO IBERICO 10,5-12"), "JAMON CEBO IBERICO")
        self.assertEqual(nombre_base_articulo("JAMON CEBO IBERICO 12,00 - 12,99 kg"), "JAMON CEBO IBERICO")
        self.assertEqual(nombre_base_articulo("JAMON CEBO IBERICO 14-15,5,"), "JAMON CEBO IBERICO")
        self.assertEqual(nombre_base_articulo("PRODUCTO 100% IBERICO 10-12 KG"), "PRODUCTO 100% IBERICO")
        self.assertEqual(nombre_base_articulo("ARTICULO 2024"), "ARTICULO 2024")
        self.assertEqual(nombre_base_articulo(""), "")
        filas = [
            FilaRango("L1", "10,5-12", "Jamón", 1, Decimal("11"), Decimal("11"), "FAC-1", "JAMON CEBO IBERICO 10,5-12"),
            FilaRango("L1", "12-13", "Jamón", 1, Decimal("12.5"), Decimal("12.5"), "FAC-1", "jamon   cebo iberico 12-13"),
            FilaRango("L1", "13-14", "Jamón", 1, Decimal("13.5"), Decimal("13.5"), "FAC-1", "JAMON CEBO IBERICO 13-14"),
            FilaRango("L1", "14-15,5", "Jamón", 1, Decimal("14.5"), Decimal("14.5"), "FAC-1", "JAMON CEBO IBERICO 14-15,5"),
        ]
        self.assertEqual(nombres_articulo_informe(filas, [], "FAC-1"), "JAMON CEBO IBERICO")
        filas.append(FilaRango("L2", "7-8", "Paleta", 1, Decimal("7.5"), Decimal("7.5"), "FAC-1", "PALETA CURADA 7-8"))
        self.assertEqual(nombres_articulo_informe(filas, [], "FAC-1"), "JAMON CEBO IBERICO, PALETA CURADA")

    def test_pdf_rangos_muestra_empresa_cliente_y_nombre_de_articulo(self) -> None:
        fila = FilaRango("L1", "7-8", "Jamón", 1, Decimal("7.5"), Decimal("7.5"), "FAC-1", "Jamón de cebo 7-8")
        registro = RegistroMaquila("entrada.txt", 1, "P1", "010125", "1200", "FAC-1", "123", "L1", Decimal("7.5"))
        oficial = RegistroOficial("A1", "FAC-1", "Jamón de cebo", "L1", "123")
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "rangos.pdf"
            generar_pdf_rangos(
                pdf,
                RecepcionResult(filas_rangos=[fila], registros_txt=[registro], registros_oficiales=[oficial]),
                {"empresa_cliente": "Cliente de prueba"},
            )
            contenido = pdf.read_bytes().decode("cp1252", errors="replace")
        self.assertIn("Empresa cliente", contenido)
        self.assertIn("Cliente de prueba", contenido)
        self.assertIn("Artículo", contenido)
        self.assertIn("Jamón de cebo", contenido)
        self.assertNotIn("Jamón de cebo 7-8", contenido)
        self.assertNotIn("Codigo FAC", contenido)

    def test_pdf_rangos_conserva_cada_empresa_cliente_configurada(self) -> None:
        fila = FilaRango("L1", "7-8", "Jamón", 1, Decimal("7.5"), Decimal("7.5"), "FAC-1", "Jamón de cebo")
        registro = RegistroMaquila("entrada.txt", 1, "P1", "010125", "1200", "FAC-1", "123", "L1", Decimal("7.5"))
        oficial = RegistroOficial("A1", "FAC-1", "Jamón de cebo", "L1", "123")
        result = RecepcionResult(filas_rangos=[fila], registros_txt=[registro], registros_oficiales=[oficial])
        companies = ("JAMONES DURIBER, S.L.", "EMBUTIDOS RODRIGUEZ, S.L.U.", "VALL TRADICION IBERICA, S.L.")
        with tempfile.TemporaryDirectory() as directory:
            for index, company in enumerate(companies):
                pdf = Path(directory) / f"rangos_{index}.pdf"
                generar_pdf_rangos(pdf, result, {"empresa_cliente": company})
                self.assertIn(company, pdf.read_bytes().decode("cp1252", errors="replace"))

    def test_pdf_rangos_muestra_un_articulo_base_y_conserva_los_rangos(self) -> None:
        rangos = ("10,5-12", "12-13", "13-14", "14-15,5")
        filas = [
            FilaRango("L1", rango, "JAMON", 1, Decimal("12"), Decimal("12"), "FAC-1", f"JAMON CEBO IBERICO {rango}")
            for rango in rangos
        ]
        registro = RegistroMaquila("entrada.txt", 1, "P1", "010125", "1200", "FAC-1", "123", "L1", Decimal("12"))
        oficial = RegistroOficial("A1", "FAC-1", "JAMON CEBO IBERICO", "L1", "123")
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "rangos.pdf"
            generar_pdf_rangos(pdf, RecepcionResult(filas_rangos=filas, registros_txt=[registro], registros_oficiales=[oficial]))
            contenido = pdf.read_bytes().decode("cp1252", errors="replace")
        self.assertEqual(contenido.count("JAMON CEBO IBERICO"), 1)
        for rango in rangos:
            self.assertIn(rango, contenido)
            self.assertNotIn(f"JAMON CEBO IBERICO {rango}", contenido)

    def test_descripciones_independientes_reemplazan_el_texto_estandar(self) -> None:
        app_key = "control_recepcion_precintos"
        header_key = header_description_key(app_key)
        process_one_key = process_description_key(app_key, "catalog")
        process_two_key = process_description_key(app_key, "review")
        with tempfile.TemporaryDirectory() as directory:
            user_a = QSettings(str(Path(directory) / "usuario-a.ini"), QSettings.IniFormat)
            user_b = QSettings(str(Path(directory) / "usuario-b.ini"), QSettings.IniFormat)
            with patch("suite_pyside6.ui.session.settings", return_value=user_a):
                header = PersonalizedDescriptionControl("Descripción estándar de cabecera", header_key)
                process_one = PersonalizedDescriptionControl("Descripción estándar del proceso", process_one_key)
                process_two = PersonalizedDescriptionControl("Otra descripción estándar", process_two_key)
                self.assertEqual(header.description_label.text(), "Descripción estándar de cabecera")
                self.assertEqual(process_one.description_label.text(), "Descripción estándar del proceso")
                self.assertEqual(header.edit_button.text(), "Añadir descripción")

                save_personal_description(header_key, "Cabecera <script>alert(1)</script>")
                save_personal_description(process_one_key, "Proceso uno")
                save_personal_description(process_two_key, "Proceso dos")
                header.configure("Descripción estándar de cabecera", header_key)
                process_one.configure("Descripción estándar del proceso", process_one_key)
                process_two.configure("Otra descripción estándar", process_two_key)
                self.assertEqual(header.description_label.text(), "Cabecera <script>alert(1)</script>")
                self.assertEqual(header.description_label.textFormat(), Qt.PlainText)
                self.assertEqual(process_one.description_label.text(), "Proceso uno")
                self.assertEqual(process_two.description_label.text(), "Proceso dos")
                self.assertEqual(header.edit_button.text(), "Editar descripción")
                self.assertFalse(header.restore_button.isHidden())

                remove_personal_description(header_key)
                header.configure("Descripción estándar de cabecera", header_key)
                self.assertEqual(header.description_label.text(), "Descripción estándar de cabecera")
                self.assertTrue(header.restore_button.isHidden())
                with self.assertRaises(ValueError):
                    save_personal_description(process_one_key, "x" * (MAX_PERSONAL_DESCRIPTION_LENGTH + 1))

                legacy_key = "control_recepcion_precintos.description"
                save_personal_description(legacy_key, "Aclaración previa")
                migrate_control_recepcion_precintos_header()
                self.assertEqual(personal_description(header_key), "Aclaración previa")
                self.assertEqual(personal_description(legacy_key), "")

            with patch("suite_pyside6.ui.session.settings", return_value=user_b):
                self.assertEqual(personal_description(header_key), "")
                other_user_header = PersonalizedDescriptionControl("Descripción estándar de cabecera", header_key)
                self.assertEqual(other_user_header.description_label.text(), "Descripción estándar de cabecera")

    def test_cabecera_y_tarjeta_de_procesos_usan_el_mismo_control_reutilizable(self) -> None:
        app = app_by_key("control_recepcion_precintos")
        with tempfile.TemporaryDirectory() as directory:
            user = QSettings(str(Path(directory) / "usuario.ini"), QSettings.IniFormat)
            with patch("suite_pyside6.ui.session.settings", return_value=user):
                window = MainWindow()
                window.open_app(app)
                self.assertEqual(window.workspace_description.description_label.text(), app.description)
                self.assertEqual(window.workspace_description.edit_button.text(), "Añadir descripción")
                header_buttons = (
                    window.workspace_description.edit_button,
                    window.workspace_description.restore_button,
                    window.about_button,
                    window.home_button,
                )
                self.assertTrue(all(button.property("headerAction") for button in header_buttons))
                self.assertEqual({button.minimumHeight() for button in header_buttons}, {header_buttons[0].minimumHeight()})
                self.assertGreaterEqual(header_buttons[0].minimumHeight(), 36)
                self.assertTrue(all(button.parentWidget() is window.header_actions for button in header_buttons))
                window.resize(1500, 900)
                window.show()
                self.application.processEvents()
                visible_buttons = tuple(button for button in header_buttons if button.isVisible())
                self.assertEqual({button.height() for button in visible_buttons}, {visible_buttons[0].height()})
                self.assertLess(window.header_actions.width(), window.header_actions.parentWidget().width())

                save_personal_description(header_description_key(app.key), "DescripciÃ³n personalizada")
                window._set_workspace_description(app.description, header_description_key(app.key))
                self.application.processEvents()
                self.assertTrue(window.workspace_description.restore_button.isVisible())
                visible_buttons = tuple(button for button in header_buttons if button.isVisible())
                self.assertEqual({button.height() for button in visible_buttons}, {visible_buttons[0].height()})
                process_row = window._process_row(app)
                process_description = process_row.findChild(PersonalizedDescriptionControl)
                self.assertIsNotNone(process_description)
                self.assertEqual(process_description.description_label.text(), app.description)  # type: ignore[union-attr]
                save_personal_description(process_description_key(app.key), "Descripción de la tarjeta")
                process_row = window._process_row(app)
                process_description = process_row.findChild(PersonalizedDescriptionControl)
                self.assertEqual(process_description.description_label.text(), "Descripción de la tarjeta")  # type: ignore[union-attr]
                window.close()


if __name__ == "__main__":
    unittest.main()
