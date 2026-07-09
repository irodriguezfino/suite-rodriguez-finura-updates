from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "suite_pyside6" / "ui"

TABLE_BEHAVIOR_METHODS = {
    "setAlternatingRowColors",
    "setEditTriggers",
    "setSelectionBehavior",
    "setSelectionMode",
    "setShowGrid",
}
TABLE_HEADER_BEHAVIOR = {
    "setVisible",
    "setDefaultSectionSize",
}
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}")
REQUIRED_TOKENS = {
    "background",
    "surface",
    "surface_muted",
    "surface_elevated",
    "border",
    "border_strong",
    "text_primary",
    "text_secondary",
    "text_muted",
    "primary",
    "primary_hover",
    "primary_active",
    "primary_soft",
    "accent_red",
    "accent_red_soft",
    "accent_gold",
    "accent_gold_soft",
    "focus_ring",
    "success",
    "warning",
    "error",
    "info",
}


def ui_files() -> list[Path]:
    return sorted(UI.glob("*.py"))


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def assert_table_behavior_is_centralized() -> None:
    offenders: list[str] = []
    for path in ui_files():
        if path.name == "polish.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in TABLE_BEHAVIOR_METHODS:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} usa {name}")
                continue
            if name in TABLE_HEADER_BEHAVIOR and isinstance(node.func, ast.Attribute):
                target = ast.unparse(node.func.value)
                if "verticalHeader()" in target:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} configura verticalHeader().{name}")
    assert not offenders, "El comportamiento de tablas debe vivir en ui/polish.py:\n" + "\n".join(offenders)


def assert_theme_is_single_source() -> None:
    offenders: list[str] = []
    for path in ui_files():
        if path.name == "theme.py":
            continue
        text = path.read_text(encoding="utf-8-sig")
        for match in HEX_COLOR.finditer(text):
            offenders.append(f"{path.relative_to(ROOT)} contiene color literal {match.group(0)}")
        if "setStyleSheet(" in text and "base_qss()" not in text:
            offenders.append(f"{path.relative_to(ROOT)} usa setStyleSheet fuera de base_qss()")
    assert not offenders, "El tema visual debe centralizarse en ui/theme.py:\n" + "\n".join(offenders)


def assert_design_system_entrypoints_exist() -> None:
    components = (UI / "components.py").read_text(encoding="utf-8-sig")
    polish = (UI / "polish.py").read_text(encoding="utf-8-sig")
    theme = (UI / "theme.py").read_text(encoding="utf-8-sig")
    for symbol in ("labeled_field", "panel", "metric", "badge", "empty_state", "step_bar"):
        assert f"def {symbol}" in components, f"Falta componente DS: {symbol}"
    for symbol in ("polish_window", "confirm_discard_work", "show_inline_message", "sync_recommended_action"):
        assert f"def {symbol}" in polish, f"Falta patrón de interacción DS: {symbol}"
    assert "def base_qss" in theme and "def palette" in theme, "El tema debe exponer palette() y base_qss()"


def assert_brand_tokens_and_assets_exist() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from suite_pyside6.core.paths import resource_path
    from suite_pyside6.ui.theme import DARK, LIGHT

    for name, tokens in (("LIGHT", LIGHT), ("DARK", DARK)):
        missing = REQUIRED_TOKENS - set(tokens)
        assert not missing, f"{name} no define tokens semánticos: {', '.join(sorted(missing))}"
    assert LIGHT["primary"].lower() == "#123283", "Rodríguez debe ser el color primario del tema claro"
    assert LIGHT["accent_red"].lower() == "#c32421", "El rojo Rodríguez debe estar tokenizado"
    assert LIGHT["accent_gold"].lower() == "#7b6a42", "El oro Finura accesible debe estar tokenizado"
    old_dark_blues = {"#123283", "#1b3891", "#0b266d", "#2f5fc7", "#3f73de", "#244fae", "#13244a", "#7dd6ea", "#112f3a"}
    for key in ("primary", "primary_hover", "primary_active", "primary_soft", "info", "info_soft", "focus_ring", "sidebar_bg"):
        value = DARK[key].lower()
        assert value not in old_dark_blues, f"El modo oscuro debe usar Finura, no azul Rodriguez: DARK[{key}]={value}"
    assert DARK["primary"].lower() == "#c8b46f", "Finura debe ser el color primario del tema oscuro"
    assert DARK["info"].lower() == "#c8b46f", "Info en oscuro debe ser Finura, no azul/cian"
    for asset in ("RODRIGUEZ.png", "FINURA.png"):
        assert resource_path(asset).exists(), f"Falta asset de marca: {asset}"


def main() -> int:
    assert_design_system_entrypoints_exist()
    assert_brand_tokens_and_assets_exist()
    assert_theme_is_single_source()
    assert_table_behavior_is_centralized()
    print("DESIGN_SYSTEM_OK")
    print("theme_single_source=true")
    print("table_behavior=centralized")
    print("components_entrypoints=ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
