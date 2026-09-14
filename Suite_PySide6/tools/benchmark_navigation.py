"""Measure navigation in a fresh interpreter, with isolated preferences.

Run with QT_QPA_PLATFORM=offscreen for reproducible headless checks. No user
documents are loaded. --source may select an existing release's src directory.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--catalog-only', action='store_true')
    args = parser.parse_args()
    if args.source:
        sys.path.insert(0, str(args.source.resolve()))
    from PySide6.QtCore import QSettings, QTimer, QEventLoop
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from suite_pyside6 import __version__
    from suite_pyside6.ui import session
    from suite_pyside6.ui.main_window import MainWindow
    from suite_pyside6.core.apps import APP_REGISTRY

    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix='suite-navigation-benchmark-') as directory:
        settings = QSettings(str(Path(directory) / 'preferences.ini'), QSettings.IniFormat)
        session.settings = lambda: settings
        window = MainWindow()
        window.show()
        app.processEvents()
        gaps = []
        previous = [time.perf_counter()]

        def tick():
            now = time.perf_counter()
            gaps.append((now - previous[0]) * 1000)
            previous[0] = now

        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(tick)
        timer.start()
        started = time.perf_counter()
        window.show_view('procesos')
        app.processEvents()
        catalog_ms = (time.perf_counter() - started) * 1000
        loop = QEventLoop()
        QTimer.singleShot(2800, loop.quit)
        loop.exec()
        tick()
        timer.stop()
        output = {'version': __version__, 'catalog_ms': round(catalog_ms, 1),
                  'max_catalog_gap_ms': round(max(gaps), 1), 'apps': []}
        if not args.catalog_only:
            for definition in APP_REGISTRY:
                started = time.perf_counter()
                window.open_app(definition)
                feedback_ms = (time.perf_counter() - started) * 1000
                deadline = time.perf_counter() + 15
                while definition.key not in window.app_pages and time.perf_counter() < deadline:
                    QTest.qWait(10)
                if definition.key not in window.app_pages:
                    raise AssertionError(f'{definition.key}: {window.navigation_loading_detail.text()}')
                app.processEvents()
                output['apps'].append({'app': definition.key, 'feedback_ms': round(feedback_ms, 1),
                                       'ready_ms': round((time.perf_counter()-started)*1000, 1)})
            output['heavy_libraries_imported'] = [name for name in ('pandas', 'openpyxl') if name in sys.modules]
        started = time.perf_counter()
        window.show_dashboard()
        app.processEvents()
        started = time.perf_counter()
        window.show_view('procesos')
        app.processEvents()
        output['catalog_revisit_ms'] = round((time.perf_counter()-started)*1000, 1)
        window.close()
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
