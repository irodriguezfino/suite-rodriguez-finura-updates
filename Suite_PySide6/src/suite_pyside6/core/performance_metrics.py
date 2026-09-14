"""Opt-in local timings: no paths, document contents or error messages."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import threading

_lock = threading.Lock()
_logger = None


def memory_snapshot():
    """Whole-process working set and peak, not a claimed per-job allocation."""
    if os.name != 'nt':
        return {}
    import ctypes
    from ctypes import wintypes as w
    class Counters(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('PageFaultCount', w.DWORD)] + [(name, ctypes.c_size_t) for name in
            ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    api = ctypes.WinDLL('psapi', use_last_error=True)
    api.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Counters), w.DWORD]
    if not api.GetProcessMemoryInfo(w.HANDLE(-1), ctypes.byref(counters), counters.cb):
        return {}
    return {'working_set_bytes': counters.WorkingSetSize, 'peak_working_set_bytes': counters.PeakWorkingSetSize}


def record_job_details(component, context):
    if os.environ.get('SUITE_PERFORMANCE_LOG') != '1':
        return
    try:
        import json
        # Phase labels may contain user file names. Log only ordinal IDs.
        phases = {str(index): round(seconds, 6) for index, seconds in enumerate(context.timings.values(), 1)}
        payload = {'component': component, 'phases_seconds': phases, **memory_snapshot()}
        if _logger:
            _logger.info('%s', json.dumps(payload))
    except (OSError, ValueError):
        pass


def record_duration(component: str, seconds: float, outcome: str) -> None:
    global _logger
    if os.environ.get('SUITE_PERFORMANCE_LOG') != '1':
        return
    try:
        with _lock:
            if _logger is None:
                root = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('TEMP') or '.') / 'RodriguezFinura' / 'Suite' / 'diagnostics'
                root.mkdir(parents=True, exist_ok=True)
                _logger = logging.getLogger('suite.performance')
                _logger.propagate = False
                _logger.setLevel(logging.INFO)
                handler = RotatingFileHandler(root/'timings.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')
                handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
                _logger.addHandler(handler)
            _logger.info('component=%s seconds=%.6f outcome=%s', component, seconds, outcome)
    except OSError:
        # A diagnostic log must never prevent a successful user operation.
        pass
