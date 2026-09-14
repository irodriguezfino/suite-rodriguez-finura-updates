from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.ui.components import configure_header_action, ActionMenuButton
from suite_pyside6.ui.session import (
    MAX_PERSONAL_DESCRIPTION_LENGTH,
    migrate_personal_description,
    personal_description,
    remove_personal_description,
    save_personal_description,
)
from suite_pyside6.ui.theme import base_qss


def header_description_key(application_key: str) -> str:
    return f"applications.{application_key}.header.description"


def process_description_key(application_key: str, process_key: str = "catalog") -> str:
    return f"applications.{application_key}.processes.{process_key}.description"


class DescriptionEditorDialog(QDialog):
    def __init__(self, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Descripción personalizada")
        self.setModal(True)
        self.resize(520, 260)
        self.setStyleSheet(base_qss())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        prompt = QLabel("Escribe una descripción privada para tu perfil.")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)
        self.editor = QPlainTextEdit(value)
        self.editor.setPlainText(value)
        self.editor.setAccessibleName("Descripción personalizada")
        layout.addWidget(self.editor, 1)
        self.counter = QLabel()
        self.counter.setAlignment(Qt.AlignRight)
        layout.addWidget(self.counter)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.save_button = self.buttons.button(QDialogButtonBox.Save)
        self.save_button.setText("Guardar")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.editor.textChanged.connect(self._refresh_counter)
        self._refresh_counter()

    def value(self) -> str:
        return self.editor.toPlainText()

    def _refresh_counter(self) -> None:
        length = len(self.editor.toPlainText())
        self.counter.setText(f"{length}/{MAX_PERSONAL_DESCRIPTION_LENGTH} caracteres")
        self.save_button.setEnabled(length <= MAX_PERSONAL_DESCRIPTION_LENGTH)


class PersonalizedDescriptionControl(QWidget):
    """Editor reutilizable de una descripción privada, mostrado como texto plano."""

    def __init__(
        self,
        standard_description: str = "",
        preference_key: str | None = None,
        *,
        label_object_name: str = "ModuleDescription",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._standard_description = standard_description
        self._preference_key = preference_key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.description_label = QLabel()
        self.description_label.setObjectName(label_object_name)
        self.description_label.setTextFormat(Qt.PlainText)
        self.description_label.setWordWrap(True)
        self.description_label.setMinimumWidth(0)
        layout.addWidget(self.description_label, 1)
        self.edit_button = QPushButton()
        self.edit_button.setObjectName("DescriptionEditButton")
        self.edit_button.clicked.connect(self.edit_description)
        layout.addWidget(self.edit_button, 0, Qt.AlignTop)
        self.restore_button = QPushButton("Restaurar descripción estándar")
        self.restore_button.setObjectName("DescriptionRestoreButton")
        self.restore_button.clicked.connect(self.restore_standard_description)
        layout.addWidget(self.restore_button, 0, Qt.AlignTop)
        self.configure(standard_description, preference_key)

    def configure(self, standard_description: str, preference_key: str | None) -> None:
        self._standard_description = standard_description
        self._preference_key = preference_key
        self._refresh()

    def move_actions_to(self, target_layout: QLayout) -> None:
        """Keep personalisation in one stable secondary menu, at either density."""
        self._external_actions = True
        self._ensure_actions_menu()
        self.layout().removeWidget(self._actions_menu)
        target_layout.addWidget(self._actions_menu, 0, Qt.AlignVCenter)
        self._refresh()

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self._ensure_actions_menu()
        self._refresh()

    def _ensure_actions_menu(self) -> None:
        if not hasattr(self, "_actions_menu"):
            self._actions_menu = ActionMenuButton(self, accessible_name="Personalizar descripción")
            self._actions_menu.setText("Opciones")
            self._actions_menu.add_action("Editar descripción", self.edit_description)
            self._restore_action = self._actions_menu.add_action("Restaurar descripción estándar", self.restore_standard_description)
            self.layout().addWidget(self._actions_menu, 0, Qt.AlignTop)

    def edit_description(self) -> None:
        if not self._preference_key:
            return
        dialog = DescriptionEditorDialog(personal_description(self._preference_key), self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            save_personal_description(self._preference_key, dialog.value())
        except ValueError as exc:
            dialog.editor.setFocus()
            dialog.counter.setText(str(exc))
            return
        self._refresh()

    def restore_standard_description(self) -> None:
        if not self._preference_key or not personal_description(self._preference_key):
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Restaurar descripción estándar")
        dialog.setStyleSheet(base_qss())
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("¿Quieres eliminar tu descripción personalizada y restaurar la estándar?"))
        buttons = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        buttons.button(QDialogButtonBox.Yes).setText("Restaurar")
        buttons.button(QDialogButtonBox.No).setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            remove_personal_description(self._preference_key)
            self._refresh()

    def _refresh(self) -> None:
        customized = personal_description(self._preference_key) if self._preference_key else ""
        self.description_label.setText(customized or self._standard_description)
        self.description_label.setToolTip(customized or self._standard_description)
        self.edit_button.setText("Editar descripción" if customized else "Añadir descripción")
        menu_mode = getattr(self, '_external_actions', False) or getattr(self, '_compact', False)
        self.edit_button.setVisible(bool(self._preference_key) and not menu_mode)
        self.restore_button.setVisible(bool(customized) and not menu_mode)
        if hasattr(self, '_actions_menu'):
            self._actions_menu.setVisible(bool(self._preference_key) and menu_mode)
            self._restore_action.setEnabled(bool(customized))


def migrate_control_recepcion_precintos_header() -> None:
    """Traslada la clave inicial al nuevo ámbito de cabecera, sin sobrescribir datos."""
    migrate_personal_description(
        "control_recepcion_precintos.description",
        header_description_key("control_recepcion_precintos"),
    )
