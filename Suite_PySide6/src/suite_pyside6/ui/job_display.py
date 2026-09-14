"""A single persistent job indicator; workflow steps are not percentages."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QProgressBar, QBoxLayout, QScrollArea, QWidget, QVBoxLayout


class JobDisplay(QFrame):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setObjectName('JobDisplay')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.label = QLabel('Preparado')
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.PlainText)
        self.bar = QProgressBar()
        self.bar.setObjectName('JobProgressBar')
        self.bar.setMinimumWidth(96)
        self.bar.setMaximumWidth(160)
        self.bar.setFixedHeight(12)
        self.bar.setTextVisible(False)
        self.bar.setAccessibleName('Progreso del trabajo activo')
        self.percent = QLabel('—')
        self.percent.setMinimumWidth(40)
        self.percent.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cancel = QPushButton('Cancelar')
        self.cancel.setAccessibleName('Cancelar el trabajo antes de guardar')
        layout.addWidget(self.label, 1)
        layout.addWidget(self.bar)
        layout.addWidget(self.percent)
        layout.addWidget(self.cancel)
        self.cancel.clicked.connect(lambda: request_cancel(owner))
        self.maximum_percent = 0
        self.hide()

    def start(self, cancellable):
        self.maximum_percent = 0
        self.label.setText('Iniciando operación…')
        self.percent.setText('—')
        self.bar.setRange(0, 0)
        self.cancel.setEnabled(cancellable)
        self.show()

    def progress(self, value):
        if self.owner.property('jobState') == 'cancelling':
            return
        count = '' if value.completed is None else f' · {value.completed}' + (f' de {value.total}' if value.total is not None else '') + f' {value.unit}'
        self.label.setText(value.phase + count)
        self.cancel.setEnabled(value.cancellable)
        if value.overall and value.total:
            self.maximum_percent = max(self.maximum_percent, min(99, int(value.completed * 100 / value.total)))
            self.bar.setRange(0, 100)
            self.bar.setValue(self.maximum_percent)
            self.percent.setText(f'{self.maximum_percent}%')
            self.bar.setFormat('%p%')
        elif not self.maximum_percent:
            self.bar.setRange(0, 0)
        self.bar.setToolTip('Avance global en unidades de trabajo, no estimación de tiempo.' if value.overall else 'Actividad: aún no hay un total global medible. Los contadores corresponden a la fase indicada.')

    def finish(self, state):
        self.cancel.setEnabled(False)
        self.bar.setRange(0, 100)
        self.bar.setValue(100 if state == 'succeeded' else self.maximum_percent)
        self.percent.setText('100%' if state == 'succeeded' else f'{self.maximum_percent}%')
        self.bar.setFormat('%p%' if state == 'succeeded' else 'Detenido')
        self.label.setText({'succeeded': 'Trabajo finalizado; revisa el resultado.', 'cancelled': 'Operación cancelada antes del guardado.', 'failed': 'Operación detenida; revisa el mensaje de error.'}.get(state, state))


def install_job_display(owner):
    existing = getattr(owner, '_job_display', None)
    if existing is not None:
        return existing
    central = getattr(owner, 'centralWidget', lambda: None)()
    if central is None:
        return None
    layout = central.layout()
    # Keep the job indicator outside scroll areas and multi-mode stacks.
    if not isinstance(layout, QBoxLayout) or isinstance(central, QScrollArea):
        content = owner.takeCentralWidget()
        central = QWidget(owner)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content, 1)
        owner.setCentralWidget(central)
    display = JobDisplay(owner)
    layout.insertWidget(0, display)
    for bar in owner.findChildren(QProgressBar):
        if bar is not display.bar:
            # Legacy bars represent workflow stages, not measured processing.
            bar.hide()
            bar.setAccessibleDescription('Etapas del flujo; avance real en el indicador del trabajo.')
    owner._job_display = display
    legacy_cancel = getattr(owner, 'cancel_button', None)
    if legacy_cancel is not None:
        legacy_cancel.hide()
    return display


def request_cancel(owner):
    context = getattr(owner, '_job_context', None)
    if context is None or not owner.property('operationActive'):
        return False
    display = getattr(owner, '_job_display', None)
    if context.cancel():
        owner.setProperty('jobState', 'cancelling')
        if display:
            display.label.setText('Cancelación solicitada; esperando el siguiente punto seguro…')
            display.cancel.setEnabled(False)
    elif display:
        display.label.setText('Guardado en curso: se terminará la verificación antes de cerrar.')
    return True
