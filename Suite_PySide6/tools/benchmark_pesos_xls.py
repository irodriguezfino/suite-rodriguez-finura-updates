"""Benchmark disposable XLS fixtures with real Excel; never touches user files."""
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from suite_pyside6.core.pesos import process_pesos_files


def powershell(script):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=60)
    parser.add_argument("--files", type=int, default=1)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pesos-benchmark-") as directory:
        root = Path(directory)
        source = root / "fixture.xls"
        quoted = str(source).replace("'", "''")
        powershell(f"""
        $excel = New-Object -ComObject Excel.Application
        $excel.Visible = $false
        $excel.DisplayAlerts = $false
        $book = $null
        try {{
            $book = $excel.Workbooks.Add()
            $sheet = $book.Worksheets.Item(1)
            $sheet.Name = 'Lote'
            $sheet.Cells.Item(1,1).Value2 = 'pesoBruto'
            $sheet.Cells.Item(1,2).Value2 = 'pesoNeto'
            $sheet.Range('A2:A{args.rows + 1}').Value2 = 143.7
            $sheet.Range('B2:B{args.rows + 1}').Value2 = 138.0
            $sheet.Range('C1').Formula = '=SUM(1,2)'
            $sheet.Range('C1').NumberFormat = '0.00'
            $book.SaveAs('{quoted}', 56)
        }} finally {{
            if ($book) {{ $book.Close($false) }}
            $excel.Quit()
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
        }}
        """)
        engines = {"current": process_pesos_files}
        if args.baseline:
            # HEAD is the pre-change implementation; load it only for this
            # controlled benchmark on a disposable fixture.
            text = subprocess.check_output(
                ["git", "show", "HEAD:Suite_PySide6/src/suite_pyside6/core/pesos.py"],
                text=True, encoding="utf-8",
            )
            spec = importlib.util.spec_from_loader("pesos_baseline_benchmark", loader=None)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            exec(compile(text, "baseline_pesos.py", "exec"), module.__dict__)
            engines["baseline"] = module.process_pesos_files
        output = {}
        targets = []
        for name, engine in engines.items():
            batch = [root / f"{name}_{index}.xls" for index in range(args.files)]
            targets.extend(batch)
            for target in batch:
                target.write_bytes(source.read_bytes())
            updates = []
            started = time.perf_counter()
            result = engine(batch, dict.fromkeys(batch, "completo"), updates.append)
            elapsed = time.perf_counter() - started
            if result.error_count:
                raise RuntimeError(result.log_text())
            fractions = [update.completed / update.total for update in updates]
            if name == "current":
                assert fractions == sorted(fractions)
                assert fractions[-1] == 1 and all(value < 1 for value in fractions[:-1])
                assert not any(update.busy for update in updates)
            output[name] = {"seconds": round(elapsed, 3), "files": len(batch),
                "weights": sum(item.adjusted_weights for item in result.results), "timings": result.timings}
        checks = []
        for path in targets:
            target = str(path).replace("'", "''")
            # The historic HEAD baseline adjusted net weight as well.
            expected_net = "'133.60'" if path.name.startswith("baseline_") else "138.0"
            checks.append(f"""
            $book = $excel.Workbooks.Open('{target}')
            try {{
                $sheet = $book.Worksheets.Item(1)
                if ($sheet.Name -ne 'Hoja1') {{ throw 'Sheet name changed incorrectly' }}
                for ($r=2; $r -le {args.rows + 1}; $r++) {{
                    if ($sheet.Cells.Item($r,1).Value2 -cne '139.20') {{ throw 'Gross weight mismatch' }}
                    if ($sheet.Cells.Item($r,2).Value2 -cne {expected_net}) {{ throw 'Net weight mismatch' }}
                }}
                if ($sheet.Range('A2').NumberFormat -ne '@') {{ throw 'Weight format mismatch' }}
                if ($sheet.Range('C1').Formula -ne '=SUM(1,2)') {{ throw 'Unrelated formula changed' }}
                if ($sheet.Range('C1').NumberFormat -ne $originalFormat) {{ throw 'Unrelated format changed' }}
            }} finally {{ $book.Close($false) }}
            """)
        powershell("""
        $ErrorActionPreference='Stop'
        $excel=New-Object -ComObject Excel.Application
        $excel.Visible=$false
        $excel.DisplayAlerts=$false
        try {
        """ + f"$reference = $excel.Workbooks.Open('{quoted}'); $originalFormat = $reference.Worksheets.Item(1).Range('C1').NumberFormat; $reference.Close($false)\n" + "\n".join(checks) + """
        } finally { $excel.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($excel) }
        """)
        output["verification"] = "All rows, sheet name, text format and unrelated formula verified in Excel"
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
