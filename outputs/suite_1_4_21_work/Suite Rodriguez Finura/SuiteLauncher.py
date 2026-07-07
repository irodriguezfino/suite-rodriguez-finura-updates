import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


APP_NAME = "Suite Rodriguez Finura"
MAIN_SCRIPT = "Menu_principal.py"
RUNTIME_DIR = "runtime"
RUNTIME_PYTHONW = Path(RUNTIME_DIR) / "pythonw.exe"
UPDATER_SCRIPT = "SuiteUpdater.py"
LOCAL_VERSION_FILE = "version_local.json"
UPDATE_CONFIG_FILE = "update_config.json"
DEFAULT_VERSION_URL = "https://raw.githubusercontent.com/irodriguezfino/suite-rodriguez-finura-updates/main/version.json"
UPDATE_LOG_FILE = (
    Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    / APP_NAME
    / "logs"
    / "launcher_update_check.log"
)
HTTP_TIMEOUT_SECONDS = 20

MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONINFORMATION = 0x00000040
MB_ICONQUESTION = 0x00000020
MB_ICONWARNING = 0x00000030
MB_YESNO = 0x00000004
IDYES = 6


def show_warning(title: str, text: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, text, title, MB_OK | MB_ICONWARNING)


def show_error(title: str, text: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, text, title, MB_OK | MB_ICONERROR)


def show_info(title: str, text: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, text, title, MB_OK | MB_ICONINFORMATION)


def ask_yes_no(title: str, text: str) -> bool:
    return ctypes.windll.user32.MessageBoxW(None, text, title, MB_YESNO | MB_ICONQUESTION) == IDYES


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def log_update_check(message: str) -> None:
    try:
        UPDATE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with UPDATE_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def update_status_file() -> Path:
    return UPDATE_LOG_FILE.parent / "update_status.json"


def write_update_status(**values) -> None:
    status = read_json(update_status_file())
    status.update(values)
    status["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        update_status_file().parent.mkdir(parents=True, exist_ok=True)
        with update_status_file().open("w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception:
        pass


def read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def filename_from_url(url: str, default: str) -> str:
    try:
        name = Path(unquote(urlparse(url).path)).name
        return name or default
    except Exception:
        return default


def parse_version(value: str):
    parts = re.findall(r"\d+", str(value or "0"))
    nums = [int(p) for p in parts[:4]]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums)


def get_local_version() -> str:
    data = read_json(app_dir() / LOCAL_VERSION_FILE)
    return str(data.get("version", "0.0.0"))


def configured_version_url() -> str:
    config = read_json(app_dir() / UPDATE_CONFIG_FILE)
    for key in ("version_url", "remote_version_url", "github_version_url"):
        value = str(config.get(key, "")).strip()
        if value:
            return value
    return DEFAULT_VERSION_URL


def launch_main() -> int:
    pythonw = app_dir() / RUNTIME_PYTHONW
    script = app_dir() / MAIN_SCRIPT
    if pythonw.exists() and script.exists():
        subprocess.Popen(
            [str(pythonw), str(script)],
            cwd=str(app_dir()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return 0

    show_error(
        APP_NAME,
        "No se encuentra una instalacion valida de la suite.\n\n"
        f"Runtime esperado:\n{pythonw}\n\n"
        f"Script principal esperado:\n{script}\n\n"
        "Reinstala la aplicacion con el ultimo instalador disponible.",
    )
    return 1


def copy_updater_to_temp() -> tuple[Path, Path, Path]:
    temp_root = Path(tempfile.gettempdir()) / "Suite_Rodriguez_Finura_Update"
    helper_dir = temp_root / f"SuiteUpdateHelper_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    helper_dir.mkdir(parents=True, exist_ok=True)

    runtime_src = app_dir() / RUNTIME_DIR
    updater_src = app_dir() / UPDATER_SCRIPT
    if not runtime_src.exists() or not updater_src.exists():
        raise FileNotFoundError(
            "No se encuentra el runtime o el script del actualizador.\n\n"
            f"Runtime esperado:\n{runtime_src}\n\n"
            f"Actualizador esperado:\n{updater_src}"
        )

    shutil.copy2(updater_src, helper_dir / UPDATER_SCRIPT)
    for asset in ("RODRIGUEZ_logo.bmp", "FINURA_logo.bmp", "ICONO_SUITE.ico"):
        src = app_dir() / asset
        if src.exists():
            shutil.copy2(src, helper_dir / asset)

    pythonw = app_dir() / RUNTIME_PYTHONW
    updater_script = helper_dir / UPDATER_SCRIPT
    if not pythonw.exists():
        raise FileNotFoundError(f"No se encuentra pythonw.exe en la instalacion:\n\n{pythonw}")
    return helper_dir, pythonw, updater_script


def start_package_update(
    package_type: str,
    package_url: str,
    package_name: str,
    expected_sha256: str,
    expected_version: str,
) -> int:
    try:
        helper_dir, pythonw, updater_script = copy_updater_to_temp()
        args = [
            str(pythonw),
            str(updater_script),
            "--package",
            package_type,
            package_url,
            package_name,
            expected_sha256,
            str(app_dir()),
            str(expected_version),
            "--wait-pid",
            str(os.getpid()),
        ]
        subprocess.Popen(
            args,
            cwd=str(helper_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log_update_check(
            "Actualizador iniciado: "
            f"type={package_type}; version={expected_version}; package={package_name}; url={package_url}"
        )
        write_update_status(
            status="updater_started",
            message="Actualizador iniciado.",
            target_version=expected_version,
            package_type=package_type,
            package_name=package_name,
            package_url=package_url,
            expected_sha256=expected_sha256,
            updater_log=str(UPDATE_LOG_FILE.parent / "updater.log"),
        )
        return 0
    except Exception as exc:
        log_update_check(f"No se pudo preparar el actualizador: {exc}")
        write_update_status(status="error", message=f"No se pudo preparar el actualizador: {exc}")
        show_error(APP_NAME, f"No se pudo preparar el actualizador:\n\n{exc}")
        return 1


def update_package_from_manifest(remote_data: dict, remote_version: str) -> tuple[str, str, str, str]:
    auto_update = remote_data.get("auto_update")
    if not isinstance(auto_update, dict):
        auto_update = {}

    package_type = str(
        auto_update.get("type")
        or auto_update.get("package_type")
        or remote_data.get("package_type")
        or "zip"
    ).strip().lower()
    package_url = str(
        auto_update.get("url")
        or auto_update.get("package_url")
        or remote_data.get("package_url")
        or ""
    ).strip()
    expected_sha256 = str(
        auto_update.get("sha256")
        or remote_data.get("sha256")
        or ""
    ).strip().lower()
    package_name = str(
        auto_update.get("file")
        or auto_update.get("package")
        or remote_data.get("package")
        or ""
    ).strip()

    if not package_name:
        package_name = filename_from_url(package_url, f"Suite_Rodriguez_Finura_v{remote_version}_update.zip")

    return package_type, package_url, package_name, expected_sha256


def recently_skipped_version(remote_version: str, minutes: int = 30) -> bool:
    status = read_json(update_status_file())
    if status.get("target_version") != remote_version:
        return False
    if status.get("status") not in {"cancelled", "error", "failed"}:
        return False
    try:
        stamp = time.strptime(str(status.get("updated_at", "")), "%Y-%m-%d %H:%M:%S")
        age_seconds = time.time() - time.mktime(stamp)
        return age_seconds < minutes * 60
    except Exception:
        return False


def check_and_update(manual: bool = False) -> bool:
    version_url = configured_version_url()
    if not version_url:
        return False

    log_update_check(f"Comprobando actualizaciones online: {version_url}")
    write_update_status(
        status="checking",
        message="Comprobando actualizaciones.",
        version_url=version_url,
        local_version=get_local_version(),
        log_file=str(UPDATE_LOG_FILE),
    )
    remote_data = read_json_url(version_url)
    if not remote_data:
        write_update_status(status="offline", message="No se pudo leer el manifiesto remoto.", version_url=version_url)
        if manual:
            show_warning(APP_NAME, "No se pudo consultar GitHub ahora.\n\nSe mantiene la version instalada.")
        return False

    remote_version = str(remote_data.get("version", "0.0.0"))
    local_version = get_local_version()
    log_update_check(f"Version local={local_version}; version remota={remote_version}")
    write_update_status(
        status="checked",
        message="Comprobacion completada.",
        version_url=version_url,
        local_version=local_version,
        remote_version=remote_version,
    )
    if parse_version(remote_version) <= parse_version(local_version):
        log_update_check("No hay actualizacion aplicable.")
        write_update_status(status="up_to_date", message="No hay actualizacion disponible.", remote_version=remote_version)
        if manual:
            show_info(APP_NAME, f"No hay actualizaciones disponibles.\n\nVersion instalada: {local_version}")
        return False

    if not manual and recently_skipped_version(remote_version):
        log_update_check(f"Se omite aviso automatico reciente para version {remote_version}.")
        return False

    package_type, package_url, package_name, expected_sha256 = update_package_from_manifest(remote_data, remote_version)
    log_update_check(
        "Paquete remoto: "
        f"type={package_type}; package={package_name}; sha256={expected_sha256}; url={package_url}"
    )
    if not package_url or not expected_sha256:
        log_update_check("Canal remoto incompleto: falta package_url o sha256.")
        write_update_status(
            status="invalid_manifest",
            message="Canal remoto incompleto: falta package_url o sha256.",
            remote_version=remote_version,
        )
        show_warning(
            APP_NAME,
            "Se ha detectado una version nueva, pero el canal no incluye un paquete verificable.\n\n"
            "Por seguridad se abrira la version instalada actualmente.",
        )
        return False

    if package_type != "zip":
        log_update_check(f"Canal rechazado: las actualizaciones automaticas solo admiten ZIP, recibido {package_type}.")
        write_update_status(
            status="invalid_manifest",
            message=f"Tipo de paquete no admitido para actualizacion automatica: {package_type}.",
            remote_version=remote_version,
            package_type=package_type,
            package_url=package_url,
        )
        show_warning(
            APP_NAME,
            f"El canal de actualizacion indica un paquete no admitido: {package_type}\n\n"
            "Las actualizaciones automaticas de la suite solo se aplican desde ZIP verificable.\n\n"
            "Por seguridad se abrira la version instalada actualmente.",
        )
        return False

    notes = str(remote_data.get("notes", "")).strip()
    msg = (
        f"Hay una actualizacion disponible de {APP_NAME}.\n\n"
        f"Version instalada: {local_version}\n"
        f"Version disponible: {remote_version}\n\n"
    )
    if notes:
        msg += f"Notas:\n{notes}\n\n"
    msg += "Pulsa Si para descargarla e instalarla ahora. La suite se abrira despues de actualizar."

    if not ask_yes_no(APP_NAME, msg):
        log_update_check("Usuario cancelo la actualizacion.")
        write_update_status(
            status="cancelled",
            message="Usuario cancelo la actualizacion.",
            target_version=remote_version,
            package_type=package_type,
            package_name=package_name,
            package_url=package_url,
        )
        return False

    start_package_update(package_type, package_url, package_name, expected_sha256, remote_version)
    return True


def main() -> int:
    try:
        if check_and_update():
            return 0
        return launch_main()
    except Exception as exc:
        show_warning(
            APP_NAME,
            "No se pudo comprobar correctamente si hay actualizaciones.\n\n"
            f"Detalle: {exc}\n\n"
            "Se abrira la version instalada actualmente.",
        )
        return launch_main()


if __name__ == "__main__":
    raise SystemExit(main())
