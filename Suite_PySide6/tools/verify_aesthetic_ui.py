"""Real Qt captures and catalogue geometry, with isolated user preferences."""
import argparse
import json
import os
import tempfile
from pathlib import Path
from PySide6.QtCore import QEventLoop, QPoint, QSettings, QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QProgressBar, QFrame
from suite_pyside6.ui import session, theme, polish


def pump(ms=40):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    scale = os.environ.get('QT_SCALE_FACTOR', '1')
    output = args.output / scale
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + name)
    app.setFont(QFont('Segoe UI', 10))
    mode = ['light']
    theme.current_theme_preference = lambda: mode[0]
    polish.current_theme_preference = lambda: mode[0]
    polish.set_theme_mode = lambda value: mode.__setitem__(0, value)
    results = {'scale': scale, 'catalogue': [], 'apps': []}
    with tempfile.TemporaryDirectory(prefix='suite-aesthetic-verification-') as directory:
        prefs = QSettings(str(Path(directory) / 'prefs.ini'), QSettings.IniFormat)
        session.settings = lambda: prefs
        from suite_pyside6.ui.main_window import MainWindow
        from suite_pyside6.ui.personalized_descriptions import PersonalizedDescriptionControl
        from suite_pyside6.core.apps import APP_REGISTRY
        from suite_pyside6.core.jobs import JobProgress
        window = MainWindow()
        window.resize(1360, 850)
        window.show()
        pump()
        window.grab().save(str(output / 'bandeja_light.png'))
        for appearance in ('light', 'dark'):
            polish.apply_theme_mode(appearance)
            window.show_view('procesos')
            for width in (1360, 1000, 960):
                window.resize(width, 620 if width == 960 else 850)
                for compact in (True, False):
                    window.compact_catalog.setChecked(compact)
                    pump()
                    name = f'procesos_{appearance}_{width}_{"compact" if compact else "detail"}'
                    window.grab().save(str(output / (name + '.png')))
                    for key, row in window._process_rows.items():
                        options, primary = row.catalog_action_buttons
                        def box(button):
                            p = button.mapTo(row, QPoint(0, 0))
                            return [p.x(), p.y(), button.width(), button.height()]
                        a, b = box(options), box(primary)
                        offset = abs(a[1] + a[3] / 2 - b[1] - b[3] / 2)
                        assert offset <= 1, (name, key, a, b)
                        assert a[3] == b[3], (name, key, a, b)
                        assert a[0] >= 0 and b[0]+b[2] <= row.width(), (name, key, a, b)
                        results['catalogue'].append({'view': name, 'key': key, 'offset': offset,
                                                     'height': a[3], 'row_height': row.height(),
                                                     'below': row._actions_below})
        # A long personal description must not affect the action group's axis.
        row = next(iter(window._process_rows.values()))
        description = row.findChild(PersonalizedDescriptionControl)
        description.description_label.setText('Descripción personalizada larga con información de trabajo. ' * 8)
        pump()
        a, b = row.catalog_action_buttons
        assert abs(a.mapTo(row, QPoint()).y()+a.height()/2-b.mapTo(row, QPoint()).y()-b.height()/2) <= 1
        window.grab().save(str(output / 'descripcion_larga.png'))
        window.resize(1360, 850)
        for definition in APP_REGISTRY:
            window.open_app(definition)
            for _ in range(200):
                pump(10)
                if definition.key in window.app_pages:
                    break
            page = window.app_pages[definition.key]
            for appearance in ('light', 'dark'):
                polish.apply_theme_mode(appearance)
                pump()
                window.grab().save(str(output / f'{definition.key}_{appearance}.png'))
            display = page._job_display
            display.start(True)
            display.progress(JobProgress('Validando registros', 38, 100, 'unidades', True))
            pump()
            assert [bar for bar in page.findChildren(QProgressBar) if bar.isVisible()] == [display.bar], definition.key
            if definition.key in ('pesos', 'file_compare', 'reparto_merma_precintos'):
                window.grab().save(str(output / f'{definition.key}_progress.png'))
            display.hide()
            results['apps'].append(definition.key)
        results['header_height'] = window.findChild(QFrame, 'ConsoleHeader').height()
        window.hide()
    (output / 'metrics.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({'scale': scale, 'rows_verified': len(results['catalogue']), 'apps': len(results['apps'])}))


if __name__ == '__main__':
    main()
