"""Disposable benchmark: compare production XLS flow with a shared Excel session.

This is an experiment, not an application processing route. No user workbooks
are accepted. Both routes operate exclusively on generated temporary fixtures.
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

from benchmark_pesos_xls import powershell
from suite_pyside6.core.pesos import process_pesos_files, _write_legacy_adjustment_script


def literal(path):
    return "'" + str(path).replace("'", "''") + "'"


def experimental_function():
    generated = _write_legacy_adjustment_script()
    try:
        script = generated.read_text(encoding="utf-8")
    finally:
        generated.unlink()
    # The shared implementation is now integrated. Keep this historical
    # experiment usable as a comparison against the direct, unprotected route.
    if 'function Invoke-PesosWorkbook {' in script:
        start = script.index('function Invoke-PesosWorkbook {')
        end = script.index('if (-not $Server)', start)
        return script[start:end].replace('Invoke-PesosWorkbook', 'Invoke-PesosExperiment')
    script = script.replace("[string]$Preview = ''", "[string]$Preview = '', [object]$SharedExcel = $null")
    script = script.replace("$excel = New-Object -ComObject Excel.Application", "$excel = $SharedExcel")
    script = script.replace('if ($excel -ne $null) { $excel.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }', '')
    script = script.replace('    [GC]::Collect()\n    [GC]::WaitForPendingFinalizers()', '')
    start = script.index('        foreach ($entry in $weightCells) {')
    end = script.index('        $workbook.Save()', start)
    script = script[:start] + r'''
        $index = 0
        while ($index -lt $weightCells.Count) {
            $first = $weightCells[$index]
            $last = $index
            while (($last + 1) -lt $weightCells.Count -and ($last - $index) -lt 255) {
                $next = $weightCells[$last + 1]
                if (-not [object]::ReferenceEquals($next.Sheet, $first.Sheet) -or
                    $next.Column -ne $first.Column -or $next.Row -ne ($weightCells[$last].Row + 1)) { break }
                $last++
            }
            $count = $last - $index + 1
            $block = New-Object 'object[,]' $count,1
            for ($offset = 0; $offset -lt $count; $offset++) {
                $entry = $weightCells[$index + $offset]
                $adjusted = $entry.Weight - ($entry.Weight * [decimal]0.011)
                if ($Vaciado -eq 'completo') { $adjusted -= [decimal]2.9 }
                $adjusted = [Math]::Round($adjusted, 1, [MidpointRounding]::AwayFromZero)
                $block[$offset,0] = $adjusted.ToString('0.00', [Globalization.CultureInfo]::InvariantCulture)
            }
            $range = $first.Sheet.Range($first.Sheet.Cells.Item($first.Row, $first.Column),
                                       $first.Sheet.Cells.Item($weightCells[$last].Row, $first.Column))
            $range.NumberFormat = '@'
            $range.Value2 = $block
            $adjustedWeights += $count
            $index = $last + 1
        }
''' + script[end:]
    return 'function Invoke-PesosExperiment {\n' + script + '\n}\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, default=60)
    parser.add_argument('--files', type=int, default=5)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='pesos-session-experiment-') as directory:
        root = Path(directory)
        fixture = root / 'fixture.xls'
        powershell(f'''
        $ErrorActionPreference='Stop'
        $excel=New-Object -ComObject Excel.Application
        $excel.Visible=$false
        $excel.DisplayAlerts=$false
        $book=$null
        try {{
            $book=$excel.Workbooks.Add()
            $sheet=$book.Worksheets.Item(1)
            $sheet.Name='Lote'
            $sheet.Range('A1').Value2='pesoBruto'
            $sheet.Range('B1').Value2='pesoNeto'
            $sheet.Range('A2:A{args.rows+1}').Value2=143.7
            $sheet.Range('B2:B{args.rows+1}').Value2=138.0
            $sheet.Range('C1').Formula='=SUM(1,2)'
            $sheet.Range('C1').NumberFormat='0.00'
            $book.SaveAs({literal(fixture)},56)
        }} finally {{ if ($book) {{ $book.Close($false) }}; $excel.Quit() }}
        ''')
        original = fixture.read_bytes()
        current = [root / f'current{i}.xls' for i in range(args.files)]
        experiment = [root / f'experiment{i}.xls' for i in range(args.files)]
        for path in current + experiment:
            path.write_bytes(original)
        start = time.perf_counter()
        result = process_pesos_files(current, dict.fromkeys(current, 'completo'))
        current_seconds = time.perf_counter() - start
        if result.error_count:
            raise RuntimeError(result.log_text())
        commands = '\n'.join(f'Invoke-PesosExperiment -Path {literal(p)} -TargetName Hoja1 -Vaciado completo -SharedExcel $excel' for p in experiment)
        start = time.perf_counter()
        stdout = powershell(experimental_function() + r'''
        $ErrorActionPreference='Stop'
        $clock=[Diagnostics.Stopwatch]::StartNew()
        $excel=New-Object -ComObject Excel.Application
        $startup=$clock.Elapsed.TotalSeconds
        try {
        ''' + commands + r'''
        } finally { $excel.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
        Write-Output "STARTUP|$startup"
        ''')
        experiment_seconds = time.perf_counter() - start
        results = [json.loads(line) for line in stdout.splitlines() if line.startswith('{')]
        assert len(results) == args.files and all(r.get('success') for r in results), stdout
        verification = []
        for path in current + experiment:
            verification.append(f'''
            $book=$excel.Workbooks.Open({literal(path)})
            try {{
                $sheet=$book.Worksheets.Item(1)
                if ($sheet.Name -ne 'Hoja1') {{ throw 'wrong name' }}
                $values=$sheet.UsedRange.Value2
                for ($r=2; $r -le {args.rows+1}; $r++) {{
                    if ($values[$r,1] -cne '139.20' -or $values[$r,2] -cne 138.0) {{ throw 'wrong weights' }}
                }}
                if ($sheet.Range('A2').NumberFormat -ne '@') {{ throw 'wrong text format' }}
                if ($sheet.Range('C1').Formula -ne '=SUM(1,2)') {{ throw 'unrelated formula changed' }}
            }} finally {{ $book.Close($false) }}
            ''')
        powershell("$ErrorActionPreference='Stop'; $excel=New-Object -ComObject Excel.Application; $excel.Visible=$false; $excel.DisplayAlerts=$false; try {\n" + '\n'.join(verification) + "\n} finally { $excel.Quit() }")
        print(json.dumps({'files':args.files,'rows_per_file':args.rows,
            'current_s':round(current_seconds,3), 'experiment_s':round(experiment_seconds,3),
            'excel_startup_s':next(line.split('|')[1] for line in stdout.splitlines() if line.startswith('STARTUP|')),
            'verification':'All weights, text format, sheet name and unrelated formula verified in Excel'}, indent=2))


if __name__ == '__main__':
    main()
