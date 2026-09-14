"""A retained Windows handle identifies one helper, never a process-name kill."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
from pathlib import Path


class OwnedProcess:
    def __init__(self, pid: int, creation_time: int, executable: str):
        self.handle = None
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        api = self.api
        api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        api.OpenProcess.restype = w.HANDLE
        api.CloseHandle.argtypes = [w.HANDLE]
        api.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
        api.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
        api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        api.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        handle = api.OpenProcess(0x1000 | 0x100000 | 1, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            times = [w.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
                raise ctypes.WinError(ctypes.get_last_error())
            actual = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            name, size = ctypes.create_unicode_buffer(32768), w.DWORD(32768)
            if not api.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            if actual != creation_time or Path(name.value).name.casefold() != executable.casefold():
                raise ValueError('No coincide la identidad del proceso auxiliar; no se terminará.')
            self.handle = handle
        except BaseException:
            api.CloseHandle(handle)
            raise

    def terminate_if_running(self):
        if self.handle and self.api.WaitForSingleObject(self.handle, 1000) == 258:
            if not self.api.TerminateProcess(self.handle, 1):
                error = ctypes.get_last_error()
                # Excel may finish Quit between Wait and TerminateProcess.
                # Windows reports access denied for an already exited process.
                if self.api.WaitForSingleObject(self.handle, 1000) == 0:
                    return
                raise ctypes.WinError(error)
            self.api.WaitForSingleObject(self.handle, 5000)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
