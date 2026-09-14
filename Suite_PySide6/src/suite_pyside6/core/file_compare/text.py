from __future__ import annotations

import difflib
from pathlib import Path
from .binary import ComparisonCancelled
from ..jobs import checkpoint
from .detectors import detect_encoding
from .models import ComparisonOptions, ComparisonResult, Difference

MAX_TEXT_ANALYSIS_SIZE = 20 * 1024 * 1024
MAX_UNIFIED_DIFF_CHARS = 2 * 1024 * 1024


def _normalise(line, options):
    if options.ignore_line_endings:
        line = line.replace("\r\n", "\n").replace("\r", "\n")
    if options.ignore_whitespace:
        line = line.strip()
    if options.ignore_case:
        line = line.casefold()
    return line


def aligned_opcodes(left, right, cancelled=None):
    """Exact equality with bounded alignment work; never omit unequal lines."""
    def check():
        checkpoint()
        if cancelled and cancelled():
            raise ComparisonCancelled()
    check()
    if left == right:
        return [("equal", 0, len(left), 0, len(right))], False
    if len(left) * len(right) <= 1_000_000:
        codes = difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes()
        check()
        return codes, False
    # Large/repetitive input uses positional alignment, explicitly disclosed.
    # It can show more changes than a minimal edit script, but loses no lines.
    codes = []
    shared = min(len(left), len(right))
    start, previous = 0, None
    for index in range(shared):
        if index % 512 == 0:
            check()
        tag = "equal" if left[index] == right[index] else "replace"
        if previous is not None and tag != previous:
            codes.append((previous, start, index, start, index))
            start = index
        previous = tag
    if previous is not None:
        codes.append((previous, start, shared, start, shared))
    if len(left) > shared:
        codes.append(("delete", shared, len(left), shared, shared))
    if len(right) > shared:
        codes.append(("insert", shared, shared, shared, len(right)))
    return codes, True


def compare_text(left: Path, right: Path, options: ComparisonOptions,
                 result: ComparisonResult, cancelled=None) -> None:
    if cancelled and cancelled():
        raise ComparisonCancelled()
    if max(left.stat().st_size, right.stat().st_size) > MAX_TEXT_ANALYSIS_SIZE:
        result.warnings.append("Diff de texto omitido: supera 20 MiB; consulte el resultado binario.")
        return
    encodings = detect_encoding(left), detect_encoding(right)
    if not all(encodings):
        result.warnings.append("No se pudo detectar la codificación. Análisis de texto incompleto.")
        return
    try:
        with left.open(encoding=encodings[0], newline="") as stream:
            a = stream.read().splitlines(keepends=True)
        with right.open(encoding=encodings[1], newline="") as stream:
            b = stream.read().splitlines(keepends=True)
    except (OSError, UnicodeError) as exc:
        result.warnings.append(f"No se pudo leer como texto: {exc}")
        return
    codes, positional = aligned_opcodes([_normalise(line, options) for line in a],
                                        [_normalise(line, options) for line in b], cancelled)
    if positional:
        result.warnings.append("Alineación por posición para limitar el coste del diff; puede mostrar más cambios que una alineación mínima.")
    unified = []
    size = 0
    for tag, a0, a1, b0, b1 in codes:
        if cancelled and cancelled():
            raise ComparisonCancelled()
        if tag == "equal":
            continue
        result.add_difference(Difference("text_" + tag,
                              f"lineas izquierda {a0 + 1}-{a1}; derecha {b0 + 1}-{b1}",
                              "".join(a[a0:a1]), "".join(b[b0:b1])), options.max_differences)
        for line in [f"@@ -{a0 + 1},{a1-a0} +{b0 + 1},{b1-b0} @@",
                     *("-" + value for value in a[a0:a1]), *("+" + value for value in b[b0:b1])]:
            size += len(line) + 1
            if size <= MAX_UNIFIED_DIFF_CHARS:
                unified.append(line)
    if size > MAX_UNIFIED_DIFF_CHARS:
        result.warnings.append("Diff unificado truncado a 2 MiB.")
    result.metadata["unified_diff"] = "\n".join(unified)
    if max(len(a), len(b)) <= 12_000 and max(left.stat().st_size, right.stat().st_size) <= 2 * 1024 * 1024:
        result.metadata["_text_preview"] = (a, b, codes)
    result.semantic_equal = result.total_differences == 0
    result.method = "diff de texto con alineación acotada"
