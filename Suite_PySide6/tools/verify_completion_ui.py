"""Repeatable UI/memory budgets and scaled renders, with isolated preferences."""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path
from PySide6.QtCore import QSettings, QEventLoop, QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QProgressBar, QWidget
from suite_pyside6.ui import session, theme, polish
from suite_pyside6.core.jobs import JobProgress
from suite_pyside6.core.performance_metrics import memory_snapshot


def pump(ms=20):
    loop=QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def contrast(a,b):
    def lum(color):
        values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
        return sum(v*w for v,w in zip(values,(.2126,.7152,.0722)))
    x,y=sorted((lum(a),lum(b)))
    return (y+.05)/(x+.05)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    scale=os.environ.get('QT_SCALE_FACTOR','1')
    app=QApplication([])
    for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+name)
    app.setFont(QFont('Segoe UI',10))
    mode=['light']
    theme.current_theme_preference=lambda: mode[0]
    polish.current_theme_preference=lambda: mode[0]
    polish.set_theme_mode=lambda value: mode.__setitem__(0,value)
    result={'scale':scale,'apps':[],'contrasts':{},'budgets':{}}
    for key,palette in (('light',theme.LIGHT),('dark',theme.DARK)):
        pairs=[(fg,bg) for fg in ('text_primary','text_secondary','text_muted') for bg in ('surface','surface_muted','background')]
        pairs += [(fg,fg+'_soft') for fg in ('success','warning','error','info')]
        values={fg+'/'+bg:round(contrast(palette[fg],palette[bg]),2) for fg,bg in pairs}
        result['contrasts'][key]=values
        assert min(values.values())>=4.5, values
    with tempfile.TemporaryDirectory(prefix='suite-ui-completion-') as directory:
        prefs=QSettings(str(Path(directory)/'prefs.ini'),QSettings.IniFormat)
        session.settings=lambda:prefs
        from suite_pyside6.ui.main_window import MainWindow
        from suite_pyside6.core.apps import APP_REGISTRY
        window=MainWindow(); window.resize(1360,850); window.show(); pump()
        start=time.perf_counter(); window.show_view('procesos'); app.processEvents()
        result['catalog_ms']=(time.perf_counter()-start)*1000
        for definition in APP_REGISTRY:
            start=time.perf_counter(); window.open_app(definition)
            feedback=(time.perf_counter()-start)*1000
            while definition.key not in window.app_pages:
                assert time.perf_counter()-start<15
                pump(5)
            ready=(time.perf_counter()-start)*1000
            page=window.app_pages[definition.key]
            display=getattr(page,'_job_display',None)
            assert display is not None, definition.key
            display.start(True)
            display.progress(JobProgress('Validando registros',38,100,'unidades',True))
            pump()
            visible=[bar for bar in page.findChildren(QProgressBar) if bar.isVisible()]
            assert visible==[display.bar], (definition.key,len(visible))
            for current in ('light','dark'):
                polish.apply_theme_mode(current); pump()
                window.grab().save(str(args.output/f'{definition.key}_{current}_{scale}.png'))
            display.hide()
            start=time.perf_counter(); window.show_view('procesos'); window.open_app(definition); app.processEvents()
            warm=(time.perf_counter()-start)*1000
            result['apps'].append({'key':definition.key,'feedback_ms':feedback,'cold_ready_ms':ready,'warm_ms':warm})
        page=window.app_pages['pesos']
        before=memory_snapshot()
        paths=[Path(f'fixture-{i}.xls') for i in range(5000)]
        start=time.perf_counter(); page.set_files(paths); app.processEvents()
        result['pesos_5000_ms']=(time.perf_counter()-start)*1000
        result['memory_before_5000']=before
        result['memory_after_5000']=memory_snapshot()
        result['pesos_table_widgets']=len(page.result_table.findChildren(QWidget))
        page.clear()
        page=window.app_pages['reparto_merma_precintos']
        page.fac_paths=paths
        start=time.perf_counter(); page._refresh_fac(); app.processEvents()
        result['fac_5000_ms']=(time.perf_counter()-start)*1000
        result['fac_table_widgets']=len(page.fac_files_table.findChildren(QWidget))
        page.fac_paths=[]
        page._refresh_fac()
        result['budgets']={
            'catalog_under_250ms':result['catalog_ms']<250,
            'feedback_under_100ms':max(item['feedback_ms'] for item in result['apps'])<100,
            'cold_forms_under_800ms':max(item['cold_ready_ms'] for item in result['apps'])<800,
            'pesos_5000_under_500ms':result['pesos_5000_ms']<500,
            'fac_5000_under_500ms':result['fac_5000_ms']<500,
            'tables_no_per_row_widgets':max(result['pesos_table_widgets'],result['fac_table_widgets'])<40,
        }
        window.hide()
    output=json.dumps(result,indent=2)
    (args.output/f'ui_{scale}.json').write_text(output,encoding='utf-8')
    print(output)
    assert all(result['budgets'].values()), 'Performance budget exceeded; inspect results'


if __name__=='__main__':
    main()
