from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


VALID_PREFIXES = ("00",)


@dataclass
class CodeIssue:
    file: str
    line: int
    original: str
    cleaned: str


@dataclass
class PaletsResult:
    selected_files: list[Path] = field(default_factory=list)
    valid_base: list[str] = field(default_factory=list)
    detected: list[str] = field(default_factory=list)
    issues: list[CodeIssue] = field(default_factory=list)
    final_palets: list[str] = field(default_factory=list)
    pending_correction: bool = False

    @property
    def duplicate_count(self) -> int:
        return max(0, len(self.detected) - len(self.final_palets))

    def summary(self) -> str:
        if self.pending_correction:
            return (
                f"Pendiente de correccion: {len(self.issues)} codigo(s) | "
                f"Validos automaticos: {len(self.valid_base)}"
            )
        if not self.selected_files:
            return "Sin archivos cargados"
        return (
            f"Proceso completado: {len(self.final_palets)} registro(s) CSV | "
            f"{len(self.detected)} lectura(s) validada(s) | "
            f"{self.duplicate_count} duplicado(s) eliminado(s)"
        )

    def preview_text(self) -> str:
        if self.pending_correction:
            lines = [
                "Se han encontrado lecturas que requieren revision.",
                "",
                f"Lecturas validas automaticas: {len(self.valid_base)}",
                f"Incidencias pendientes: {len(self.issues)}",
                "",
                "Vista previa de lecturas validas automaticas:",
            ]
            lines.extend(code[2:] for code in self.valid_base[:500])
            return "\n".join(lines).rstrip()
        if not self.final_palets:
            return "No se han encontrado lecturas validas de palets."
        return (
            "CSV final preparado\n"
            f"Duplicados eliminados: {self.duplicate_count}\n\n"
            "Vista previa CSV final:\n"
            + "\n".join(self.final_palets)
        )

    def correction_text(self) -> str:
        if not self.pending_correction:
            return "No hay registros pendientes de revision. Puedes guardar el CSV."
        lines = [
            "Corrige solo estos codigos no validos.",
            "Debe quedar una lectura por linea, con 20 digitos y empezando por 00.",
            "Las lineas que empiezan por # son informativas y se ignoran.",
            "",
        ]
        for issue in self.issues:
            lines.append(f"# Archivo: {issue.file} | Linea: {issue.line}")
            lines.append(f"# Original: {issue.original}")
            lines.append(issue.cleaned)
            lines.append("")
        return "\n".join(lines).rstrip()


def normalize_line(line: str) -> str:
    return re.sub(r"\D+", "", line)


def is_valid_code(code: str, prefixes: Sequence[str] = VALID_PREFIXES) -> bool:
    return len(code) == 20 and code.isdigit() and any(code.startswith(prefix) for prefix in prefixes)


def validate_txt_lines(paths: Iterable[Path], prefixes: Sequence[str] = VALID_PREFIXES) -> tuple[list[str], list[CodeIssue]]:
    valid: list[str] = []
    issues: list[CodeIssue] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                original = line.strip()
                if not original:
                    continue
                cleaned = normalize_line(original)
                if "\ufffd" in original or not is_valid_code(cleaned, prefixes):
                    issues.append(CodeIssue(path.name, line_number, original, cleaned))
                else:
                    valid.append(cleaned)
    return valid, issues


def validate_corrected_codes(text: str, prefixes: Sequence[str] = VALID_PREFIXES) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    for line in text.splitlines():
        original = line.strip()
        if not original or original.startswith("#"):
            continue
        cleaned = normalize_line(original)
        if len(cleaned) < 10:
            continue
        if is_valid_code(cleaned, prefixes):
            valid.append(cleaned)
        else:
            invalid.append(original)
    return valid, invalid


def validate_final_palets_text(text: str, prefixes: Sequence[str] = VALID_PREFIXES) -> tuple[list[str], list[str]]:
    palets: list[str] = []
    invalid: list[str] = []
    for line in text.splitlines():
        original = line.strip()
        if not original or original.startswith("#"):
            continue
        cleaned = normalize_line(original)
        if len(cleaned) < 10:
            continue
        if len(cleaned) == 18 and cleaned.isdigit():
            palets.append(cleaned)
        elif is_valid_code(cleaned, prefixes):
            palets.append(cleaned[2:])
        else:
            invalid.append(original)
    return dedupe_final_palets(palets), invalid


def clean_and_dedupe(readings_20: Iterable[str]) -> list[str]:
    return dedupe_final_palets(reading[2:] for reading in readings_20)


def dedupe_final_palets(palets: Iterable[str]) -> list[str]:
    reversed_result: list[str] = []
    seen_keys: set[str] = set()
    for pallet in reversed(list(palets)):
        key = pallet[-10:]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        reversed_result.append(pallet)
    return list(reversed(reversed_result))


def process_palets_files(paths: list[Path]) -> PaletsResult:
    valid, issues = validate_txt_lines(paths)
    result = PaletsResult(selected_files=list(paths), valid_base=valid, issues=issues)
    if issues:
        result.pending_correction = True
        return result
    result.detected = valid
    result.final_palets = clean_and_dedupe(valid)
    return result


def integrate_corrections(base_valid: list[str], issues: list[CodeIssue], correction_text: str) -> tuple[PaletsResult, list[str]]:
    corrected, invalid = validate_corrected_codes(correction_text)
    result = PaletsResult(valid_base=list(base_valid), issues=list(issues))
    if invalid:
        result.pending_correction = True
        return result, invalid
    result.detected = list(base_valid) + corrected
    result.final_palets = clean_and_dedupe(result.detected)
    return result, []


def write_palets_csv(path: Path, palets: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        for pallet in palets:
            writer.writerow([pallet])

