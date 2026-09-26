"""store.py — atomic JSON/text writes and a cross-process lock for read-modify-write.

Every writer that can race with itself (a second request, a second process) should
route through here instead of calling .write_text()/json.dump() directly.
"""
import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path


def _replace_with_backup(tmp_path, dest):
    dest = Path(dest)
    bak = dest.with_suffix(dest.suffix + ".bak")
    if dest.exists():
        try:
            os.replace(dest, bak)
        except OSError:
            pass
    os.replace(tmp_path, dest)


def atomic_write_text(path, text):
    """Write text to path atomically: temp file in the same dir, flush+fsync, os.replace.
    Keeps one .bak of the prior contents."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        _replace_with_backup(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_json(path, obj, indent=1):
    atomic_write_text(path, json.dumps(obj, indent=indent))


@contextlib.contextmanager
def locked(path):
    """File lock (flock on path.lock) guarding a read-modify-write against another
    process or thread touching the same file. Usage:
        with locked(DONE):
            d = jload(DONE, {})
            ...
            atomic_write_json(DONE, d)
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    lock_path = dest.with_suffix(dest.suffix + ".lock")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
