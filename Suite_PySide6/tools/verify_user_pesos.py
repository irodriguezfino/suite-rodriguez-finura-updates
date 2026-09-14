"""Read-only reference folder; only disposable copies are processed by Pesos."""
import argparse
import hashlib
import json
import shutil
import tempfile
import time
from pathlib import Path
from benchmark_pesos_xls import powershell
from suite_pyside6.core.pesos import process_pesos_files


def quoted(path):
    return "'" + str(path).replace("'", "''") + "'"


def verify(reference):
    sources = sorted(reference.glob('*.xls'))
    if not sources:
        raise ValueError('No hay archivos XLS de referencia.')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    original_hashes = {p: digest(p) for p in sources}
    result_info = []
    with tempfile.TemporaryDirectory(prefix='suite-real-regression-') as directory:
        root = Path(directory)
        pairs = []
        modes = {}
        for mode in ('normal', 'completo', 'ninguno'):
            for i, source in enumerate(sources):
                target = root / f'{mode}-{i}.xls'
                shutil.copy2(source, target)
                pairs.append((source, target, mode))
                modes[target] = mode
        updates = []
        started = time.perf_counter()
        result = process_pesos_files(list(modes), modes, updates.append)
        elapsed = time.perf_counter() - started
        rejected = []
        if result.error_count:
            failed = {item.path for item in result.results if not item.success}
            assert all(digest(b) == original_hashes[a] for a,b,_ in pairs), 'Invalid batch partially saved'
            for item in result.results:
                if not item.success and 'encabezado pesoBruto' not in item.message:
                    raise AssertionError(result.log_text())
            # Independently confirm that these documents do not have the
            # required gross-weight header; do not silently accept a writer bug.
            names = ','.join(quoted(path) for path in sorted(failed))
            powershell('''
            $ErrorActionPreference='Stop'
            $e=New-Object -ComObject Excel.Application
            $e.Visible=$false; $e.DisplayAlerts=$false; $e.AutomationSecurity=3
            try { foreach ($p in @(''' + names + ''')) {
                $b=$e.Workbooks.Open($p,0,$true)
                try { foreach ($s in @($b.Worksheets)) {
                    foreach ($value in $s.UsedRange.Value2) {
                        if (([string]$value -replace '\\s','').ToLowerInvariant() -eq 'pesobruto') { throw 'Header exists: unexpected rejection' }
                    }
                } } finally { $b.Close($false) }
            } } finally { $e.Quit() }
            ''')
            rejected = [b.name for a,b,mode in pairs if b in failed]
            pairs = [(a,b,mode) for a,b,mode in pairs if b not in failed]
            modes = {b: mode for a,b,mode in pairs}
            updates.clear()
            started = time.perf_counter()
            result = process_pesos_files(list(modes), modes, updates.append)
            elapsed = time.perf_counter() - started
            assert not result.error_count, result.log_text()
        fractions = [p.completed / p.total for p in updates]
        assert fractions == sorted(fractions) and fractions[-1] == 1
        assert all(p < 1 for p in fractions[:-1])
        # Verify using Excel's bulk arrays, independently of the writer.
        entries = ',\n'.join(f'@({quoted(a)}, {quoted(b)}, {quoted(mode)})' for a,b,mode in pairs)
        answer = powershell('''
        $ErrorActionPreference='Stop'
        $excel=New-Object -ComObject Excel.Application
        $excel.Visible=$false; $excel.DisplayAlerts=$false; $excel.AutomationSecurity=3
        $excel.EnableEvents=$false
        $count=0; $gross=0; $untouched=0
        try {
        $pairs=@(
        ''' + entries + '''
        )
        foreach ($pair in $pairs) {
            $a=$null; $b=$null
            try {
                $a=$excel.Workbooks.Open($pair[0],0,$true)
                $b=$excel.Workbooks.Open($pair[1],0,$true)
                if ($a.Worksheets.Count -ne $b.Worksheets.Count) { throw 'sheet count changed' }
                $first=$true
                for ($s=1; $s -le $a.Worksheets.Count; $s++) {
                    $sa=$a.Worksheets.Item($s); $sb=$b.Worksheets.Item($s)
                    $expectedName=$sa.Name
                    if ($first -and $sa.Visible -eq -1) { $expectedName='Hoja1'; $first=$false }
                    if ($sb.Name -ne $expectedName -or $sb.Visible -ne $sa.Visible) { throw 'sheet identity changed' }
                    $ra=$sa.UsedRange; $rb=$sb.UsedRange
                    if ($ra.Address() -ne $rb.Address()) { throw 'used range changed' }
                    $va=$ra.Value2; $vb=$rb.Value2; $fa=$ra.Formula; $fb=$rb.Formula
                    $nr=$ra.Rows.Count; $nc=$ra.Columns.Count
                    if ($ra.Cells.Count -eq 1) {
                        if ($va -cne $vb -or $fa -cne $fb) { throw 'single cell changed' }
                        continue
                    }
                    $gc=0; $hr=0
                    for ($r=1; $r -le $nr; $r++) {
                        for ($c=1; $c -le $nc; $c++) {
                            if (([string]$va[$r,$c] -replace '\\s','').ToLowerInvariant() -eq 'pesobruto') { $gc=$c; $hr=$r; break }
                        }
                        if ($gc) { break }
                    }
                    for ($r=1; $r -le $nr; $r++) {
                        for ($c=1; $c -le $nc; $c++) {
                            $v=$va[$r,$c]; $actual=$vb[$r,$c]
                            $isGross=$gc -eq $c -and $r -gt $hr -and $pair[2] -ne 'ninguno' -and $null -ne $v -and [string]$v -ne ''
                            if ($isGross) {
                                $number=[decimal]::Parse(([Convert]::ToString($v,[Globalization.CultureInfo]::InvariantCulture)).Replace(',','.'),[Globalization.CultureInfo]::InvariantCulture)
                                $expected=$number * [decimal]0.989
                                if ($pair[2] -eq 'completo') { $expected -= [decimal]2.9 }
                                $expected=[Math]::Round($expected,1,[MidpointRounding]::AwayFromZero).ToString('0.00',[Globalization.CultureInfo]::InvariantCulture)
                                if ($actual -isnot [string] -or $actual -cne $expected) { throw "gross mismatch at $r,$c" }
                                $gross++
                            } else {
                                if ($v -cne $actual -or $fa[$r,$c] -cne $fb[$r,$c]) { throw "unrelated cell changed at $r,$c" }
                                if ($null -ne $v -and $v.GetType() -ne $actual.GetType()) { throw 'cell type changed' }
                                $untouched++
                            }
                        }
                    }
                    for ($c=1; $c -le $nc; $c++) {
                        if ($c -eq $gc -and $pair[2] -ne 'ninguno') { continue }
                        if ($ra.Columns.Item($c).NumberFormat -cne $rb.Columns.Item($c).NumberFormat) { throw 'unrelated number format changed' }
                    }
                }
                $count++
            } finally { if ($b) { $b.Close($false) }; if ($a) { $a.Close($false) } }
        }
        @{files=$count; gross_checked=$gross; other_cells_checked=$untouched} | ConvertTo-Json -Compress
        } finally { $excel.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
        ''')
        result_info = dict(files=len(sources), copies=len(pairs), rejected_without_gross_header=len(rejected), seconds=elapsed,
                           timings=result.timings, verification=json.loads(answer), progress_events=len(updates))
    assert all(digest(path) == value for path, value in original_hashes.items()), 'Original source changed'
    result_info['originals_unchanged'] = True
    return result_info


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.reference), indent=2))
