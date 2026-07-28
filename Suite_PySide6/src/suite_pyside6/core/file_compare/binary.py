from __future__ import annotations

import hashlib
from pathlib import Path

from .models import ComparisonOptions, ComparisonResult, Difference


def sha256_and_size(path: Path, block_size: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(block_size):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def _window(data: bytes, index: int, width: int = 12) -> str:
    start = max(0, index - width // 2)
    end = min(len(data), index + width // 2)
    return data[start:end].hex(" ")


def compare_binary(left: Path, right: Path, options: ComparisonOptions, result: ComparisonResult) -> None:
    """Comparacion exacta por bloques; nunca carga el archivo completo."""
    offset = 0
    changed_ranges: list[tuple[int, int]] = []
    active_start: int | None = None
    previous_changed = -2
    with left.open("rb") as left_stream, right.open("rb") as right_stream:
        while True:
            left_chunk = left_stream.read(options.block_size)
            right_chunk = right_stream.read(options.block_size)
            if not left_chunk and not right_chunk:
                break
            length = max(len(left_chunk), len(right_chunk))
            for index in range(length):
                a = left_chunk[index] if index < len(left_chunk) else None
                b = right_chunk[index] if index < len(right_chunk) else None
                if a == b:
                    if active_start is not None:
                        changed_ranges.append((active_start, offset + index - 1))
                        active_start = None
                    continue
                position = offset + index
                if active_start is None:
                    active_start = position
                previous_changed = position
                result.add_difference(
                    Difference(
                        kind="byte",
                        location=f"offset {position} (0x{position:X})",
                        left=None if a is None else f"0x{a:02X}",
                        right=None if b is None else f"0x{b:02X}",
                        detail=f"izquierda: {_window(left_chunk, min(index, max(0, len(left_chunk)-1)))} | derecha: {_window(right_chunk, min(index, max(0, len(right_chunk)-1)))}",
                    ),
                    options.max_differences,
                )
            if active_start is not None:
                changed_ranges.append((active_start, offset + length - 1))
                active_start = None
            offset += length
    result.metadata["changed_ranges"] = [f"{start}-{end}" for start, end in changed_ranges[:options.max_differences]]
    result.strict_equal = result.total_differences == 0
    result.method = "SHA-256 y comparacion binaria por bloques"
