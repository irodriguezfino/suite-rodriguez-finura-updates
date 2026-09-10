"""Helpers for recoverable output writes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_bytes_atomically(path: Path, content: bytes) -> None:
    """Replace a destination only after a complete sibling temporary write."""
    path = Path(path)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f".{path.name}.") as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def write_text_atomically(path: Path, content: str, *, encoding: str) -> None:
    write_bytes_atomically(Path(path), content.encode(encoding))
