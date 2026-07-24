from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget


def reduced_motion_enabled() -> bool:
    """Respeta la preferencia del sistema cuando Qt la expone."""
    hints = QApplication.styleHints()
    reduce_motion = getattr(hints, "reduceMotion", None)
    return bool(reduce_motion()) if callable(reduce_motion) else False


def reveal_view(widget: QWidget) -> None:
    """Marca el cambio sin alterar la opacidad de una página ya visible.

    Aplicar un efecto de opacidad después de cambiar el `QStackedWidget` producía
    un frame a brillo completo seguido de otro atenuado. El shell ya comunica el
    cambio mediante el estado activo, así que la entrada estable evita ese flash.
    """
    widget.setProperty("navigationTransition", "reduced" if reduced_motion_enabled() else "stable")
