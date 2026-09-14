from __future__ import annotations

import os
import json
import shutil
import subprocess
import tempfile
import errno
import time
import queue
import threading
from .jobs import checkpoint, begin_commit
from .owned_process import OwnedProcess
from .batch_recovery import RecoverableBatch
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Callable, Literal
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET


TARGET_SHEET_NAME = "Hoja1"
OOXML_EXTENSIONS = {".xlsx", ".xlsm"}
LEGACY_EXCEL_EXTENSIONS = {".xls"}
SUPPORTED_EXTENSIONS = OOXML_EXTENSIONS | LEGACY_EXCEL_EXTENSIONS
OLD_EXCEL_EXTENSIONS = {".xlsb"}
WORKBOOK_XML = "xl/workbook.xml"
WORKBOOK_RELS_XML = "xl/_rels/workbook.xml.rels"
STYLES_XML = "xl/styles.xml"
SHARED_STRINGS_XML = "xl/sharedStrings.xml"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOCUMENT_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

VaciadoType = Literal["ninguno", "normal", "completo"]
VALID_VACIADO_TYPES = frozenset(("ninguno", "normal", "completo"))


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
    vaciado: VaciadoType = "ninguno"
    adjusted_sheets: int = 0
    adjusted_weights: int = 0


@dataclass(frozen=True)
class PesosProgress:
    """A unit of real work completed while processing a group of workbooks."""

    completed: int
    total: int
    message: str
    # Legacy helpers may describe an opaque operation; the batch coordinator
    # still emits one determinate global counter and never resets its total.
    busy: bool = False


@dataclass(frozen=True)
class _WeightColumnPlan:
    label: str
    column: int
    rows: tuple[int, ...]


@dataclass(frozen=True)
class _WeightSheetPlan:
    title: str
    columns: tuple[_WeightColumnPlan, ...]

    @property
    def weight_count(self) -> int:
        return sum(len(column.rows) for column in self.columns)


@dataclass(frozen=True)
class _OoxmlCellUpdate:
    sheet_path: str
    coordinate: str
    value: str
    style_id: int


@dataclass(frozen=True)
class _OoxmlPartReplacement:
    path: str
    content: bytes


@dataclass(frozen=True)
class _FilePlan:
    path: Path
    vaciado: VaciadoType
    weight_sheets: tuple[_WeightSheetPlan, ...] = ()
    legacy_weight_count: int | None = None
    ooxml_updates: tuple[_OoxmlCellUpdate, ...] = ()
    ooxml_replacements: tuple[_OoxmlPartReplacement, ...] = ()
    workbook_xml: bytes | None = None
    archive_entries: int = 0
    before: str = ""
    renamed: bool = False

    @property
    def weight_count(self) -> int:
        return self.legacy_weight_count if self.legacy_weight_count is not None else sum(sheet.weight_count for sheet in self.weight_sheets)

    @property
    def work_units(self) -> int:
        """Real units exposed by the progress bar after validation."""
        if self.legacy_weight_count is not None:
            return 2 + self.legacy_weight_count
        if self.vaciado == "ninguno" and not self.renamed:
            return 1
        # Value changes have already been prepared during validation.  The
        # remaining measurable work is the atomic package replacement.
        return max(1, 3 + self.archive_entries)


@dataclass
class PesosResult:
    selected_files: list[Path] = field(default_factory=list)
    results: list[SheetRename] = field(default_factory=list)
    ignored_files: list[Path] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

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
            adjustment = (
                f" Vaciado {item.vaciado}: {item.adjusted_weights} valores de peso en {item.adjusted_sheets} hoja(s)."
                if item.vaciado != "ninguno" and item.success
                else ""
            )
            if item.success and item.changed:
                lines.append(f"- OK {item.path.name}: '{item.before}' -> '{item.after}'.{adjustment}")
            elif item.success:
                lines.append(f"- OK {item.path.name}: la hoja ya se llamaba '{TARGET_SHEET_NAME}'.{adjustment}")
            else:
                lines.append(f"- ERROR {item.path.name}: {item.message}")

        for path in self.ignored_files:
            ext = path.suffix.lower()
            if ext in OLD_EXCEL_EXTENSIONS:
                lines.append(f"- Ignorado {path.name}: formato Excel antiguo/no soportado.")
            else:
                lines.append(f"- Ignorado {path.name}: no es un Excel .xlsx/.xlsm/.xls.")
        if self.timings:
            lines.append("Tiempos: " + " | ".join(f"{name}: {seconds:.2f} s" for name, seconds in self.timings.items()))
        lines.extend("Aviso: " + warning for warning in self.warnings)
        return "\n".join(lines)


def calcular_peso_vaciado(peso: object, tipo_vaciado: VaciadoType) -> str:
    """Apply the business rule and return the Excel representation (two decimals).

    Decimal plus ROUND_HALF_UP is intentional: Python's default rounding is
    banker's rounding and differs from Excel's ROUND for values ending in 5.
    The business result is rounded once to one decimal; the trailing zero is a
    display precision requirement, so ``142.1`` is represented as ``142.10``.
    """
    value = _calcular_peso_vaciado_decimal(peso, tipo_vaciado)
    return _format_decimal(value)


def _calcular_peso_vaciado_decimal(peso: object, tipo_vaciado: VaciadoType) -> Decimal:
    """Return the numeric result without passing through a binary float."""
    if tipo_vaciado not in VALID_VACIADO_TYPES:
        raise ValueError(f"tipo de vaciado no valido: {tipo_vaciado}")
    value = _as_decimal(peso)
    if tipo_vaciado == "ninguno":
        return value
    adjusted = value - (value * Decimal("0.011"))
    if tipo_vaciado == "completo":
        adjusted -= Decimal("2.9")
    # One decimal is an explicit rule of Vaciado, not an intermediate rounding.
    return adjusted.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))


def process_pesos_files(
    paths: list[Path],
    vaciados: dict[Path, VaciadoType] | None = None,
    progress: Callable[[PesosProgress], None] | None = None,
) -> PesosResult:
    """Prepare the whole batch privately before committing source files."""
    with tempfile.TemporaryDirectory(prefix="suite-pesos-") as directory, _LegacyExcelSession() as session:
        return _process_pesos_batch(paths, vaciados, progress, Path(directory), session)


def _process_pesos_batch(
    paths: list[Path],
    vaciados: dict[Path, VaciadoType] | None,
    progress: Callable[[PesosProgress], None] | None,
    staging: Path,
    session: _LegacyExcelSession,
) -> PesosResult:
    result = PesosResult(selected_files=list(paths))
    started = time.perf_counter()
    selection = vaciados or {}
    validation_errors: dict[int, SheetRename] = {}
    candidates: list[tuple[int, Path, VaciadoType]] = []
    staged_xls: dict[int, tuple[Path, SheetRename]] = {}
    source_versions: dict[Path, tuple[int, int]] = {}
    # Fixed denominator for the entire batch: preparation and commit for
    # each file, with measured substeps. This is work completion, not ETA.
    total = max(1, len(paths) * 3000)
    current = 0

    def report(value: int, message: str, *, finished: bool = False) -> None:
        checkpoint()
        nonlocal current
        current = max(current, min(value, total if finished else total - 1))
        _emit_progress(progress, current, total, message)

    def phase(offset: int) -> Callable[[PesosProgress], None]:
        def receive(update: PesosProgress) -> None:
            fraction = min(1, max(0, update.completed / max(1, update.total)))
            report(offset + int(1000 * fraction), update.message)
        return receive

    report(0, "Preparando lote…")

    for index, path in enumerate(paths):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            result.ignored_files.append(path)
            continue
        try:
            candidates.append((index, path, _normalise_vaciado(selection.get(path, "ninguno"))))
        except Exception as exc:
            validation_errors[index] = SheetRename(path=path, success=False, message=str(exc))

    plans_by_index: dict[int, _FilePlan] = {}
    validation_total = max(1, len(candidates))
    for validation_index, (index, path, vaciado) in enumerate(candidates, start=1):
        report(index * 1000, f"Preparando archivo {validation_index} de {validation_total}: {path.name}…")
        try:
            stat = path.stat()
            source_versions[path] = (stat.st_size, stat.st_mtime_ns)
            if path.suffix.lower() == ".xls":
                working = staging / f"{index}.xls"
                shutil.copy2(path, working)
                # Already a private copy: reuse the batch session and avoid a
                # second copy/Excel startup for every workbook.
                item = session.process(_FilePlan(working, vaciado), phase(index * 1000), 0, 1000)
                staged_xls[index] = (working, replace(item, path=path))
            else:
                plans_by_index[index] = _build_file_plan(path, vaciado, progress=phase(index * 1000))
        except Exception as exc:
            validation_errors[index] = SheetRename(path=path, success=False, message=str(exc), vaciado=vaciado)
        report((index + 1) * 1000, f"Preparado {validation_index} de {validation_total}: {path.name}.")

    result.results.extend(validation_errors[index] for index in sorted(validation_errors))
    session.close()
    result.timings["Preparación"] = time.perf_counter() - started

    # All source files have passed validation before the first replacement.
    report(len(paths) * 1000, "Validación completada. Guardando resultados…")

    # A validation failure is reported before any source workbook is changed.
    # It is safer to ask the operator to correct the batch than to leave a
    # mixed batch where only the first files were written successfully.
    if result.error_count:
        report(current, "Validación detenida por errores; originales sin modificar.")
        return result

    for path, version in source_versions.items():
        try:
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != version:
                raise ValueError("El archivo cambió durante la preparación; vuelve a cargar el lote.")
        except Exception as exc:
            result.results.append(SheetRename(path, False, message=str(exc)))
    if result.error_count:
        report(current, "Lote detenido: un original cambió durante la preparación.")
        return result

    saving_started = time.perf_counter()
    prepared_outputs = []
    # Finish every output before replacing any original.
    for index, path, vaciado in candidates:
        offset = (len(paths) + index) * 1000
        try:
            if index in staged_xls:
                working, item = staged_xls.pop(index)
            else:
                working = staging / f"prepared-{index}{path.suffix}"
                shutil.copy2(path, working)
                plan = replace(plans_by_index.pop(index), path=working)
                item = _process_file_plan(plan, phase(offset), 0, plan.work_units)
                item = replace(item, path=path)
            prepared_outputs.append((working, item))
        except Exception as exc:
            result.results.append(SheetRename(path, False, message=str(exc), vaciado=vaciado))
            report(current, "Preparación detenida; originales intactos.")
            return result
    try:
        recovery = RecoverableBatch([path for _, path, _ in candidates], source_versions)
    except Exception as exc:
        result.results.append(SheetRename(candidates[0][1] if candidates else Path(), False, message=str(exc)))
        return result
    for commit_index, (index, path, vaciado) in enumerate(candidates):
        offset = (2 * len(paths) + index) * 1000
        report(offset, f"Guardando {path.name}…")
        try:
            working, item = prepared_outputs[commit_index]
            recovery.commit(commit_index, working, _commit_temporary)
            result.results.append(item)
            report(offset + 1000, f"Guardado {path.name}.")
        except Exception as exc:
            result.results.append(
                SheetRename(path=path, success=False, message=str(exc), vaciado=vaciado)
            )
            rollback_errors = recovery.rollback(_commit_temporary)
            recovery_note = (f"Recuperación pendiente en {recovery.directory}: " + "; ".join(rollback_errors)
                             if rollback_errors else "Lote cancelado: originales restaurados.")
            result.results = [replace(item, success=False, message=(item.message + " " + recovery_note).strip())
                              for item in result.results]
            if not rollback_errors:
                recovery.cleanup()
            report(current, recovery_note)
            break
    result.timings["Guardado"] = time.perf_counter() - saving_started
    result.timings["Total motor"] = time.perf_counter() - started
    if not result.error_count:
        try:
            recovery.complete()
            recovery.cleanup()
        except OSError:
            result.warnings.append(f"El lote se guardó; queda pendiente limpiar su copia de seguridad en {recovery.directory}.")
        report(total, "Proceso completado.", finished=True)
    return result


def _normalise_vaciado(value: object) -> VaciadoType:
    normalised = str(value).strip().casefold()
    if normalised not in VALID_VACIADO_TYPES:
        raise ValueError(f"tipo de vaciado no valido: {value}")
    return normalised  # type: ignore[return-value]


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("no es un numero valido")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace(" ", "")
    if not text:
        raise ValueError("no es un numero valido")
    # Accept the usual Excel imports without changing their textual contents.
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("no es un numero valido") from exc


def _format_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), ".2f")


def _normalise_header(value: object) -> str:
    return "".join(str(value or "").split()).casefold()


def _build_file_plan(
    path: Path,
    vaciado: VaciadoType,
    progress: Callable[[PesosProgress], None] | None = None,
) -> _FilePlan:
    if path.suffix.lower() in LEGACY_EXCEL_EXTENSIONS:
        if vaciado == "ninguno":
            return _FilePlan(path=path, vaciado=vaciado)
        return _FilePlan(path=path, vaciado=vaciado, legacy_weight_count=_inspect_legacy_xls(path, vaciado))
    return _build_ooxml_file_plan(path, vaciado, progress=progress)


def _build_ooxml_file_plan(
    path: Path,
    vaciado: VaciadoType,
    *,
    progress: Callable[[PesosProgress], None] | None,
) -> _FilePlan:
    """Validate only the XML parts that Pesos actually uses.

    ``openpyxl`` loads an object for every cell and regenerates the whole
    workbook when saving.  This route reads the workbook manifest and the
    relevant worksheets directly, preserving all untouched package members
    (including VBA, drawings, formulas and validations) byte-for-byte.
    """
    try:
        with ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            if WORKBOOK_XML not in names or WORKBOOK_RELS_XML not in names:
                raise ValueError("no se encontro la estructura interna del libro Excel")
            workbook_xml = archive.read(WORKBOOK_XML)
            renamed_xml, before, changed = _renamed_workbook_xml(workbook_xml)
            relationships = _workbook_sheet_parts(archive.read(WORKBOOK_RELS_XML))
            sheets = _workbook_sheets(workbook_xml, relationships)
            shared_strings = _shared_strings(archive.read(SHARED_STRINGS_XML)) if SHARED_STRINGS_XML in names else ()
            if vaciado == "ninguno":
                return _FilePlan(
                    path=path,
                    vaciado=vaciado,
                    workbook_xml=renamed_xml if changed else None,
                    archive_entries=len(archive.infolist()),
                    before=before,
                    renamed=changed,
                )

            weight_sheets: list[_WeightSheetPlan] = []
            updates: list[_OoxmlCellUpdate] = []
            parsed_sheets: list[tuple[str, ET.Element, tuple[_OoxmlCellUpdate, ...]]] = []
            for sheet_index, (title, sheet_path) in enumerate(sheets):
                if sheet_path not in names:
                    raise ValueError(f"{path.name}: falta la hoja interna {sheet_path}")
                sheet_root, sheet_plan, sheet_updates = _ooxml_weight_sheet_plan(
                    archive.read(sheet_path), title, sheet_path, shared_strings, vaciado
                )
                if sheet_plan is not None:
                    weight_sheets.append(sheet_plan)
                    updates.extend(sheet_updates)
                    parsed_sheets.append((sheet_path, sheet_root, sheet_updates))
                _emit_progress(progress, sheet_index + 1, len(sheets) * 2,
                               f"Inspeccionada hoja {sheet_index + 1} de {len(sheets)} en {path.name}.")
            if not weight_sheets:
                raise ValueError(f"{path.name}: no se encontró el encabezado pesoBruto en ninguna hoja")
            style_xml = archive.read(STYLES_XML) if STYLES_XML in names else None
            style_mapping, updated_styles = _text_style_mapping(style_xml, {update.style_id for update in updates})
            replacements: list[_OoxmlPartReplacement] = []
            if updated_styles is not None and updated_styles != style_xml:
                replacements.append(_OoxmlPartReplacement(STYLES_XML, updated_styles))
            for sheet_index, (sheet_path, sheet_root, sheet_updates) in enumerate(parsed_sheets):
                report_every = max(1, len(sheet_updates) // 100)
                _apply_ooxml_weight_updates(
                    sheet_root,
                    sheet_updates,
                    style_mapping,
                    report_every=report_every,
                    report_progress=lambda processed, index=sheet_index, total_updates=len(sheet_updates): _emit_progress(
                        progress,
                        1000 * len(parsed_sheets) + 1000 * index + int(900 * processed / max(1, total_updates)),
                        2000 * len(parsed_sheets),
                        f"Ajustando pesos en {path.name}: {processed} de {total_updates}…",
                    ),
                )
                replacements.append(
                    _OoxmlPartReplacement(
                        sheet_path,
                        ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True),
                    )
                )
                _emit_progress(progress, len(parsed_sheets) + sheet_index + 1, 2 * len(parsed_sheets),
                               f"Preparada hoja {sheet_index + 1} de {len(parsed_sheets)} en {path.name}.")
            return _FilePlan(
                path=path,
                vaciado=vaciado,
                weight_sheets=tuple(weight_sheets),
                ooxml_updates=tuple(updates),
                ooxml_replacements=tuple(replacements),
                workbook_xml=renamed_xml if changed else None,
                archive_entries=len(archive.infolist()),
                before=before,
                renamed=changed,
            )
    except BadZipFile as exc:
        raise ValueError("el archivo no parece un Excel XLSX/XLSM valido") from exc


def _workbook_sheet_parts(relationships_xml: bytes) -> dict[str, str]:
    root = ET.fromstring(relationships_xml)
    parts: dict[str, str] = {}
    for relation in root.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        relation_id = relation.attrib.get("Id")
        target = relation.attrib.get("Target", "")
        if relation_id and target:
            parts[relation_id] = "xl/" + target.lstrip("/").removeprefix("xl/")
    return parts


def _workbook_sheets(workbook_xml: bytes, relationships: dict[str, str]) -> tuple[tuple[str, str], ...]:
    root = ET.fromstring(workbook_xml)
    sheets = root.find(f"{{{MAIN_NS}}}sheets")
    if sheets is None:
        raise ValueError("el libro no contiene hojas")
    result: list[tuple[str, str]] = []
    for sheet in sheets.findall(f"{{{MAIN_NS}}}sheet"):
        relation_id = sheet.attrib.get(f"{{{DOCUMENT_REL_NS}}}id", "")
        sheet_path = relationships.get(relation_id)
        if sheet_path is None:
            raise ValueError("no se encontro la relación interna de una hoja")
        result.append((sheet.attrib.get("name", ""), sheet_path))
    if not result:
        raise ValueError("el libro no contiene hojas")
    return tuple(result)


def _shared_strings(shared_strings_xml: bytes) -> tuple[str, ...]:
    root = ET.fromstring(shared_strings_xml)
    return tuple("".join(node.itertext()) for node in root.findall(f"{{{MAIN_NS}}}si"))


def _ooxml_weight_sheet_plan(
    sheet_xml: bytes,
    title: str,
    sheet_path: str,
    shared_strings: tuple[str, ...],
    vaciado: VaciadoType,
) -> tuple[ET.Element, _WeightSheetPlan | None, tuple[_OoxmlCellUpdate, ...]]:
    root = ET.fromstring(sheet_xml)
    cells = list(root.iter(f"{{{MAIN_NS}}}c"))
    # Vaciado applies exclusively to gross weight. Net cells (including
    # formulas, text and styles) must never enter the adjustment plan.
    matches: dict[str, list[tuple[int, int]]] = {"pesoBruto": []}
    parsed_cells: list[tuple[ET.Element, int, int, str]] = []
    for cell in cells:
        coordinate = cell.attrib.get("r", "")
        row, column = _cell_position(coordinate)
        value = _ooxml_cell_value(cell, shared_strings)
        parsed_cells.append((cell, row, column, value))
        key = _normalise_header(value)
        if key == "pesobruto":
            matches["pesoBruto"].append((row, column))

    if not any(matches.values()):
        return root, None, ()

    columns: list[_WeightColumnPlan] = []
    updates: list[_OoxmlCellUpdate] = []
    for label, header_matches in matches.items():
        if not header_matches:
            raise ValueError(f"hoja {title}: falta el encabezado {label}")
        if len(header_matches) != 1:
            raise ValueError(f"hoja {title}: encabezado {label} ambiguo")
        header_row, weight_column = header_matches[0]
        rows: list[int] = []
        for cell, row, column, value in parsed_cells:
            if row <= header_row or column != weight_column or value == "":
                continue
            try:
                adjusted = _format_decimal(_calcular_peso_vaciado_decimal(value, vaciado))
            except ValueError as exc:
                raise ValueError(f"hoja {title}, fila {row}, {label}: {exc}") from exc
            rows.append(row)
            updates.append(
                _OoxmlCellUpdate(
                    sheet_path=sheet_path,
                    coordinate=cell.attrib["r"],
                    value=adjusted,
                    style_id=int(cell.attrib.get("s", "0")),
                )
            )
        columns.append(_WeightColumnPlan(label, weight_column, tuple(rows)))
    return root, _WeightSheetPlan(title, tuple(columns)), tuple(updates)


def _cell_position(coordinate: str) -> tuple[int, int]:
    letters = "".join(character for character in coordinate if character.isalpha())
    digits = "".join(character for character in coordinate if character.isdigit())
    if not letters or not digits:
        raise ValueError(f"celda Excel no valida: {coordinate or '(sin referencia)'}")
    column = 0
    for character in letters.upper():
        column = column * 26 + ord(character) - ord("A") + 1
    return int(digits), column


def _ooxml_cell_value(cell: ET.Element, shared_strings: tuple[str, ...]) -> str:
    formula = cell.find(f"{{{MAIN_NS}}}f")
    if formula is not None:
        return "=" + (formula.text or "")
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{{{MAIN_NS}}}is")
        return "".join(inline.itertext()) if inline is not None else ""
    value = cell.find(f"{{{MAIN_NS}}}v")
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared_strings[int(value.text)]
        except (IndexError, ValueError) as exc:
            raise ValueError("índice de texto compartido no valido") from exc
    return value.text


def _process_file_plan(
    plan: _FilePlan,
    progress: Callable[[PesosProgress], None] | None,
    completed: int,
    total: int,
) -> SheetRename:
    if plan.path.suffix.lower() in LEGACY_EXCEL_EXTENSIONS:
        _emit_progress(progress, completed, total, f"Abriendo {plan.path.name} con Excel…", busy=True)
        return _process_legacy_xls(plan, progress, completed, total)
    if plan.vaciado == "ninguno":
        _emit_progress(progress, completed, total, f"Actualizando {plan.path.name}…", busy=True)
    return _process_ooxml(plan, progress, completed, total)


def _process_ooxml(
    plan: _FilePlan,
    progress: Callable[[PesosProgress], None] | None,
    completed: int,
    total: int,
) -> SheetRename:
    if plan.vaciado == "ninguno" and not plan.renamed:
        _emit_progress(progress, completed + 1, total, f"{plan.path.name} ya está actualizado.")
        return SheetRename(path=plan.path, success=True, before=plan.before, changed=False)

    replacements: dict[str, bytes] = {}
    if plan.workbook_xml is not None:
        replacements[WORKBOOK_XML] = plan.workbook_xml
    replacements.update({part.path: part.content for part in plan.ooxml_replacements})
    _emit_progress(progress, completed + 1, total, f"Preparada la actualización de {plan.path.name}…")

    _replace_archive_parts(
        plan.path,
        replacements,
        progress=progress,
        completed=completed + 1,
        total=total,
    )
    return SheetRename(
        path=plan.path,
        success=True,
        before=plan.before,
        changed=plan.renamed,
        vaciado=plan.vaciado,
        adjusted_sheets=len(plan.weight_sheets),
        adjusted_weights=len(plan.ooxml_updates),
    )


def _rename_ooxml_atomically(path: Path) -> SheetRename:
    """Keep the original XML-only rename route for files without vaciado."""
    temp_path = _temporary_path_for(path)
    try:
        shutil.copy2(path, temp_path)
        temporary_result = rename_first_visible_sheet(temp_path)
        if not temporary_result.success:
            raise ValueError(temporary_result.message or "no se pudo renombrar la hoja")
        _commit_temporary(temp_path, path)
        return SheetRename(
            path=path,
            success=True,
            before=temporary_result.before,
            changed=temporary_result.changed,
        )
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _text_style_mapping(styles_xml: bytes | None, style_ids: set[int]) -> tuple[dict[int, int], bytes | None]:
    """Create text-format style variants while leaving existing styles intact."""
    if not style_ids or styles_xml is None:
        return {}, styles_xml
    root = ET.fromstring(styles_xml)
    cell_xfs = root.find(f"{{{MAIN_NS}}}cellXfs")
    if cell_xfs is None:
        # Inline strings still preserve the exchange value as text.  This is
        # the only valid fallback for unusually minimal OOXML workbooks.
        return {}, styles_xml
    formats = list(cell_xfs)
    mapping: dict[int, int] = {}
    for style_id in sorted(style_ids):
        if not 0 <= style_id < len(formats):
            raise ValueError("índice de estilo de celda no valido")
        variant = ET.fromstring(ET.tostring(formats[style_id], encoding="utf-8"))
        variant.set("numFmtId", "49")  # Built-in Excel format: Text (@)
        variant.set("applyNumberFormat", "1")
        mapping[style_id] = len(formats)
        cell_xfs.append(variant)
        formats.append(variant)
    cell_xfs.set("count", str(len(formats)))
    return mapping, ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _apply_ooxml_weight_updates(
    root: ET.Element,
    updates: list[_OoxmlCellUpdate],
    style_mapping: dict[int, int],
    *,
    report_every: int,
    report_progress: Callable[[int], None] | None,
) -> None:
    by_coordinate = {update.coordinate: update for update in updates}
    found: set[str] = set()
    processed = 0
    for cell in root.iter(f"{{{MAIN_NS}}}c"):
        coordinate = cell.attrib.get("r", "")
        update = by_coordinate.get(coordinate)
        if update is None:
            continue
        found.add(coordinate)
        cell.set("t", "inlineStr")
        if update.style_id in style_mapping:
            cell.set("s", str(style_mapping[update.style_id]))
        for child in list(cell):
            if child.tag in {f"{{{MAIN_NS}}}v", f"{{{MAIN_NS}}}is", f"{{{MAIN_NS}}}f"}:
                cell.remove(child)
        inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
        text = ET.SubElement(inline, f"{{{MAIN_NS}}}t")
        text.text = update.value
        processed += 1
        if report_progress is not None and processed % report_every == 0:
            report_progress(processed)
    missing = by_coordinate.keys() - found
    if missing:
        raise ValueError(f"no se encontraron {len(missing)} celdas validadas al actualizar el libro")
    if report_progress is not None and processed % report_every:
        report_progress(processed)


def _replace_archive_parts(
    path: Path,
    replacements: dict[str, bytes],
    *,
    progress: Callable[[PesosProgress], None] | None,
    completed: int,
    total: int,
) -> None:
    """Write a validated replacement archive and atomically swap it in."""
    temp_path = _temporary_path_for(path)
    try:
        with ZipFile(path, "r") as source, ZipFile(temp_path, "w") as target:
            target.comment = source.comment
            entries = source.infolist()
            for index, info in enumerate(entries, start=1):
                content = replacements[info.filename] if info.filename in replacements else source.read(info.filename)
                target.writestr(info, content)
                _emit_progress(
                    progress,
                    completed + index,
                    total,
                    f"Guardando {plan_path_name(path)}: componente {index} de {len(entries)}…",
                )
        with ZipFile(temp_path, "r") as check:
            invalid_member = check.testzip()
            if invalid_member is not None:
                raise ValueError(f"la copia temporal tiene datos dañados en {invalid_member}")
        _emit_progress(progress, completed + len(entries) + 1, total, f"Verificado {path.name}; confirmando guardado…")
        _commit_temporary(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def plan_path_name(path: Path) -> str:
    return path.name


def _temporary_path_for(path: Path) -> Path:
    with tempfile.NamedTemporaryFile(delete=False, prefix="suite-pesos-", suffix=path.suffix) as temp_file:
        return Path(temp_file.name)


def _commit_temporary(temporary: Path, destination: Path) -> None:
    """Atomic replacement; only cross-volume saves need a short-lived sibling."""
    from .guarded_replace import guarded_replace
    if guarded_replace(temporary, destination):
        return
    try:
        os.replace(temporary, destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
            raise
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".suite-pesos-", suffix=".tmp", delete=False) as handle:
            sibling = Path(handle.name)
        try:
            shutil.copyfile(temporary, sibling)
            os.replace(sibling, destination)
        finally:
            sibling.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def _emit_progress(
    callback: Callable[[PesosProgress], None] | None,
    completed: int,
    total: int,
    message: str,
    *,
    busy: bool = False,
) -> None:
    if callback is not None:
        callback(PesosProgress(completed=max(0, completed), total=max(1, total), message=message, busy=busy))


def _inspect_legacy_xls(path: Path, vaciado: VaciadoType) -> int:
    """Compatibility inspection uses the same supervised engine on a copy."""
    with tempfile.TemporaryDirectory(prefix="suite-xls-inspect-") as directory:
        working = Path(directory) / "inspect.xls"
        shutil.copy2(path, working)
        with _LegacyExcelSession() as session:
            return session.process(_FilePlan(working, vaciado), None, 0, 1000).adjusted_weights


class _LegacyExcelSession:
    """One lazily started, private Excel/PowerShell session per batch.

    Only staged copies are submitted. Commands are sequential; a reader thread
    drains output so the timeout also covers a blocked Excel operation.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._script: Path | None = None
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._closed = False
        self._excel_owner = None

    def __enter__(self) -> _LegacyExcelSession:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _start(self) -> None:
        if self._closed:
            raise ValueError("La sesión de Excel se cerró; vuelve a procesar el lote.")
        if self._process is not None:
            return
        self._script = _write_legacy_adjustment_script()
        try:
            self._process = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(self._script), "-Server"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as exc:
            self.close()
            raise ValueError("no se encontro PowerShell para procesar archivos .xls") from exc
        stream = self._process.stdout
        assert stream is not None

        def read_output() -> None:
            try:
                for line in stream:
                    self._lines.put(line.rstrip("\r\n"))
            finally:
                self._lines.put(None)

        self._reader = threading.Thread(target=read_output, daemon=True, name="pesos-excel-output")
        self._reader.start()

    def process(
        self, plan: _FilePlan, progress: Callable[[PesosProgress], None] | None,
        completed_units: int, total_units: int,
    ) -> SheetRename:
        self._start()
        assert self._process is not None and self._process.stdin is not None
        command = json.dumps({"path": str(plan.path), "target": TARGET_SHEET_NAME, "vaciado": plan.vaciado})
        try:
            self._process.stdin.write(command + "\n")
            self._process.stdin.flush()
        except OSError as exc:
            raise ValueError("Se interrumpió la sesión de Excel; originales sin modificar.") from exc
        deadline = time.monotonic() + 180
        diagnostics: list[str] = []
        while True:
            checkpoint()
            try:
                line = self._lines.get(timeout=min(0.2, max(0, deadline - time.monotonic())))
            except queue.Empty as exc:
                if time.monotonic() < deadline:
                    continue
                self.close()
                raise ValueError("Excel no respondió en 180 segundos; originales sin modificar.") from exc
            if line is None:
                self.close()
                raise ValueError("La sesión de Excel terminó sin resultado. " + "\n".join(diagnostics[-5:]))
            if line.startswith("EXCEL|"):
                _, pid, created = line.split("|")
                self._excel_owner = OwnedProcess(int(pid), int(created), 'EXCEL.EXE')
                self._process.stdin.write('OWNED\n')
                self._process.stdin.flush()
            elif line.startswith("PROGRESS|"):
                _, processed, planned = line.split("|", maxsplit=2)
                _emit_progress(progress,
                    completed_units + int(800 * int(processed) / max(1, int(planned))),
                    total_units, f"Escritos {processed} de {planned} pesos…")
            elif line.startswith("{"):
                data = _json_last_line(line)
                if not data.get("success"):
                    raise ValueError(str(data.get("message") or "no se pudo procesar el archivo .xls"))
                return SheetRename(
                    path=plan.path, success=True, before=str(data.get("before") or ""),
                    changed=bool(data.get("changed")), vaciado=plan.vaciado,
                    adjusted_sheets=int(data.get("adjustedSheets") or 0),
                    adjusted_weights=int(data.get("adjustedWeights") or 0),
                )
            else:
                diagnostics.append(line)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._process is not None:
                try:
                    if self._process.stdin is not None:
                        self._process.stdin.close()
                except OSError:
                    pass
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if self._excel_owner is not None:
                        self._excel_owner.terminate_if_running()
                    self._process.kill()
                    self._process.wait(timeout=10)
                if self._reader is not None:
                    self._reader.join(timeout=2)
                if self._process.stdout is not None:
                    self._process.stdout.close()
        finally:
            if self._excel_owner is not None:
                try:
                    self._excel_owner.terminate_if_running()
                finally:
                    self._excel_owner.close()
            if self._script is not None:
                self._script.unlink(missing_ok=True)


def _process_legacy_xls(plan, progress, completed_units, total_units) -> SheetRename:
    """Legacy callers share the recoverable batch route, not a second engine."""
    def report(update):
        fraction = update.completed / max(1, update.total)
        _emit_progress(progress, completed_units + int(plan.work_units * fraction),
                       total_units, update.message)
    result = process_pesos_files([plan.path], {plan.path: plan.vaciado}, report)
    return result.results[0]


def _json_last_line(output: str) -> dict[str, object]:
    try:
        data = json.loads(output.strip().splitlines()[-1]) if output.strip() else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_legacy_adjustment_script() -> Path:
    # This remains deliberately self-contained because pyproject intentionally
    # has no XLS writer dependency.  COM is only the legacy fallback; XLSX/XLSM
    # processing above does not require Excel to be installed.
    script = r'''
param([string]$Path, [string]$TargetName, [string]$Vaciado, [string]$Preview = '', [switch]$Server)
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
function Invoke-PesosWorkbook {
param([string]$Path, [string]$TargetName, [string]$Vaciado, [string]$Preview = '', [object]$SharedExcel = $null)
$ErrorActionPreference = "Stop"
$excel = $null
$workbook = $null
$isPreview = $Preview -eq 'preview'
function Header-Key([object]$Value) {
    return (([string]$Value -replace '\s', '').ToLowerInvariant())
}
function Decimal-Value([object]$Value) {
    if ($null -eq $Value -or $Value -is [bool]) { throw "no es un numero valido" }
    $invariant = [Globalization.CultureInfo]::InvariantCulture
    $styles = [Globalization.NumberStyles]::AllowLeadingWhite -bor [Globalization.NumberStyles]::AllowTrailingWhite -bor [Globalization.NumberStyles]::AllowLeadingSign -bor [Globalization.NumberStyles]::AllowDecimalPoint -bor [Globalization.NumberStyles]::AllowExponent
    # Value2 returns native numeric COM values.  Converting those to a string
    # with the current culture first turns 143.7 into "143,7" in Spanish;
    # invariant Number parsing then reads that comma as a thousands separator.
    # Format numerics invariantly before parsing so no decimal is displaced.
    if ($Value -is [byte] -or $Value -is [sbyte] -or $Value -is [int16] -or $Value -is [uint16] -or $Value -is [int32] -or $Value -is [uint32] -or $Value -is [int64] -or $Value -is [uint64] -or $Value -is [single] -or $Value -is [double] -or $Value -is [decimal]) {
        $text = [Convert]::ToString($Value, $invariant)
        return [decimal]::Parse($text, $styles, $invariant)
    }
    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { throw "no es un numero valido" }
    $text = $text -replace '\s', ''
    if ($text.Contains(',') -and $text.Contains('.')) {
        if ($text.LastIndexOf(',') -gt $text.LastIndexOf('.')) {
            $text = $text.Replace('.', '').Replace(',', '.')
        } else {
            $text = $text.Replace(',', '')
        }
    } elseif ($text.Contains(',')) {
        $text = $text.Replace(',', '.')
    }
    try { return [decimal]::Parse($text, $styles, $invariant) }
    catch { throw "no es un numero valido" }
}
try {
    $excel = $SharedExcel
    if ($null -eq $excel) { $excel = New-Object -ComObject Excel.Application }
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.ScreenUpdating = $false
    $excel.EnableEvents = $false
    $excel.AutomationSecurity = 3
    $workbook = $excel.Workbooks.Open($Path)
    $targetSheet = $null
    foreach ($sheet in @($workbook.Worksheets)) {
        if ($sheet.Visible -eq -1) { $targetSheet = $sheet; break }
    }
    if ($null -eq $targetSheet) { $targetSheet = $workbook.Worksheets.Item(1) }
    $previous = [string]$targetSheet.Name
    $changed = $false
    if ($previous -ne $TargetName) {
        foreach ($sheet in @($workbook.Worksheets)) {
            if ($sheet.Name -ieq $TargetName -and $sheet.Index -ne $targetSheet.Index) {
                throw "ya existe otra hoja llamada $TargetName; no se cambia nada para evitar nombres duplicados"
            }
        }
        if (-not $isPreview) {
            $targetSheet.Name = $TargetName
            $changed = $true
        }
    }
    $adjustedSheets = 0
    $adjustedWeights = 0
    $weightCells = New-Object 'System.Collections.Generic.List[object]'
    if ($Vaciado -ne 'ninguno') {
        foreach ($sheet in @($workbook.Worksheets)) {
            $used = $sheet.UsedRange
            # Fetch the sheet once across COM; scan the array in PowerShell.
            # Per-cell COM calls dominated the runtime of small XLS lots.
            $values = $used.Value2
            $rowCount = $used.Rows.Count
            $columnCount = $used.Columns.Count
            $firstRow = $used.Row
            $firstColumn = $used.Column
            $headerHits = @{ pesobruto = @() }
            for ($r = 1; $r -le $rowCount; $r++) {
                for ($c = 1; $c -le $columnCount; $c++) {
                    $rawValue = if ($values -is [array]) { $values.GetValue($r, $c) } else { $values }
                    $headerKey = Header-Key $rawValue
                    if ($headerKey -eq 'pesobruto') {
                        $headerHits[$headerKey] += ,@(($firstRow + $r - 1), ($firstColumn + $c - 1))
                    }
                }
            }
            if ($headerHits['pesobruto'].Count -eq 0) { continue }
            foreach ($headerKey in @('pesobruto')) {
                $headerLabel = 'pesoBruto'
                if ($headerHits[$headerKey].Count -eq 0) { throw "hoja $($sheet.Name): falta el encabezado $headerLabel" }
                if ($headerHits[$headerKey].Count -ne 1) { throw "hoja $($sheet.Name): encabezado $headerLabel ambiguo" }
            }
            $adjustedSheets++
            $lastRow = $firstRow + $rowCount - 1
            foreach ($headerKey in @('pesobruto')) {
                $header = $headerHits[$headerKey][0]
                $headerRow = [int]$header[0]
                $weightColumn = [int]$header[1]
                $headerLabel = 'pesoBruto'
                for ($r = $headerRow + 1; $r -le $lastRow; $r++) {
                    $rawWeight = $values.GetValue(($r - $firstRow + 1), ($weightColumn - $firstColumn + 1))
                    if ($null -eq $rawWeight -or [string]$rawWeight -eq '') { continue }
                    try { $weight = Decimal-Value $rawWeight }
                    catch { throw "hoja $($sheet.Name), fila $r, ${headerLabel}: $($_.Exception.Message)" }
                    $weightCells.Add([pscustomobject]@{Sheet=$sheet; Row=$r; Column=$weightColumn; Weight=$weight; Label=$headerLabel})
                }
            }
        }
        if ($adjustedSheets -eq 0) { throw "no se encontro el encabezado pesoBruto en ninguna hoja" }
    }
    $plannedWeights = $weightCells.Count
    if (-not $isPreview) {
        $index = 0
        while ($index -lt $weightCells.Count) {
            $first = $weightCells[$index]
            $last = $index
            # Never include blank gaps or cells in another column/sheet.
            # Bounded blocks also expose real completed work to the UI.
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
                # Text preserves the literal decimal point on Spanish Excel.
                $block[$offset,0] = $adjusted.ToString('0.00', [Globalization.CultureInfo]::InvariantCulture)
            }
            $range = $first.Sheet.Range($first.Sheet.Cells.Item($first.Row, $first.Column),
                                       $first.Sheet.Cells.Item($weightCells[$last].Row, $first.Column))
            $range.NumberFormat = '@'
            $range.Value2 = $block
            $adjustedWeights += $count
            $index = $last + 1
            Write-Output "PROGRESS|$adjustedWeights|$plannedWeights"
        }
        $workbook.Save()
    }
    $result = [pscustomobject]@{success=$true; before=$previous; changed=$changed; adjustedSheets=$adjustedSheets; adjustedWeights=$adjustedWeights; plannedWeights=$plannedWeights}
} catch {
    $result = [pscustomobject]@{success=$false; message=$_.Exception.Message}
} finally {
    if ($workbook -ne $null) { $workbook.Close($false) }
    if ($excel -ne $null -and $null -eq $SharedExcel) {
        $excel.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}
# A result is sent only once the workbook is closed and its lock released.
$result | ConvertTo-Json -Compress
}
if (-not $Server) {
    Invoke-PesosWorkbook -Path $Path -TargetName $TargetName -Vaciado $Vaciado -Preview $Preview
    return
}
$shared = $null
try {
    Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class SuiteExcelOwner { [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process); }'
    $existingExcel = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $shared = New-Object -ComObject Excel.Application
    [uint32]$excelId = 0
    [void][SuiteExcelOwner]::GetWindowThreadProcessId([IntPtr]$shared.Hwnd, [ref]$excelId)
    if ($excelId -eq 0 -or $existingExcel -contains $excelId) {
        $shared = $null
        throw 'Excel no creó una instancia privada; se cancela para proteger las ventanas existentes.'
    }
    $created = [Diagnostics.Process]::GetProcessById($excelId).StartTime.ToUniversalTime().ToFileTimeUtc()
    Write-Output "EXCEL|$excelId|$created"
    # The first input is the already queued workbook request. Wait for Python
    # to retain the exact process handle before submitting any COM work.
    $firstRequest = [Console]::ReadLine()
    if ([Console]::ReadLine() -ne 'OWNED') { throw 'No se pudo supervisar Excel.' }
    $shared.Visible = $false
    $shared.DisplayAlerts = $false
    $shared.ScreenUpdating = $false
    $shared.EnableEvents = $false
    $shared.AutomationSecurity = 3
    $request = $firstRequest | ConvertFrom-Json
    Invoke-PesosWorkbook -Path $request.path -TargetName $request.target -Vaciado $request.vaciado -SharedExcel $shared
    while ($null -ne ($line = [Console]::ReadLine())) {
        $request = $line | ConvertFrom-Json
        Invoke-PesosWorkbook -Path $request.path -TargetName $request.target -Vaciado $request.vaciado -SharedExcel $shared
    }
} catch {
    [pscustomobject]@{success=$false; message=$_.Exception.Message} | ConvertTo-Json -Compress
} finally {
    if ($null -ne $shared) { $shared.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shared) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
'''
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".ps1", encoding="utf-8-sig") as temp_file:
        temp_file.write(script)
        return Path(temp_file.name)


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
    _replace_archive_parts(path, {WORKBOOK_XML: workbook_xml}, progress=None, completed=0, total=1)


def _rename_legacy_xls_with_excel(path: Path) -> SheetRename:
    result = process_pesos_files([path])
    return result.results[0]
