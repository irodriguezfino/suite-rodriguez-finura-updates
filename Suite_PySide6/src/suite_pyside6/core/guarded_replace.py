"""Windows replacement retains the actual predecessor, including late edits.

The journal owns the backup name before replacement. This is recoverable
conflict detection, not a cross-file or distributed transaction.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import ctypes
from ctypes import wintypes as w
import os
import shutil
import tempfile

_backup = ContextVar('replacement_backup', default=None)


@contextmanager
def preserve_predecessor(path):
    token = _backup.set(path)
    try:
        yield
    finally:
        _backup.reset(token)


def guarded_replace(source: Path, destination: Path) -> bool:
    backup = _backup.get()
    if backup is None:
        return False
    if os.name != 'nt':
        raise OSError('El guardado recuperable con detección de conflictos requiere Windows.')
    if backup.exists():
        raise FileExistsError('La copia del reemplazo ya existe; requiere recuperación.')
    staged = None
    replacement = source
    # ReplaceFile requires all three names on the same volume.
    if source.stat().st_dev != destination.parent.stat().st_dev:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.suite-stage-', delete=False) as handle:
            staged = Path(handle.name)
        shutil.copy2(source, staged)
        replacement = staged
    try:
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.ReplaceFileW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.DWORD, w.LPVOID, w.LPVOID]
        api.ReplaceFileW.restype = w.BOOL
        if not api.ReplaceFileW(str(destination.resolve()), str(replacement.resolve()), str(backup.resolve()), 0, None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        if staged is not None:
            source.unlink(missing_ok=True)
        return True
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
