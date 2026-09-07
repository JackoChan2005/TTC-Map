"""One writer across the server and CLI on a single Windows/Unix host."""

from contextlib import contextmanager

from filelock import FileLock, SoftFileLock

from ttcmap.config import get_settings


@contextmanager
def refresh_lock():
    path = get_settings().database_path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".refresh.lock", timeout=0)
    if isinstance(lock, SoftFileLock):
        raise RuntimeError("Refresh requires native OS file locking")
    with lock:
        yield
