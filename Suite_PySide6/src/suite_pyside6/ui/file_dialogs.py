from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from suite_pyside6.ui.session import dialog_start_path, remember_export, remember_paths


def open_files(parent: QWidget, key: str, title: str, file_filter: str) -> list[Path]:
    files, _selected_filter = QFileDialog.getOpenFileNames(
        parent,
        title,
        dialog_start_path(key),
        file_filter,
    )
    paths = [Path(file) for file in files]
    remember_paths(key, paths)
    return paths


def open_file(parent: QWidget, key: str, title: str, file_filter: str) -> Path | None:
    file, _selected_filter = QFileDialog.getOpenFileName(
        parent,
        title,
        dialog_start_path(key),
        file_filter,
    )
    if not file:
        return None
    path = Path(file)
    remember_paths(key, [path])
    return path


def save_file(parent: QWidget, key: str, title: str, default_name: str, file_filter: str) -> Path | None:
    file, _selected_filter = QFileDialog.getSaveFileName(
        parent,
        title,
        dialog_start_path(key, default_name),
        file_filter,
    )
    if not file:
        return None
    path = Path(file)
    remember_export(key, path)
    return path


def choose_directory(parent: QWidget, key: str, title: str) -> Path | None:
    folder = QFileDialog.getExistingDirectory(parent, title, dialog_start_path(key))
    if not folder:
        return None
    path = Path(folder)
    remember_paths(key, [path])
    return path
