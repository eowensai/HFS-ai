"""Run the pinned engine; discard raw logs and exit on fatal worker failure.

Docker's restart policy restarts this container after a nonzero exit. No Docker
socket, elevated host privileges, request log, or persisted crash output is used.
"""

import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

from diagnostics import Diagnostics, classify_fatal
from watchdog import ProgressWatchdog

def verify_files(root, manifest):
    for name, expected in manifest.items():
        p = root / name
        if not p.is_file() or p.stat().st_size != expected["bytes"]:
            raise ValueError("Model file identity mismatch")
        digest = hashlib.sha256()
        with p.open("rb") as stream:
            for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected["sha256"]:
            raise ValueError("Model file hash mismatch")


def supervise(command, diagnostics=None, watchdog=None):
    diagnostics = diagnostics or Diagnostics()
    watchdog = watchdog or ProgressWatchdog(diagnostics, float(os.environ.get('EPHEMERAI_ENGINE_STALL_SECONDS', '600')))
    diagnostics.emit("starting")
    child = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    stopping = False
    fatal = False
    deadline = None

    def stop(signum, frame):
        nonlocal stopping, deadline
        if not stopping:
            diagnostics.emit("stopping")
        stopping = True
        deadline = time.monotonic() + 20
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poller = selectors.DefaultSelector()
    poller.register(child.stdout, selectors.EVENT_READ)
    tail = b""
    native_seen = set()
    while child.poll() is None:
        if not stopping and watchdog.stalled():
            fatal = True
            stop(signal.SIGTERM, None)
        for key, _ in poller.select(timeout=1):
            chunk = os.read(key.fd, 8192)
            if not chunk:
                poller.unregister(key.fileobj)
                continue
            # Keep only a bounded rolling diagnostic window in memory. Never
            # forward model stdout/stderr: exception text can include inputs.
            combined = tail + chunk
            for device in (0, 1):
                marker = b'EPHEMERAI_NATIVE_READY_DEVICE_' + str(device).encode()
                if device not in native_seen and marker in combined:
                    diagnostics.emit('native_prefill', device)
                    native_seen.add(device)
            if not fatal:
                codes = [classify_fatal(line) for line in combined.splitlines()]
                code = next((code for code in codes if code is not None), None)
                if code is not None:
                    diagnostics.emit(code)
                    fatal = True
                    stop(signal.SIGTERM, None)
            tail = combined[-4096:]
        if (
            deadline is not None
            and time.monotonic() > deadline
            and child.poll() is None
        ):
            os.killpg(child.pid, signal.SIGKILL)
    poller.close()
    child.stdout.close()
    code = child.wait()
    diagnostics.emit("child_exit", code)
    if fatal:
        return 70
    return 0 if stopping else (code if code > 0 else 1)


def main():
    root = Path("/opt/ephemerai")
    diagnostics = Diagnostics()
    try:
        verify_files(
            Path("/models/radixark"),
            json.loads((root / "model-files.json").read_text()),
        )
        if (root / "draft-files.json").exists():
            verify_files(Path("/models/dflash"), json.loads((root / "draft-files.json").read_text()))
    except (OSError, ValueError, KeyError, TypeError):
        diagnostics.emit("model_invalid")
        return 78
    diagnostics.emit("model_verified")
    return supervise(json.loads((root / "launch.json").read_text()), diagnostics)


if __name__ == "__main__":
    raise SystemExit(main())
