"""Tiny fictional archives exercise recovery checks without Docker or real models."""
import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'recovery', Path(__file__).resolve().parents[1] / 'scripts/recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


@pytest.fixture
def model(monkeypatch):
    content = b'FICTIONAL miniature model fixture'
    sha = hashlib.sha256(content).hexdigest()
    descriptor = {'digest': 'sha256:' + sha, 'size': len(content)}
    manifest = json.dumps({'config': descriptor, 'layers': [descriptor]}).encode()
    lock = {'model_manifest_path': 'models/manifests/fictional/latest',
            'model_manifest_sha256': hashlib.sha256(manifest).hexdigest(),
            'images': {'ephemeral-app': {'ref': 'fictional:1', 'id': 'sha256:fictional'}}}
    monkeypatch.setattr(recovery, 'LOCK', lock)
    monkeypatch.setattr(recovery, 'MODEL_MANIFEST', manifest)
    return [(lock['model_manifest_path'], manifest), ('models/blobs/sha256-' + sha, content)]


def archive(tmp_path, entries, symlink=False):
    path = tmp_path / 'model.tar'
    with tarfile.open(path, 'w') as tar:
        for i, (name, content) in enumerate(entries):
            member = tarfile.TarInfo(name)
            if symlink and i == 0:
                member.type = tarfile.SYMTYPE
                member.linkname = '/outside'
                tar.addfile(member)
            else:
                member.size = len(content)
                tar.addfile(member, io.BytesIO(content))
    return path


def test_exact_fictional_archive_is_accepted(tmp_path, model):
    assert recovery.verify_model_archive(archive(tmp_path, model)) == 2


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'traversal', 'duplicate', 'symlink', 'size', 'hash'])
def test_model_archive_rejects_invalid_members(tmp_path, model, mutation):
    entries = list(model)
    if mutation == 'missing':
        entries.pop()
    elif mutation in ('extra', 'traversal'):
        entries.append(('unrequested' if mutation == 'extra' else '../../outside', b'fiction'))
    elif mutation == 'duplicate':
        entries.append(entries[0])
    elif mutation in ('size', 'hash'):
        name, content = entries[-1]
        entries[-1] = (name, content + b'x' if mutation == 'size' else b'X' * len(content))
    with pytest.raises(ValueError):
        recovery.verify_model_archive(archive(tmp_path, entries, symlink=mutation == 'symlink'))


def test_manifest_itself_must_match_lock(model, monkeypatch):
    monkeypatch.setattr(recovery, 'MODEL_MANIFEST', b'{}')
    with pytest.raises(ValueError, match='manifest identity'):
        recovery.expected_model_files()


@pytest.mark.parametrize('existing', ['container', 'volume'])
def test_restore_refuses_existing_runtime_before_any_mutation(tmp_path, model, monkeypatch, existing):
    calls = []

    def probe(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0 if args[1] == existing else 1)

    monkeypatch.setattr(recovery.subprocess, 'run', probe)
    monkeypatch.setattr(recovery, 'verify', lambda path: pytest.fail('Should stop before archive access'))
    monkeypatch.setattr(recovery, 'docker', lambda *args, **kw: pytest.fail('No Docker mutation is allowed'))
    with pytest.raises(ValueError, match='existing'):
        recovery.restore(tmp_path)
    assert all(args[2] == 'inspect' for args in calls)


def test_capture_refuses_existing_destination(tmp_path, model, monkeypatch):
    monkeypatch.setattr(recovery, 'docker', lambda *args, **kw: pytest.fail('No Docker call is allowed'))
    with pytest.raises(ValueError, match='new directory'):
        recovery.capture(tmp_path)


def test_outer_inventory_cannot_add_an_archive_path(tmp_path, model):
    (tmp_path / 'assets.json').write_text(json.dumps({
        'schema': 1, 'images': recovery.LOCK['images'],
        'model_manifest_sha256': recovery.LOCK['model_manifest_sha256'],
        'files': {'../../outside': {}}}))
    with pytest.raises(ValueError, match='Unexpected asset inventory'):
        recovery.verify(tmp_path)


def test_restore_rejects_legacy_image_store_before_loading(tmp_path, model, monkeypatch):
    monkeypatch.setattr(recovery.subprocess, 'run',
                        lambda args, **kw: subprocess.CompletedProcess(args, 1))
    calls = []

    def read_store(*args, **kwargs):
        calls.append(args)
        assert args[0] == 'info'
        return subprocess.CompletedProcess(args, 0, stdout='[["Backing Filesystem", "extfs"]]')

    monkeypatch.setattr(recovery, 'docker', read_store)
    monkeypatch.setattr(recovery, 'verify', lambda path: pytest.fail('Should stop before loading'))
    with pytest.raises(ValueError, match='containerd image store'):
        recovery.restore(tmp_path)
    assert len(calls) == 1
