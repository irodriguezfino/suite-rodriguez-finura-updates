import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QMainWindow, QWidget, QVBoxLayout, QProgressBar
from suite_pyside6.core.jobs import JobContext, JobCancelled, JobProgress, checkpoint, job_scope
from suite_pyside6.core.batch_recovery import RecoverableBatch
from suite_pyside6.core.pesos import _commit_temporary
from suite_pyside6.ui.record_table import RecordTable
from suite_pyside6.ui.background import run_background
from suite_pyside6.ui.job_display import request_cancel
from qt_jobs import wait_for_jobs


class CompletionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_cancel_is_not_swallowed_as_a_validation_error(self):
        context = JobContext()
        context.cancel()
        with self.assertRaises(JobCancelled), job_scope(context):
            try:
                checkpoint()
            except Exception:
                self.fail('Domain error boundary swallowed cancellation')

    def test_commit_disables_cancellation_and_deadline(self):
        context = JobContext()
        with job_scope(context):
            context.begin_commit()
            context.deadline = 0
            self.assertFalse(context.cancel())
            checkpoint()

    def test_preparation_timeout(self):
        with self.assertRaises(TimeoutError), job_scope(JobContext(timeout=-1)):
            pass

    def test_cancelled_backup_preparation_cleans_owned_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, SUITE_RECOVERY_DIR=directory):
            path = Path(directory)/'a.xls'
            path.write_bytes(b'original')
            stat = path.stat()
            context = JobContext()
            with job_scope(context):
                context.cancel()
                with self.assertRaises(JobCancelled):
                    RecoverableBatch([path], {path:(stat.st_size, stat.st_mtime_ns)})
            self.assertEqual(list((Path(directory)/'suite-recovery').iterdir()), [])

    def test_late_external_edit_is_preserved_and_restored(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, SUITE_RECOVERY_DIR=directory):
            root = Path(directory)
            path, output = root/'original.xls', root/'prepared.xls'
            path.write_bytes(b'original'); output.write_bytes(b'prepared')
            stat = path.stat()
            batch = RecoverableBatch([path], {path:(stat.st_size,stat.st_mtime_ns)})
            def late_edit(source, target):
                target.write_bytes(b'external version written in race window')
                _commit_temporary(source, target)
            with self.assertRaisesRegex(ValueError, 'Conflicto'):
                batch.commit(0, output, late_edit)
            loaded = RecoverableBatch.load(batch.manifest)
            self.assertEqual(loaded.rollback(_commit_temporary), [])
            self.assertEqual(path.read_bytes(), b'external version written in race window')
            loaded.cleanup()
            self.assertFalse(list(root.glob('.suite-*')))

    def test_open_file_lock_does_not_destroy_original(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, SUITE_RECOVERY_DIR=directory):
            path, output = Path(directory)/'a.xls', Path(directory)/'b.xls'
            path.write_bytes(b'original'); output.write_bytes(b'prepared')
            stat=path.stat()
            batch=RecoverableBatch([path], {path:(stat.st_size,stat.st_mtime_ns)})
            with path.open('rb'), self.assertRaises(PermissionError):
                batch.commit(0, output, _commit_temporary)
            self.assertEqual(path.read_bytes(), b'original')
            self.assertEqual(batch.rollback(_commit_temporary), [])
            batch.cleanup()

    def test_five_thousand_rows_have_no_per_row_widgets_and_keyboard_works(self):
        window = QMainWindow()
        table = RecordTable(['Archivo', 'Vaciado'], window)
        window.setCentralWidget(table)
        checked = set()
        table.records.checks = {1:(lambda key: key in checked, lambda key, value: checked.add(key) if value else checked.discard(key))}
        table.set_records(range(5000), [(f'file-{i}.xls', 'Normal') for i in range(5000)])
        self.assertEqual(table.rowCount(), 5000)
        self.assertFalse(table.findChildren(QCheckBox))
        self.assertLess(len(table.findChildren(QWidget)), 30)
        window.show()
        index = table.model().index(4999, 1)
        table.setCurrentIndex(index)
        table.scrollTo(index)
        QTest.qWait(10)
        before=table.verticalScrollBar().value()
        QTest.keyClick(table, Qt.Key_Space)
        self.assertIn(4999, checked)
        self.assertEqual(table.verticalScrollBar().value(), before)
        window.setProperty('operationActive', True)
        self.assertFalse(table.activate(index))
        window.close()

    def test_indicator_does_not_reset_on_phase_change_or_finish_early(self):
        window=QMainWindow(); body=QWidget(); QVBoxLayout(body); window.setCentralWidget(body)
        from suite_pyside6.ui.job_display import install_job_display
        display=install_job_display(window)
        display.start(True)
        for done in (10, 80, 20, 100):
            display.progress(JobProgress('Preparando', done, 100, 'unidades', True))
        self.assertEqual(display.bar.value(), 99)
        display.progress(JobProgress('Verificando'))
        self.assertEqual(display.bar.value(), 99)
        window.setProperty('jobState', 'cancelling')
        display.cancel.setEnabled(False)
        display.progress(JobProgress('Preparando', 50, 100, 'unidades', True))
        self.assertFalse(display.cancel.isEnabled())
        display.finish('succeeded')
        self.assertEqual(display.bar.value(), 100)
        window.close()

    def test_background_cancel_releases_busy_and_can_restart(self):
        window=QMainWindow(); body=QWidget(); QVBoxLayout(body); window.setCentralWidget(body)
        results, errors = [], []
        def work():
            for _ in range(100):
                checkpoint()
                time.sleep(.005)
            return 'done'
        self.assertTrue(run_background(window, work, results.append, errors.append))
        self.assertFalse(run_background(window, work, results.append, errors.append))
        request_cancel(window)
        wait_for_jobs(window)
        self.assertEqual(window.property('jobState'), 'cancelled')
        self.assertFalse(results)
        self.assertTrue(errors)
        self.assertTrue(run_background(window, lambda:'again', results.append, errors.append))
        wait_for_jobs(window)
        self.assertEqual(results, ['again'])
        window.close()

    def test_xml_spaces_are_significant_unless_option_is_enabled(self):
        from suite_pyside6.core.file_compare import compare_paths, ComparisonOptions
        from suite_pyside6.core.file_compare.models import CompareMode
        with tempfile.TemporaryDirectory() as directory:
            a,b=Path(directory)/'a.xml',Path(directory)/'b.xml'
            a.write_text('<a> x <b/> y </a>'); b.write_text('<a>x<b/>y</a>')
            exact=compare_paths(a,b,ComparisonOptions(mode=CompareMode.SEMANTIC))
            relaxed=compare_paths(a,b,ComparisonOptions(mode=CompareMode.SEMANTIC, ignore_whitespace=True))
            self.assertGreater(exact.total_differences, 0)
            self.assertEqual(relaxed.total_differences, 0)

    def test_encoding_fallback_yields_no_duplicate_prefix(self):
        from suite_pyside6.core.text_stream import iter_text_lines
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'a.txt'
            path.write_bytes(b'valid\r\n' * 20000 + b'caf\xe9\r\n')
            rows=list(iter_text_lines(path))
            self.assertEqual(len(rows), 20001)
            self.assertEqual(rows[-1], 'café')

    def test_stream_preserves_all_legacy_line_separators(self):
        from suite_pyside6.core.text_stream import iter_text_lines
        text='a\r\nb\rc\nd\ve\ff\x1cg\x85h\u2028i\u2029'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'a.txt'
            path.write_text(text,encoding='utf-8',newline='')
            self.assertEqual(list(iter_text_lines(path)),text.splitlines())

    def test_supervisor_tolerates_exit_between_wait_and_terminate(self):
        from unittest.mock import MagicMock
        from suite_pyside6.core.owned_process import OwnedProcess
        owner=OwnedProcess.__new__(OwnedProcess)
        owner.handle=42
        owner.api=MagicMock()
        owner.api.WaitForSingleObject.side_effect=[258,0]
        owner.api.TerminateProcess.return_value=False
        owner.terminate_if_running()
        owner.api.TerminateProcess.assert_called_once_with(42,1)

    def test_supervisor_never_accepts_reused_process_identity(self):
        import ctypes
        from ctypes import wintypes as w
        import subprocess
        import sys
        from suite_pyside6.core.owned_process import OwnedProcess
        executable=getattr(sys, '_base_executable', sys.executable)
        child=subprocess.Popen([executable,'-c','import time; time.sleep(30)'],creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            api=ctypes.WinDLL('kernel32',use_last_error=True)
            api.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]; api.OpenProcess.restype=w.HANDLE
            api.GetProcessTimes.argtypes=[w.HANDLE]+[ctypes.POINTER(w.FILETIME)]*4
            api.CloseHandle.argtypes=[w.HANDLE]
            handle=api.OpenProcess(0x1000,False,child.pid)
            values=[w.FILETIME() for _ in range(4)]
            self.assertTrue(api.GetProcessTimes(handle,*(ctypes.byref(v) for v in values)))
            api.CloseHandle(handle)
            created=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime
            with self.assertRaises(ValueError):
                OwnedProcess(child.pid,created+1,Path(executable).name)
            self.assertIsNone(child.poll())
            owner=OwnedProcess(child.pid,created,Path(executable).name)
            try:
                owner.terminate_if_running()
                child.wait(timeout=5)
            finally:
                owner.close()
        finally:
            if child.poll() is None:
                child.kill(); child.wait(timeout=5)

    def test_comparison_inputs_are_not_inferred_from_visible_labels(self):
        from suite_pyside6.ui.file_compare_window import FileCompareWindow
        window=FileCompareWindow()
        window._set_path(window.left_label,Path('example.xml'))
        window.left_label.setText('Texto de presentación modificado')
        self.assertEqual(window._left_path(),Path('example.xml'))
        window._result=object()
        window.ignore_case.setChecked(True)
        self.assertIsNone(window._result)
        window.close()

    def test_virtual_table_reset_preserves_multiple_selected_keys(self):
        from PySide6.QtCore import QItemSelectionModel
        window=QMainWindow()
        table=RecordTable(['Archivo'],window)
        table.set_records(['a','b','c'],[('A',),('B',),('C',)])
        table.setCurrentIndex(table.model().index(1,0))
        for row in (0,1,2):
            table.selectionModel().select(table.model().index(row,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
        table.set_records(['c','b','a'],[('C',),('B',),('A',)])
        self.assertEqual({index.data(Qt.UserRole) for index in table.selectionModel().selectedRows()},{'a','b','c'})
        self.assertEqual(table.currentIndex().data(Qt.UserRole),'b')
        window.close()
