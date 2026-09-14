from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from suite_pyside6.core.file_compare.models import ComparisonOptions, CompareMode, ComparisonResult
from suite_pyside6.core.file_compare.service import compare_paths
from suite_pyside6.core.precintos_jamones import process_precintos_jamones, revalidate_corrections


class AuditCoreRegressionTests(unittest.TestCase):
    def test_recovery_survives_restart_and_rejects_external_edits(self):
        from suite_pyside6.core.batch_recovery import RecoverableBatch
        import os
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'SUITE_RECOVERY_DIR': directory}):
            path, prepared = Path(directory)/'a.xlsx', Path(directory)/'prepared.xlsx'
            path.write_bytes(b'original'); prepared.write_bytes(b'new')
            stat = path.stat()
            batch = RecoverableBatch([path], {path: (stat.st_size, stat.st_mtime_ns)})
            batch.commit(0, prepared, lambda src, dst: src.replace(dst))
            recovered = RecoverableBatch.load(batch.manifest)
            path.write_bytes(b'external')
            self.assertTrue(recovered.rollback(lambda src, dst: src.replace(dst)))
            self.assertEqual(path.read_bytes(), b'external')
            self.assertTrue(batch.manifest.exists())
            path.write_bytes(b'new')
            self.assertEqual(recovered.rollback(lambda src, dst: src.replace(dst)), [])
            self.assertEqual(path.read_bytes(), b'original')
            recovered.cleanup()

    def test_completed_recovery_never_rolls_back_a_successful_batch(self):
        from suite_pyside6.core.batch_recovery import RecoverableBatch
        import os
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'SUITE_RECOVERY_DIR': directory}):
            path, prepared = Path(directory)/'a.xlsx', Path(directory)/'prepared.xlsx'
            path.write_bytes(b'original'); prepared.write_bytes(b'new')
            stat = path.stat()
            batch = RecoverableBatch([path], {path: (stat.st_size, stat.st_mtime_ns)})
            batch.commit(0, prepared, lambda src, dst: src.replace(dst))
            batch.complete()
            restarted = RecoverableBatch.load(batch.manifest)
            self.assertEqual(restarted.rollback(lambda src, dst: src.replace(dst)), [])
            self.assertEqual(path.read_bytes(), b'new')
            restarted.cleanup()

    def test_layout_rejects_nonfinite_or_wrong_types(self):
        from suite_pyside6.core.numerador_etiquetas import LabelLayout
        for value in (float('nan'), float('inf'), True, 'invalid', 1e100):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                LabelLayout(width_mm=value).normalized()

    def test_tabular_streaming_reports_last_row(self):
        result = self.compare('.csv', b'a;b\n1;2\n3;4\n', b'a;b\n1;2\n3;5\n')
        self.assertFalse(result.semantic_equal)
        self.assertIn('fila 3', result.differences[0].location)

    def test_txt_errors_include_source_line_and_distinguish_same_names(self):
        from suite_pyside6.core.txt_csv import process_txt_files
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory)/'one', Path(directory)/'two'
            first.mkdir(); second.mkdir()
            paths = [folder/'same.txt' for folder in (first, second)]
            for path in paths: path.write_bytes(b'correct;1\ninvalid;\xff\n')
            result = process_txt_files(paths)
            self.assertEqual(result.error_count, 2)
            self.assertEqual(len(result.error_files), 2)
            self.assertEqual([issue['line'] for issue in result.issues], [2, 2])

    def compare(self, suffix, a, b, **options):
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory)/('a'+suffix), Path(directory)/('b'+suffix)
            left.write_bytes(a)
            right.write_bytes(b)
            return compare_paths(left, right, ComparisonOptions(mode=CompareMode.SEMANTIC, **options))

    def test_xml_mixed_content_tail(self):
        result = self.compare('.xml', b'<p>a<b/>x</p>', b'<p>a<b/>y</p>')
        self.assertFalse(result.semantic_equal)
        self.assertEqual(result.differences[0].kind, 'xml_tail')

    def test_preserve_eol_unless_requested(self):
        for ignore in (False, True):
            result = self.compare('.txt', b'a\r\nb\r\n', b'a\nb\n', ignore_line_endings=ignore)
            self.assertEqual(result.semantic_equal, ignore)
            self.assertFalse(result.strict_equal)

    def test_normalized_report_uses_same_options(self):
        result = self.compare('.txt', b'ABC\n', b'abc\n', ignore_case=True)
        self.assertTrue(result.semantic_equal)
        self.assertEqual(result.metadata['unified_diff'], '')

    def test_large_diff_uses_bounded_alignment(self):
        result = self.compare('.txt', b'A\nB\n'*3000, b'B\nA\n'*3000)
        self.assertFalse(result.semantic_equal)
        self.assertTrue(any('posición' in message for message in result.warnings))
        self.assertIn('_text_preview', result.metadata)
        self.assertNotIn('_text_preview', result.to_dict()['metadata'])

    def test_unknown_comparison_is_not_different(self):
        self.assertEqual(ComparisonResult('a', 'b').status_text(), 'INCOMPLETO')
        self.assertEqual(ComparisonResult('a', 'b', errors=['error']).status_text(), 'ERROR / INCOMPLETO')

    def test_duplicate_zip_entries_not_declared_equal(self):
        with tempfile.TemporaryDirectory() as directory, warnings.catch_warnings():
            warnings.simplefilter('ignore')
            paths = [Path(directory)/name for name in ('a.zip', 'b.zip')]
            for index, path in enumerate(paths):
                with ZipFile(path, 'w') as archive:
                    archive.writestr('same', str(index))
                    archive.writestr('same', 'last')
            result = compare_paths(*paths, ComparisonOptions(mode=CompareMode.SEMANTIC))
            self.assertIsNone(result.semantic_equal)
            self.assertTrue(result.errors)

    def test_internal_series_does_not_become_mixed_by_checksum_coincidences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'internal.txt'
            source = ''.join(f'123456;01/01/2026;10:00:00;TEST;{123456780000+i};LOT;12,5;\n' for i in range(1, 80))
            path.write_text(source, encoding='utf-8')
            before = path.read_bytes()
            result = process_precintos_jamones([path])
            self.assertEqual(result.tipo_jamon, 'Blanco')
            self.assertEqual(len(result.validos), 79)
            self.assertEqual({result.tipo_registro(item) for item in result.validos}, {'Blanco'})
            self.assertEqual(revalidate_corrections(result, '').tipo_jamon, 'Blanco')
            self.assertEqual(path.read_bytes(), before)
            path.write_text(source + '123456;01/01/2026;10:00:00;OTHER;036000291452;LOT;12,5;\n', encoding='utf-8')
            self.assertEqual(process_precintos_jamones([path]).tipo_jamon, 'Mixto')

    def test_batch_rolls_back_when_second_commit_fails(self):
        from openpyxl import Workbook
        from suite_pyside6.core import pesos
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/name for name in ('a.xlsx', 'b.xlsx')]
            for path in paths:
                book = Workbook()
                book.active.append(['pesoBruto', 'pesoNeto'])
                book.active.append([143.7, '=SUM(1,2)'])
                book.save(path)
                book.close()
            original = [path.read_bytes() for path in paths]
            commit = pesos._commit_temporary
            def fail_second(source, destination):
                if destination.resolve() == paths[1].resolve():
                    raise PermissionError('Injected failure')
                return commit(source, destination)
            with patch.object(pesos, '_commit_temporary', fail_second):
                result = pesos.process_pesos_files(paths, dict.fromkeys(paths, 'normal'))
            self.assertGreater(result.error_count, 0)
            self.assertEqual([path.read_bytes() for path in paths], original)


class AuditUIRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_destroyed_dynamic_controls_do_not_break_finalization(self):
        from PySide6.QtWidgets import QWidget, QPushButton
        from PySide6.QtCore import QCoreApplication, QEvent
        from threading import Event
        from suite_pyside6.ui.background import run_background
        from qt_jobs import wait_for_jobs
        owner = QWidget(); button = QPushButton('Eliminar', owner)
        release = Event(); completed = []
        run_background(owner, lambda: release.wait(5), completed.append, self.fail)
        button.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        release.set(); wait_for_jobs(owner)
        self.assertEqual(completed, [True])

    def test_table_selection_tracks_key_after_inserting_row(self):
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
        from suite_pyside6.ui.table_utils import bulk_table_update
        table = QTableWidget(2, 1)
        for row, value in enumerate(('a', 'b')): table.setItem(row, 0, QTableWidgetItem(value))
        table.setCurrentCell(1, 0)
        with bulk_table_update(table):
            table.setRowCount(3)
            for row, value in enumerate(('new', 'a', 'b')): table.setItem(row, 0, QTableWidgetItem(value))
        self.assertEqual(table.currentItem().text(), 'b')
        self.assertEqual([item.text() for item in table.selectedItems()], ['b'])

    def test_print_failure_keeps_pending_interval_before_sending(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QDialog
        from suite_pyside6.ui import numerador_etiquetas_window as module
        with tempfile.TemporaryDirectory() as directory:
            prefs = QSettings(str(Path(directory)/'prefs.ini'), QSettings.IniFormat)
            prefs.setValue('labels/numerador/layout', '[]')
            with patch.object(module, 'settings', lambda: prefs):
                window = module.NumeradorEtiquetasWindow()
                def fail_after_start(*args):
                    self.assertIsNotNone(window.pending_job)
                    self.assertTrue(prefs.value(f'{window.SETTINGS_PREFIX}/pending/first'))
                    raise RuntimeError('Synthetic printer failure')
                with patch.object(module.QPrintDialog, 'exec', return_value=QDialog.Accepted), patch.object(window, '_configure_printer'), patch.object(window, '_render_print_job', side_effect=fail_after_start):
                    window.print_labels()
                self.assertIsNotNone(window.pending_job)
                self.assertEqual(window.last_code, '')
                window.hide()

    def test_job_finalizes_before_callback_and_releases_bridges(self):
        from PySide6.QtWidgets import QWidget
        from PySide6.QtCore import QCoreApplication, QEvent
        from suite_pyside6.ui.background import run_background, _CompletionBridge
        from qt_jobs import wait_for_jobs
        owner, active_states = QWidget(), []
        for _ in range(20):
            run_background(owner, lambda: 1,
                           lambda value: active_states.append(owner.property('operationActive')),
                           lambda message: self.fail(message))
            wait_for_jobs(owner)
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertEqual(active_states, [False]*20)
        self.assertEqual(len(owner.findChildren(_CompletionBridge)), 0)

    def test_mermas_inputs_invalidate_result(self):
        from suite_pyside6.ui.mermas_window import MermasWindow
        window = MermasWindow()
        window.result = object()
        window.set_origin_file(Path('changed.csv'))
        self.assertIsNone(window.result)
        self.assertFalse(window.save_button.isEnabled())
        window.close()
