"""Detect prolonged active-engine stalls from bounded, content-free counters.

Generation counters include reasoning tokens. Idle engines are never restarted
for inactivity. The 10-minute default exceeds the measured full-context prefill
by a wide margin; it is an operational bound, not a per-token latency promise.
"""
import math
import time
import urllib.request


def read_progress():
    with urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=2) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('Metrics limit exceeded')
    names = ('num_requests_running', 'prompt_tokens_total', 'generation_tokens_total')
    values, found = dict.fromkeys(names, 0.), set()
    for line in raw.decode('utf-8').splitlines():
        for name in names:
            if line.startswith('vllm:' + name + '{'):
                value = float(line.split()[-1])
                if not math.isfinite(value) or value < 0:
                    raise ValueError('Invalid engine progress counter')
                values[name] += value
                found.add(name)
    if len(found) != len(names):
        raise ValueError('Missing engine progress counters')
    return values['num_requests_running'] > 0, (values['prompt_tokens_total'], values['generation_tokens_total'])


class ProgressWatchdog:
    def __init__(self, diagnostics, timeout=600, reader=read_progress, clock=time.monotonic):
        if not math.isfinite(timeout) or not 180 <= timeout <= 3600:
            raise ValueError('Engine stall limit must be 180–3600 seconds')
        self.diagnostics, self.timeout, self.reader, self.clock = diagnostics, timeout, reader, clock
        self.next_poll, self.last_progress = 0., None
        self.counters, self.active, self.ready, self.error_reported = None, False, False, False

    def stalled(self):
        now = self.clock()
        if now < self.next_poll:
            return False
        self.next_poll = now + 10
        try:
            active, counters = self.reader()
        except (OSError, ValueError, UnicodeError):
            if self.ready and not self.error_reported:
                self.diagnostics.emit('metrics_unavailable')
                self.error_reported = True
            # Missing metrics alone never restarts an idle engine. An already
            # active request still has its last confirmed progress deadline.
        else:
            self.error_reported = False
            if not self.ready:
                self.ready = True
                self.diagnostics.emit('ready')
            if not active or not self.active or counters != self.counters:
                self.last_progress = now
            self.active, self.counters = active, counters
        if self.active and self.last_progress is not None and now - self.last_progress >= self.timeout:
            self.diagnostics.emit('progress_stalled', round(now - self.last_progress))
            return True
        return False
