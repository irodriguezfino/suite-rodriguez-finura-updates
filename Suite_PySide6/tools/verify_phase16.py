from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    build_script = (ROOT / "tools" / "build_update_150.py").read_text(encoding="utf-8-sig")
    main_window = (ROOT / "src" / "suite_pyside6" / "ui" / "main_window.py").read_text(encoding="utf-8-sig")

    assert 'VERSION = "1.7.2"' in build_script
    assert "Abrir_Suite_Rodriguez_Finura.vbs" in build_script
    assert "runtime\\\\pythonw.exe" in build_script
    assert 'start "" "%INSTALL_DIR%\\\\Abrir_Suite_Rodriguez_Finura.cmd"' not in build_script
    assert 'creationflags=getattr(subprocess, \\"CREATE_NO_WINDOW\\", 0)' in build_script

    assert "self.search.setVisible(False)" in main_window
    assert "self.search.setVisible(True)" in main_window
    assert "ShellNextAction" in main_window
    assert "_compact_action_text" in main_window

    print("PHASE16_OK")
    print("silent_launcher=true")
    print("cmd_primary_launch=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
