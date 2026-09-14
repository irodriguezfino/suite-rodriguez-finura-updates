from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import errno
import io
import json
import queue

from openpyxl import Workbook

from suite_pyside6.core.pesos import SheetRename, process_pesos_files, _commit_temporary, _LegacyExcelSession, _FilePlan


def write_book(path):
    book = Workbook()
    for sheet in (book.active, book.create_sheet("Segundo")):
        sheet.append(["pesoBruto", "pesoNeto"])
        for _ in range(25):
            sheet.append([143.7, 138])
    book.save(path)
    book.close()


class BatchTests(TestCase):
    def test_session_starts_once_streams_progress_and_cleans_script(self):
        with TemporaryDirectory() as directory:
            script = Path(directory) / "worker.ps1"
            script.write_text("fixture", encoding="utf-8")
            reply = json.dumps({"success": True, "before": "Lote", "changed": True,
                                "adjustedSheets": 1, "adjustedWeights": 2})
            from unittest.mock import MagicMock
            process = MagicMock()
            process.stdin = io.StringIO()
            process.stdout = io.StringIO("PROGRESS|1|2\nPROGRESS|2|2\n" + reply + "\n" + reply + "\n")
            updates = []
            with patch("suite_pyside6.core.pesos._write_legacy_adjustment_script", return_value=script), patch(
                "suite_pyside6.core.pesos.subprocess.Popen", return_value=process
            ) as popen:
                with _LegacyExcelSession() as session:
                    for _ in range(2):
                        result = session.process(_FilePlan(Path("á.xls"), "normal"), updates.append, 0, 1000)
                        self.assertEqual(result.adjusted_weights, 2)
                    requests = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
                    self.assertEqual([request["path"] for request in requests], ["á.xls", "á.xls"])
                popen.assert_called_once()
            self.assertEqual([update.completed for update in updates], [400, 800])
            self.assertFalse(script.exists())
            self.assertTrue(process.stdin.closed)

    def test_session_timeout_covers_waiting_for_output(self):
        from unittest.mock import MagicMock
        with _LegacyExcelSession() as session:
            session._process = MagicMock()
            with patch.object(session, "_start"), patch.object(session._lines, "get", side_effect=queue.Empty), patch('suite_pyside6.core.pesos.time.monotonic', side_effect=[0, 181, 181]):
                with self.assertRaisesRegex(ValueError, "180 segundos"):
                    session.process(_FilePlan(Path("a.xls"), "normal"), None, 0, 1000)
            self.assertTrue(session._closed)

    def test_cross_volume_commit_cleans_sibling_if_replace_fails(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "prepared.tmp"
            destination = Path(directory) / "original.xls"
            source.write_bytes(b"prepared")
            destination.write_bytes(b"original")
            with patch("suite_pyside6.core.pesos.os.replace", side_effect=[OSError(errno.EXDEV, "different volumes"), PermissionError("locked")]):
                with self.assertRaises(PermissionError):
                    _commit_temporary(source, destination)
            self.assertEqual(destination.read_bytes(), b"original")
            self.assertEqual(set(Path(directory).iterdir()), {source, destination})

    def test_global_progress_does_not_restart_between_sheets_or_files(self):
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / f"{i}.xlsx" for i in range(2)]
            for path in paths:
                write_book(path)
            updates = []
            result = process_pesos_files(paths, dict.fromkeys(paths, "normal"), updates.append)
            self.assertEqual(result.error_count, 0)
            values = [u.completed / u.total for u in updates]
            self.assertEqual(values, sorted(values))
            self.assertEqual(values[0], 0)
            self.assertEqual(values[-1], 1)
            self.assertTrue(all(value < 1 for value in values[:-1]))
            self.assertFalse(any(u.busy for u in updates))
            self.assertEqual(set(Path(directory).iterdir()), set(paths))

    def test_failed_commit_preserves_original_and_cleans_staging(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "original.xlsx"
            write_book(path)
            original = path.read_bytes()
            observed = []
            def fail(temporary, target):
                self.assertNotEqual(temporary.parent, path.parent)
                observed.append(temporary)
                raise PermissionError("locked")
            updates = []
            with patch("suite_pyside6.core.pesos._commit_temporary", side_effect=fail):
                result = process_pesos_files([path], {path: "normal"}, updates.append)
            self.assertEqual(result.error_count, 1)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(observed)
            self.assertTrue(all(not item.exists() for item in observed))
            self.assertTrue(all(u.completed < u.total for u in updates))

    def test_xls_processed_once_and_validation_error_does_not_commit_any_file(self):
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / f"{i}.xls" for i in range(2)]
            for path in paths:
                path.write_bytes(b"original")
            observed = []
            def prepare(plan, *args):
                observed.append(plan.path)
                self.assertNotEqual(plan.path.parent, paths[0].parent)
                if len(observed) == 2:
                    raise ValueError("invalid weights")
                plan.path.write_bytes(b"prepared")
                return SheetRename(plan.path, True, changed=True)
            with patch.object(_LegacyExcelSession, "process", side_effect=prepare) as worker:
                result = process_pesos_files(paths, dict.fromkeys(paths, "normal"))
            self.assertEqual(worker.call_count, 2)
            self.assertEqual(result.error_count, 1)
            self.assertTrue(all(p.read_bytes() == b"original" for p in paths))
            self.assertTrue(all(not p.exists() for p in observed))

    def test_xls_batch_uses_one_session_and_commits_only_after_close(self):
        with TemporaryDirectory() as directory:
            paths = [Path(directory) / f"{i}.xls" for i in range(3)]
            for path in paths:
                path.write_bytes(b"original")
            sessions = []
            def prepare(session, plan, callback, *args):
                self.assertTrue(all(p.read_bytes() == b"original" for p in paths))
                sessions.append(session)
                plan.path.write_bytes(b"prepared")
                return SheetRename(plan.path, True, changed=True)
            def commit(temporary, target):
                self.assertTrue(sessions[0]._closed)
                target.write_bytes(temporary.read_bytes())
            with patch.object(_LegacyExcelSession, "process", prepare), patch(
                "suite_pyside6.core.pesos._commit_temporary", side_effect=commit
            ):
                result = process_pesos_files(paths, dict.fromkeys(paths, "normal"))
            self.assertEqual(result.error_count, 0)
            self.assertEqual(len(sessions), 3)
            self.assertTrue(all(session is sessions[0] for session in sessions))
            self.assertTrue(all(p.read_bytes() == b"prepared" for p in paths))

    def test_xlsx_does_not_start_excel(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "a.xlsx"
            write_book(path)
            with patch.object(_LegacyExcelSession, "_start") as start:
                result = process_pesos_files([path], {path: "normal"})
            self.assertEqual(result.error_count, 0)
            start.assert_not_called()

    def test_original_changed_during_xls_preparation_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "a.xls"
            path.write_bytes(b"original")
            def prepare(plan, *args):
                plan.path.write_bytes(b"prepared")
                path.write_bytes(b"externally edited original")
                return SheetRename(plan.path, True, changed=True)
            with patch.object(_LegacyExcelSession, "process", side_effect=prepare):
                result = process_pesos_files([path], {path: "normal"})
            self.assertEqual(result.error_count, 1)
            self.assertEqual(path.read_bytes(), b"externally edited original")

    def test_invalid_mode_is_reported_without_changing_any_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "a.xlsx"
            write_book(path)
            original = path.read_bytes()
            result = process_pesos_files([path], {path: "bad-mode"})
            self.assertEqual(result.error_count, 1)
            self.assertEqual(path.read_bytes(), original)
