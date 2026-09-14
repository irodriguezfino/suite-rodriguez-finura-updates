"""Real Excel regression checks on disposable fixtures only (Windows)."""
import json
import tempfile
from pathlib import Path

from benchmark_pesos_xls import powershell
from suite_pyside6.core.pesos import process_pesos_files


def literal(path):
    return "'" + str(path).replace("'", "''") + "'"


def main():
    with tempfile.TemporaryDirectory(prefix="pesos-session-regression-") as directory:
        root = Path(directory)
        fixture = root / "reference.xls"
        invalid = root / "invalid.xls"
        powershell(f"""
        $ErrorActionPreference='Stop'
        $excel=New-Object -ComObject Excel.Application
        $excel.Visible=$false; $excel.DisplayAlerts=$false
        $book=$null
        try {{
            $book=$excel.Workbooks.Add()
            while ($book.Worksheets.Count -lt 3) {{ [void]$book.Worksheets.Add() }}
            $notes=$book.Worksheets.Item(1); $notes.Name='Notas'; $notes.Visible=0
            $notes.Range('A1').Formula='=SUM(1,2)'
            $notes.Range('A1').NumberFormat='0.0000'
            $sheet=$book.Worksheets.Item(2); $sheet.Name='Lote'
            $sheet.Range('C3').Value2='pesoBruto'; $sheet.Range('E3').Value2='pesoNeto'
            $sheet.Range('C4:C303').Value2=143.7; $sheet.Range('E4:E303').Value2=138.0
            $sheet.Range('E4:E303').NumberFormat='0.0000'
            $sheet.Range('C5').ClearContents(); $sheet.Range('E5').ClearContents()
            $sheet.Range('C5').NumberFormat='0.0000'
            $sheet.Range('C6').NumberFormat='@'; $sheet.Range('C6').Value2='143,7'
            $sheet.Range('E6').NumberFormat='@'; $sheet.Range('E6').Value2='138,0'
            $sheet.Range('C7').Value2=0; $sheet.Range('E7').Value2=-10
            $sheet.Range('E8').Formula='=SUM(1,2)'
            $sheet.Range('E9').Value2='pendiente'
            $sheet.Range('D4').Value2='no tocar'
            $sheet.Range('D4').Interior.Color=65535
            $last=$book.Worksheets.Item(3); $last.Name='Segundo'
            $last.Range('B2').Value2='pesoBruto'; $last.Range('D2').Value2='pesoNeto'
            $last.Range('B3').Value2=143.7; $last.Range('D3').Value2=138.0
            $book.SaveAs({literal(fixture)},56)
            $sheet.Range('C6').Value2='INVALID'
            $book.SaveCopyAs({literal(invalid)})
        }} finally {{ if ($book) {{ $book.Close($false) }}; $excel.Quit() }}
        """)
        modes = ("normal", "completo", "ninguno")
        paths = [root / f"prueba á {mode}.xls" for mode in modes]
        for path in paths:
            path.write_bytes(fixture.read_bytes())
        updates = []
        result = process_pesos_files(paths, dict(zip(paths, modes)), updates.append)
        assert not result.error_count, result.log_text()
        assert [item.adjusted_weights for item in result.results] == [300, 300, 0]
        fractions = [update.completed / update.total for update in updates]
        assert fractions == sorted(fractions)
        assert fractions[-1] == 1 and all(fraction < 1 for fraction in fractions[:-1])
        checks = []
        for path, mode in zip(paths, modes):
            gross, net, zero, negative = ("142.10", "136.50", "0.00", "-9.90") if mode == "normal" else ("139.20", "133.60", "-2.90", "-12.80")
            weights = f"""
                for ($r=4; $r -le 303; $r++) {{
                    if ($r -eq 5) {{ continue }}
                    $g='{gross}'; $n='{net}'
                    if ($r -eq 7) {{ $g='{zero}'; $n='{negative}' }}
                    if ($values[($r-2),1] -cne $g) {{ throw "wrong gross weight at $r" }}
                }}
                if ($sheet.Range('C4').NumberFormat -ne '@') {{ throw 'weight format changed' }}
                $last=$book.Worksheets.Item(3)
                if ($last.Range('B3').Value2 -cne '{gross}' -or $last.Range('D3').Value2 -cne 138.0) {{ throw 'single-cell block wrong' }}
            """ if mode != "ninguno" else """
                if ($sheet.Range('C4').Value2 -ne 143.7 -or $sheet.Range('C6').Value2 -cne '143,7') { throw 'ninguno changed weights' }
            """
            checks.append(f"""
            $book=$excel.Workbooks.Open({literal(path)})
            try {{
                $sheet=$book.Worksheets.Item(2)
                if ($sheet.Name -ne 'Hoja1') {{ throw 'wrong visible sheet renamed' }}
                $notes=$book.Worksheets.Item(1)
                if ($notes.Name -ne 'Notas' -or $notes.Visible -ne 0 -or $notes.Range('A1').Formula -ne '=SUM(1,2)') {{ throw 'hidden sheet changed' }}
                if ($notes.Range('A1').NumberFormat -ne $referenceNotesFormat) {{ throw 'formula format changed' }}
                if ($null -ne $sheet.Range('C5').Value2 -or $null -ne $sheet.Range('E5').Value2) {{ throw 'blank gap overwritten' }}
                if ($sheet.Range('C5').NumberFormat -ne $referenceGapFormat) {{ throw 'blank format overwritten' }}
                if ($sheet.Range('D4').Value2 -ne 'no tocar' -or $sheet.Range('D4').Interior.Color -ne 65535) {{ throw 'unrelated data changed' }}
                $values=$sheet.UsedRange.Value2
                $netValues=$sheet.Range('E3:E303').Value2
                $netFormulas=$sheet.Range('E3:E303').Formula
                for ($i=1; $i -le 301; $i++) {{
                    if ($netValues[$i,1] -cne $referenceNetValues[$i,1] -or $netFormulas[$i,1] -cne $referenceNetFormulas[$i,1]) {{ throw "net weight modified at $i" }}
                }}
                if ($sheet.Range('E4').Value2 -isnot [double]) {{ throw 'numeric net converted to text' }}
                if ($sheet.Range('E4').NumberFormat -ne $referenceNetFormat -or $sheet.Range('E6').NumberFormat -ne '@') {{ throw 'net format changed' }}
                {weights}
            }} finally {{ $book.Close($false) }}
            """)
        powershell("""
        $ErrorActionPreference='Stop'
        $excel=New-Object -ComObject Excel.Application
        $excel.Visible=$false; $excel.DisplayAlerts=$false
        try {
        """ + f"""
        $reference=$excel.Workbooks.Open({literal(fixture)})
        $referenceGapFormat=$reference.Worksheets.Item(2).Range('C5').NumberFormat
        $referenceNotesFormat=$reference.Worksheets.Item(1).Range('A1').NumberFormat
        $referenceNetValues=$reference.Worksheets.Item(2).Range('E3:E303').Value2
        $referenceNetFormulas=$reference.Worksheets.Item(2).Range('E3:E303').Formula
        $referenceNetFormat=$reference.Worksheets.Item(2).Range('E4').NumberFormat
        $reference.Close($false)
        """ + "\n".join(checks) + "\n} finally { $excel.Quit() }")
        good = root / "good-before-error.xls"
        good.write_bytes(fixture.read_bytes())
        before = {path: path.read_bytes() for path in (good, invalid)}
        failed = process_pesos_files([good, invalid], {good: "normal", invalid: "normal"})
        assert failed.error_count == 1, failed.log_text()
        assert all(path.read_bytes() == content for path, content in before.items())
        assert set(root.iterdir()) == {fixture, invalid, good, *paths}, "stray temporary files"
        print(json.dumps({"status": "OK", "gross_weights_adjusted": 600,
            "checks": "net values/formulas/types/formats untouched; all modes, 256-row boundaries, blank gaps, single-cell blocks, hidden sheets, accented paths, global progress, failed batch preserves originals",
            "timings": result.timings}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
