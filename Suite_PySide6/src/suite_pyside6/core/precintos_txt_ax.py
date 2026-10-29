from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from .jobs import checked

from .atomic_io import write_bytes_atomically, atomic_text_writer


AX_ENCODING = "cp1252"
AX_LINE_ENDING = "\r\n"
AX_DELIMITER = ";"
SOURCE_DELIMITER = "->"
# Keep the Unicode arrow escaped so this source remains unambiguous in every
# Windows editor used to maintain the Suite.  The last variant is the common
# mojibake spelling produced when an UTF-8 arrow was saved after a bad decode.
SUPPORTED_SOURCE_DELIMITERS = (SOURCE_DELIMITER, "\u2192", "=>", "\u00e2\u2020\u2019")
_INVISIBLE_CHARACTERS = "\ufeff\u200b\u200c\u200d\u2060"
_WINDOWS_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
LOGGER = logging.getLogger(__name__)
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_IGNORED_LINE_DETAILS = 10_000
MAX_IGNORED_LINE_CHARS = 2_048


@dataclass(frozen=True)
class IgnoredTxtLine:
    """A source line excluded from the AX CSV, with its specific reason."""

    line_number: int
    original_content: str
    reason: str


@dataclass
class PrecintosTxtAxResult:
    source_path: Path | None = None
    source_paths: list[Path] = field(default_factory=list)
    source_encoding: str = ""
    lines_read: int = 0
    precintos: list[str] = field(default_factory=list)
    ignored_lines: list[IgnoredTxtLine] = field(default_factory=list)
    ignored_count: int = 0
    detected_count: int = 0
    duplicate_count_value: int = 0

    @property
    def exported_count(self) -> int:
        """Number of unique precintos that will be written to the CSV."""
        return len(self.precintos)

    @property
    def valid_lines(self) -> int:
        """Number of source lines that produced a precinto."""
        return self.detected_count

    @property
    def duplicate_count(self) -> int:
        """Repeated precintos, excluding the first occurrence of each one."""
        return self.duplicate_count_value

    @property
    def skipped_lines(self) -> int:
        """Keep the summary count tied to the detailed ignored-line register."""
        return self.ignored_count

    def summary(self) -> str:
        return (
            f"Líneas leídas: {self.lines_read} | "
            f"Precintos detectados: {self.detected_count} | "
            f"Líneas válidas: {self.valid_lines} | "
            f"Líneas omitidas: {self.skipped_lines} | "
            f"Duplicados: {self.duplicate_count} | "
            f"Precintos finales para el CSV: {self.exported_count}. "
            "Los duplicados y las líneas ignoradas no se incluirán."
        )


def decode_txt_bytes(content: bytes) -> tuple[str, str]:
    """Decode common source encodings without changing the extracted values."""
    for encoding in ("utf-8-sig",):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16"), "utf-16"
    for encoding in ("cp1252", "latin-1"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("txt", content, 0, len(content), "unsupported text encoding")


def extract_precintos(text: str) -> PrecintosTxtAxResult:
    """Extract the right-hand number and remove its final control digit."""
    result = PrecintosTxtAxResult()
    seen_precintos: set[str] = set()
    for line_number, line in enumerate(checked(text.splitlines(), phase='Extrayendo precintos', unit='líneas'), start=1):
        result.lines_read = line_number
        if not line.strip():
            _record_ignored_line(result, line_number, line, "Línea vacía")
            continue
        delimiter_position, delimiter = _first_delimiter(line)
        if delimiter_position is None:
            _record_ignored_line(result, line_number, line, "Separador no encontrado")
            continue
        raw_precinto = line[delimiter_position + len(delimiter):]
        if not raw_precinto.strip():
            _record_ignored_line(result, line_number, line, "Segunda columna vacía")
            continue
        source_value = _clean_precinto(raw_precinto)
        if not source_value:
            _record_ignored_line(result, line_number, line, "Precinto vacío")
            continue
        if _has_disallowed_control_characters(source_value):
            _record_ignored_line(result, line_number, line, "Caracteres no permitidos en el precinto")
            continue
        if re.fullmatch(r"[0-9]+", source_value) is None:
            _record_ignored_line(result, line_number, line, "El valor después de la flecha no es numérico")
            continue
        if len(source_value) < 2:
            _record_ignored_line(result, line_number, line, "El valor no permite eliminar el último dígito")
            continue
        precinto = source_value[:-1]
        result.detected_count += 1
        if precinto in seen_precintos:
            result.duplicate_count_value += 1
            continue
        seen_precintos.add(precinto)
        result.precintos.append(precinto)
    return result


def _record_ignored_line(result: PrecintosTxtAxResult, line_number: int, content: str, reason: str) -> None:
    result.ignored_count += 1
    if len(result.ignored_lines) < MAX_IGNORED_LINE_DETAILS:
        result.ignored_lines.append(IgnoredTxtLine(line_number, content[:MAX_IGNORED_LINE_CHARS], reason))


def _clean_precinto(value: str) -> str:
    """Remove whitespace and invisible copy/paste characters around a code."""
    return value.translate({ord(character): None for character in _INVISIBLE_CHARACTERS}).strip()


def _has_disallowed_control_characters(value: str) -> bool:
    """Tabs and other controls inside a precinto are not valid AX values."""
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _first_delimiter(line: str) -> tuple[int | None, str]:
    matches = [(line.find(delimiter), delimiter) for delimiter in SUPPORTED_SOURCE_DELIMITERS]
    valid_matches = [(position, delimiter) for position, delimiter in matches if position >= 0]
    if not valid_matches:
        return None, ""
    return min(valid_matches, key=lambda match: match[0])


def process_txt_file(path: Path) -> PrecintosTxtAxResult:
    LOGGER.info("Procesando TXT de precintos: %s", path)
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("El TXT supera el límite seguro de 32 MiB. Divídelo en archivos más pequeños.")
    content = path.read_bytes()
    text, encoding = decode_txt_bytes(content)
    result = extract_precintos(text)
    result.source_path = path
    result.source_paths = [path]
    result.source_encoding = encoding
    LOGGER.info(
        "TXT procesado: archivo=%s codificacion=%s lineas=%s precintos=%s omitidas=%s",
        path,
        encoding,
        result.lines_read,
        result.exported_count,
        result.skipped_lines,
    )
    return result


def merge_results(results: list[PrecintosTxtAxResult]) -> PrecintosTxtAxResult:
    """Combine several processed TXT files in selection order."""
    merged = PrecintosTxtAxResult()
    line_offset = 0
    encodings: list[str] = []
    seen_precintos: set[str] = set()
    for result in results:
        if result.source_path is not None:
            merged.source_paths.append(result.source_path)
        elif result.source_paths:
            merged.source_paths.extend(result.source_paths)
        if result.source_encoding and result.source_encoding not in encodings:
            encodings.append(result.source_encoding)
        merged.detected_count += result.detected_count
        merged.duplicate_count_value += result.duplicate_count
        for precinto in result.precintos:
            if precinto in seen_precintos:
                merged.duplicate_count_value += 1
                continue
            seen_precintos.add(precinto)
            merged.precintos.append(precinto)
        merged.ignored_count += result.ignored_count
        available_slots = MAX_IGNORED_LINE_DETAILS - len(merged.ignored_lines)
        if available_slots > 0:
            merged.ignored_lines.extend(
                IgnoredTxtLine(item.line_number + line_offset, item.original_content, item.reason)
                for item in result.ignored_lines[:available_slots]
            )
        line_offset += result.lines_read
    merged.lines_read = line_offset
    merged.source_path = merged.source_paths[0] if merged.source_paths else None
    merged.source_encoding = ", ".join(encodings)
    return merged


def process_txt_files(paths: list[Path]) -> PrecintosTxtAxResult:
    """Process and unify any number of TXT files in the supplied order."""
    return merge_results([process_txt_file(path) for path in paths])


def render_ax_csv(precintos: list[str]) -> bytes:
    """Render one standard CSV field per row for Dynamics AX imports."""
    output = io.StringIO(newline="")
    writer = csv.writer(
        output,
        delimiter=AX_DELIMITER,
        lineterminator=AX_LINE_ENDING,
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writerows([[precinto] for precinto in precintos])
    return output.getvalue().encode(AX_ENCODING)


def write_ax_csv(path: Path, precintos: list[str]) -> None:
    LOGGER.info("Iniciando escritura de CSV AX: archivo=%s precintos=%s", path, len(precintos))
    with atomic_text_writer(path, encoding=AX_ENCODING) as stream:
        writer = csv.writer(stream, delimiter=AX_DELIMITER, lineterminator=AX_LINE_ENDING, quoting=csv.QUOTE_MINIMAL)
        writer.writerows((value,) for value in precintos)
    LOGGER.info("CSV AX generado: archivo=%s precintos=%s", path, len(precintos))


def csv_filename_from_source(path: Path) -> str:
    stem = _WINDOWS_INVALID_FILENAME.sub("_", path.stem).strip(" .")
    if not stem or stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = "precintos"
    return f"{stem}.csv"


def ensure_csv_extension(path: Path) -> Path:
    return path if path.suffix.lower() == ".csv" else path.with_suffix(".csv")
