from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


VERSION = "1.5.3"
PACKAGE_NAME = f"Suite_Rodriguez_Finura_v{VERSION}_update.zip"
ROOT = Path(__file__).resolve().parents[2]
PYSIDE_ROOT = ROOT / "Suite_PySide6"
LEGACY_APP = ROOT / "outputs" / "suite_1_4_21_work" / "Suite Rodriguez Finura"
LEGACY_RESOURCES = ROOT / "outputs" / "worktree_1_4_27" / "build_1_4_43"
QT_ENV = ROOT / "qtv"
RELEASE_ROOT = ROOT / "outputs" / f"release_{VERSION}"
STAGING = RELEASE_ROOT / "Suite Rodriguez Finura"
REMOTE_BASE = "https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/refs/heads/main"


PYSIDE_FILES = [
    "__init__.py",
    "_config.py",
    "_git_pyside_version.py",
    "py.typed",
    "pyside6.abi3.dll",
    "QtCore.pyd",
    "QtGui.pyd",
    "QtWidgets.pyd",
    "QtPrintSupport.pyd",
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "Qt6Network.dll",
    "Qt6PrintSupport.dll",
    "opengl32sw.dll",
    "d3dcompiler_47.dll",
    "dxcompiler.dll",
    "dxil.dll",
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_codecvt_ids.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
]


def copytree_clean(source: Path, destination: Path) -> None:
    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.egg-info",
        ".pytest_cache",
        ".ruff_cache",
    )
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def remove_tree(path: Path) -> None:
    def on_error(func, failed_path, _exc_info):
        os.chmod(failed_path, 0o700)
        func(failed_path)

    shutil.rmtree(path, onerror=on_error)


def prepare_staging() -> None:
    if RELEASE_ROOT.exists():
        remove_tree(RELEASE_ROOT)
    STAGING.mkdir(parents=True)

    copytree_clean(PYSIDE_ROOT, STAGING / "Suite_PySide6")
    for name in ("SuiteLauncher.py", "SuiteUpdater.py", "Abrir_Suite_Rodriguez_Finura.cmd"):
        shutil.copy2(LEGACY_APP / name, STAGING / name)
    for name in (
        "RODRIGUEZ.png",
        "FINURA.png",
        "RODRIGUEZ_logo.bmp",
        "FINURA_logo.bmp",
        "ICONO_SUITE.ico",
        "ICONO_SUITE.png",
        "config_articulos.csv",
    ):
        shutil.copy2(LEGACY_RESOURCES / name, STAGING / name)

    write_text(
        STAGING / "Menu_principal.py",
        """from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
SRC = APP_DIR / "Suite_PySide6" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from suite_pyside6.main import main


if __name__ == "__main__":
    raise SystemExit(main())
""",
    )
    write_text(STAGING / "version_local.json", json.dumps({"version": VERSION}, indent=2) + "\n")
    write_text(
        STAGING / "update_config.json",
        json.dumps({"version_url": f"{REMOTE_BASE}/version.json"}, indent=2) + "\n",
    )

    site_packages = STAGING / "runtime" / "Lib" / "site-packages"
    pyside_src = QT_ENV / "Lib" / "site-packages" / "PySide6"
    pyside_dst = site_packages / "PySide6"
    pyside_dst.mkdir(parents=True)
    for name in PYSIDE_FILES:
        source = pyside_src / name
        if source.exists():
            shutil.copy2(source, pyside_dst / name)
    shutil.copytree(pyside_src / "plugins", pyside_dst / "plugins", dirs_exist_ok=True)
    for name in (
        "shiboken6",
        "shiboken6-6.11.1.dist-info",
        "pyside6-6.11.1.dist-info",
        "pyside6_essentials-6.11.1.dist-info",
    ):
        copytree_clean(QT_ENV / "Lib" / "site-packages" / name, site_packages / name)


def build_zip() -> Path:
    package = ROOT / PACKAGE_NAME
    if package.exists():
        package.unlink()
    with ZipFile(package, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in STAGING.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(RELEASE_ROOT).as_posix())
    return package


def update_manifest(package: Path) -> None:
    digest = sha256(package)
    notes = (
        "- Nueva aplicacion Pesos para renombrar la primera hoja visible de varios Excel a Hoja1.\n"
        "- Area de trabajo Pesos integrada en el panel principal con acceso Alt+9.\n"
        "- El actualizador automatico cierra la suite antes de copiar archivos PySide6 bloqueados.\n"
        "- Reintentos de copia ante bloqueos temporales de DLLs durante la actualizacion."
    )
    manifest = {
        "schema": "suite-rodriguez-finura-update-v1",
        "version": VERSION,
        "published_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "auto_update": {
            "type": "zip",
            "file": PACKAGE_NAME,
            "url": f"{REMOTE_BASE}/{PACKAGE_NAME}",
            "sha256": digest,
        },
        "fresh_install": {
            "type": "msi",
            "file": "Suite_Rodriguez_Finura_v1.3.33.msi",
            "url": f"{REMOTE_BASE}/Suite_Rodriguez_Finura_v1.3.33.msi",
            "sha256": "A4ABB193DB0CC17F5481B062D70B714038969B54D6F30957B33792091F8D0518",
        },
        "notes": notes,
        "package_type": "zip",
        "package": PACKAGE_NAME,
        "package_url": f"{REMOTE_BASE}/{PACKAGE_NAME}",
        "sha256": digest,
        "fresh_install_msi": "Suite_Rodriguez_Finura_v1.3.33.msi",
        "fresh_install_url": f"{REMOTE_BASE}/Suite_Rodriguez_Finura_v1.3.33.msi",
        "fresh_install_sha256": "A4ABB193DB0CC17F5481B062D70B714038969B54D6F30957B33792091F8D0518",
    }
    write_text(ROOT / "version.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    write_text(ROOT / f"CHANGELOG_v{VERSION}.txt", f"Suite Rodriguez Finura v{VERSION}\n\n{notes}\n")


def main() -> int:
    prepare_staging()
    package = build_zip()
    update_manifest(package)
    size_mb = package.stat().st_size / 1024 / 1024
    print(f"PACKAGE={package}")
    print(f"SIZE_MB={size_mb:.2f}")
    print(f"SHA256={sha256(package)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
