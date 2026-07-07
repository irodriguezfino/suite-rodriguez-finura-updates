from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    init_text = (ROOT / "src" / "suite_pyside6" / "__init__.py").read_text(encoding="utf-8-sig")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8-sig")
    init_version = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    project_version = re.search(r'version\s*=\s*"([^"]+)"', pyproject)
    assert init_version and project_version
    assert init_version.group(1) == project_version.group(1)

    from suite_pyside6.core.apps import APP_REGISTRY
    from suite_pyside6.ui.app_windows import WINDOW_CLASSES
    from suite_pyside6.ui.polish import operational_snapshot, prepare_embedded_window, trigger_next_action

    assert set(WINDOW_CLASSES) == {app.key for app in APP_REGISTRY}
    assert callable(prepare_embedded_window)
    assert callable(operational_snapshot)
    assert callable(trigger_next_action)

    for path in (ROOT / "src" / "suite_pyside6" / "ui").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8-sig"))

    print("PHASE15_OK")
    print(f"version={init_version.group(1)}")
    print(f"ui_sources={len(list((ROOT / 'src' / 'suite_pyside6' / 'ui').glob('*.py')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
