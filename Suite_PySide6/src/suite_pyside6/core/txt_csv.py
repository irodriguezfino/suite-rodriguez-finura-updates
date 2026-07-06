from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TxtCsvResult:
    selected_files: list[Path] = field(default_factory=list)
    processed_lines: list[str] = field(default_factory=list)
    error_count: int = 0
    error_files: list[str] = field(default_factory=list)

    def summary(self) -> str:
        text = f"Proceso completado: {len(self.processed_lines)} linea(s)"
        if self.error_count:
            files = ", ".join(self.error_files[:3])
            text += f" | Errores en {self.error_count} archivo(s): {files}"
        return text

    def preview_text(self, limit: int = 100) -> str:
        if not self.processed_lines:
            return "No hay datos validos para mostrar."
        return "\n".join(self.processed_lines[:limit])


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

    for path in paths:
        try:
            with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
                for raw_line in handle:
                    text = raw_line.rstrip("\n\r")
                    if not text.strip():
                        continue
                    if text.strip().replace(";", "") == "":
                        continue
                    if "\ufffd" in text:
                        result.error_count += 1
                        if path.name not in seen_error_files:
                            result.error_files.append(path.name)
                            seen_error_files.add(path.name)
                        continue
                    result.processed_lines.append(process_line(text))
        except Exception:
            result.error_count += 1
            if path.name not in seen_error_files:
                result.error_files.append(path.name)
                seen_error_files.add(path.name)

    return result


def write_txt_csv(path: Path, lines: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for line in lines:
            handle.write(line + "\n")

