"""Diagnostics must remain useful without persisting backend exception content."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'deployment/fp4'
spec = importlib.util.spec_from_file_location('fp4_diagnostics', SOURCE / 'diagnostics.py')
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
spec = importlib.util.spec_from_file_location('fp4_watchdog', SOURCE / 'watchdog.py')
watchdog_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog_module)


def test_bounded_events_never_copy_raw_exception_text(tmp_path, capsys):
    ring = diag.Diagnostics(tmp_path / 'engine-state.json', limit=3)
    private = b'ERROR torch.OutOfMemoryError: PRIVATE_PROMPT_AND_DOCUMENT'
    for _ in range(10):
        ring.emit(diag.classify_fatal(private))
    stored = (tmp_path / 'engine-state.json').read_text()
    assert len(json.loads(stored)['events']) == 3
    assert 'PRIVATE' not in stored + capsys.readouterr().out
    with pytest.raises(ValueError):
        ring.emit(private.decode())
    with pytest.raises(ValueError):
        ring.emit('child_exit', 'PRIVATE')


def test_nonfatal_text_does_not_trigger_restart():
    assert diag.classify_fatal(b'ordinary CUDA error: quoted text') is None
    assert diag.classify_fatal(b'WARNING model loading') is None
    assert diag.classify_fatal(b'ERROR WorkerProc hit an exception SECRET') == 'worker_failed'


def test_fatal_child_returns_restart_code_without_leaking(tmp_path, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, 'diagnostics', diag)
    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    spec = importlib.util.spec_from_file_location('fp4_supervise', SOURCE / 'supervise.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.supervise([sys.executable, '-u', '-c',
                            'import time; print("ERROR CUDA error: PRIVATE", flush=True); time.sleep(20)'],
                           diag.Diagnostics(tmp_path / 'state.json'))
    assert code == 70
    assert 'PRIVATE' not in capsys.readouterr().out + (tmp_path / 'state.json').read_text()


def test_watchdog_ignores_idle_and_counts_reasoning_progress(tmp_path):
    now, progress = [0.], [(False, (0., 0.))]
    ring = diag.Diagnostics(tmp_path/'state.json')
    w = watchdog_module.ProgressWatchdog(ring, reader=lambda:progress[0], clock=lambda:now[0])
    assert not w.stalled()
    now[0] = 10000
    assert not w.stalled(), 'Idle time is not a hung request'
    progress[0] = (True, (100., 0.))
    now[0] += 10
    assert not w.stalled()
    for _ in range(20):
        now[0] += 300
        progress[0] = (True, (100., progress[0][1][1]+100.))
        assert not w.stalled(), 'Hidden reasoning tokens constitute real progress'
    now[0] += 599
    assert not w.stalled()
    now[0] += 10
    assert w.stalled()
    assert ring.events[-1]['event'] == 'progress_stalled'


def test_missing_metrics_does_not_restart_idle_engine(tmp_path):
    now = [0.]
    def unavailable():
        raise OSError('SECRET request information must not be retained')
    ring = diag.Diagnostics(tmp_path/'state.json')
    w = watchdog_module.ProgressWatchdog(ring, reader=unavailable, clock=lambda:now[0])
    for _ in range(10):
        now[0] += 1000
        assert not w.stalled()
    assert not ring.events


def test_watchdog_stops_a_stuck_child_without_a_cuda_error(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'diagnostics', diag)
    monkeypatch.setitem(sys.modules, 'watchdog', watchdog_module)
    spec = importlib.util.spec_from_file_location('fp4_supervise_stall', SOURCE/'supervise.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class Stalled:
        def stalled(self):
            return True
    assert module.supervise([sys.executable, '-c', 'import time; time.sleep(30)'],
                            diag.Diagnostics(tmp_path/'state.json'), Stalled()) == 70
