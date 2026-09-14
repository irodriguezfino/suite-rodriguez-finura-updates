"""Recoverable multi-file replacement. Never silently overwrite a conflict."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from .atomic_io import write_text_atomically
from .guarded_replace import preserve_predecessor
from .jobs import checkpoint, begin_commit


def recovery_root() -> Path:
    override = os.environ.get('SUITE_RECOVERY_DIR')
    if override:
        return Path(override) / 'suite-recovery'
    base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
    return Path(base) / 'RodriguezFinura' / 'Suite' / 'recovery'


def pending_recoveries() -> list[Path]:
    root = recovery_root()
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob('pesos-*/recovery.json')
                  if not path.is_symlink() and not path.parent.is_symlink())


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class RecoverableBatch:
    def __init__(self, paths: list[Path], versions: dict[Path, tuple[int, int]]):
        root = recovery_root()
        root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix='pesos-', dir=root))
        self.entries = []
        self.completed = False
        self.manifest = self.directory / 'recovery.json'
        try:
            for index, path in enumerate(paths):
                checkpoint()
                backup = self.directory / f'{index}.original'
                before = path.stat()
                if (before.st_size, before.st_mtime_ns) != versions[path]:
                    raise ValueError(f'El original cambió antes del guardado: {path.name}')
                shutil.copy2(path, backup)
                digest = file_digest(backup)
                if file_digest(path) != digest:
                    raise ValueError(f'El original cambió durante la copia de seguridad: {path.name}')
                self.entries.append(dict(path=str(path.resolve()), backup=backup.name,
                                         predecessor=f'.suite-{self.directory.name}-{index}.previous',
                                         original=digest, prepared=None, state='ready'))
            begin_commit()
            self.save()
        except BaseException:
            # Nothing has been replaced. Remove only files owned by this batch.
            self.cleanup()
            raise

    def save(self):
        write_text_atomically(self.manifest, json.dumps({'version': 1, 'completed': self.completed, 'entries': self.entries}, ensure_ascii=False), encoding='utf-8')

    def complete(self):
        self.completed = True
        self.save()

    @classmethod
    def load(cls, manifest: Path):
        """Read only a bounded, validated journal inside our recovery directory."""
        import re
        manifest = manifest.resolve()
        root = recovery_root().resolve()
        if manifest.parent.parent != root or not manifest.parent.name.startswith('pesos-') or manifest.name != 'recovery.json':
            raise ValueError('El diario no pertenece a la carpeta de recuperación de la suite')
        if manifest.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('El diario supera el tamaño permitido')
        payload = json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(payload, dict) or payload.get('version') != 1 or not isinstance(payload.get('entries'), list):
            raise ValueError('Formato de diario no válido')
        for index, entry in enumerate(payload['entries']):
            if not isinstance(entry, dict):
                raise ValueError('Entrada de diario no válida')
            path = Path(entry.get('path', ''))
            if not path.is_absolute() or path.suffix.lower() not in ('.xls', '.xlsx', '.xlsm'):
                raise ValueError('Destino de recuperación no válido')
            if entry.get('backup') != f'{index}.original' or not re.fullmatch('[0-9a-f]{64}', entry.get('original', '')):
                raise ValueError('Copia de recuperación no válida')
            if entry.get('state') not in ('ready', 'replacing', 'written', 'restored'):
                raise ValueError('Estado del diario no válido')
            if entry.get('prepared') is not None and not re.fullmatch('[0-9a-f]{64}', entry['prepared']):
                raise ValueError('Huella de salida no válida')
            if 'predecessor' in entry and entry['predecessor'] != f'.suite-{manifest.parent.name}-{index}.previous':
                raise ValueError('Nombre de copia del reemplazo no válido')
        batch = cls.__new__(cls)
        batch.directory, batch.manifest, batch.entries = manifest.parent, manifest, payload['entries']
        batch.completed = payload.get('completed') is True
        return batch

    def commit(self, index, prepared, replace_file):
        entry = self.entries[index]
        path = Path(entry['path'])
        if file_digest(path) != entry['original']:
            raise ValueError(f'Conflicto: otro programa modificó {path.name}. No se sobrescribió.')
        entry['prepared'] = file_digest(prepared)
        entry['state'] = 'replacing'
        self.save()
        predecessor = path.parent / entry['predecessor'] if 'predecessor' in entry else None
        with preserve_predecessor(predecessor):
            replace_file(prepared, path)
        if predecessor is not None and predecessor.exists() and file_digest(predecessor) != entry['original']:
            raise ValueError(f'Conflicto de guardado en {path.name}; se conserva la versión externa para restaurarla.')
        if file_digest(path) != entry['prepared']:
            raise ValueError(f'No se pudo verificar el contenido guardado: {path.name}')
        entry['state'] = 'written'
        self.save()

    def rollback(self, replace_file) -> list[str]:
        if self.completed:
            return []
        errors = []
        for entry in reversed(self.entries):
            if entry['state'] not in ('written', 'replacing'):
                continue
            path = Path(entry['path'])
            try:
                predecessor = path.parent / entry['predecessor'] if 'predecessor' in entry else None
                backup = predecessor if predecessor is not None and predecessor.exists() else self.directory / entry['backup']
                restore_digest = file_digest(backup)
                current = file_digest(path)
                if current == restore_digest:
                    entry['state'] = 'restored'
                    continue
                if current != entry['prepared']:
                    raise ValueError('El archivo cambió externamente; se conserva para revisión manual')
                if backup.parent == self.directory and restore_digest != entry['original']:
                    raise ValueError('La copia de recuperación no supera la verificación')
                working = self.directory / (entry['backup'] + '.restore')
                shutil.copy2(backup, working)
                undo_predecessor = path.parent / (entry['predecessor'] + '.undo') if predecessor is not None else None
                with preserve_predecessor(undo_predecessor):
                    replace_file(working, path)
                if undo_predecessor is not None and undo_predecessor.exists() and file_digest(undo_predecessor) != current:
                    raise ValueError('Conflicto durante la restauración; se conservan ambas versiones y el diario')
                if file_digest(path) != restore_digest:
                    raise ValueError('No se pudo verificar la restauración')
                entry['state'] = 'restored'
                self.save()
            except Exception as exc:
                errors.append(f'{path.name}: {exc}')
        self.save()
        return errors

    def cleanup(self):
        # This directory is created exclusively by this instance, never user-selected.
        import re
        for entry in self.entries:
            if 'predecessor' in entry:
                predecessor = Path(entry['path']).parent / entry['predecessor']
                predecessor.unlink(missing_ok=True)
                Path(str(predecessor) + '.undo').unlink(missing_ok=True)
        for child in self.directory.iterdir():
            if child.is_file() and (child.name == 'recovery.json' or re.fullmatch(r'\d+\.original(?:\.restore)?', child.name)):
                child.unlink()
        self.directory.rmdir()
