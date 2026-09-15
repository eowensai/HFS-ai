"""Protect retained identities and interruption-safe, single-engine transitions."""
import contextlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('selected_manager', ROOT / 'deployment/selected/manage.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


def row(name='engine', image='expected', running=True):
    return {'Id': name + '-id', 'Name': '/' + name, 'Image': image,
            'Config': {}, 'HostConfig': {}, 'State': {'Running': running, 'Health': {'Status': 'healthy'}}}


def test_identity_mismatch_refuses_replacement(monkeypatch):
    monkeypatch.setattr(manager, 'inspect', lambda _: row(image='wrong'))
    monkeypatch.setattr(manager, 'docker', lambda *a: pytest.fail('Mutation during identity check'))
    with pytest.raises(RuntimeError, match='Image identity'):
        manager.check_identity('engine', {'image': 'expected', 'compose': 'recover.json'}, {})


def test_existing_name_does_not_hide_config_change(monkeypatch):
    current = row()
    bound = {'engine': {'id': current['Id'], 'config_sha256': manager.fingerprint(current)}}
    current['HostConfig']['Memory'] = 123
    monkeypatch.setattr(manager, 'inspect', lambda _: current)
    with pytest.raises(RuntimeError, match='configuration changed'):
        manager.check_identity('engine', {'image': 'expected'}, bound)


def test_missing_retained_container_cannot_be_recreated(monkeypatch):
    monkeypatch.setattr(manager, 'inspect', lambda _: None)
    with pytest.raises(RuntimeError, match='Retained container is missing'):
        manager.check_identity('old-app', {'image': 'expected'}, {})


@pytest.mark.parametrize('names', [['foreign'], ['engine', 'other']])
def test_gpu_guard_rejects_foreign_or_multiple_engines(monkeypatch, names):
    rows = [{'Name': '/' + n, 'HostConfig': {'DeviceRequests': [{}]}} for n in names]
    monkeypatch.setattr(manager, 'docker', lambda *a: 'ids' if a[0] == 'ps' else json.dumps(rows))
    with pytest.raises(RuntimeError, match='Unexpected GPU'):
        manager.check_gpu({'engine', 'other'})


def test_start_healthy_retained_engine_has_no_start_or_recreate(monkeypatch):
    current = row()
    monkeypatch.setattr(manager, 'check_identity', lambda *a: current)
    monkeypatch.setattr(manager, 'healthy', lambda _: None)
    monkeypatch.setattr(manager, 'docker', lambda *a: pytest.fail('Running engine was operated'))
    manager.start_component({'name': 'engine', 'image': 'expected'}, {})


def test_transition_keeps_wanted_engine_and_records_intent_before_stop(tmp_path, monkeypatch):
    catalog = {
        'stable-prefix': {'app': {'name': 'new'}, 'engine': {'name': 'engine'}},
        'baseline': {'app': {'name': 'old'}, 'engine': {'name': 'engine'}},
    }
    monkeypatch.setattr(manager, 'LOCAL', tmp_path)
    monkeypatch.setattr(manager, 'profiles', lambda: catalog)
    monkeypatch.setattr(manager, 'bindings', lambda: {})
    monkeypatch.setattr(manager, 'check_identity', lambda *a: row())
    monkeypatch.setattr(manager, 'check_gpu', lambda _: ['engine'])
    monkeypatch.setattr(manager, 'idle', lambda _: None)
    stopped = []
    def stop(name):
        assert manager.read(tmp_path / 'selected-state.json') == {'profile': 'stable-prefix', 'phase': 'transitioning'}
        stopped.append(name)
    monkeypatch.setattr(manager, 'stop', stop)
    monkeypatch.setattr(manager, 'start_component', lambda *a: None)
    manager.select('stable-prefix')
    assert stopped == ['old']
    assert manager.read(tmp_path / 'selected-state.json')['phase'] == 'ready'


def test_adoption_failure_restores_baseline(monkeypatch):
    calls = []
    def select(profile):
        calls.append(profile)
        if profile == 'stable-prefix':
            raise RuntimeError('packaging fault')
    monkeypatch.setattr(manager, 'select', select)
    monkeypatch.setattr(manager, 'transition_lock', contextlib.nullcontext)
    monkeypatch.setattr('sys.argv', ['manage.py', 'adopt'])
    with pytest.raises(RuntimeError, match='packaging fault'):
        manager.main()
    assert calls == ['stable-prefix', 'baseline']


def test_start_resumes_persisted_transition(tmp_path, monkeypatch):
    manager.write(tmp_path / 'selected-state.json', {'profile': 'baseline', 'phase': 'transitioning'})
    monkeypatch.setattr(manager, 'LOCAL', tmp_path)
    monkeypatch.setattr(manager, 'transition_lock', contextlib.nullcontext)
    calls = []
    monkeypatch.setattr(manager, 'select', calls.append)
    monkeypatch.setattr('sys.argv', ['manage.py', 'start'])
    manager.main()
    assert calls == ['baseline']


def test_mtp_recovery_cannot_overwrite_selected_containers_or_cache():
    catalog = manager.profiles()
    stable, fallback = catalog['stable-prefix'], catalog['mtp']
    assert {stable[k]['name'] for k in ('app', 'engine')}.isdisjoint({fallback[k]['name'] for k in ('app', 'engine')})
    main = manager.read(ROOT / 'deployment/selected/engine.compose.json')
    mtp = manager.read(ROOT / 'deployment/selected/mtp.compose.json')
    assert main['volumes']['qualified-kernel-cache']['name'] != mtp['volumes']['qualified-kernel-cache']['name']
    assert catalog['baseline']['engine'] == stable['engine']
    for profile in catalog.values():
        assert profile['app']['image'].startswith('sha256:')
        assert profile['engine']['image'].startswith('sha256:')


def test_frozen_runtime_and_source_manifests():
    spec = importlib.util.spec_from_file_location('verify_selected', ROOT / 'scripts/verify_selected.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.source_checks()


def test_default_compose_selects_qualified_frontend_only():
    descriptor = 'deployment/selected/app.compose.json'
    root = (ROOT / 'docker-compose.yml').read_text()
    assert root.splitlines()[-2:] == ['include:', '  - ' + descriptor]
    app = manager.read(ROOT / descriptor)
    assert set(app['services']) == {'ephemeral-app'}
    assert app['services']['ephemeral-app']['image'] == manager.profiles()['stable-prefix']['app']['image']
