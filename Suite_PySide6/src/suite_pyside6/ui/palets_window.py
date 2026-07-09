from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from suite_pyside6.core.palets import PaletsResult, integrate_corrections, process_palets_files, validate_final_palets_text, write_palets_csv
from suite_pyside6.core.paths import resource_path
from suite_pyside6.ui.components import control_metric_pair, control_pill, control_rail_label, section_label, step_bar
from suite_pyside6.ui.file_dialogs import open_files, save_file
from suite_pyside6.ui.polish import confirm_discard_work, show_inline_message, polish_window, sync_recommended_action
from suite_pyside6.ui.table_utils import bulk_table_update, update_count_label
from suite_pyside6.ui.theme import base_qss


class PaletsWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[Path] = []
        self.result = PaletsResult()
        self.show_dialogs = True
        self.setWindowTitle("Palets PDA a CSV")
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
        return ("Cargar TXT", "Validar", "Corregir", "Guardar Stock01")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        hero = QFrame()
        hero.setObjectName("ControlProductHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        hero_layout.setSpacing(14)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(3)
        title = QLabel("Palets PDA a CSV")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Valida lecturas PDA, corrige incidencias y genera Stock01.csv.")
        subtitle.setObjectName("WindowSubtitle")
        subtitle.setWordWrap(True)
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)

        hero_status = QFrame()
        hero_status.setObjectName("ControlHeroStatus")
        hero_status_layout = QVBoxLayout(hero_status)
        hero_status_layout.setContentsMargins(10, 8, 10, 8)
        hero_status_layout.setSpacing(3)
        hero_status_label = QLabel("Stock01")
        hero_status_label.setObjectName("Overline")
        hero_status_value = QLabel("PDA a CSV")
        hero_status_value.setObjectName("ModuleTitle")
        hero_status_layout.addWidget(hero_status_label)
        hero_status_layout.addWidget(hero_status_value)
        hero_layout.addWidget(hero_status)
        layout.addWidget(hero)

        steps = step_bar("1 Cargar TXT  ->  2 Validar  ->  3 Corregir si hace falta  ->  4 Guardar Stock01")
        layout.addWidget(steps)

        actions = QFrame()
        actions.setObjectName("Toolbar")
        actions.setProperty("controlCommand", True)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(10, 8, 10, 8)
        actions_layout.setSpacing(8)

        command_panel = QFrame()
        command_panel.setObjectName("ControlCommandCopy")
        command_copy = QVBoxLayout(command_panel)
        command_copy.setContentsMargins(0, 0, 0, 0)
        command_copy.setSpacing(2)
        command_label = QLabel("Siguiente acción")
        command_label.setObjectName("Overline")
        self.command_hint = QLabel("Cargar TXT")
        self.command_hint.setObjectName("ControlCommandTitle")
        self.command_hint.setWordWrap(True)
        command_copy.addWidget(command_label)
        command_copy.addWidget(self.command_hint)
        actions_layout.addWidget(command_panel, 1)

        entrada_label = QLabel("ENTRADA")
        entrada_label.setObjectName("GroupLabel")
        entrada_label.setVisible(False)
        entrada_label.setMaximumSize(0, 0)
        actions_layout.addWidget(entrada_label)

        self.select_button = QPushButton("Cargar TXT")
        self.select_button.setProperty("primary", True)
        self.select_button.clicked.connect(self.select_files)
        actions_layout.addWidget(self.select_button)

        validacion_label = QLabel("VALIDACIÓN")
        validacion_label.setObjectName("GroupLabel")
        validacion_label.setVisible(False)
        validacion_label.setMaximumSize(0, 0)
        actions_layout.addWidget(validacion_label)

        self.process_button = QPushButton("Procesar palets")
        self.process_button.clicked.connect(self.process_selected_files)
        actions_layout.addWidget(self.process_button)

        self.revalidate_button = QPushButton("Revalidar")
        self.revalidate_button.clicked.connect(self.revalidate)
        actions_layout.addWidget(self.revalidate_button)

        salida_label = QLabel("SALIDA")
        salida_label.setObjectName("GroupLabel")
        salida_label.setVisible(False)
        salida_label.setMaximumSize(0, 0)
        actions_layout.addWidget(salida_label)

        self.save_button = QPushButton("Guardar CSV")
        self.save_button.clicked.connect(self.save_csv_dialog)

        self.clear_button = QPushButton("Limpiar")
        self.clear_button.clicked.connect(self.clear)
        actions_layout.addWidget(self.clear_button)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        self.summary = QLabel("Sin archivos cargados")
        self.summary.setObjectName("ResultLabel")
        layout.addWidget(self.summary)

        workspace = QFrame()
        workspace.setObjectName("ControlPilotWorkspace")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(10)

        preview_panel = QFrame()
        preview_panel.setObjectName("ControlPreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 10, 12, 10)
        preview_layout.setSpacing(8)
        preview_header = QHBoxLayout()
        preview_header.setSpacing(8)
        preview_title = section_label("Lecturas y CSV final")
        self.preview_count = control_pill("0 registros")
        preview_header.addWidget(preview_title)
        preview_header.addStretch(1)
        preview_header.addWidget(self.preview_count)

        self.metrics_strip = QFrame()
        self.metrics_strip.setObjectName("ControlMetricStrip")
        metrics_layout = QGridLayout(self.metrics_strip)
        metrics_layout.setContentsMargins(8, 7, 8, 7)
        metrics_layout.setHorizontalSpacing(8)
        metrics_layout.setVerticalSpacing(4)
        self.metric_files = control_metric_pair(metrics_layout, 0, "Archivos", "0")
        self.metric_valid = control_metric_pair(metrics_layout, 1, "Válidas", "0")
        self.metric_issues = control_metric_pair(metrics_layout, 2, "Incidencias", "0")
        self.metric_output = control_metric_pair(metrics_layout, 3, "Stock01", "0")

        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setAccessibleName("Lecturas PDA y resultado Stock01")
        self.preview_table.setHorizontalHeaderLabels(["#", "Código", "Estado"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.preview_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.preview = QPlainTextEdit()
        self.preview.setObjectName("OutputText")
        self.preview.setAccessibleName("Resumen textual de validación de palets")
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setMaximumHeight(110)

        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.metrics_strip)
        preview_layout.addWidget(self.preview_table, 1)

        rail = QFrame()
        rail.setObjectName("ControlStatusRail")
        rail.setMinimumWidth(245)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(12, 10, 12, 10)
        rail_layout.setSpacing(9)
        rail_title = section_label("Control de validación")
        self.rail_state = control_rail_label("Pendiente de TXT", role="state")
        self.rail_state.setWordWrap(True)
        self.rail_detail = control_rail_label("Carga TXT de PDA para validar lecturas de palets.")
        self.rail_detail.setWordWrap(True)
        self.rail_progress = QProgressBar()
        self.rail_progress.setObjectName("ControlProgress")
        self.rail_progress.setRange(0, 100)
        self.rail_progress.setTextVisible(True)
        next_title = section_label("Siguiente acción")
        self.rail_next = control_rail_label("Cargar TXT", role="action")
        self.rail_next.setWordWrap(True)
        files_title = section_label("Archivos")
        self.rail_files = control_rail_label("Sin archivos seleccionados")
        self.rail_files.setWordWrap(True)
        review_title = section_label("Corrección / CSV final")
        self.review = QPlainTextEdit()
        self.review.setObjectName("OutputText")
        self.review.setAccessibleName("Corrección de incidencias y CSV final")
        self.review.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.review.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.review.setMinimumHeight(120)
        self.review.textChanged.connect(self._mark_manual_edit)
        rail_layout.addWidget(rail_title)
        rail_layout.addWidget(self.rail_state)
        rail_layout.addWidget(self.rail_detail)
        rail_layout.addWidget(self.rail_progress)
        rail_layout.addWidget(next_title)
        rail_layout.addWidget(self.rail_next)
        rail_layout.addWidget(files_title)
        rail_layout.addWidget(self.rail_files)
        rail_layout.addWidget(self.save_button)
        rail_layout.addWidget(review_title)
        rail_layout.addWidget(self.review, 1)

        workspace_layout.addWidget(preview_panel, 5)
        workspace_layout.addWidget(rail, 2)
        layout.addWidget(workspace, 1)

        self.status = QLabel("Sin archivos cargados")
        self.status.setObjectName("StatusLabel")
        self.status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status)

        self.setCentralWidget(root)

    def set_files(self, paths: list[Path]) -> None:
        self.paths = list(paths)
        self.result = PaletsResult(selected_files=self.paths)
        self.status.setText(f"{len(self.paths)} archivos cargados.")
        self._refresh(selected_only=True)

    def select_files(self) -> None:
        files = open_files(
            self,
            "palets/input",
            "Selecciona archivos TXT de PDA",
            "Archivos TXT (*.txt);;Todos (*.*)",
        )
        if files:
            self.set_files(files)

    def process_selected_files(self) -> None:
        if not self.paths:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Carga primero uno o varios archivos TXT.")
            return
        self.result = process_palets_files(self.paths)
        self.status.setText(self.result.summary())
        self._refresh()
        if self.result.pending_correction and self.show_dialogs:
            show_inline_message(self, "warning", "Hay códigos que requieren corrección antes de guardar.")

    def revalidate(self) -> None:
        if self.result.pending_correction:
            updated, invalid = integrate_corrections(self.result.valid_base, self.result.issues, self.review.toPlainText())
            updated.selected_files = list(self.paths)
            if invalid:
                self.result = updated
                self.status.setText(f"Quedan {len(invalid)} códigos por corregir.")
                self._refresh_pilot_state()
                self._sync_recommended_action()
                if self.show_dialogs:
                    show_inline_message(self, "warning", "Aún quedan códigos con formato incorrecto.")
                return
            self.result = updated
            self.status.setText("Validación completada. Los códigos corregidos ya están integrados.")
            self._refresh()
            return

        palets, invalid = validate_final_palets_text(self.review.toPlainText())
        if invalid:
            self.status.setText("Hay palets modificados con formato incorrecto.")
            self._refresh_pilot_state()
            self._sync_recommended_action()
            if self.show_dialogs:
                show_inline_message(self, "error", "Hay líneas con formato CSV incorrecto.")
            return
        self.result.final_palets = palets
        self.result.detected = ["00" + pallet for pallet in palets]
        self.status.setText("Revalidación correcta. Ya puedes guardar el CSV.")
        self._refresh()

    def save_csv_dialog(self) -> None:
        if self.result.pending_correction:
            if self.show_dialogs:
                show_inline_message(self, "warning", "Revalida antes de guardar.")
            return
        if not self.result.final_palets:
            if self.show_dialogs:
                show_inline_message(self, "warning", "No hay datos procesados para guardar.")
            return
        file = save_file(
            self,
            "palets/export_csv",
            "Guardar CSV final",
            "Stock01.csv",
            "CSV (*.csv);;Todos (*.*)",
        )
        if file:
            self.save_csv_path(file)

    def save_csv_path(self, path: Path) -> None:
        write_palets_csv(path, self.result.final_palets)
        self.status.setText(f"CSV guardado: {path}")
        show_inline_message(self, "success", f"CSV guardado: {path.name}")
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def clear(self) -> None:
        if not confirm_discard_work(self, "Limpiar selección"):
            return
        self.paths = []
        self.result = PaletsResult()
        self.status.setText("Sin archivos cargados")
        self._refresh()

    def _refresh(self, *, selected_only: bool = False) -> None:
        if selected_only:
            self.summary.setText(f"{len(self.paths)} archivos seleccionados")
            self.preview.setPlainText("Archivos seleccionados:\n\n" + "\n".join(str(path) for path in self.paths))
            self._set_review_text("Sin incidencias por revisar. Procesa los archivos para validar las lecturas.", editable=False)
            self._fill_preview_table(empty=True)
        else:
            self.summary.setText(self.result.summary())
            self.preview.setPlainText(
                self.result.preview_text()
                if self.result.selected_files
                else "Arrastra TXT de PDA aquí o carga TXT para empezar.\n\nSe validarán las incidencias antes de generar Stock01."
            )
            if self.result.pending_correction:
                self._set_review_text(self.result.correction_text(), editable=True)
            elif self.result.final_palets:
                self._set_review_text("\n".join(self.result.final_palets), editable=True)
            else:
                self._set_review_text("La revisión y el CSV final aparecerán aquí después de procesar.", editable=False)
            self._fill_preview_table()

        self.process_button.setEnabled(bool(self.paths) and not self.result.pending_correction)
        self.revalidate_button.setEnabled(bool(self.result.pending_correction or self.result.final_palets))
        self.save_button.setEnabled(bool(self.result.final_palets) and not self.result.pending_correction)
        self.clear_button.setEnabled(bool(self.paths or self.result.final_palets or self.result.issues))
        self._refresh_pilot_state()
        self._sync_recommended_action()

    def _fill_preview_table(self, *, empty: bool = False) -> None:
        with bulk_table_update(self.preview_table):
            self.preview_table.setRowCount(0)
            if empty:
                return
            rows: list[tuple[str, str]] = []
            if self.result.pending_correction:
                rows.extend((code[2:], "Válido automático") for code in self.result.valid_base[:200])
                rows.extend((issue.cleaned or issue.original, "Revisar") for issue in self.result.issues[:80])
            elif self.result.final_palets:
                rows.extend((pallet, "Stock01") for pallet in self.result.final_palets[:250])
            elif self.result.detected:
                rows.extend((code[2:] if code.startswith("00") else code, "Lectura") for code in self.result.detected[:250])
            else:
                return
            self.preview_table.setRowCount(len(rows))
            for row_index, (code, state) in enumerate(rows):
                number_item = QTableWidgetItem(str(row_index + 1))
                number_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                code_item = QTableWidgetItem(code)
                code_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                state_item = QTableWidgetItem(state)
                state_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.preview_table.setItem(row_index, 0, number_item)
                self.preview_table.setItem(row_index, 1, code_item)
                self.preview_table.setItem(row_index, 2, state_item)

    def _refresh_pilot_state(self) -> None:
        file_count = len(self.paths or self.result.selected_files)
        valid_count = len(self.result.valid_base) if self.result.pending_correction else len(self.result.detected)
        issue_count = len(self.result.issues)
        output_count = len(self.result.final_palets)
        self.metric_files.setText(str(file_count))
        self.metric_valid.setText(str(valid_count))
        self.metric_issues.setText(str(issue_count))
        self.metric_output.setText(str(output_count))
        for label, value in (
            (self.metric_files, file_count),
            (self.metric_valid, valid_count),
            (self.metric_issues, issue_count),
            (self.metric_output, output_count),
        ):
            label.setAccessibleDescription(f"{label.accessibleName()}: {value}")

        table_count = issue_count + valid_count if self.result.pending_correction else output_count
        update_count_label(self.preview_count, self.preview_table.rowCount(), table_count, "registros")
        state, detail, progress = self._pilot_state_text()
        self.rail_state.setText(state)
        self.rail_state.setAccessibleDescription(f"Estado actual: {state}. {detail}")
        self.rail_detail.setText(detail)
        self.rail_progress.setValue(progress)
        self.rail_progress.setAccessibleName("Progreso de validación de palets")
        self.rail_progress.setAccessibleDescription(f"Progreso estimado del proceso: {progress} por ciento.")
        self.rail_next.setText(self._next_action_text())
        self.rail_next.setAccessibleDescription(f"Siguiente acción recomendada: {self.rail_next.text()}")
        if self.paths:
            shown = [path.name for path in self.paths[:4]]
            suffix = f"\n+{len(self.paths) - 4} más" if len(self.paths) > 4 else ""
            self.rail_files.setText("\n".join(shown) + suffix)
        else:
            self.rail_files.setText("Sin archivos seleccionados")

    def _pilot_state_text(self) -> tuple[str, str, int]:
        status = self.status.text().lower()
        if "guardado" in status:
            return "Stock01 guardado", "El CSV final se ha exportado correctamente.", 100
        if "no valido" in status or "formato incorrecto" in status or self.result.pending_correction:
            return "Corrección pendiente", "Revisa los códigos del panel lateral y revalida.", 65
        if self.result.final_palets:
            return "Stock01 listo", "Revisa el CSV final y guárdalo cuando esté correcto.", 85
        if self.paths:
            return "TXT cargados", "Procesa los TXT para validar lecturas de PDA.", 35
        return "Pendiente de TXT", "Carga TXT de PDA para validar lecturas de palets.", 0

    def _next_action_text(self) -> str:
        if not self.paths:
            return "Cargar TXT"
        if self.result.pending_correction or (("no valido" in self.status.text().lower() or "formato incorrecto" in self.status.text().lower()) and self.review.toPlainText().strip()):
            return "Revalidar"
        if not self.result.final_palets:
            return "Procesar palets"
        return "Guardar CSV"

    def _sync_recommended_action(self) -> None:
        next_text = self._next_action_text()
        sync_recommended_action(
            self,
            next_text,
            {
                "Cargar TXT": self.select_button,
                "Procesar palets": self.process_button,
                "Revalidar": self.revalidate_button,
                "Guardar CSV": self.save_button,
            },
            (self.select_button, self.process_button, self.revalidate_button, self.save_button, self.clear_button),
        )

    def _set_review_text(self, text: str, *, editable: bool) -> None:
        self.review.blockSignals(True)
        self.review.setPlainText(text)
        self.review.blockSignals(False)
        self.review.setReadOnly(not editable)

    def _mark_manual_edit(self) -> None:
        if self.result.final_palets and not self.result.pending_correction:
            self.revalidate_button.setEnabled(True)
            self.save_button.setEnabled(False)
            self.status.setText("Hay cambios en el CSV final. Revalida antes de guardar.")
            self._refresh_pilot_state()
            self._sync_recommended_action()

    def flow_state(self) -> tuple[int, bool, bool]:
        status = self.status.text().lower()
        if "guardado" in status:
            return 4, False, True
        if "no valido" in status or "formato incorrecto" in status or self.result.pending_correction:
            return 3, True, False
        if self.result.final_palets:
            return 4, False, False
        if self.paths:
            return 2, False, False
        return 1, False, False
