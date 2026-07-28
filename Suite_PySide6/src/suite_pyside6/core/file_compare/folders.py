from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from .models import ComparisonOptions, ComparisonResult, Difference


def _files(root: Path, exclusions: tuple[str, ...]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if not any(fnmatch(relative, pattern) for pattern in exclusions):
            result[relative] = path
    return result


def compare_folders(left: Path, right: Path, options: ComparisonOptions, compare_file: object) -> ComparisonResult:
    result = ComparisonResult(str(left), str(right), detected_type="directory", method="comparacion recursiva de carpetas")
    first, second = _files(left, options.exclusions), _files(right, options.exclusions)
    for name in first.keys() - second.keys():
        result.add_difference(Difference("only_left", name), options.max_differences)
    for name in second.keys() - first.keys():
        result.add_difference(Difference("only_right", name), options.max_differences)
    equal_files = 0
    for name in first.keys() & second.keys():
        item = compare_file(first[name], second[name], options)
        if item.strict_equal:
            equal_files += 1
        else:
            result.add_difference(Difference("modified", name, detail=item.detected_type), options.max_differences)
    result.metadata = {"left_files": len(first), "right_files": len(second), "equal_files": equal_files}
    result.strict_equal = result.total_differences == 0
    result.semantic_equal = result.strict_equal
    return result
