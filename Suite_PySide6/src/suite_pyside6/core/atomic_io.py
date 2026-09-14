"""Helpers for recoverable output writes."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from .jobs import checkpoint, begin_commit


def _replace_output(source: Path, destination: Path):
    # Antivirus/indexers can briefly hold the private recovery journal open.
    # Retry only that owned journal, not an arbitrary user destination.
    attempts = (0, .025, .05, .1, .2) if destination.name == 'recovery.json' and destination.parent.name.startswith('pesos-') else (0,)
    for attempt, delay in enumerate(attempts):
        if delay:
            time.sleep(delay)
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == len(attempts)-1:
                raise


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
        begin_commit()
        _replace_output(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def write_text_atomically(path: Path, content: str, *, encoding: str) -> None:
    write_bytes_atomically(Path(path), content.encode(encoding))

from contextlib import contextmanager


@contextmanager
def atomic_text_writer(path: Path, *, encoding: str, newline: str = ""):
    """Streaming text writer with one encoder (also one BOM) per file."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, newline=newline,
                                         delete=False, dir=path.parent, prefix=f".{path.name}.") as stream:
            temporary = Path(stream.name)
            stream.write("")
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        begin_commit()
        _replace_output(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
