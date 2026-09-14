from __future__ import annotations

from fnmatch import fnmatch
import os
from pathlib import Path
from collections.abc import Callable

from .models import ComparisonOptions, ComparisonResult, Difference
from .binary import ComparisonCancelled


MAX_DIRECTORY_FILES = 20_000


def _files(
    root: Path, exclusions: tuple[str, ...], cancelled: Callable[[], bool] | None = None,
) -> dict[str, Path]:
    result: dict[str, Path] = {}
    pending = [root]
    scanned = 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                scanned += 1
                if cancelled and cancelled():
                    raise ComparisonCancelled()
                if scanned > 250_000:
                    raise ValueError("El recorrido supera el límite de 250.000 entradas.")
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if entry.is_symlink():
                    continue
                is_dir = entry.is_dir(follow_symlinks=False)
                if any(fnmatch(relative, pattern) or is_dir and fnmatch(relative + "/", pattern) for pattern in exclusions):
                    continue
                if is_dir:
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    result[relative] = path
                    if len(result) > MAX_DIRECTORY_FILES:
                        raise ValueError(f"La carpeta supera el límite seguro de {MAX_DIRECTORY_FILES:,} archivos.")
    return result


def compare_folders(
    left: Path,
    right: Path,
    options: ComparisonOptions,
    compare_file: object,
    cancelled: Callable[[], bool] | None = None,
) -> ComparisonResult:
    result = ComparisonResult(str(left), str(right), detected_type="directory", method="comparacion recursiva de carpetas")
    first, second = _files(left, options.exclusions, cancelled), _files(right, options.exclusions, cancelled)
    for name in sorted(first.keys() - second.keys()):
        result.add_difference(Difference("only_left", name), options.max_differences)
    for name in sorted(second.keys() - first.keys()):
        result.add_difference(Difference("only_right", name), options.max_differences)
    equal_files = 0
    semantic_equal_files = 0
    semantic_unknown = False
    binary_changed_files = len(first.keys() ^ second.keys())
    for name in sorted(first.keys() & second.keys()):
        if cancelled and cancelled():
            raise ComparisonCancelled()
        item = compare_file(first[name], second[name], options, cancelled=cancelled)
        if item.metadata.get("cancelled"):
            raise ComparisonCancelled()
        result.errors.extend(f"{name}: {message}" for message in item.errors)
        result.warnings.extend(f"{name}: {message}" for message in item.warnings)
        semantic_unknown = semantic_unknown or item.semantic_equal is None
        semantic_equal_files += int(item.semantic_equal is True)
        if item.strict_equal:
            equal_files += 1
        if item.strict_equal is False:
            binary_changed_files += 1
        chosen_equal = item.strict_equal if options.mode.value == "strict" else item.semantic_equal
        if chosen_equal is False:
            result.add_difference(Difference("modified", name, detail=item.detected_type), options.max_differences)
    result.metadata = {"left_files": len(first), "right_files": len(second), "equal_files": equal_files}
    result.metadata["binary_changed_files"] = binary_changed_files
    result.strict_equal = None if result.errors else binary_changed_files == 0
    result.semantic_equal = (None if result.errors or semantic_unknown else
                             len(first) == len(second) == semantic_equal_files)
    result.metadata["mode"] = options.mode.value
    return result
