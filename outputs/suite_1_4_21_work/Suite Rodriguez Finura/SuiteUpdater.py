import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from ctypes import wintypes
from pathlib import Path
from urllib.request import Request, urlopen


APP_NAME = "Suite Rodriguez Finura"
MAIN_SCRIPT = "Menu_principal.py"
RUNTIME_PYTHONW = Path("runtime") / "pythonw.exe"
LOCAL_VERSION_FILE = "version_local.json"
RODRIGUEZ_LOGO = "RODRIGUEZ_logo.bmp"
FINURA_LOGO = "FINURA_logo.bmp"
HTTP_TIMEOUT_SECONDS = 20
UPDATE_LOG_FILE = (
    Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    / APP_NAME
    / "logs"
    / "updater.log"
)
UPDATE_STATUS_FILE = UPDATE_LOG_FILE.parent / "update_status.json"

MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONINFORMATION = 0x00000040
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102

WS_OVERLAPPED = 0x00000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_EX_TOPMOST = 0x00000008
WS_EX_DLGMODALFRAME = 0x00000001
SS_CENTER = 0x00000001
SS_BITMAP = 0x0000000E
PBS_MARQUEE = 0x00000008

WM_PAINT = 0x000F
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_SETFONT = 0x0030
WM_SETICON = 0x0080
WM_CTLCOLORSTATIC = 0x0138
WM_USER = 0x0400
WM_APP = 0x8000
WM_APP_STATUS = WM_APP + 1
WM_APP_DONE = WM_APP + 2
WM_APP_ERROR = WM_APP + 3
STM_SETIMAGE = 0x0172
PBM_SETMARQUEE = WM_USER + 10

ICC_PROGRESS_CLASS = 0x00000020
COLOR_BTNFACE = 15
IDI_APPLICATION = 32512
IDC_ARROW = 32512
IMAGE_BITMAP = 0
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
ICON_SMALL = 0
ICON_BIG = 1
SW_SHOWNORMAL = 1
TRANSPARENT = 1

DIALOG_BG = 0x00FDF9F5
HEADER_BG = 0x00FFFFFF
SEPARATOR = 0x00D7D7D7
RODRIGUEZ_BLUE = 0x00994A00
RODRIGUEZ_RED = 0x002416C6
PANEL_BG = 0x00FAFAFA
TEXT_DARK = 0x00202020
TEXT_MUTED = 0x00666666

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
comctl32 = ctypes.windll.comctl32
HMENU = getattr(wintypes, "HMENU", wintypes.HANDLE)

kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.LoadIconW.restype = wintypes.HICON
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.RegisterClassW.argtypes = [wintypes.LPVOID]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateFontW.restype = wintypes.HANDLE
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]


class INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("dwICC", wintypes.DWORD),
    ]


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.BeginPaint.restype = wintypes.HDC
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), wintypes.HBRUSH]


def show_error(title: str, text: str) -> None:
    user32.MessageBoxW(None, text, title, MB_OK | MB_ICONERROR)


def log_update(message: str) -> None:
    try:
        UPDATE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with UPDATE_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def read_update_status() -> dict:
    try:
        with UPDATE_STATUS_FILE.open("r", encoding="utf-8-sig") as f:
            import json

            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_update_status(**values) -> None:
    status = read_update_status()
    status.update(values)
    status["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        UPDATE_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with UPDATE_STATUS_FILE.open("w", encoding="utf-8") as f:
            import json

            json.dump(status, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception:
        pass


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def download_file(url: str, target: Path) -> None:
    log_update(f"Descargando paquete: url={url}; target={target}")
    request = Request(url, headers={"User-Agent": "Suite-Rodriguez-Finura-Updater"})
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response, target.open("wb") as f:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    log_update(f"Descarga completada: target={target}; bytes={target.stat().st_size}")


def unique_temp_package(name: str) -> Path:
    temp_dir = Path(tempfile.gettempdir()) / "Suite_Rodriguez_Finura_Update"
    base = Path(name or "Suite_Rodriguez_Finura_Update.zip").name
    path = Path(base)
    suffix = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    return temp_dir / f"{path.stem}_{suffix}{path.suffix or '.zip'}"


def unique_msi_log(version: str = "") -> Path:
    temp_dir = Path(tempfile.gettempdir()) / "Suite_Rodriguez_Finura_Update"
    suffix = version.replace(".", "_") if version else f"{int(time.time())}"
    return temp_dir / f"msi_update_{suffix}_{uuid.uuid4().hex[:8]}.log"


def read_installed_version(install_dir: Path) -> str:
    version_file = install_dir / LOCAL_VERSION_FILE
    try:
        import json

        with version_file.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return str(data.get("version", "")).strip()
    except Exception:
        return ""


def wait_for_installed_version(install_dir: Path, expected_version: str = "", timeout: float = 12.0) -> None:
    if not expected_version:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if read_installed_version(install_dir) == expected_version:
            return
        time.sleep(0.35)
    current = read_installed_version(install_dir) or "desconocida"
    raise RuntimeError(
        "La actualizacion no dejo la version esperada.\n\n"
        f"Version esperada: {expected_version}\n"
        f"Version encontrada: {current}"
    )


def wait_for_process_exit(pid: int, timeout: float = 45.0) -> None:
    if pid <= 0:
        return
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        time.sleep(2.0)
        return
    try:
        result = kernel32.WaitForSingleObject(handle, int(timeout * 1000))
        if result == WAIT_TIMEOUT:
            log_update(f"El proceso principal sigue abierto tras {timeout:.0f}s: pid={pid}")
        elif result == WAIT_OBJECT_0:
            log_update(f"Proceso principal cerrado: pid={pid}")
    finally:
        kernel32.CloseHandle(handle)


def close_running_suite_processes(install_dir: Path, wait_pid: int = 0) -> None:
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not powershell.exists():
        return
    install = str(install_dir.resolve()).replace("'", "''").lower()
    excluded = [str(os.getpid())]
    excluded_list = ",".join(excluded) if excluded else "0"
    script = f"""
$install = '{install}'
$excluded = @({excluded_list})
Get-CimInstance Win32_Process | Where-Object {{
    $_.ProcessId -notin $excluded -and
    $_.CommandLine -and
    $_.CommandLine.ToLower().Contains($install) -and
    ($_.Name -match 'python|pythonw|Suite')
}} | ForEach-Object {{
    try {{
        Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    }} catch {{}}
}}
"""
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=12,
        )
        log_update(f"Cierre preventivo de procesos de suite completado: code={result.returncode}")
    except Exception as exc:
        log_update(f"No se pudo ejecutar cierre preventivo de procesos: {exc}")


def launch_suite(install_dir: Path) -> None:
    pythonw = install_dir / RUNTIME_PYTHONW
    script = install_dir / MAIN_SCRIPT
    if not pythonw.exists() or not script.exists():
        raise FileNotFoundError(
            "No se encuentra una instalacion valida de la suite actualizada.\n\n"
            f"Runtime esperado:\n{pythonw}\n\n"
            f"Script esperado:\n{script}"
        )
    subprocess.Popen(
        [str(pythonw), str(script)],
        cwd=str(install_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def safe_extract_zip(zip_path: Path, target_dir: Path) -> Path:
    extract_dir = target_dir / f"extract_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    log_update(f"Extrayendo ZIP: zip={zip_path}; extract_dir={extract_dir}")
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            destination = (extract_dir / member.filename).resolve()
            if not str(destination).lower().startswith(str(extract_dir.resolve()).lower()):
                raise RuntimeError("El paquete de actualizacion contiene rutas no validas.")
        archive.extractall(extract_dir)

    children = [child for child in extract_dir.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        log_update(f"ZIP extraido con carpeta raiz: source_dir={children[0]}")
        return children[0]
    log_update(f"ZIP extraido sin carpeta raiz unica: source_dir={extract_dir}")
    return extract_dir


def remove_obsolete_files(install_dir: Path) -> None:
    for name in ("SuiteLauncher.exe", "SuiteUpdater.exe", "Suite_Rodriguez_Finura.exe"):
        path = install_dir / name
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


def copy_package_files_once(source_dir: Path, install_dir: Path) -> None:
    skip_names = {"__pycache__"}
    preserve_existing = {"update_config.json"}
    remove_obsolete_files(install_dir)
    log_update(f"Copiando paquete: source_dir={source_dir}; install_dir={install_dir}")
    for source in source_dir.iterdir():
        if source.name in skip_names:
            continue
        destination = install_dir / source.name
        if source.name in preserve_existing and destination.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    log_update("Copia de paquete completada.")


def copy_package_files(source_dir: Path, install_dir: Path, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    attempt = 1
    last_error: Exception | None = None
    while True:
        try:
            copy_package_files_once(source_dir, install_dir)
            return
        except (PermissionError, OSError, shutil.Error) as exc:
            last_error = exc
            if time.time() >= deadline:
                break
            log_update(f"Copia bloqueada, reintentando: intento={attempt}; error={exc}")
            attempt += 1
            time.sleep(1.2)
    raise RuntimeError(
        "No se pudo copiar la actualizacion porque la suite o alguno de sus archivos sigue en uso.\n\n"
        "Cierra todas las ventanas de Suite Rodriguez Finura y vuelve a intentarlo.\n\n"
        f"Detalle: {last_error}"
    )


def run_msi_update(msi_path: Path, expected_version: str = "") -> Path:
    log_path = unique_msi_log(expected_version)
    msiexec = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "msiexec.exe"
    args = [
        str(msiexec),
        "/i",
        str(msi_path),
        "/qn",
        "/norestart",
        "/L*V",
        str(log_path),
    ]
    result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode not in (0, 3010):
        raise RuntimeError(
            "Windows Installer no pudo completar la actualizacion.\n\n"
            f"Codigo de salida: {result.returncode}\n"
            f"Log: {log_path}"
        )
    return log_path


class NativeProgressWindow:
    def __init__(
        self,
        install_dir: Path,
        expected_version: str = "",
        logo_dir: Path | None = None,
        package_url: str = "",
        package_name: str = "",
        expected_sha256: str = "",
        package_type: str = "zip",
        wait_pid: int = 0,
    ):
        self.install_dir = install_dir
        self.expected_version = expected_version
        self.logo_dir = logo_dir or install_dir
        self.package_url = package_url
        self.package_name = package_name
        self.expected_sha256 = expected_sha256.lower().strip()
        self.package_type = package_type.lower().strip() or "zip"
        self.wait_pid = wait_pid
        self.window_title = "Actualizando"
        self.status_text = "Preparando la actualizacion. No cierres esta ventana."
        self.error_text = ""
        self.finished_ok = False
        self.hwnd = None
        self.title_hwnd = None
        self.status_hwnd = None
        self.detail_hwnd = None
        self.progress_hwnd = None
        self.logo_bitmaps = []
        self.dialog_brush = gdi32.CreateSolidBrush(DIALOG_BG)
        self.header_brush = gdi32.CreateSolidBrush(HEADER_BG)
        self.separator_brush = gdi32.CreateSolidBrush(SEPARATOR)
        self.blue_brush = gdi32.CreateSolidBrush(RODRIGUEZ_BLUE)
        self.red_brush = gdi32.CreateSolidBrush(RODRIGUEZ_RED)
        self.panel_brush = gdi32.CreateSolidBrush(PANEL_BG)
        self.title_font = None
        self.text_font = None
        self.small_font = None
        self._wndproc = WNDPROC(self.wndproc)

    def run(self) -> int:
        self.create_window()
        threading.Thread(target=self.install, daemon=True).start()
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        return 0 if self.finished_ok else 1

    def create_window(self) -> None:
        controls = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX), ICC_PROGRESS_CLASS)
        comctl32.InitCommonControlsEx(ctypes.byref(controls))

        hinstance = kernel32.GetModuleHandleW(None)
        class_name = "SuiteRodriguezFinuraUpdater"
        wc = WNDCLASS()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinstance
        wc.hIcon = user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW))
        wc.hbrBackground = wintypes.HBRUSH(COLOR_BTNFACE + 1)
        wc.lpszClassName = class_name
        user32.RegisterClassW(ctypes.byref(wc))

        width, height = 560, 270
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        x = max(0, int((screen_w - width) / 2))
        y = max(0, int((screen_h - height) / 2))

        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_DLGMODALFRAME,
            class_name,
            f"{self.window_title} {APP_NAME}",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
            x,
            y,
            width,
            height,
            None,
            None,
            hinstance,
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError()

        self.apply_icon()
        self.title_font = gdi32.CreateFontW(-18, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI")
        self.text_font = gdi32.CreateFontW(-13, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI")
        self.small_font = gdi32.CreateFontW(-12, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI")

        self.create_logo(46, 28, RODRIGUEZ_LOGO)
        self.create_logo(367, 28, FINURA_LOGO)

        self.title_hwnd = user32.CreateWindowExW(
            0, "STATIC", f"{self.window_title} {APP_NAME}", WS_CHILD | WS_VISIBLE | SS_CENTER,
            54, 102, 440, 28, self.hwnd, None, hinstance, None
        )
        self.status_hwnd = user32.CreateWindowExW(
            0, "STATIC", self.status_text, WS_CHILD | WS_VISIBLE | SS_CENTER,
            54, 137, 440, 24, self.hwnd, None, hinstance, None
        )
        self.progress_hwnd = user32.CreateWindowExW(
            0, "msctls_progress32", "", WS_CHILD | WS_VISIBLE | PBS_MARQUEE,
            70, 176, 404, 20, self.hwnd, None, hinstance, None
        )
        self.detail_hwnd = user32.CreateWindowExW(
            0, "STATIC", "La suite se abrira automaticamente al finalizar.", WS_CHILD | WS_VISIBLE | SS_CENTER,
            54, 211, 440, 24, self.hwnd, None, hinstance, None
        )

        user32.SendMessageW(self.title_hwnd, WM_SETFONT, self.title_font, True)
        user32.SendMessageW(self.status_hwnd, WM_SETFONT, self.text_font, True)
        user32.SendMessageW(self.detail_hwnd, WM_SETFONT, self.small_font, True)
        user32.SendMessageW(self.progress_hwnd, PBM_SETMARQUEE, True, 35)
        user32.ShowWindow(self.hwnd, SW_SHOWNORMAL)
        user32.UpdateWindow(self.hwnd)

    def create_logo(self, x: int, y: int, name: str) -> None:
        path = self.logo_dir / name
        if not path.exists():
            return
        bitmap = user32.LoadImageW(None, str(path), IMAGE_BITMAP, 0, 0, LR_LOADFROMFILE)
        if not bitmap:
            return
        self.logo_bitmaps.append(bitmap)
        hinstance = kernel32.GetModuleHandleW(None)
        handle = user32.CreateWindowExW(
            0, "STATIC", "", WS_CHILD | WS_VISIBLE | SS_BITMAP,
            x, y, 145, 42, self.hwnd, None, hinstance, None
        )
        user32.SendMessageW(handle, STM_SETIMAGE, IMAGE_BITMAP, bitmap)

    def apply_icon(self) -> None:
        try:
            icon_path = self.logo_dir / "ICONO_SUITE.ico"
            if not icon_path.exists():
                return
            icon = user32.LoadImageW(None, str(icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if icon:
                user32.SendMessageW(self.hwnd, WM_SETICON, ICON_SMALL, icon)
                user32.SendMessageW(self.hwnd, WM_SETICON, ICON_BIG, icon)
        except Exception:
            pass

    def post_status(self, text: str) -> None:
        self.status_text = text
        user32.PostMessageW(self.hwnd, WM_APP_STATUS, 0, 0)

    def install(self) -> None:
        try:
            time.sleep(0.6)
            if not self.package_url:
                raise RuntimeError("No se ha recibido el paquete de actualizacion.")

            log_update(
                "Inicio de actualizacion: "
                f"type={self.package_type}; expected_version={self.expected_version}; "
                f"package={self.package_name}; url={self.package_url}; sha256={self.expected_sha256}; "
                f"install_dir={self.install_dir}"
            )
            write_update_status(
                status="updating",
                message="Actualizacion en curso.",
                target_version=self.expected_version,
                package_type=self.package_type,
                package_name=self.package_name,
                package_url=self.package_url,
                expected_sha256=self.expected_sha256,
                updater_log=str(UPDATE_LOG_FILE),
            )
            temp_dir = Path(tempfile.gettempdir()) / "Suite_Rodriguez_Finura_Update"
            self.post_status("Cerrando la suite antes de actualizar...")
            if self.wait_pid:
                wait_for_process_exit(self.wait_pid, timeout=12.0)
            close_running_suite_processes(self.install_dir, self.wait_pid)
            time.sleep(1.0)

            self.post_status("Descargando el paquete de actualizacion...")
            package = unique_temp_package(self.package_name)
            download_file(self.package_url, package)

            self.post_status("Validando la descarga...")
            actual_sha256 = sha256_file(package)
            log_update(f"Hash descarga: esperado={self.expected_sha256}; obtenido={actual_sha256}")
            if self.expected_sha256 and actual_sha256 != self.expected_sha256:
                write_update_status(
                    status="failed",
                    message="El hash del paquete descargado no coincide.",
                    target_version=self.expected_version,
                    expected_sha256=self.expected_sha256,
                    actual_sha256=actual_sha256,
                )
                raise RuntimeError(
                    "El paquete descargado no coincide con el hash esperado.\n\n"
                    f"Hash esperado: {self.expected_sha256}\n"
                    f"Hash obtenido: {actual_sha256}"
                )

            if self.package_type == "zip":
                self.post_status("Preparando archivos...")
                source_dir = safe_extract_zip(package, temp_dir)

                self.post_status("Aplicando la actualizacion...")
                copy_package_files(source_dir, self.install_dir)
            else:
                raise RuntimeError(
                    f"Tipo de paquete no soportado: {self.package_type}. "
                    "Las actualizaciones automaticas solo admiten ZIP."
                )

            self.post_status("Comprobando la version instalada...")
            wait_for_installed_version(self.install_dir, self.expected_version)
            log_update(f"Version instalada comprobada: {self.expected_version}")
            write_update_status(
                status="updated",
                message="Actualizacion aplicada correctamente.",
                local_version=self.expected_version,
                target_version=self.expected_version,
                package_type=self.package_type,
                package_name=self.package_name,
                package_url=self.package_url,
            )

            self.post_status("Abriendo la suite actualizada...")
            launch_suite(self.install_dir)
            log_update("Suite actualizada abierta correctamente.")
            time.sleep(0.5)
            user32.PostMessageW(self.hwnd, WM_APP_DONE, 0, 0)
        except Exception as exc:
            self.error_text = str(exc)
            log_update(f"ERROR actualizando: {exc}")
            write_update_status(
                status="failed",
                message=str(exc),
                target_version=self.expected_version,
                package_type=self.package_type,
                package_name=self.package_name,
                package_url=self.package_url,
            )
            user32.PostMessageW(self.hwnd, WM_APP_ERROR, 0, 0)

    def wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLOSE:
            user32.MessageBeep(MB_ICONINFORMATION)
            return 0
        if msg == WM_PAINT:
            self.paint(hwnd)
            return 0
        if msg == WM_CTLCOLORSTATIC:
            hdc = wintypes.HDC(wparam)
            gdi32.SetBkMode(hdc, TRANSPARENT)
            if lparam in (self.title_hwnd, self.status_hwnd):
                gdi32.SetTextColor(hdc, TEXT_DARK)
                return self.panel_brush
            if lparam == self.detail_hwnd:
                gdi32.SetTextColor(hdc, TEXT_MUTED)
                return self.panel_brush
            gdi32.SetTextColor(hdc, TEXT_MUTED)
            return self.header_brush
        if msg == WM_APP_STATUS:
            user32.SetWindowTextW(self.status_hwnd, self.status_text)
            return 0
        if msg == WM_APP_DONE:
            self.finished_ok = True
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_APP_ERROR:
            user32.SendMessageW(self.progress_hwnd, PBM_SETMARQUEE, False, 0)
            user32.SetWindowTextW(self.status_hwnd, "No se pudo completar la actualizacion.")
            user32.MessageBoxW(
                hwnd,
                f"No se pudo completar la actualizacion.\n\n"
                f"Detalle: {self.error_text}\n\n"
                "Vuelve a intentarlo o instala la ultima version manualmente.",
                APP_NAME,
                MB_OK | MB_ICONERROR,
            )
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            for handle in (
                self.dialog_brush, self.header_brush, self.separator_brush, self.blue_brush,
                self.red_brush, self.panel_brush, self.title_font, self.text_font, self.small_font,
            ):
                if handle:
                    gdi32.DeleteObject(handle)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def paint(self, hwnd) -> None:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        client = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client))
        user32.FillRect(hdc, ctypes.byref(client), self.dialog_brush)
        header = RECT(client.left, client.top, client.right, 90)
        user32.FillRect(hdc, ctypes.byref(header), self.header_brush)
        blue_width = int((client.right - client.left) * 0.88)
        blue_bar = RECT(client.left, client.top, client.left + blue_width, 7)
        red_bar = RECT(client.left + blue_width, client.top, client.right, 7)
        user32.FillRect(hdc, ctypes.byref(blue_bar), self.blue_brush)
        user32.FillRect(hdc, ctypes.byref(red_bar), self.red_brush)
        line = RECT(client.left, 90, client.right, 91)
        user32.FillRect(hdc, ctypes.byref(line), self.separator_brush)
        panel = RECT(34, 104, client.right - 34, client.bottom - 28)
        user32.FillRect(hdc, ctypes.byref(panel), self.panel_brush)
        panel_accent_blue = RECT(34, 104, 40, client.bottom - 28)
        panel_accent_red = RECT(40, 104, 42, client.bottom - 28)
        user32.FillRect(hdc, ctypes.byref(panel_accent_blue), self.blue_brush)
        user32.FillRect(hdc, ctypes.byref(panel_accent_red), self.red_brush)
        user32.EndPaint(hwnd, ctypes.byref(ps))


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--package":
        if len(sys.argv) < 7:
            show_error(APP_NAME, "No se han recibido los datos del paquete de actualizacion.")
            return 1
        if len(sys.argv) >= 8:
            package_type = sys.argv[2].strip().lower()
            package_url = sys.argv[3].strip()
            package_name = sys.argv[4].strip()
            expected_sha256 = sys.argv[5].strip()
            install_dir = Path(sys.argv[6]).resolve()
            expected_version = str(sys.argv[7]).strip()
            wait_pid = 0
            if "--wait-pid" in sys.argv:
                index = sys.argv.index("--wait-pid")
                if index + 1 < len(sys.argv):
                    try:
                        wait_pid = int(sys.argv[index + 1])
                    except ValueError:
                        wait_pid = 0
        else:
            package_type = "zip"
            package_url = sys.argv[2].strip()
            package_name = sys.argv[3].strip()
            expected_sha256 = sys.argv[4].strip()
            install_dir = Path(sys.argv[5]).resolve()
            expected_version = str(sys.argv[6]).strip()
            wait_pid = 0
        try:
            return NativeProgressWindow(
                install_dir,
                expected_version,
                package_url=package_url,
                package_name=package_name,
                expected_sha256=expected_sha256,
                package_type=package_type,
                wait_pid=wait_pid,
            ).run()
        except Exception as exc:
            show_error(APP_NAME, f"No se pudo preparar la actualizacion:\n\n{exc}")
            return 1

    show_error(APP_NAME, "No se ha recibido un paquete de actualizacion valido.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
