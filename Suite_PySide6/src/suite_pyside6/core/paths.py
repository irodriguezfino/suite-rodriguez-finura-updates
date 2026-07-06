from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT.parent
LEGACY_SOURCE_DIR = WORKSPACE_ROOT / "outputs" / "worktree_1_4_27" / "build_1_4_43"


def resource_path(name: str) -> Path:
    candidates = (
        PROJECT_ROOT / "resources" / name,
        PROJECT_ROOT / name,
        PROJECT_ROOT.parent / name,
        Path.cwd() / name,
    )
    for local in candidates:
        if local.exists():
            return local
    return LEGACY_SOURCE_DIR / name
