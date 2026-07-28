from __future__ import annotations

from pathlib import Path
from time import perf_counter

from .binary import compare_binary, sha256_and_size
from .detectors import detect_type
from .folders import compare_folders
from .models import CompareMode, ComparisonOptions, ComparisonResult
from .structured import compare_json, compare_tabular, compare_xml, compare_zip
from .text import compare_text

MAX_STRUCTURED_ANALYSIS_SIZE = 50 * 1024 * 1024


def compare_paths(left_path: str | Path, right_path: str | Path, options: ComparisonOptions | None = None) -> ComparisonResult:
    options = options or ComparisonOptions()
    left, right = Path(left_path), Path(right_path)
    started = perf_counter()
    if not left.exists() or not right.exists():
        result = ComparisonResult(str(left), str(right))
        result.errors.append("Uno o ambos caminos no existen.")
        result.elapsed_seconds = perf_counter() - started
        return result
    if left.resolve() == right.resolve():
        result = ComparisonResult(str(left), str(right), detected_type="directory" if left.is_dir() else detect_type(left), strict_equal=True, semantic_equal=True, method="misma ruta")
        result.warnings.append("Se comparo la misma ruta.")
        result.elapsed_seconds = perf_counter() - started
        return result
    if left.is_dir() and right.is_dir():
        result = compare_folders(left, right, options, compare_paths)
        result.elapsed_seconds = perf_counter() - started
        return result
    if left.is_dir() != right.is_dir():
        result = ComparisonResult(str(left), str(right))
        result.errors.append("No se puede comparar un archivo con una carpeta.")
        result.elapsed_seconds = perf_counter() - started
        return result
    result = ComparisonResult(str(left), str(right))
    try:
        result.left_sha256, result.left_size = sha256_and_size(left, options.block_size)
        result.right_sha256, result.right_size = sha256_and_size(right, options.block_size)
        result.detected_type = detect_type(left)
        # El hash acelera la respuesta, pero toda igualdad se confirma por lectura binaria.
        compare_binary(left, right, options, result)
        strict_differences = result.total_differences
        if result.detected_type == "text":
            # Conserva la igualdad binaria y sustituye el detalle por un diff legible.
            strict_equal = result.strict_equal
            strict_differences = result.total_differences
            result.differences.clear()
            result.total_differences = 0
            result.truncated = False
            compare_text(left, right, options, result)
            result.metadata["strict_difference_count"] = strict_differences
            result.strict_equal = strict_equal
        elif options.mode != CompareMode.STRICT and result.detected_type in {"json", "xml", "csv", "tsv", "zip"} and max(result.left_size, result.right_size) <= MAX_STRUCTURED_ANALYSIS_SIZE:
            result.differences.clear()
            result.total_differences = 0
            result.truncated = False
            if result.detected_type == "text":
                compare_text(left, right, options, result)
            elif result.detected_type == "json":
                compare_json(left, right, options, result)
            elif result.detected_type == "xml":
                compare_xml(left, right, options, result)
            elif result.detected_type in {"csv", "tsv"}:
                compare_tabular(left, right, options, result)
            else:
                compare_zip(left, right, options, result)
            result.metadata["strict_difference_count"] = strict_differences
        elif options.mode != CompareMode.STRICT and result.detected_type in {"json", "xml", "csv", "tsv", "zip"}:
            result.warnings.append("Analisis semantico omitido: el archivo supera el limite seguro de 50 MiB; se conserva el resultado binario.")
            result.semantic_equal = None
        else:
            result.semantic_equal = result.strict_equal
    except (OSError, PermissionError) as error:
        result.errors.append(f"No se pudo leer el archivo: {error}")
    result.elapsed_seconds = perf_counter() - started
    return result
