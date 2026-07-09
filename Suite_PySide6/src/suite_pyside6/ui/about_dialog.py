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

from suite_pyside6.core.paths import resource_path
from suite_pyside6.core.update import (
    UpdateCheckResult,
    check_for_updates,
    configured_version_url,
    diagnostic_text,
    local_version,
    start_update,
)
from suite_pyside6.ui.polish import brand_logo_pixmap
from suite_pyside6.ui.theme import base_qss


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result: UpdateCheckResult | None = None
        self.setWindowTitle("Acerca de")
        self.setAccessibleName("Diagnóstico y actualizaciones")
        self.setAccessibleDescription("Diálogo para consultar la versión instalada, buscar actualizaciones y copiar el diagnóstico.")
        self.setMinimumSize(560, 430)
        self.setStyleSheet(base_qss())
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("Panel")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(3)
        logo_row = QHBoxLayout()
        rodriguez = self._logo("RODRIGUEZ.png", 150, 42, "Rodríguez")
        if rodriguez is not None:
            logo_row.addWidget(rodriguez)
        logo_row.addStretch(1)
        finura = self._logo("FINURA.png", 86, 30, "Finura")
        if finura is not None:
            finura.setObjectName("BrandSeal")
            logo_row.addWidget(finura)
        header_layout.addLayout(logo_row)
        title = QLabel("Diagnostico y actualizaciones")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Consulta versión, canal remoto y estado del actualizador.")
        subtitle.setObjectName("WindowSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)

        self.version = QLabel()
        self.version.setObjectName("ResultLabel")
        self.version.setWordWrap(True)
        self.version.setAccessibleName("Información de versión")
        layout.addWidget(self.version)

        self.status = QLabel()
        self.status.setObjectName("StatusLabel")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Estado de actualización")
        layout.addWidget(self.status)

        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.notes.setPlaceholderText("Las notas de la versión remota aparecerán aquí al buscar actualizaciones.")
        self.notes.setAccessibleName("Notas de la versión remota")
        self.notes.setAccessibleDescription("Notas de la versión disponible o mensaje indicando que no hay notas publicadas.")
        layout.addWidget(self.notes, 1)

        actions = QHBoxLayout()
        self.check_button = QPushButton("Buscar actualización")
        self.check_button.setProperty("primary", True)
        self.check_button.setAccessibleName("Buscar actualización")
        self.check_button.setAccessibleDescription("Consulta el canal remoto para comprobar si hay una actualización disponible.")
        self.check_button.clicked.connect(self.check_updates)
        self.copy_button = QPushButton("Copiar diagnóstico")
        self.copy_button.setAccessibleName("Copiar diagnóstico")
        self.copy_button.setAccessibleDescription("Copia al portapapeles la información de diagnóstico de la instalación.")
        self.copy_button.clicked.connect(self.copy_diagnostic)
        actions.addWidget(self.check_button)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        if buttons.button(QDialogButtonBox.Close) is not None:
            buttons.button(QDialogButtonBox.Close).setAccessibleName("Cerrar")
            buttons.button(QDialogButtonBox.Close).setAccessibleDescription("Cierra el diálogo de diagnóstico y actualizaciones.")
        layout.addWidget(buttons)

    def _refresh(self) -> None:
        self.version.setText(
            f"Versión instalada: {local_version()}\n"
            f"Canal de actualización: {configured_version_url()}"
        )
        self.version.setAccessibleDescription(self.version.text())
        if self.result is None:
            self.status.setText("Busca una actualización para consultar el canal remoto.")
            self.status.setAccessibleDescription(self.status.text())
            return
        remote = self.result.remote_version or "-"
        self.status.setText(f"{self.result.message}\nVersión remota: {remote}")
        self.status.setAccessibleDescription(self.status.text())
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
        if not self._close_open_windows_for_update():
            return
        try:
            start_update(package, self.result.remote_version)
        except Exception as exc:
            QMessageBox.warning(self, "Actualizaciones", f"No se pudo iniciar el actualizador:\n\n{exc}")
            return
        self.accept()
        QApplication.processEvents()
        QApplication.quit()

    def copy_diagnostic(self) -> None:
        QApplication.clipboard().setText(diagnostic_text(self.result))
        QMessageBox.information(self, "Diagnóstico", "Diagnóstico copiado al portapapeles.")

    def _close_open_windows_for_update(self) -> bool:
        parent = self.parent()
        close_embedded = getattr(parent, "close_embedded_apps_for_update", None)
        if callable(close_embedded):
            return bool(close_embedded())
        open_windows = getattr(parent, "open_windows", {}) if parent is not None else {}
        for window in list(open_windows.values()):
            if not window.isVisible():
                continue
            window.close()
            QApplication.processEvents()
            if window.isVisible():
                QMessageBox.warning(
                    self,
                    "Actualizaciones",
                    "La actualización se ha cancelado porque hay una ventana con trabajo pendiente.",
                )
                return False
        return True

    @staticmethod
    def _logo(name: str, width: int, height: int, accessible_name: str) -> QLabel | None:
        path = resource_path(name)
        if not path.exists():
            return None
        pixmap = brand_logo_pixmap(path)
        if pixmap.isNull():
            return None
        label = QLabel()
        label.setObjectName("SidebarBrandLogo")
        label.setAccessibleName(accessible_name)
        label.setPixmap(pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        label.setMinimumHeight(height)
        return label
