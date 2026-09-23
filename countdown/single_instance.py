"""One running copy per user (R12: no second silent process, no double popups)."""
import logging
import os
import sys

log = logging.getLogger(__name__)

MUTEX_NAME = "Global\\CountdownRoExpiry_v1"

_handle = None
_file = None


def acquire() -> bool:
    """True when this process is the only one running."""
    global _handle, _file
    if sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        _handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS

    import fcntl
    from . import paths
    _file = open(paths.lock_path(), "w")
    try:
        fcntl.flock(_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    _file.write(str(os.getpid()))
    _file.flush()
    return True
