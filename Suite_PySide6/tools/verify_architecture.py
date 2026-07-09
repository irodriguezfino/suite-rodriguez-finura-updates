from __future__ import annotations

import ast
import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CORE = SRC / "suite_pyside6" / "core"


def _imports_for(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def assert_core_has_no_ui_dependencies() -> None:
    offenders: list[str] = []
    for path in CORE.glob("*.py"):
        for imported in _imports_for(path):
            if imported == "PySide6" or imported.startswith("PySide6.") or imported.startswith("suite_pyside6.ui"):
                offenders.append(f"{path.relative_to(ROOT)} -> {imported}")
    assert not offenders, "core/ no debe depender de UI: " + ", ".join(offenders)


def assert_window_registry_is_lazy() -> None:
    sys.path.insert(0, str(SRC))
    from suite_pyside6.core.apps import APP_REGISTRY
    from suite_pyside6.ui.app_windows import WINDOW_CLASSES, get_window_class

    loaded = [name for name in sys.modules if name.startswith("suite_pyside6.ui.") and name.endswith("_window")]
    assert not loaded, "Importar el registro no debe cargar ventanas: " + ", ".join(loaded)
    assert set(WINDOW_CLASSES) == {app.key for app in APP_REGISTRY}
    assert len(WINDOW_CLASSES) == len(APP_REGISTRY)
    assert get_window_class("txt_csv") is not None
    assert get_window_class("clave_inexistente") is None


def main() -> int:
    assert_core_has_no_ui_dependencies()
    assert_window_registry_is_lazy()
    print("ARCHITECTURE_OK")
    print("core_ui_dependencies=0")
    print("window_registry=lazy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
