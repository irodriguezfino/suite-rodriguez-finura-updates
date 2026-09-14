"""Check local ZIP/source identity and open all forms with the packaged runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = root / 'Suite_PySide6' / 'src'
    packaged = root / 'outputs' / f'full_release_{args.version}' / 'Suite Rodriguez Finura' / 'Suite_PySide6' / 'src'
    files = list(source.rglob('*.py'))
    result = {'runtime': sys.version, 'packages': {}}
    for kind in ('update', 'full'):
        package = root / f'Suite_Rodriguez_Finura_v{args.version}_{kind}.zip'
        with ZipFile(package) as archive:
            assert archive.testzip() is None
            for file in files:
                relative = file.relative_to(source)
                assert archive.read('Suite Rodriguez Finura/Suite_PySide6/src/' + relative.as_posix()) == file.read_bytes(), str(file)
                assert (packaged / relative).read_bytes() == file.read_bytes(), str(file)
        with package.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        result['packages'][kind] = {'sha256': digest, 'bytes': package.stat().st_size, 'source_files': len(files), 'crc': 'OK'}
    baseline = root / 'outputs' / 'full_release_1.7.21' / 'Suite Rodriguez Finura' / 'Suite_PySide6' / 'src'
    core = [p for p in (source / 'suite_pyside6' / 'core').rglob('*') if p.is_file() and p.suffix in ('.py', '.ps1')]
    for file in core:
        assert file.read_bytes() == (baseline / file.relative_to(source)).read_bytes(), str(file)
    result['unchanged_core_files'] = len(core)
    sys.path.insert(0, str(packaged))
    from PySide6.QtCore import QSettings, QEventLoop, QTimer, QPoint
    from PySide6.QtWidgets import QApplication
    from suite_pyside6 import __version__
    from suite_pyside6.ui import session
    from suite_pyside6.ui.main_window import MainWindow
    from suite_pyside6.core.apps import APP_REGISTRY
    from suite_pyside6.core.file_compare.models import CompareMode
    app = QApplication([])
    assert __version__ == args.version
    result['version'] = __version__
    result['forms'] = []
    with tempfile.TemporaryDirectory(prefix='suite-release-ui-check-') as directory:
        prefs = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
        session.settings = lambda: prefs
        window = MainWindow()
        window.show()
        window.show_view('procesos')
        app.processEvents()
        for row in window._process_rows.values():
            first, second = row.catalog_action_buttons
            assert first.height() == second.height()
            assert abs(first.mapTo(row, QPoint()).y() + first.height()/2 - second.mapTo(row, QPoint()).y() - second.height()/2) <= 1
        for definition in APP_REGISTRY:
            window.open_app(definition)
            started = time.monotonic()
            while definition.key not in window.app_pages:
                assert time.monotonic() - started < 15, definition.key
                loop = QEventLoop()
                QTimer.singleShot(10, loop.quit)
                loop.exec()
            result['forms'].append(definition.key)
        compare = window.app_pages['file_compare']
        assert compare.mode.currentData() == CompareMode.STRICT.value
        assert compare.maximum.value() == 100
        result['heavy_libraries_imported_on_open'] = [name for name in ('pandas', 'openpyxl') if name in sys.modules]
        assert not result['heavy_libraries_imported_on_open']
        window.hide()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
