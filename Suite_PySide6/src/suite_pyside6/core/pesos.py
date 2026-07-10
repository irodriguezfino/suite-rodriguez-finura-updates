from __future__ import annotations

import os
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET


TARGET_SHEET_NAME = "Hoja1"
OOXML_EXTENSIONS = {".xlsx", ".xlsm"}
LEGACY_EXCEL_EXTENSIONS = {".xls"}
SUPPORTED_EXTENSIONS = OOXML_EXTENSIONS | LEGACY_EXCEL_EXTENSIONS
OLD_EXCEL_EXTENSIONS = {".xlsb"}
WORKBOOK_XML = "xl/workbook.xml"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
ET.register_namespace("x15", "http://schemas.microsoft.com/office/spreadsheetml/2010/11/main")
ET.register_namespace("xr", "http://schemas.microsoft.com/office/spreadsheetml/2014/revision")
ET.register_namespace("xr6", "http://schemas.microsoft.com/office/spreadsheetml/2016/revision6")
ET.register_namespace("xr10", "http://schemas.microsoft.com/office/spreadsheetml/2016/revision10")


@dataclass(frozen=True)
class SheetRename:
    path: Path
    success: bool
    before: str = ""
    after: str = TARGET_SHEET_NAME
    changed: bool = False
    message: str = ""


@dataclass
class PesosResult:
    selected_files: list[Path] = field(default_factory=list)
    results: list[SheetRename] = field(default_factory=list)
    ignored_files: list[Path] = field(default_factory=list)

    @property
    def processed_count(self) -> int:
        return sum(1 for item in self.results if item.success and item.changed)

    @property
    def ok_count(self) -> int:
        return sum(1 for item in self.results if item.success)

    @property
    def unchanged_count(self) -> int:
        return sum(1 for item in self.results if item.success and not item.changed)

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.results if not item.success) + len(self.ignored_files)

    def summary(self) -> str:
        return (
            f"Archivos seleccionados: {len(self.selected_files)} | "
            f"Renombrados: {self.processed_count} | "
            f"Ya estaban correctos: {self.unchanged_count} | "
            f"Errores/ignorados: {self.error_count}"
        )

    def log_text(self) -> str:
        if not self.selected_files:
            return "Selecciona archivos Excel para empezar."

        lines = ["Resultado del proceso:"]
        for item in self.results:
            if item.success and item.changed:
                lines.append(f"- OK {item.path.name}: '{item.before}' -> '{item.after}'.")
            elif item.success:
                lines.append(f"- OK {item.path.name}: la hoja ya se llamaba '{TARGET_SHEET_NAME}'.")
            else:
                lines.append(f"- ERROR {item.path.name}: {item.message}")

        for path in self.ignored_files:
            ext = path.suffix.lower()
            if ext in OLD_EXCEL_EXTENSIONS:
                lines.append(f"- Ignorado {path.name}: formato Excel antiguo/no soportado.")
            else:
                lines.append(f"- Ignorado {path.name}: no es un Excel .xlsx/.xlsm/.xls.")
        return "\n".join(lines)


def process_pesos_files(paths: list[Path]) -> PesosResult:
    result = PesosResult(selected_files=list(paths))
    for path in paths:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            result.ignored_files.append(path)
            continue
        result.results.append(rename_first_visible_sheet(path))
    return result


def rename_first_visible_sheet(path: Path) -> SheetRename:
    if path.suffix.lower() in LEGACY_EXCEL_EXTENSIONS:
        return _rename_legacy_xls_with_excel(path)
    try:
        with ZipFile(path, "r") as source:
            if WORKBOOK_XML not in source.namelist():
                raise ValueError("no se encontro xl/workbook.xml")
            workbook_xml = source.read(WORKBOOK_XML)
        new_workbook_xml, previous_name, changed = _renamed_workbook_xml(workbook_xml)
        if not changed:
            return SheetRename(path=path, success=True, before=previous_name, changed=False)
        _replace_workbook_xml(path, new_workbook_xml)
        return SheetRename(path=path, success=True, before=previous_name, changed=True)
    except BadZipFile:
        return SheetRename(path=path, success=False, message="el archivo no parece un Excel XLSX/XLSM valido")
    except PermissionError:
        return SheetRename(path=path, success=False, message="no se pudo escribir; cierra el archivo en Excel")
    except Exception as exc:
        return SheetRename(path=path, success=False, message=str(exc))


def _renamed_workbook_xml(workbook_xml: bytes) -> tuple[bytes, str, bool]:
    root = ET.fromstring(workbook_xml)
    sheets = root.find(f"{{{MAIN_NS}}}sheets")
    if sheets is None:
        raise ValueError("el libro no contiene hojas")

    sheet_nodes = list(sheets.findall(f"{{{MAIN_NS}}}sheet"))
    if not sheet_nodes:
        raise ValueError("el libro no contiene hojas")

    target_sheet = _first_visible_sheet(sheet_nodes)
    previous_name = target_sheet.attrib.get("name", "")
    if previous_name == TARGET_SHEET_NAME:
        return workbook_xml, previous_name, False

    for sheet in sheet_nodes:
        if sheet is not target_sheet and sheet.attrib.get("name", "").casefold() == TARGET_SHEET_NAME.casefold():
            raise ValueError("ya existe otra hoja llamada Hoja1; no se cambia nada para evitar nombres duplicados")

    target_sheet.set("name", TARGET_SHEET_NAME)
    updated = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return updated, previous_name, True


def _first_visible_sheet(sheet_nodes: list[ET.Element]) -> ET.Element:
    for sheet in sheet_nodes:
        if sheet.attrib.get("state", "visible") == "visible":
            return sheet
    return sheet_nodes[0]


def _replace_workbook_xml(path: Path, workbook_xml: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, suffix=path.suffix) as temp_file:
            temp_path = Path(temp_file.name)

        with ZipFile(path, "r") as source, ZipFile(temp_path, "w") as target:
            workbook_written = False
            for info in source.infolist():
                if info.filename == WORKBOOK_XML:
                    if not workbook_written:
                        target.writestr(info, workbook_xml)
                        workbook_written = True
                    continue
                target.writestr(info, source.read(info.filename))

        os.replace(temp_path, path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise


def _rename_legacy_xls_with_excel(path: Path) -> SheetRename:
    script = r"""
param([string]$Path, [string]$TargetName)
$ErrorActionPreference = "Stop"
$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $workbook = $excel.Workbooks.Open($Path)
    $targetSheet = $null
    foreach ($sheet in @($workbook.Worksheets)) {
        if ($sheet.Visible -eq -1) {
            $targetSheet = $sheet
            break
        }
    }
    if ($null -eq $targetSheet) {
        $targetSheet = $workbook.Worksheets.Item(1)
    }
    $previous = [string]$targetSheet.Name
    $changed = $false
    if ($previous -ne $TargetName) {
        foreach ($sheet in @($workbook.Worksheets)) {
            if ($sheet.Name -ieq $TargetName -and $sheet.Index -ne $targetSheet.Index) {
                throw "ya existe otra hoja llamada $TargetName; no se cambia nada para evitar nombres duplicados"
            }
        }
        $targetSheet.Name = $TargetName
        $workbook.Save()
        $changed = $true
    }
    [pscustomobject]@{success=$true; before=$previous; changed=$changed} | ConvertTo-Json -Compress
} catch {
    [pscustomobject]@{success=$false; message=$_.Exception.Message} | ConvertTo-Json -Compress
    exit 2
} finally {
    if ($workbook -ne $null) {
        $workbook.Close($false)
    }
    if ($excel -ne $null) {
        $excel.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
"""
    script_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".ps1", encoding="utf-8") as temp_file:
            temp_file.write(script)
            script_path = Path(temp_file.name)
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                str(path),
                TARGET_SHEET_NAME,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        return SheetRename(path=path, success=False, message="no se encontro PowerShell para procesar archivos .xls")
    except subprocess.TimeoutExpired:
        return SheetRename(path=path, success=False, message="Excel no respondio al procesar el archivo .xls")
    finally:
        if script_path is not None:
            script_path.unlink(missing_ok=True)

    output = completed.stdout.strip()
    try:
        data = json.loads(output.splitlines()[-1] if output else "{}")
    except json.JSONDecodeError:
        data = {}
    if completed.returncode != 0 or not data.get("success"):
        message = str(data.get("message") or completed.stderr.strip() or "no se pudo procesar el archivo .xls con Excel")
        return SheetRename(path=path, success=False, message=message)
    return SheetRename(
        path=path,
        success=True,
        before=str(data.get("before") or ""),
        changed=bool(data.get("changed")),
    )
