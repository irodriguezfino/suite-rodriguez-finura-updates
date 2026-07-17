from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path


AX_ENCODING = "cp1252"
AX_LINE_ENDING = "\r\n"
SOURCE_DELIMITER = "->"
_WINDOWS_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass
class PrecintosTxtAxResult:
    source_path: Path | None = None
    source_encoding: str = ""
    lines_read: int = 0
    precintos: list[str] = field(default_factory=list)
    skipped_lines: int = 0

    @property
    def exported_count(self) -> int:
        return len(self.precintos)

    def summary(self) -> str:
        return (
            f"Líneas leídas: {self.lines_read} | "
            f"Precintos exportados: {self.exported_count} | "
            f"Líneas omitidas: {self.skipped_lines}"
        )


def decode_txt_bytes(content: bytes) -> tuple[str, str]:
    """Decode common source encodings without changing the extracted values."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("txt", content, 0, len(content), "unsupported text encoding")


def extract_precintos(text: str) -> PrecintosTxtAxResult:
    """Extract the value after the first literal ASCII arrow on each valid line."""
    result = PrecintosTxtAxResult(lines_read=len(text.splitlines()))
    for line in text.splitlines():
        if not line.strip():
            result.skipped_lines += 1
            continue
        _left, delimiter, right = line.partition(SOURCE_DELIMITER)
        if not delimiter:
            result.skipped_lines += 1
            continue
        precinto = right.strip()
        if not precinto:
            result.skipped_lines += 1
            continue
        result.precintos.append(precinto)
    return result


def process_txt_file(path: Path) -> PrecintosTxtAxResult:
    content = path.read_bytes()
    text, encoding = decode_txt_bytes(content)
    result = extract_precintos(text)
    result.source_path = path
    result.source_encoding = encoding
    return result


def render_ax_csv(precintos: list[str]) -> bytes:
    """Render one standard CSV field per row for Dynamics AX imports."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator=AX_LINE_ENDING, quoting=csv.QUOTE_MINIMAL)
    writer.writerows([[precinto] for precinto in precintos])
    return output.getvalue().encode(AX_ENCODING)


def write_ax_csv(path: Path, precintos: list[str]) -> None:
    path.write_bytes(render_ax_csv(precintos))


def csv_filename_from_source(path: Path) -> str:
    stem = _WINDOWS_INVALID_FILENAME.sub("_", path.stem).strip(" .")
    if not stem or stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = "precintos"
    return f"{stem}.csv"
