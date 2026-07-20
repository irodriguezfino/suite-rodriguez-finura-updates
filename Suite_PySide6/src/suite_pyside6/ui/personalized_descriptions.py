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

from suite_pyside6.ui.components import configure_header_action
from suite_pyside6.ui.session import (
    MAX_PERSONAL_DESCRIPTION_LENGTH,
    migrate_personal_description,
    personal_description,
    remove_personal_description,
    save_personal_description,
)


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
        """Agrupa sus acciones con las demás acciones de la cabecera."""
        layout = self.layout()
        if layout is None:
            return
        for button in (self.edit_button, self.restore_button):
            layout.removeWidget(button)
            configure_header_action(button)
            target_layout.addWidget(button, 0, Qt.AlignVCenter)

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
        self.edit_button.setText("Editar descripción" if customized else "Añadir descripción")
        self.edit_button.setVisible(bool(self._preference_key))
        self.restore_button.setVisible(bool(customized))


def migrate_control_recepcion_precintos_header() -> None:
    """Traslada la clave inicial al nuevo ámbito de cabecera, sin sobrescribir datos."""
    migrate_personal_description(
        "control_recepcion_precintos.description",
        header_description_key("control_recepcion_precintos"),
    )
