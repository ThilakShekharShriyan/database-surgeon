"""Crash-safe experiment artifacts shared by the runner and reporting tools."""
import json
import os
import tempfile
import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def evaluation_lock(root):
    """Keep benchmarks in separate terminal processes from contaminating timings."""
    local = Path(root) / ".local"
    local.mkdir(parents=True, exist_ok=True)
    with (local / "evaluation.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another evaluation is running; wait for it to finish before benchmarking.") from None
        yield


def persist(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".pending-",
                                         delete=False, encoding="utf-8") as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
