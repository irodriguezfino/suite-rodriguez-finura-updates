from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


VERSION = "1.7.4"
PACKAGE_NAME = f"Suite_Rodriguez_Finura_v{VERSION}_update.zip"
FULL_PACKAGE_NAME = f"Suite_Rodriguez_Finura_v{VERSION}_full.zip"
INSTALLER_BAT_NAME = f"Instalar_Suite_Rodriguez_Finura_v{VERSION}.bat"
SILENT_LAUNCHER_NAME = "Abrir_Suite_Rodriguez_Finura.vbs"
LEGACY_CMD_LAUNCHER_NAME = "Abrir_Suite_Rodriguez_Finura.cmd"
ROOT = Path(__file__).resolve().parents[2]
PYSIDE_ROOT = ROOT / "Suite_PySide6"
LEGACY_APP = ROOT / "outputs" / "suite_1_4_21_work" / "Suite Rodriguez Finura"
LEGACY_RESOURCES = ROOT / "outputs" / "worktree_1_4_27" / "build_1_4_43"
BASE_FULL_APP = ROOT / "audit_extract" / "_msi_admin_test_1_3_33" / "Suite Rodriguez Finura"
QT_ENV = ROOT / "qtv"
RELEASE_ROOT = ROOT / "outputs" / f"release_{VERSION}"
STAGING = RELEASE_ROOT / "Suite Rodriguez Finura"
FULL_RELEASE_ROOT = ROOT / "outputs" / f"full_release_{VERSION}"
FULL_STAGING = FULL_RELEASE_ROOT / "Suite Rodriguez Finura"
REMOTE_BASE = "https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main"


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

PYSIDE_PACKAGE_PATTERNS = [
    "shiboken6",
    "shiboken6-*.dist-info",
    "pyside6-*.dist-info",
    "pyside6_essentials-*.dist-info",
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


def copy_site_package(source: Path, destination: Path) -> None:
    if source.is_dir():
        copytree_clean(source, destination / source.name)
        return
    if source.is_file():
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination / source.name)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def silent_launcher_vbs_text() -> str:
    return '''Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = base
command = """" & base & "\\runtime\\pythonw.exe" & """ """ & base & "\\SuiteLauncher.py" & """"
shell.Run command, 0, False
'''


def compatibility_cmd_text() -> str:
    return f"""@echo off
setlocal
wscript.exe "%~dp0{SILENT_LAUNCHER_NAME}"
exit /b 0
"""


def harden_legacy_runtime_scripts(target: Path) -> None:
    updater = target / "SuiteUpdater.py"
    text = updater.read_text(encoding="utf-8-sig")
    text = text.replace(
        "            timeout=12,\n        )",
        "            timeout=12,\n"
        "            creationflags=getattr(subprocess, \"CREATE_NO_WINDOW\", 0),\n"
        "        )",
    )
    text = text.replace(
        "result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
        "result = subprocess.run(\n"
        "        args,\n"
        "        stdout=subprocess.DEVNULL,\n"
        "        stderr=subprocess.DEVNULL,\n"
        "        creationflags=getattr(subprocess, \"CREATE_NO_WINDOW\", 0),\n"
        "    )",
    )
    updater.write_text(text, encoding="utf-8")


def remove_tree(path: Path) -> None:
    def on_error(func, failed_path, _exc_info):
        os.chmod(failed_path, 0o700)
        func(failed_path)

    shutil.rmtree(path, onerror=on_error)


def overlay_current_suite(target: Path) -> None:
    copytree_clean(PYSIDE_ROOT, target / "Suite_PySide6")
    for name in ("SuiteLauncher.py", "SuiteUpdater.py"):
        shutil.copy2(LEGACY_APP / name, target / name)
    write_text(target / SILENT_LAUNCHER_NAME, silent_launcher_vbs_text())
    write_text(target / LEGACY_CMD_LAUNCHER_NAME, compatibility_cmd_text())
    harden_legacy_runtime_scripts(target)
    for name in (
        "RODRIGUEZ.png",
        "FINURA.png",
        "RODRIGUEZ_logo.bmp",
        "FINURA_logo.bmp",
        "ICONO_SUITE.ico",
        "ICONO_SUITE.png",
        "config_articulos.csv",
    ):
        shutil.copy2(LEGACY_RESOURCES / name, target / name)

    write_text(
        target / "Menu_principal.py",
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
    write_text(target / "version_local.json", json.dumps({"version": VERSION}, indent=2) + "\n")
    write_text(
        target / "update_config.json",
        json.dumps({"version_url": f"{REMOTE_BASE}/version.json"}, indent=2) + "\n",
    )

    site_packages = target / "runtime" / "Lib" / "site-packages"
    pyside_src = QT_ENV / "Lib" / "site-packages" / "PySide6"
    pyside_dst = site_packages / "PySide6"
    pyside_dst.mkdir(parents=True)
    for name in PYSIDE_FILES:
        source = pyside_src / name
        if source.exists():
            shutil.copy2(source, pyside_dst / name)
    shutil.copytree(pyside_src / "plugins", pyside_dst / "plugins", dirs_exist_ok=True)
    qt_site_packages = QT_ENV / "Lib" / "site-packages"
    for pattern in PYSIDE_PACKAGE_PATTERNS:
        for source in qt_site_packages.glob(pattern):
            copy_site_package(source, site_packages)


def prepare_staging() -> None:
    if RELEASE_ROOT.exists():
        remove_tree(RELEASE_ROOT)
    STAGING.mkdir(parents=True)
    overlay_current_suite(STAGING)


def prepare_full_staging() -> None:
    if FULL_RELEASE_ROOT.exists():
        remove_tree(FULL_RELEASE_ROOT)
    copytree_clean(BASE_FULL_APP, FULL_STAGING)
    overlay_current_suite(FULL_STAGING)


def build_zip(package_name: str, release_root: Path) -> Path:
    package = ROOT / package_name
    if package.exists():
        package.unlink()
    with ZipFile(package, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in release_root.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(release_root).as_posix())
    return package


def installer_bat_text(full_package: Path, full_sha256: str) -> str:
    full_url = f"{REMOTE_BASE}/{full_package.name}"
    return f"""@echo off
setlocal
set "APP_NAME=Suite Rodriguez Finura"
set "INSTALL_DIR=%LOCALAPPDATA%\\Suite Rodriguez Finura"
set "TEMP_ROOT=%TEMP%\\Suite_Rodriguez_Finura_FullInstall"
set "ZIP_FILE=%TEMP_ROOT%\\{full_package.name}"
set "EXPECTED_SHA={full_sha256}"
set "DOWNLOAD_URL={full_url}"

echo Instalando %APP_NAME% {VERSION}
echo Cerrando procesos abiertos de la suite...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$install=$env:INSTALL_DIR.ToLower(); Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -and $_.CommandLine.ToLower().Contains($install) -and ($_.Name -match 'python|pythonw|Suite') }} | ForEach-Object {{ try {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }} catch {{}} }}"

if not exist "%TEMP_ROOT%" mkdir "%TEMP_ROOT%"
echo Descargando paquete completo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%ZIP_FILE%' -UseBasicParsing"
if errorlevel 1 goto error

echo Verificando descarga...
for /f "usebackq tokens=*" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash '%ZIP_FILE%' -Algorithm SHA256).Hash"`) do set "ACTUAL_SHA=%%H"
if /I not "%ACTUAL_SHA%"=="%EXPECTED_SHA%" (
  echo Hash incorrecto.
  echo Esperado: %EXPECTED_SHA%
  echo Obtenido: %ACTUAL_SHA%
  goto error
)

echo Preparando instalacion limpia...
if exist "%TEMP_ROOT%\\extract" rmdir /s /q "%TEMP_ROOT%\\extract"
mkdir "%TEMP_ROOT%\\extract"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP_FILE%' -DestinationPath '%TEMP_ROOT%\\extract' -Force"
if errorlevel 1 goto error

if exist "%INSTALL_DIR%.bak" rmdir /s /q "%INSTALL_DIR%.bak"
if exist "%INSTALL_DIR%" ren "%INSTALL_DIR%" "Suite Rodriguez Finura.bak"
mkdir "%LOCALAPPDATA%\\Suite Rodriguez Finura"
robocopy "%TEMP_ROOT%\\extract\\Suite Rodriguez Finura" "%INSTALL_DIR%" /E /NFL /NDL /NJH /NJS /NP
if %ERRORLEVEL% GEQ 8 goto error

echo Abriendo suite actualizada...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $desktop=[Environment]::GetFolderPath('Desktop'); $shortcut=$ws.CreateShortcut((Join-Path $desktop 'Suite Rodriguez Finura.lnk')); $shortcut.TargetPath=(Join-Path $env:INSTALL_DIR '{SILENT_LAUNCHER_NAME}'); $shortcut.WorkingDirectory=$env:INSTALL_DIR; $shortcut.IconLocation=(Join-Path $env:INSTALL_DIR 'ICONO_SUITE.ico'); $shortcut.Save()"
start "" "%INSTALL_DIR%\\runtime\\pythonw.exe" "%INSTALL_DIR%\\SuiteLauncher.py"
echo Instalacion completada.
pause
exit /b 0

:error
echo.
echo No se pudo completar la instalacion.
echo Si existia una copia anterior, revisa: %INSTALL_DIR%.bak
pause
exit /b 1
"""


def update_manifest(package: Path, full_package: Path, installer_bat: Path) -> None:
    digest = sha256(package)
    full_digest = sha256(full_package)
    installer_digest = sha256(installer_bat)
    notes = (
        "- Control y Recepción Maquilas recupera el informe PDF profesional de rangos.\n"
        "- El PDF de rangos ya no depende de carpetas internas de desarrollo para mantener su formato en instalaciones publicadas.\n"
        "- Se conservan los campos del informe: ganadero, origen, DAC, contrato, temperatura, PH, observaciones y especificacion.\n"
        "- Se mantienen la tabla de lotes origen albaran, la clasificacion por rangos y los totales profesionales.\n"
        "- No se cambia el flujo funcional ni los estilos globales de la suite."
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
            "type": "bat",
            "file": installer_bat.name,
            "url": f"{REMOTE_BASE}/{installer_bat.name}",
            "sha256": installer_digest,
            "full_package": full_package.name,
            "full_package_url": f"{REMOTE_BASE}/{full_package.name}",
            "full_package_sha256": full_digest,
        },
        "notes": notes,
        "package_type": "zip",
        "package": PACKAGE_NAME,
        "package_url": f"{REMOTE_BASE}/{PACKAGE_NAME}",
        "sha256": digest,
        "fresh_install_msi": "Suite_Rodriguez_Finura_v1.3.33.msi",
        "fresh_install_url": f"{REMOTE_BASE}/Suite_Rodriguez_Finura_v1.3.33.msi",
        "fresh_install_sha256": "A4ABB193DB0CC17F5481B062D70B714038969B54D6F30957B33792091F8D0518",
        "full_install_bat": installer_bat.name,
        "full_install_bat_url": f"{REMOTE_BASE}/{installer_bat.name}",
        "full_install_bat_sha256": installer_digest,
        "full_install_package": full_package.name,
        "full_install_package_url": f"{REMOTE_BASE}/{full_package.name}",
        "full_install_package_sha256": full_digest,
    }
    write_text(ROOT / "version.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    write_text(ROOT / f"CHANGELOG_v{VERSION}.txt", f"Suite Rodriguez Finura v{VERSION}\n\n{notes}\n")


def main() -> int:
    prepare_staging()
    prepare_full_staging()
    package = build_zip(PACKAGE_NAME, RELEASE_ROOT)
    full_package = build_zip(FULL_PACKAGE_NAME, FULL_RELEASE_ROOT)
    installer_bat = ROOT / INSTALLER_BAT_NAME
    write_text(installer_bat, installer_bat_text(full_package, sha256(full_package)))
    update_manifest(package, full_package, installer_bat)
    size_mb = package.stat().st_size / 1024 / 1024
    full_size_mb = full_package.stat().st_size / 1024 / 1024
    print(f"PACKAGE={package}")
    print(f"SIZE_MB={size_mb:.2f}")
    print(f"SHA256={sha256(package)}")
    print(f"FULL_PACKAGE={full_package}")
    print(f"FULL_SIZE_MB={full_size_mb:.2f}")
    print(f"FULL_SHA256={sha256(full_package)}")
    print(f"INSTALLER_BAT={installer_bat}")
    print(f"INSTALLER_SHA256={sha256(installer_bat)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
