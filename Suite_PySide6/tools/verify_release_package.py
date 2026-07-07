from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ENTRIES = (
    "Suite Rodriguez Finura/Menu_principal.py",
    "Suite Rodriguez Finura/version_local.json",
    "Suite Rodriguez Finura/Suite_PySide6/src/suite_pyside6/__init__.py",
    "Suite Rodriguez Finura/runtime/Lib/site-packages/PySide6/QtCore.pyd",
)
REQUIRED_SITE_PACKAGES = (
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
    assert package.exists(), f"No existe el paquete: {package}"
    assert sha256(package) == manifest["auto_update"]["sha256"]

    with ZipFile(package) as archive:
        names = set(archive.namelist())
        for entry in REQUIRED_ENTRIES:
            assert entry in names, f"Falta entrada en ZIP: {entry}"
        for package_name in REQUIRED_SITE_PACKAGES:
            assert has_site_package(names, package_name), f"Falta dependencia runtime: {package_name}"

        local_version = json.loads(archive.read("Suite Rodriguez Finura/version_local.json").decode("utf-8-sig"))
        assert local_version["version"] == manifest["version"]
        pyproject = archive.read("Suite Rodriguez Finura/Suite_PySide6/pyproject.toml").decode("utf-8")
        assert f'version = "{manifest["version"]}"' in pyproject

    print("RELEASE_PACKAGE_OK")
    print(f"version={manifest['version']}")
    print(f"package={package.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
