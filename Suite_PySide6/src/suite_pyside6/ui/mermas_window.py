from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.mermas import MermasResult, process_mermas, save_mermas_excel
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.file_dialogs import open_file, open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window
from suite_pyside6.ui.theme import base_qss


class MermasWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.final_files: list[Path] = []
        self.origin_file: Path | None = None
        self.result = MermasResult()
        self.show_dialogs = True
        self.setWindowTitle("Merma Jamones FAC")
        self.resize(1120, 720)
        self.setMinimumSize(720, 540)
        icon_path = resource_path("ICONO_SUITE.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(base_qss())
        self._build_ui()
        polish_window(self)
        self._refresh()

    def flow_steps(self) -> tuple[str, ...]:
        return ("Cargar finales", "Cargar origen", "Procesar", "Guardar Excel")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("Merma Jamones FAC")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Carga CSV finales, cruza el origen y genera el Excel de resultado.")
        subtitle.setObjectName("WindowSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        steps = QLabel("1 Cargar finales  ->  2 Cargar origen  ->  3 Filtrar/procesar  ->  4 Guardar Excel")
        steps.setObjectName("StepBar")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("preserveButtonText", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(4, 4, 4, 4)
        actions_layout.setSpacing(7)

        entrada_label = QLabel("ENTRADA")
        entrada_label.setObjectName("GroupLabel")
        actions_layout.addWidget(entrada_label)

        self.final_button = QPushButton("Cargar CSVs finales")
        self.final_button.setProperty("primary", True)
        self.final_button.clicked.connect(self.select_final_files)
        actions_layout.addWidget(self.final_button)

        self.origin_button = QPushButton("Cargar origen")
        self.origin_button.clicked.connect(self.select_origin_file)
        actions_layout.addWidget(self.origin_button)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["SI", "NO", "TODOS"])
        actions_layout.addWidget(self.filter_combo)

        proceso_label = QLabel("PROCESO")
        proceso_label.setObjectName("GroupLabel")
        actions_layout.addWidget(proceso_label)

        self.process_button = QPushButton("Procesar cruce")
        self.process_button.clicked.connect(self.process_files)
        actions_layout.addWidget(self.process_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        actions_layout.addWidget(salida_label)

        self.save_button = QPushButton("Guardar Excel")
        self.save_button.clicked.connect(self.save_dialog)
        actions_layout.addWidget(self.save_button)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        layout.addWidget(self.summary)

        panel = QFrame()
        panel.setObjectName("AppCard")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 9, 12, 12)
        panel_title = QLabel("Vista previa del resultado")
        panel_title.setObjectName("SectionLabel")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(self.preview, 1)
        layout.addWidget(panel, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def select_final_files(self) -> None:
        files = open_files(
            self,
            "mermas/finales",
            "Selecciona archivos CSV finales",
            "Archivos CSV (*.csv);;Todos (*.*)",
        )
        if files:
            self.set_final_files(files)

    def select_origin_file(self) -> None:
        file = open_file(
            self,
            "mermas/origen",
            "Selecciona fichero origen",
            "Origen (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls);;Todos (*.*)",
        )
        if file:
            self.set_origin_file(file)

    def set_final_files(self, paths: list[Path]) -> None:
        self.final_files = list(paths)
        self.status.setText(f"{len(self.final_files)} archivo(s) final(es) cargado(s)")
        self._refresh(selected_only=True)

    def set_origin_file(self, path: Path) -> None:
        self.origin_file = path
        self.status.setText(f"Origen cargado: {path.name}")
        self._refresh(selected_only=True)

    def process_files(self) -> None:
        if not self.final_files:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Primero selecciona uno o mas archivos CSV finales.")
            return
        if self.origin_file is None:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Primero selecciona el fichero origen.")
            return
        try:
            self.result = process_mermas(self.final_files, self.origin_file, self.filter_combo.currentText())  # type: ignore[arg-type]
        except Exception as exc:
            self.status.setText(f"Error: {exc}")
            if self.show_dialogs:
                show_inline_message(self, "error", str(exc))
            return
        self.status.setText(f"Proceso completado: {len(self.result.dataframe)} registros")
        self._refresh()

    def save_dialog(self) -> None:
        if self.result.dataframe.empty:
            if self.show_dialogs:
                show_inline_message(self, "warning", "No hay resultados para guardar.")
            return
        file = save_file(
            self,
            "mermas/export_excel",
            "Guardar resultado en Excel",
            "resultado_mermas.xlsx",
            "Excel (*.xlsx)",
        )
        if file:
            self.save_path(file)

    def save_path(self, path: Path) -> None:
        save_mermas_excel(path, self.result)
        self.status.setText(f"Archivo guardado correctamente: {path}")
        show_inline_message(self, "success", f"Archivo guardado correctamente: {path}")

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar seleccion"):
            return
        self.final_files = []
        self.origin_file = None
        self.result = MermasResult()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            lines = ["FICHEROS FINALES:"]
            lines.extend(str(path) for path in self.final_files)
            lines.append("")
            lines.append("FICHERO ORIGEN:")
            lines.append(str(self.origin_file) if self.origin_file else "")
            self.preview.setPlainText("\n".join(lines).strip())
            self.summary.setText(f"Finales: {len(self.final_files)} | Origen: {'si' if self.origin_file else 'no'}")
        else:
            self.summary.setText(
                " | ".join(self.result.summary.lines()[:4])
                if not self.result.dataframe.empty
                else "Sin archivos cargados"
            )
            self.preview.setPlainText(self.result.preview_text() if not self.result.dataframe.empty else "Selecciona archivos para empezar.")
        self.process_button.setEnabled(bool(self.final_files and self.origin_file))
        self.save_button.setEnabled(not self.result.dataframe.empty)
        self.clear_button.setEnabled(bool(self.final_files or self.origin_file or not self.result.dataframe.empty))

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if "error" in status:
            return 3, True, False
        if not self.result.dataframe.empty:
            return 4, False, False
        if self.final_files and self.origin_file:
            return 3, False, False
        if self.final_files:
            return 2, False, False
        if self.origin_file:
            return 1, True, False
        return 1, False, False
