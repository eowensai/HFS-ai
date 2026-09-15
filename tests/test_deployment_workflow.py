"""Protect production isolation and immutable provisioning contracts."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deployment_workflow', ROOT / 'scripts/deployment.py')
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


def test_start_refuses_another_gpu_installation(monkeypatch):
    monkeypatch.setattr(deployment, 'other_gpu_containers', lambda _: ['production'])
    monkeypatch.setattr(deployment, 'compose', lambda *a: pytest.fail('Touched Compose'))
    monkeypatch.setattr('sys.argv', ['deployment.py', 'start', 'fp4'])
    with pytest.raises(SystemExit, match='Another GPU'):
        deployment.main()


def test_foreign_gpu_container_is_not_confused_with_own_project(monkeypatch):
    rows = [
        {'Name': 'own', 'HostConfig': {'DeviceRequests': [{}]},
         'Config': {'Labels': {'com.docker.compose.project': 'ephemerai-review-fp4'}}},
        {'Name': 'production', 'HostConfig': {'DeviceRequests': [{}]},
         'Config': {'Labels': {}}},
        {'Name': 'parser', 'HostConfig': {'DeviceRequests': None}, 'Config': {'Labels': {}}},
    ]
    monkeypatch.setattr(deployment, 'docker', lambda *a, **k: 'a b c' if a[0] == 'ps' else json.dumps(rows))
    assert deployment.other_gpu_containers('ephemerai-review-fp4') == ['production']


def test_existing_wrong_download_is_never_overwritten(tmp_path, monkeypatch):
    p = tmp_path / 'model'
    p.write_bytes(b'preserve existing bytes')
    monkeypatch.setattr(deployment.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('Network used'))
    with pytest.raises(ValueError, match='wrong identity'):
        deployment.download('https://example.invalid/model', p, '0' * 64)
    assert p.read_bytes() == b'preserve existing bytes'


def test_exact_ollama_manifest_and_small_blobs():
    import base64
    p = ROOT / 'deployment/ollama-manifest.json'
    profile = deployment.read('deployment/ollama-profile.json')
    assert hashlib.sha256(p.read_bytes()).hexdigest() == profile['manifest_sha256']
    manifest = json.loads(p.read_text())
    small = deployment.read('deployment/ollama-small-blobs.json')
    for item in [manifest['config'], *manifest['layers']]:
        if item['digest'] in small:
            value = base64.b64decode(small[item['digest']], validate=True)
            assert len(value) == item['size']
            assert hashlib.sha256(value).hexdigest() == item['digest'].split(':')[1]


def test_fp4_preserves_capacity_images_mtp_and_memory_profile():
    launch = deployment.read('deployment/fp4/launch.json')
    def option(name):
        return launch[launch.index(name) + 1]
    assert option('--max-model-len') == '131072'
    assert option('--tensor-parallel-size') == '1'
    assert option('--pipeline-parallel-size') == '2'
    assert option('--kv-cache-dtype') == 'fp8_e4m3'
    assert option('--kv-cache-memory-bytes') == '2952790016'
    assert json.loads(option('--limit-mm-per-prompt')) == {'image': 999, 'video': 0}
    assert json.loads(option('--speculative-config')) == {'method': 'mtp', 'num_speculative_tokens': 3}
    assert '--enable-prefix-caching' in launch
    assert option('--mamba-cache-mode') == 'align'


def test_placement_patch_and_wheels_are_hash_guarded():
    record = deployment.read('deployment/fp4/upstream-patch.json')
    assert deployment.sha(ROOT / 'deployment/fp4/qwen3_5.py') == record['patched_sha256']
    assert record['upstream_commit'] == '6fe67cbbf3e43da89bebf6ab0eeaca4ba6c75663'
    lock = (ROOT / 'deployment/fp4/requirements.lock').read_text()
    for wheel in deployment.read('deployment/fp4/wheels.json'):
        assert wheel['sha256'] in lock
        assert wheel['url'].startswith('https://')


def test_native_object_reuse_is_hash_guarded(tmp_path, monkeypatch):
    monkeypatch.setattr(deployment, 'LOCAL', tmp_path)
    data = b'qualified fixture'
    monkeypatch.setattr(deployment, 'read', lambda _: {'files': {'native-nhd.o': hashlib.sha256(data).hexdigest()}})
    target = tmp_path / 'native-rebuild/native-nhd.o'
    target.parent.mkdir()
    target.write_bytes(data)
    monkeypatch.setattr(deployment, 'docker', lambda *a, **k: pytest.fail('Unnecessary build'))
    assert deployment.prepare_native_object() == target.parent
    target.write_bytes(b'wrong')
    with pytest.raises(ValueError, match='differs'):
        deployment.prepare_native_object()


def test_missing_native_object_does_not_compile_beside_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(deployment, 'LOCAL', tmp_path)
    monkeypatch.setattr(deployment, 'read', lambda _: {'files': {'native-nhd.o': '0' * 64}})
    monkeypatch.setattr(deployment, 'other_gpu_containers', lambda _: ['running'])
    monkeypatch.setattr(deployment, 'docker', lambda *a, **k: pytest.fail('Touched Docker'))
    with pytest.raises(SystemExit, match='Stop inference explicitly'):
        deployment.prepare_native_object()


@pytest.mark.parametrize('backend,filename', [
    ('ollama', 'docker-compose.ollama-recovery.yml'),
    ('fp4', 'docker-compose.fp4.yml'),
])
def test_review_commands_cannot_select_existing_shared_stack(tmp_path, monkeypatch, backend, filename):
    monkeypatch.setattr(deployment, 'ROOT', tmp_path)
    monkeypatch.setattr(deployment, 'LOCAL', tmp_path / '.local')
    calls = []
    monkeypatch.setattr(deployment.subprocess, 'run', lambda argv, **kw: calls.append(argv))
    deployment.compose(backend, 'config')
    command = calls[0]
    assert command[command.index('-f') + 1] == str(tmp_path / filename)
    assert str(tmp_path / 'docker-compose.yml') not in command
