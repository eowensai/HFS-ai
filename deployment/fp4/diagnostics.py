"""Bounded engine metadata. Raw model logs must never enter this module."""
from collections import deque
import json
import os
from pathlib import Path
import threading
import time

CODES = frozenset({'starting', 'model_verified', 'model_invalid', 'ready', 'stopping',
                  'oom', 'cuda_error', 'worker_failed', 'engine_failed', 'assertion',
                  'child_exit', 'progress_stalled', 'metrics_unavailable', 'native_prefill'})

class Diagnostics:
    def __init__(self, path='/tmp/ephemerai/engine-state.json', limit=128):
        self.path = Path(path)
        self.events = deque(maxlen=limit)
        self.started = time.monotonic()
        self.lock = threading.Lock()

    def emit(self, code, number=None):
        if code not in CODES or (number is not None and type(number) not in (int, float)):
            raise ValueError('Diagnostic schema rejected')
        if number is not None and not (-1e15 < number < 1e15):
            raise ValueError('Invalid diagnostic number')
        event = {'event': code, 'elapsed_seconds': round(time.monotonic()-self.started, 3)}
        if number is not None:
            event['number'] = number
        with self.lock:
            self.events.append(event)
            payload = json.dumps({'schema': 1, 'events': list(self.events)}, separators=(',', ':'))
            # Only an allowlisted code and bounded numbers reach stdout or tmpfs.
            print(json.dumps(event, separators=(',', ':')), flush=True)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(payload)
                os.replace(temporary, self.path)
            except OSError:
                # An unwritable diagnostic volume must not leak raw exception data
                # or prevent a healthy model from running.
                pass

def classify_fatal(line):
    if b'ERROR' not in line:
        return None
    for marker, code in ((b'torch.OutOfMemoryError:', 'oom'),
                         (b'INTERNAL ASSERT FAILED', 'assertion'),
                         (b'CUDA error:', 'cuda_error'),
                         (b'WorkerProc hit an exception', 'worker_failed'),
                         (b'EngineCore failed to start', 'engine_failed'),
                         (b'EngineCore encountered a fatal error', 'engine_failed')):
        if marker in line:
            return code
    return None
