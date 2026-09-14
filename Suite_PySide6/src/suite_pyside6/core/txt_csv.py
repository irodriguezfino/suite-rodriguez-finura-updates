from __future__ import annotations

from .jobs import checkpoint, checked, report_progress, begin_commit

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from .atomic_io import write_text_atomically, atomic_text_writer


@dataclass
class TxtCsvResult:
    selected_files: list[Path] = field(default_factory=list)
    processed_lines: list[str] = field(default_factory=list)
    error_count: int = 0
    error_files: list[str] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        text = f"Proceso completado: {len(self.processed_lines)} linea(s)"
        if self.error_count:
            files = ", ".join(self.error_files[:3])
            text += f" | {self.error_count} incidencia(s) en {len(self.error_files)} archivo(s): {files}"
        return text

    def preview_text(self, limit: int = 100) -> str:
        if not self.processed_lines:
            return "No hay datos validos para mostrar."
        preview = "\n".join(self.processed_lines[:limit])
        if self.issues:
            preview += "\n\nIncidencias (no incluidas en la salida):\n" + "\n".join(
                f"{item['path']}:{item['line'] or '-'} · {item['reason']}" for item in self.issues[:limit])
        return preview


def format_decimal_2(value: str) -> str:
    text = str(value).strip()
    if text == "":
        return text
    text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return value
    return f"{number:.2f}".replace(".", ",")


def process_line(text: str) -> str:
    try:
        columns = next(csv.reader([text], delimiter=";", quotechar='"'))
    except csv.Error:
        columns = text.split(";")

    if not columns:
        return text

    if len(columns) >= 2 and columns[-1].strip() == "":
        columns[-2] = format_decimal_2(columns[-2])
    else:
        columns[-1] = format_decimal_2(columns[-1])

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quotechar='"', lineterminator="")
    writer.writerow(columns)
    return output.getvalue()


def process_txt_files(paths: list[Path]) -> TxtCsvResult:
    result = TxtCsvResult(selected_files=list(paths))
    seen_error_files: set[str] = set()

    for path in checked(paths, phase="Leyendo archivos", total=len(paths), unit="archivos"):
        try:
            with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
                for line_number, raw_line in enumerate(checked(handle, phase='Leyendo TXT', unit='líneas'), 1):
                    text = raw_line.rstrip("\n\r")
                    if not text.strip():
                        continue
                    if text.strip().replace(";", "") == "":
                        continue
                    if "\ufffd" in text:
                        result.error_count += 1
                        if len(result.issues) < 10_000:
                            result.issues.append(dict(path=str(path), line=line_number, reason="Codificación no válida"))
                        if str(path) not in seen_error_files:
                            result.error_files.append(path.name)
                            seen_error_files.add(str(path))
                        continue
                    result.processed_lines.append(process_line(text))
        except Exception as exc:
            result.error_count += 1
            if len(result.issues) < 10_000:
                result.issues.append(dict(path=str(path), line=None, reason=type(exc).__name__))
            if str(path) not in seen_error_files:
                result.error_files.append(path.name)
                seen_error_files.add(str(path))

    return result


def write_txt_csv(path: Path, lines: list[str]) -> None:
    with atomic_text_writer(path, encoding="utf-8") as stream:
        stream.writelines(line + "\n" for line in lines)

