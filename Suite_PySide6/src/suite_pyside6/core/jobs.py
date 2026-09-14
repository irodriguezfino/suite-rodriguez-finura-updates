"""Cooperative jobs independent from Qt; commits are never interrupted halfway."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from threading import Event, Lock
from time import monotonic


class JobState(str, Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    CANCELLING = 'cancelling'
    COMMITTING = 'committing'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class JobCancelled(BaseException):
    """Must not be swallowed by domain 'except Exception' error collection."""


@dataclass(frozen=True)
class JobProgress:
    phase: str
    completed: int | None = None
    total: int | None = None
    unit: str = ''
    overall: bool = False
    cancellable: bool = True


class JobContext:
    def __init__(self, report=None, *, cancellable=True, timeout=600):
        self.report = report
        self.cancel_event = Event()
        self.lock = Lock()
        self.cancellable = cancellable
        self.deadline = monotonic() + timeout
        self.started = monotonic()
        self.last_emit = 0.0
        self.last_phase = ''
        self.phase_started = self.started
        self.timings = {}

    def cancel(self):
        with self.lock:
            if not self.cancellable:
                return False
            self.cancel_event.set()
            return True

    def checkpoint(self):
        if self.cancellable and self.cancel_event.is_set():
            raise JobCancelled('Operación cancelada; no se ha iniciado el guardado.')
        if self.cancellable and monotonic() > self.deadline:
            raise TimeoutError('La operación superó su límite de duración; no se inició el guardado.')

    def emit(self, phase, completed=None, total=None, unit='', *, overall=False, force=False):
        self.checkpoint()
        now = monotonic()
        if phase != self.last_phase:
            if self.last_phase:
                self.timings[self.last_phase] = self.timings.get(self.last_phase, 0) + now-self.phase_started
            self.phase_started = now
        if force or phase != self.last_phase or now-self.last_emit >= 0.1:
            self.last_emit = now
            if self.report:
                self.report(JobProgress(phase, completed, total, unit, overall, self.cancellable))
        self.last_phase = phase

    def begin_commit(self):
        with self.lock:
            if not self.cancellable:
                return
            self.checkpoint()
            self.cancellable = False
        self.emit('Guardando y verificando — ya no se puede cancelar', force=True)


_current = ContextVar('suite_job', default=None)


@contextmanager
def job_scope(context):
    token = _current.set(context)
    try:
        context.checkpoint()
        yield context
    finally:
        _current.reset(token)


def checkpoint():
    context = _current.get()
    if context is not None:
        context.checkpoint()


def report_progress(phase, completed=None, total=None, unit='', *, overall=False):
    context = _current.get()
    if context is not None:
        context.emit(phase, completed, total, unit, overall=overall)


def begin_commit():
    context = _current.get()
    if context is not None:
        context.begin_commit()


def checked(iterable, *, phase='Procesando', total=None, unit='registros', start=0):
    """One checkpoint per item, throttled progress; never materializes inputs."""
    for count, value in enumerate(iterable, start+1):
        report_progress(phase, count-1, total, unit)
        checkpoint()
        yield value
