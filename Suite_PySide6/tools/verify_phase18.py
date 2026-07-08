from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK_ROOTS = (
    ROOT / "src" / "suite_pyside6" / "ui",
    ROOT / "src" / "suite_pyside6" / "core" / "apps.py",
    ROOT / "tools" / "build_update_150.py",
)
BAD_FRAGMENTS = ("Ã", "Â", "�", "Recepcion Maquilas", "Control y Recepcion Maquilas", "Precintos Expedicion")


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in CHECK_ROOTS:
        if root.is_file():
            files.append(root)
        else:
            files.extend(sorted(root.rglob("*.py")))
    return files


def main() -> int:
    offenders: list[str] = []
    for path in iter_files():
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        for fragment in BAD_FRAGMENTS:
            if fragment in text:
                offenders.append(f"{path.relative_to(ROOT)} contiene {fragment!r}")
    assert not offenders, "\n".join(offenders)
    print("PHASE18_OK")
    print("copy_quality=true")
    print(f"files_checked={len(iter_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
