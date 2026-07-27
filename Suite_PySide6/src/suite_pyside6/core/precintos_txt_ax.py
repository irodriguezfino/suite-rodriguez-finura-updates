from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path


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


@dataclass(frozen=True)
class IgnoredTxtLine:
    """A source line excluded from the AX CSV, with its specific reason."""

    line_number: int
    original_content: str
    reason: str


@dataclass
class PrecintosTxtAxResult:
    source_path: Path | None = None
    source_encoding: str = ""
    lines_read: int = 0
    precintos: list[str] = field(default_factory=list)
    ignored_lines: list[IgnoredTxtLine] = field(default_factory=list)

    @property
    def exported_count(self) -> int:
        return len(self.precintos)

    @property
    def valid_lines(self) -> int:
        """Number of source lines that produced a precinto."""
        return len(self.precintos)

    @property
    def duplicate_count(self) -> int:
        """Repeated precintos, excluding the first occurrence of each one."""
        return len(self.precintos) - len(set(self.precintos))

    @property
    def skipped_lines(self) -> int:
        """Keep the summary count tied to the detailed ignored-line register."""
        return len(self.ignored_lines)

    def summary(self) -> str:
        return (
            f"Líneas leídas: {self.lines_read} | "
            f"Precintos detectados: {self.exported_count} | "
            f"Líneas válidas: {self.valid_lines} | "
            f"Líneas omitidas: {self.skipped_lines} | "
            f"Duplicados: {self.duplicate_count}"
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
    """Extract the value after the first supported arrow on each valid line."""
    result = PrecintosTxtAxResult(lines_read=len(text.splitlines()))
    for line_number, line in enumerate(text.splitlines(), start=1):
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
        precinto = _clean_precinto(raw_precinto)
        if not precinto:
            _record_ignored_line(result, line_number, line, "Precinto vacío")
            continue
        if _has_disallowed_control_characters(precinto):
            _record_ignored_line(result, line_number, line, "Caracteres no permitidos en el precinto")
            continue
        result.precintos.append(precinto)
    return result


def _record_ignored_line(result: PrecintosTxtAxResult, line_number: int, content: str, reason: str) -> None:
    result.ignored_lines.append(IgnoredTxtLine(line_number, content, reason))


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
    content = path.read_bytes()
    text, encoding = decode_txt_bytes(content)
    result = extract_precintos(text)
    result.source_path = path
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
    path.write_bytes(render_ax_csv(precintos))
    LOGGER.info("CSV AX generado: archivo=%s precintos=%s", path, len(precintos))


def csv_filename_from_source(path: Path) -> str:
    stem = _WINDOWS_INVALID_FILENAME.sub("_", path.stem).strip(" .")
    if not stem or stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = "precintos"
    return f"{stem}.csv"


def ensure_csv_extension(path: Path) -> Path:
    return path if path.suffix.lower() == ".csv" else path.with_suffix(".csv")
