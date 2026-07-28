from __future__ import annotations

import difflib
from pathlib import Path

from .detectors import detect_encoding
from .models import ComparisonOptions, ComparisonResult, Difference

MAX_TEXT_ANALYSIS_SIZE = 20 * 1024 * 1024


def _normalise(line: str, options: ComparisonOptions) -> str:
    if options.ignore_line_endings:
        line = line.replace("\r\n", "\n").replace("\r", "\n")
    if options.ignore_whitespace:
        line = line.strip()
    if options.ignore_case:
        line = line.casefold()
    return line


def compare_text(left: Path, right: Path, options: ComparisonOptions, result: ComparisonResult) -> None:
    if left.stat().st_size > MAX_TEXT_ANALYSIS_SIZE or right.stat().st_size > MAX_TEXT_ANALYSIS_SIZE:
        result.warnings.append("Diff de texto omitido: el archivo supera el limite seguro de 20 MiB; consulte la comparacion binaria.")
        return
    left_encoding, right_encoding = detect_encoding(left), detect_encoding(right)
    if not left_encoding or not right_encoding:
        result.warnings.append("No se pudo detectar con seguridad la codificacion; se uso comparacion binaria.")
        return
    try:
        left_raw = left.read_text(encoding=left_encoding)
        right_raw = right.read_text(encoding=right_encoding)
    except (OSError, UnicodeDecodeError) as error:
        result.warnings.append(f"No se pudo leer como texto ({error}); se uso comparacion binaria.")
        return
    left_lines, right_lines = left_raw.splitlines(keepends=True), right_raw.splitlines(keepends=True)
    left_normalized = [_normalise(line, options) for line in left_lines]
    right_normalized = [_normalise(line, options) for line in right_lines]
    matcher = difflib.SequenceMatcher(None, left_normalized, right_normalized, autojunk=False)
    unified = list(difflib.unified_diff(left_lines, right_lines, fromfile=str(left), tofile=str(right), lineterm=""))
    result.metadata["unified_diff"] = "\n".join(unified)
    for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        location = f"lineas izquierda {a_start + 1}-{a_end}; derecha {b_start + 1}-{b_end}"
        result.add_difference(Difference("text_" + tag, location, "".join(left_lines[a_start:a_end]), "".join(right_lines[b_start:b_end])), options.max_differences)
    if not options.ignore_line_endings and left_raw.replace("\r\n", "\n") == right_raw.replace("\r\n", "\n") and left_raw != right_raw:
        result.warnings.append("La unica diferencia de texto detectada son los finales de linea (LF/CRLF).")
    result.semantic_equal = result.total_differences == 0
    result.method = "diff unificado de texto"
