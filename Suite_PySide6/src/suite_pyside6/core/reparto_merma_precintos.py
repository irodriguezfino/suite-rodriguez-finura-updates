"""Dominio para repartir una merma de peso entre precintos y exportar a AX.

El contrato de salida se concentra en :data:`AX_CSV_FORMAT`: dos columnas sin
cabecera, ``;``, decimal con coma, cp1252, CRLF y sin BOM.  Los importes de
peso usan :class:`decimal.Decimal` de extremo a extremo.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Literal
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.workbook import Workbook


Severity = Literal["error"]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: Severity = "error"
    line_number: int | None = None


@dataclass(frozen=True)
class IgnoredRow:
    line_number: int
    reason: str


@dataclass(frozen=True)
class SourceFormat:
    worksheet: str
    column: str
    has_message_header: bool


@dataclass(frozen=True)
class SourceRecord:
    line_number: int
    position: int
    precinto: str
    peso_original: Decimal


@dataclass(frozen=True)
class SourceReadResult:
    source_format: SourceFormat | None
    records: tuple[SourceRecord, ...]
    ignored_rows: tuple[IgnoredRow, ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def total_weight(self) -> Decimal:
        return sum((record.peso_original for record in self.records), Decimal("0"))

    @property
    def is_valid(self) -> bool:
        return bool(self.records) and not self.errors

    def require_valid(self) -> None:
        if self.is_valid:
            return
        if self.errors:
            raise DomainValidationError(self.errors)
        raise DomainValidationError((ValidationIssue("NO_VALID_RECORDS", "No hay registros validos."),))


@dataclass(frozen=True)
class AXCsvFormat:
    encoding: str = "cp1252"
    delimiter: str = ";"
    decimal_separator: str = ","
    precision: int = 2
    line_ending: str = "\r\n"
    include_header: bool = False
    bom: bytes = b""
    headers: tuple[str, str] = ("Precinto", "Peso ajustado")


AX_CSV_FORMAT = AXCsvFormat()


@dataclass(frozen=True)
class FinalWeightValidation:
    weight: Decimal | None
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def is_valid(self) -> bool:
        return self.weight is not None and not self.errors

    def require_valid(self) -> Decimal:
        if self.is_valid:
            assert self.weight is not None
            return self.weight
        raise DomainValidationError(self.errors)


@dataclass(frozen=True)
class AdjustmentRow:
    source: SourceRecord
    exact_weight: Decimal
    adjusted_weight: Decimal
    rounding_units: int


@dataclass(frozen=True)
class AdjustmentResult:
    source_total: Decimal
    final_weight: Decimal
    absolute_loss: Decimal
    loss_percentage: Decimal
    adjustment_factor: Decimal
    rows: tuple[AdjustmentRow, ...]

    @property
    def adjusted_total(self) -> Decimal:
        return sum((row.adjusted_weight for row in self.rows), Decimal("0"))


@dataclass(frozen=True)
class PreviewRow:
    line_number: int
    precinto: str
    peso_original: Decimal
    peso_ajustado: Decimal


@dataclass(frozen=True)
class PreviewModel:
    source_total: Decimal
    final_weight: Decimal
    absolute_loss: Decimal
    loss_percentage: Decimal
    adjustment_factor: Decimal
    rows: tuple[PreviewRow, ...]


class DomainValidationError(ValueError):
    """Error que conserva los problemas mostrables por la futura interfaz."""

    def __init__(self, issues: tuple[ValidationIssue, ...]):
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def _is_message_header(value: str) -> bool:
    return value.strip().casefold().startswith("mensaje")


def _parse_decimal(value: str, field_name: str, line_number: int | None = None) -> Decimal:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} vacio")
    sign = ""
    if text[:1] in "+-":
        sign, text = text[:1], text[1:]
    if not text or not re.fullmatch(r"[0-9.,]+", text):
        raise ValueError(f"{field_name} no numerico")

    comma = "," in text
    dot = "." in text
    if comma and dot:
        if text.rfind(",") > text.rfind("."):
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif comma:
        normalized = text.replace(",", ".")
    else:
        normalized = text
    try:
        return Decimal(sign + normalized)
    except InvalidOperation as exc:
        suffix = f" en linea {line_number}" if line_number is not None else ""
        raise ValueError(f"{field_name} no numerico{suffix}") from exc


def _read_message_workbook(workbook: Workbook) -> SourceReadResult:
    records: list[SourceRecord] = []
    ignored: list[IgnoredRow] = []
    issues: list[ValidationIssue] = []
    first_content_seen = False
    has_message_header = False
    worksheet = workbook.active

    for line_number, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
        value = row[0] if row else None
        if value is None or not str(value).strip():
            ignored.append(IgnoredRow(line_number, "fila vacia"))
            continue
        if any(cell is not None and str(cell).strip() for cell in row[1:]):
            issues.append(
                ValidationIssue(
                    "INVALID_WORKBOOK_LAYOUT",
                    "Cada mensaje debe estar contenido en la primera columna del Excel.",
                    line_number=line_number,
                )
            )
            continue
        message = str(value).strip()
        if not first_content_seen:
            first_content_seen = True
            if _is_message_header(message):
                has_message_header = True
                ignored.append(IgnoredRow(line_number, "encabezado de mensaje"))
                continue
        try:
            fields = next(csv.reader([message], delimiter=";", quotechar='"', strict=True))
        except csv.Error as exc:
            issues.append(ValidationIssue("INVALID_MESSAGE_ROW", f"Mensaje invalido: {exc}", line_number=line_number))
            continue
        if len(fields) < 3:
            issues.append(
                ValidationIssue("TOO_FEW_FIELDS", "El mensaje tiene menos de tres campos.", line_number=line_number)
            )
            continue
        precinto = fields[0].strip()
        if not precinto:
            issues.append(ValidationIssue("EMPTY_SEAL", "El precinto esta vacio.", line_number=line_number))
            continue
        raw_weight = fields[2].strip()
        if not raw_weight:
            issues.append(ValidationIssue("EMPTY_WEIGHT", "El peso esta vacio.", line_number=line_number))
            continue
        try:
            weight = _parse_decimal(raw_weight, "El peso", line_number)
        except ValueError as exc:
            issues.append(ValidationIssue("INVALID_WEIGHT", str(exc), line_number=line_number))
            continue
        if weight < 0:
            issues.append(ValidationIssue("NEGATIVE_WEIGHT", "El peso no puede ser negativo.", line_number=line_number))
            continue
        records.append(SourceRecord(line_number, len(records), precinto, weight))

    total = sum((record.peso_original for record in records), Decimal("0"))
    if records and total == 0:
        issues.append(ValidationIssue("ZERO_SOURCE_TOTAL", "El peso total de origen es cero."))
    if not records and not issues:
        issues.append(ValidationIssue("NO_VALID_RECORDS", "No hay registros validos."))

    source_format = SourceFormat(worksheet.title, "A", has_message_header)
    return SourceReadResult(source_format, tuple(records), tuple(ignored), tuple(issues))


def read_source_file(path: Path) -> SourceReadResult:
    """Lee el Excel de mensajes con precinto primero y peso tercero."""

    if path.suffix.lower() != ".xlsx":
        return SourceReadResult(
            None,
            (),
            (),
            (ValidationIssue("UNSUPPORTED_FORMAT", "Solo se admiten libros Excel .xlsx."),),
        )
    try:
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    except (OSError, InvalidFileException, BadZipFile, KeyError, ValueError) as exc:
        return SourceReadResult(None, (), (), (ValidationIssue("READ_ERROR", f"No se pudo leer el fichero: {exc}"),))
    try:
        return _read_message_workbook(workbook)
    finally:
        workbook.close()


def validate_final_weight(
    value: str | Decimal | None,
    source_total: Decimal,
    export_format: AXCsvFormat = AX_CSV_FORMAT,
) -> FinalWeightValidation:
    if value is None or not str(value).strip():
        return FinalWeightValidation(None, (ValidationIssue("EMPTY_FINAL_WEIGHT", "El peso final esta vacio."),))
    try:
        weight = value if isinstance(value, Decimal) else _parse_decimal(str(value), "El peso final")
    except ValueError:
        return FinalWeightValidation(None, (ValidationIssue("INVALID_FINAL_WEIGHT", "El peso final no es numerico."),))
    if weight < 0:
        return FinalWeightValidation(None, (ValidationIssue("NEGATIVE_FINAL_WEIGHT", "El peso final no puede ser negativo."),))
    quantum = Decimal(1).scaleb(-export_format.precision)
    if weight != weight.quantize(quantum):
        return FinalWeightValidation(
            None,
            (
                ValidationIssue(
                    "FINAL_WEIGHT_PRECISION",
                    f"El peso final requiere mas de {export_format.precision} decimales para AX.",
                ),
            ),
        )
    return FinalWeightValidation(weight, ())


def _rounding_order(
    exact_units: list[Decimal],
    rounded_units: list[int],
    records: tuple[SourceRecord, ...],
    positive_residual: bool,
) -> list[int]:
    candidates = range(len(records))
    if not positive_residual:
        candidates = (index for index in candidates if rounded_units[index] > 0)
    return sorted(
        candidates,
        key=lambda index: (
            -(exact_units[index] - exact_units[index].to_integral_value(rounding=ROUND_FLOOR))
            if positive_residual
            else exact_units[index] - exact_units[index].to_integral_value(rounding=ROUND_FLOOR),
            -records[index].peso_original,
            records[index].precinto,
            records[index].position,
        ),
    )


def _reconcile_units(
    exact_units: list[Decimal],
    target_units: int,
    records: tuple[SourceRecord, ...],
) -> list[int]:
    """Conciliacion por mayores restos con desempate estable y comprobable."""

    rounded = [int(units.to_integral_value(rounding=ROUND_HALF_UP)) for units in exact_units]
    residual = target_units - sum(rounded)
    if residual == 0:
        return rounded
    order = _rounding_order(exact_units, rounded, records, positive_residual=residual > 0)
    if not order:
        raise ValueError("No hay filas aptas para conciliar el redondeo.")
    step = 1 if residual > 0 else -1
    for offset in range(abs(residual)):
        index = order[offset % len(order)]
        if rounded[index] + step < 0:
            raise ValueError("La conciliacion produciria un peso negativo.")
        rounded[index] += step
    if sum(rounded) != target_units:
        raise ValueError("La conciliacion no alcanza el peso final.")
    return rounded


def calculate_adjustment(
    source: SourceReadResult,
    final_weight_value: str | Decimal,
    export_format: AXCsvFormat = AX_CSV_FORMAT,
) -> AdjustmentResult:
    """Calcula el reparto proporcional y concilia a la precision de AX."""

    source.require_valid()
    final_validation = validate_final_weight(final_weight_value, source.total_weight, export_format)
    final_weight = final_validation.require_valid()
    quantum = Decimal(1).scaleb(-export_format.precision)
    target_units = int((final_weight / quantum).to_integral_exact())
    with localcontext() as context:
        context.prec = 50
        factor = final_weight / source.total_weight
        exact_weights = [record.peso_original * factor for record in source.records]
        exact_units = [weight / quantum for weight in exact_weights]
        rounded_units = _reconcile_units(exact_units, target_units, source.records)
    rows = tuple(
        AdjustmentRow(
            source=record,
            exact_weight=exact_weight,
            adjusted_weight=(Decimal(units) * quantum),
            rounding_units=units,
        )
        for record, exact_weight, units in zip(source.records, exact_weights, rounded_units, strict=True)
    )
    result = AdjustmentResult(
        source_total=source.total_weight,
        final_weight=final_weight,
        absolute_loss=source.total_weight - final_weight,
        loss_percentage=((source.total_weight - final_weight) / source.total_weight) * Decimal("100"),
        adjustment_factor=factor,
        rows=rows,
    )
    if result.adjusted_total != final_weight:
        raise ValueError("La suma de pesos ajustados no coincide exactamente con el peso final.")
    return result


def build_preview(result: AdjustmentResult) -> PreviewModel:
    return PreviewModel(
        source_total=result.source_total,
        final_weight=result.final_weight,
        absolute_loss=result.absolute_loss,
        loss_percentage=result.loss_percentage,
        adjustment_factor=result.adjustment_factor,
        rows=tuple(
            PreviewRow(
                line_number=row.source.line_number,
                precinto=row.source.precinto,
                peso_original=row.source.peso_original,
                peso_ajustado=row.adjusted_weight,
            )
            for row in result.rows
        ),
    )


def _format_decimal(value: Decimal, export_format: AXCsvFormat) -> str:
    quantum = Decimal(1).scaleb(-export_format.precision)
    text = format(value.quantize(quantum), f".{export_format.precision}f")
    return text.replace(".", export_format.decimal_separator)


def _export_issues(result: AdjustmentResult) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    for row in result.rows:
        if row.source.precinto.lstrip().startswith(("=", "+", "-", "@")):
            issues.append(
                ValidationIssue(
                    "CSV_INJECTION_RISK",
                    "El precinto podria interpretarse como formula CSV; no se altera para preservar AX.",
                    line_number=row.source.line_number,
                )
            )
    if result.adjusted_total != result.final_weight:
        issues.append(ValidationIssue("EXPORT_TOTAL_MISMATCH", "El total exportado no coincide con el peso final."))
    return tuple(issues)


def render_ax_csv(result: AdjustmentResult, export_format: AXCsvFormat = AX_CSV_FORMAT) -> bytes:
    """Genera y valida el CSV AX, sin mutar identificadores de precinto."""

    issues = _export_issues(result)
    if issues:
        raise DomainValidationError(issues)
    output = io.StringIO(newline="")
    writer = csv.writer(
        output,
        delimiter=export_format.delimiter,
        quotechar='"',
        quoting=csv.QUOTE_MINIMAL,
        lineterminator=export_format.line_ending,
    )
    if export_format.include_header:
        writer.writerow(export_format.headers)
    for row in result.rows:
        writer.writerow((row.source.precinto, _format_decimal(row.adjusted_weight, export_format)))
    content = export_format.bom + output.getvalue().encode(export_format.encoding, errors="strict")
    validate_ax_csv_content(content, result, export_format)
    return content


def write_ax_csv(path: Path, result: AdjustmentResult, export_format: AXCsvFormat = AX_CSV_FORMAT) -> None:
    path.write_bytes(render_ax_csv(result, export_format))


def validate_ax_csv_content(
    content: bytes,
    result: AdjustmentResult,
    export_format: AXCsvFormat = AX_CSV_FORMAT,
) -> None:
    """Relee los bytes exportados y comprueba contrato, filas y suma exacta."""

    if export_format.bom:
        if not content.startswith(export_format.bom):
            raise ValueError("El BOM de exportacion no coincide con el formato.")
        payload = content[len(export_format.bom) :]
    else:
        if content.startswith(b"\xef\xbb\xbf"):
            raise ValueError("El CSV AX no debe incluir BOM UTF-8.")
        payload = content
    text = payload.decode(export_format.encoding, errors="strict")
    if not text.endswith(export_format.line_ending):
        raise ValueError("El CSV AX debe terminar en CRLF.")
    raw_rows = text[: -len(export_format.line_ending)].split(export_format.line_ending)
    expected_count = len(result.rows) + (1 if export_format.include_header else 0)
    if len(raw_rows) != expected_count or any(not row for row in raw_rows):
        raise ValueError("El CSV AX contiene lineas adicionales o inesperadas.")
    parsed = list(csv.reader(raw_rows, delimiter=export_format.delimiter, quotechar='"', strict=True))
    if export_format.include_header:
        if tuple(parsed.pop(0)) != export_format.headers:
            raise ValueError("Las cabeceras del CSV AX no coinciden.")
    if any(len(row) != 2 for row in parsed):
        raise ValueError("Cada fila del CSV AX debe tener exactamente dos columnas.")
    expected_seals = [row.source.precinto for row in result.rows]
    exported_seals = [row[0] for row in parsed]
    if exported_seals != expected_seals:
        raise ValueError("Los precintos exportados no coinciden con los registros validos.")
    exported_total = sum((_parse_decimal(row[1], "El peso ajustado") for row in parsed), Decimal("0"))
    if exported_total != result.final_weight:
        raise ValueError("La suma del CSV AX no coincide exactamente con el peso final.")
