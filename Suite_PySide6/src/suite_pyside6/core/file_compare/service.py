from __future__ import annotations

from pathlib import Path
from time import perf_counter

from collections.abc import Callable

from .binary import ComparisonCancelled, compare_binary, sha256_and_size
from .detectors import detect_type
from .folders import compare_folders
from .models import CompareMode, ComparisonOptions, ComparisonResult
from .structured import compare_json, compare_tabular, compare_xml, compare_zip
from .text import compare_text

MAX_STRUCTURED_ANALYSIS_SIZE = 50 * 1024 * 1024
MAX_BINARY_COMPARISON_SIZE = 512 * 1024 * 1024


def compare_paths(
    left_path: str | Path,
    right_path: str | Path,
    options: ComparisonOptions | None = None,
    *,
    cancelled: Callable[[], bool] | None = None,
) -> ComparisonResult:
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
        try:
            result = compare_folders(left, right, options, compare_paths, cancelled)
        except ComparisonCancelled:
            result = ComparisonResult(str(left), str(right), detected_type="directory")
            result.warnings.append("Comparación cancelada por el usuario.")
            result.metadata["cancelled"] = True
        except (OSError, PermissionError, ValueError, RecursionError) as error:
            result = ComparisonResult(str(left), str(right), detected_type="directory")
            result.errors.append(f"No se pudo comparar la carpeta: {error}")
        result.elapsed_seconds = perf_counter() - started
        return result
    if left.is_dir() != right.is_dir():
        result = ComparisonResult(str(left), str(right))
        result.errors.append("No se puede comparar un archivo con una carpeta.")
        result.elapsed_seconds = perf_counter() - started
        return result
    result = ComparisonResult(str(left), str(right))
    result.metadata["mode"] = options.mode.value
    result._cancelled = cancelled
    versions = None
    try:
        versions = (left.stat().st_size, left.stat().st_mtime_ns, right.stat().st_size, right.stat().st_mtime_ns)
        # Refuse inputs that cannot be compared safely in a desktop UI.  This
        # protects memory, long network reads and accidental whole-drive scans.
        if max(left.stat().st_size, right.stat().st_size) > MAX_BINARY_COMPARISON_SIZE:
            result.errors.append(
                "Comparación omitida: un archivo supera el límite seguro de 512 MiB. "
                "Use una herramienta de línea de comandos o compare una copia reducida."
            )
            result.elapsed_seconds = perf_counter() - started
            return result
        result.detected_type = detect_type(left)
        # El hash acelera la respuesta, pero toda igualdad se confirma por lectura binaria.
        compare_binary(left, right, options, result, cancelled)
        strict_differences = result.total_differences
        if result.strict_equal and (options.mode == CompareMode.STRICT or result.detected_type not in {"json", "xml", "csv", "tsv", "zip"}):
            result.semantic_equal = True
            result.elapsed_seconds = perf_counter() - started
            return result
        if result.detected_type == "text":
            # Conserva la igualdad binaria y sustituye el detalle por un diff legible.
            strict_equal = result.strict_equal
            strict_differences = result.total_differences
            result.differences.clear()
            result.total_differences = 0
            result.truncated = False
            compare_text(left, right, options, result, cancelled)
            result.metadata["strict_difference_count"] = strict_differences
            result.strict_equal = strict_equal
        elif options.mode != CompareMode.STRICT and result.detected_type in {"json", "xml", "csv", "tsv", "zip"} and max(result.left_size, result.right_size) <= MAX_STRUCTURED_ANALYSIS_SIZE:
            result.differences.clear()
            result.total_differences = 0
            result.truncated = False
            if result.detected_type == "text":
                compare_text(left, right, options, result, cancelled)
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
    except ComparisonCancelled:
        result.warnings.append("Comparación cancelada por el usuario.")
        result.metadata["cancelled"] = True
    except (OSError, PermissionError, ValueError, RecursionError) as error:
        result.errors.append(f"No se pudo leer el archivo: {error}")
    finally:
        if versions is not None:
            try:
                current = (left.stat().st_size, left.stat().st_mtime_ns, right.stat().st_size, right.stat().st_mtime_ns)
            except OSError:
                current = None
            if current != versions:
                result.errors.append("Un archivo cambió durante la comparación. Repite con copias estables.")
                result.strict_equal = result.semantic_equal = None
    result.elapsed_seconds = perf_counter() - started
    return result
