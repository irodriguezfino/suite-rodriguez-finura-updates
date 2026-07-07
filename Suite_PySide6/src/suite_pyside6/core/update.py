from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from suite_pyside6 import __version__


APP_NAME = "Suite Rodriguez Finura"
LOCAL_VERSION_FILE = "version_local.json"
UPDATE_CONFIG_FILE = "update_config.json"
UPDATER_SCRIPT = "SuiteUpdater.py"
RUNTIME_PYTHONW = Path("runtime") / "pythonw.exe"
DEFAULT_VERSION_URL = "https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main/version.json"
HTTP_TIMEOUT_SECONDS = 20
UPDATE_LOG_FILE = (
    Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    / APP_NAME
    / "logs"
    / "launcher_update_check.log"
)


@dataclass(frozen=True)
class UpdatePackage:
    package_type: str
    url: str
    name: str
    sha256: str


@dataclass(frozen=True)
class UpdateCheckResult:
    ok: bool
    local_version: str
    remote_version: str = ""
    version_url: str = DEFAULT_VERSION_URL
    notes: str = ""
    package: UpdatePackage | None = None
    message: str = ""
    update_available: bool = False


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    for parent in Path(__file__).resolve().parents:
        if (parent / LOCAL_VERSION_FILE).exists() or (parent / UPDATE_CONFIG_FILE).exists():
            return parent
    return Path.cwd()


def read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_update_status(**values) -> None:
    path = update_status_file()
    status = read_json(path)
    status.update(values)
    status["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(status, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except Exception:
        pass


def update_status_file() -> Path:
    return UPDATE_LOG_FILE.parent / "update_status.json"


def log_update_check(message: str) -> None:
    try:
        UPDATE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with UPDATE_LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def read_json_url(url: str) -> dict:
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Suite-Rodriguez-Finura-Updater",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            raw = response.read(1024 * 1024)
        data = json.loads(raw.decode("utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        log_update_check(f"No se pudo leer version.json online: {exc}")
        return {}


def parse_version(value: str) -> tuple[int, int, int, int]:
    parts = re.findall(r"\d+", str(value or "0"))
    nums = [int(part) for part in parts[:4]]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums)  # type: ignore[return-value]


def local_version() -> str:
    data = read_json(app_dir() / LOCAL_VERSION_FILE)
    return str(data.get("version") or __version__)


def configured_version_url() -> str:
    config = read_json(app_dir() / UPDATE_CONFIG_FILE)
    for key in ("version_url", "remote_version_url", "github_version_url"):
        value = str(config.get(key, "")).strip()
        if value:
            return value
    return DEFAULT_VERSION_URL


def filename_from_url(url: str, default: str) -> str:
    try:
        name = Path(unquote(urlparse(url).path)).name
        return name or default
    except Exception:
        return default


def update_package_from_manifest(remote_data: dict, remote_version: str) -> UpdatePackage:
    auto_update = remote_data.get("auto_update")
    if not isinstance(auto_update, dict):
        auto_update = {}
    package_type = str(auto_update.get("type") or remote_data.get("package_type") or "zip").lower().strip()
    package_url = str(auto_update.get("url") or remote_data.get("package_url") or "").strip()
    package_name = str(auto_update.get("file") or remote_data.get("package") or "").strip()
    expected_sha256 = str(auto_update.get("sha256") or remote_data.get("sha256") or "").lower().strip()
    if not package_name and package_url:
        package_name = filename_from_url(package_url, f"Suite_Rodriguez_Finura_v{remote_version}_update.zip")
    return UpdatePackage(package_type, package_url, package_name, expected_sha256)


def check_for_updates() -> UpdateCheckResult:
    version_url = configured_version_url()
    current = local_version()
    log_update_check(f"Comprobando actualizaciones online: {version_url}")
    write_update_status(status="checking", message="Comprobando actualizaciones.", version_url=version_url, local_version=current)

    remote_data = read_json_url(version_url)
    if not remote_data:
        message = "No se pudo consultar GitHub ahora. Se mantiene la version instalada."
        write_update_status(status="offline", message=message, version_url=version_url)
        return UpdateCheckResult(False, current, version_url=version_url, message=message)

    remote_version = str(remote_data.get("version", "0.0.0"))
    notes = str(remote_data.get("notes", "")).strip()
    package = update_package_from_manifest(remote_data, remote_version)
    available = parse_version(remote_version) > parse_version(current)
    message = "Hay una actualizacion disponible." if available else "No hay actualizaciones disponibles."
    write_update_status(
        status="checked",
        message=message,
        version_url=version_url,
        local_version=current,
        remote_version=remote_version,
    )
    return UpdateCheckResult(
        True,
        current,
        remote_version=remote_version,
        version_url=version_url,
        notes=notes,
        package=package,
        message=message,
        update_available=available,
    )


def copy_updater_to_temp() -> tuple[Path, Path, Path]:
    base = app_dir()
    temp_root = Path(tempfile.gettempdir()) / "Suite_Rodriguez_Finura_Update"
    helper_dir = temp_root / f"SuiteUpdateHelper_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    helper_dir.mkdir(parents=True, exist_ok=True)

    pythonw = base / RUNTIME_PYTHONW
    updater_src = base / UPDATER_SCRIPT
    if not pythonw.exists() or not updater_src.exists():
        raise FileNotFoundError(
            "No se encuentra el runtime o el script del actualizador.\n\n"
            f"Runtime esperado:\n{pythonw}\n\n"
            f"Actualizador esperado:\n{updater_src}"
        )
    updater_script = helper_dir / UPDATER_SCRIPT
    shutil.copy2(updater_src, updater_script)
    for asset in ("RODRIGUEZ_logo.bmp", "FINURA_logo.bmp", "ICONO_SUITE.ico"):
        src = base / asset
        if src.exists():
            shutil.copy2(src, helper_dir / asset)
    return helper_dir, pythonw, updater_script


def start_update(package: UpdatePackage, remote_version: str) -> None:
    if package.package_type != "zip":
        raise ValueError(f"Tipo de paquete no admitido para actualizacion automatica: {package.package_type}")
    if not package.url or not package.sha256:
        raise ValueError("El canal remoto no incluye URL y SHA-256 verificables.")

    helper_dir, pythonw, updater_script = copy_updater_to_temp()
    args = [
        str(pythonw),
        str(updater_script),
        "--package",
        package.package_type,
        package.url,
        package.name,
        package.sha256,
        str(app_dir()),
        str(remote_version),
        "--wait-pid",
        str(os.getpid()),
    ]
    subprocess.Popen(
        args,
        cwd=str(helper_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    log_update_check(
        "Actualizador iniciado: "
        f"type={package.package_type}; version={remote_version}; package={package.name}; url={package.url}"
    )
    write_update_status(
        status="updater_started",
        message="Actualizador iniciado.",
        target_version=remote_version,
        package_type=package.package_type,
        package_name=package.name,
        package_url=package.url,
        expected_sha256=package.sha256,
    )


def diagnostic_text(result: UpdateCheckResult | None = None) -> str:
    status = read_json(update_status_file())
    lines = [
        APP_NAME,
        f"Version instalada: {local_version()}",
        f"Ruta: {app_dir()}",
        f"Canal: {configured_version_url()}",
        f"Log: {UPDATE_LOG_FILE}",
    ]
    if result is not None:
        lines.extend(
            [
                f"Version remota: {result.remote_version or '-'}",
                f"Estado comprobacion: {result.message or '-'}",
            ]
        )
    if status:
        lines.append("Estado persistente:")
        for key in ("status", "message", "local_version", "remote_version", "target_version", "updated_at"):
            if key in status:
                lines.append(f"- {key}: {status[key]}")
    return "\n".join(lines)
