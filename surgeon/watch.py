"""A single-process local check loop. Never invokes a paid model provider."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import fcntl
import io
import math
import os
import subprocess
import sys
import time

from .artifacts import persist
from .config import ROOT


def watch(args, run_mock):
    if not math.isfinite(args.interval) or args.interval < 10 or args.cycles < 0:
        raise ValueError("Watch interval must be at least 10 seconds; cycles must be >= 0.")
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    with (local / "watch.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another Database Surgeon watch process is already running.") from None
        state = {"pid": os.getpid(), "cycles": 0, "state": "starting", "provider": "mock"}
        def update(status, **details):
            state.update(state=status, updated_at=datetime.now(timezone.utc).isoformat(), **details)
            persist(local / "watch.json", state)
            print(f"{state['updated_at']} {status}", flush=True)
        try:
            while not args.cycles or state["cycles"] < args.cycles:
                state["cycles"] += 1
                update("testing", error=None)
                env = dict(os.environ, SURGEON_TEST_DATABASE="0")
                checks = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                (local / "watch-tests.log").write_text(checks.stdout + checks.stderr)
                if checks.returncode:
                    update("tests_failed", error="See .local/watch-tests.log")
                else:
                    try:
                        update("checking_database")
                        with redirect_stdout(io.StringIO()) as output:
                            directory, summary = run_mock(args)
                        (local / "watch-benchmark.log").write_text(output.getvalue())
                        if summary["errors"]:
                            update("benchmark_failed", error="See .local/watch-benchmark.log", last_run=str(directory))
                        else:
                            update("healthy", last_run=str(directory), last_success_at=datetime.now(timezone.utc).isoformat())
                    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
                        update("check_failed", error=str(exc))
                if not args.cycles or state["cycles"] < args.cycles:
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            update("stopped")
        except Exception as exc:
            update("failed", error=str(exc))
            raise
        else:
            update("finished", last_check=state["state"])
        return state
