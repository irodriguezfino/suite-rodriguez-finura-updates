from __future__ import annotations

def main() -> int:
    try:
        from suite_pyside6.ui.main_window import run
    except ModuleNotFoundError:
        print("PySide6 no esta instalado en este entorno.")
        print("Instalacion prevista: python -m pip install -e Suite_PySide6")
        return 2

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
