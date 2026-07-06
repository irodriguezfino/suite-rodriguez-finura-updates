from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)

from suite_pyside6.core.update import (
    UpdateCheckResult,
    check_for_updates,
    configured_version_url,
    diagnostic_text,
    local_version,
    start_update,
)
from suite_pyside6.ui.theme import base_qss


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result: UpdateCheckResult | None = None
        self.setWindowTitle("Acerca de")
        self.setMinimumSize(560, 430)
        self.setStyleSheet(base_qss())
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("AppBrandBar")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel("Suite Rodriguez Finura")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Panel operativo PySide6")
        subtitle.setObjectName("WindowSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        self.version = QLabel()
        self.version.setObjectName("ResultLabel")
        self.version.setWordWrap(True)
        layout.addWidget(self.version)

        self.status = QLabel()
        self.status.setObjectName("StatusLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.notes.setPlaceholderText("Las notas de la version remota apareceran aqui al buscar actualizaciones.")
        layout.addWidget(self.notes, 1)

        actions = QHBoxLayout()
        self.check_button = QPushButton("Buscar actualización")
        self.check_button.setProperty("primary", True)
        self.check_button.clicked.connect(self.check_updates)
        self.copy_button = QPushButton("Copiar diagnóstico")
        self.copy_button.clicked.connect(self.copy_diagnostic)
        actions.addWidget(self.check_button)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh(self) -> None:
        self.version.setText(
            f"Versión instalada: {local_version()}\n"
            f"Canal de actualización: {configured_version_url()}"
        )
        if self.result is None:
            self.status.setText("Pulsa Buscar actualización para consultar el canal remoto.")
            return
        remote = self.result.remote_version or "-"
        self.status.setText(f"{self.result.message}\nVersión remota: {remote}")
        self.notes.setPlainText(self.result.notes or "Sin notas publicadas para esta versión.")

    def check_updates(self) -> None:
        self.check_button.setEnabled(False)
        self.status.setText("Consultando GitHub...")
        QApplication.processEvents()
        self.result = check_for_updates()
        self._refresh()
        self.check_button.setEnabled(True)
        if not self.result.ok:
            QMessageBox.warning(self, "Actualizaciones", self.result.message)
            return
        if not self.result.update_available:
            QMessageBox.information(self, "Actualizaciones", self.result.message)
            return
        package = self.result.package
        if package is None:
            QMessageBox.warning(self, "Actualizaciones", "El manifiesto remoto no incluye paquete de actualización.")
            return
        text = (
            "Hay una actualización disponible.\n\n"
            f"Versión instalada: {self.result.local_version}\n"
            f"Versión disponible: {self.result.remote_version}\n\n"
            f"{self.result.notes}\n\n"
            "¿Quieres descargarla e instalarla ahora?"
        )
        answer = QMessageBox.question(self, "Actualizaciones", text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            start_update(package, self.result.remote_version)
        except Exception as exc:
            QMessageBox.warning(self, "Actualizaciones", f"No se pudo iniciar el actualizador:\n\n{exc}")
            return
        QMessageBox.information(self, "Actualizaciones", "Actualizador iniciado. La suite se abrirá después de actualizar.")

    def copy_diagnostic(self) -> None:
        QApplication.clipboard().setText(diagnostic_text(self.result))
        QMessageBox.information(self, "Diagnóstico", "Diagnóstico copiado al portapapeles.")
