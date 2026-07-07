from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
VERIFY_SCRIPTS = (
    "verify_phase1.py",
    "verify_phase2.py",
    "verify_phase3.py",
    "verify_phase4.py",
    "verify_phase5.py",
    "verify_phase6.py",
    "verify_phase7.py",
    "verify_phase8.py",
    "verify_phase9.py",
    "verify_phase10.py",
)


def run(command: list[str], *, cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


def git_path() -> str:
    override = os.environ.get("GIT_EXE")
    if override:
        return override
    return "git"


def assert_core_unchanged() -> None:
    try:
        output = run(
            [
                git_path(),
                "diff",
                "--name-only",
                "HEAD",
                "--",
                "Suite_PySide6/src/suite_pyside6/core",
            ],
            cwd=REPO,
        )
    except Exception as exc:
        raise AssertionError(f"No se pudo comprobar el estado de core/: {exc}") from exc
    changed = [line.strip() for line in output.splitlines() if line.strip()]
    assert not changed, "La capa core/ no debe cambiar en esta fase: " + ", ".join(changed)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    assert_core_unchanged()
    for script in VERIFY_SCRIPTS:
        output = run([sys.executable, str(ROOT / "tools" / script)])
        marker = script.replace("verify_", "").replace(".py", "").upper()
        print(output.strip())
        assert "OK" in output, f"No se encontro marcador OK en {script} ({marker})"
    print("UI_CONTRACTS_OK")
    print("core_unchanged=true")
    print(f"checks={len(VERIFY_SCRIPTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
