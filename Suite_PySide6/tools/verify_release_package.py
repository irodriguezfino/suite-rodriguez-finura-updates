from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_UPDATE_ENTRIES = (
    "Suite Rodriguez Finura/Abrir_Suite_Rodriguez_Finura.vbs",
    "Suite Rodriguez Finura/Abrir_Suite_Rodriguez_Finura.cmd",
    "Suite Rodriguez Finura/SuiteUpdater.py",
    "Suite Rodriguez Finura/Menu_principal.py",
    "Suite Rodriguez Finura/version_local.json",
    "Suite Rodriguez Finura/Suite_PySide6/src/suite_pyside6/__init__.py",
    "Suite Rodriguez Finura/runtime/Lib/site-packages/PySide6/QtCore.pyd",
)
REQUIRED_UPDATE_SITE_PACKAGES = (
    "PySide6",
    "shiboken6",
)
FORBIDDEN_UPDATE_SITE_PACKAGES = (
    "numpy",
    "pandas",
)
REQUIRED_FULL_ENTRIES = (
    "Suite Rodriguez Finura/Abrir_Suite_Rodriguez_Finura.vbs",
    "Suite Rodriguez Finura/Abrir_Suite_Rodriguez_Finura.cmd",
    "Suite Rodriguez Finura/SuiteUpdater.py",
    "Suite Rodriguez Finura/runtime/python.exe",
    "Suite Rodriguez Finura/runtime/pythonw.exe",
    "Suite Rodriguez Finura/Menu_principal.py",
    "Suite Rodriguez Finura/version_local.json",
    "Suite Rodriguez Finura/Suite_PySide6/src/suite_pyside6/__init__.py",
)
REQUIRED_FULL_SITE_PACKAGES = (
    "PySide6",
    "shiboken6",
    "openpyxl",
    "pandas",
    "numpy",
    "et_xmlfile",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def has_site_package(names: set[str], package: str) -> bool:
    base = "Suite Rodriguez Finura/runtime/Lib/site-packages/"
    return any(name.startswith(base + package) or name.startswith(base + package + "-") for name in names)


def main() -> int:
    manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8-sig"))
    package = ROOT / manifest["auto_update"]["file"]
    full_package = ROOT / manifest["full_install_package"]
    installer_bat = ROOT / manifest["full_install_bat"]
    assert package.exists(), f"No existe el paquete: {package}"
    assert full_package.exists(), f"No existe el paquete completo: {full_package}"
    assert installer_bat.exists(), f"No existe el instalador BAT: {installer_bat}"
    assert sha256(package) == manifest["auto_update"]["sha256"]
    assert sha256(full_package) == manifest["full_install_package_sha256"]
    assert sha256(installer_bat) == manifest["full_install_bat_sha256"]
    installer_text = installer_bat.read_text(encoding="utf-8-sig")
    assert "Abrir_Suite_Rodriguez_Finura.cmd" not in installer_text
    assert "runtime\\pythonw.exe" in installer_text
    assert "Abrir_Suite_Rodriguez_Finura.vbs" not in installer_text

    with ZipFile(package) as archive:
        names = set(archive.namelist())
        for entry in REQUIRED_UPDATE_ENTRIES:
            assert entry in names, f"Falta entrada en ZIP: {entry}"
        for package_name in REQUIRED_UPDATE_SITE_PACKAGES:
            assert has_site_package(names, package_name), f"Falta dependencia runtime: {package_name}"
        for package_name in FORBIDDEN_UPDATE_SITE_PACKAGES:
            assert not has_site_package(names, package_name), f"El incremental no debe incluir: {package_name}"

        local_version = json.loads(archive.read("Suite Rodriguez Finura/version_local.json").decode("utf-8-sig"))
        assert local_version["version"] == manifest["version"]
        pyproject = archive.read("Suite Rodriguez Finura/Suite_PySide6/pyproject.toml").decode("utf-8")
        assert f'version = "{manifest["version"]}"' in pyproject
        launcher = archive.read("Suite Rodriguez Finura/Abrir_Suite_Rodriguez_Finura.vbs").decode("utf-8-sig")
        assert "pythonw.exe" in launcher and "SuiteLauncher.py" in launcher
        updater = archive.read("Suite Rodriguez Finura/SuiteUpdater.py").decode("utf-8-sig")
        assert updater.count("CREATE_NO_WINDOW") >= 3

    with ZipFile(full_package) as archive:
        names = set(archive.namelist())
        for entry in REQUIRED_FULL_ENTRIES:
            assert entry in names, f"Falta entrada en ZIP completo: {entry}"
        for package_name in REQUIRED_FULL_SITE_PACKAGES:
            assert has_site_package(names, package_name), f"Falta dependencia completa: {package_name}"
        local_version = json.loads(archive.read("Suite Rodriguez Finura/version_local.json").decode("utf-8-sig"))
        assert local_version["version"] == manifest["version"]
        launcher = archive.read("Suite Rodriguez Finura/Abrir_Suite_Rodriguez_Finura.vbs").decode("utf-8-sig")
        assert "pythonw.exe" in launcher and "SuiteLauncher.py" in launcher

    print("RELEASE_PACKAGE_OK")
    print(f"version={manifest['version']}")
    print(f"package={package.name}")
    print(f"full_package={full_package.name}")
    print(f"installer_bat={installer_bat.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
