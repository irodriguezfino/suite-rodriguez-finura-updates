"""Bounded decoding with fallback chosen before any records are yielded."""
from pathlib import Path
import re
from .jobs import checkpoint, checked


def iter_text_lines(path):
    path = Path(path)
    before = path.stat()
    encoding = 'latin-1'
    for candidate in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            with path.open(encoding=candidate) as stream:
                while stream.read(65536):
                    checkpoint()
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('El archivo cambió mientras se leía; vuelve a seleccionarlo.')
    with path.open(encoding=encoding) as stream:
        tail = ''
        count = 0
        while chunk := stream.read(65536):
            # TextIOWrapper already normalizes CR/LF, including boundaries.
            # Preserve str.splitlines' other separators used by old readers.
            parts = re.split(r'[\n\v\f\x1c-\x1e\x85\u2028\u2029]', tail + chunk)
            tail = parts.pop()
            yield from checked(parts, phase='Leyendo texto', unit='líneas', start=count)
            count += len(parts)
        if tail:
            checkpoint()
            yield tail
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('El archivo cambió mientras se leía; vuelve a seleccionarlo.')
