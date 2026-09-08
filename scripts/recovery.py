#!/usr/bin/env python3
"""Capture/verify exact EphemerAI assets; restore only into an absent model volume.

No HFS runtime, credential, log, chat, or document path is read. Docker images and
content-addressed model artifacts are immutable; capture does not stop services.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'deployment/runtime-lock.json').read_text())
MODEL_MANIFEST = (ROOT / 'deployment/model/manifest.json').read_bytes()
VOLUME = 'ephemeral-llm_ollama-models'


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, **kwargs)


def expected_model_files():
    expected = LOCK['model_manifest_sha256']
    if hashlib.sha256(MODEL_MANIFEST).hexdigest() != expected:
        raise ValueError('Repository model manifest identity mismatch')
    manifest = json.loads(MODEL_MANIFEST)
    files = {LOCK['model_manifest_path']: (expected, len(MODEL_MANIFEST))}
    for layer in [manifest['config'], *manifest['layers']]:
        sha = layer['digest'].removeprefix('sha256:')
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid model digest')
        files['models/blobs/sha256-' + sha] = (sha, layer['size'])
    return files


def verify_model_archive(path):
    """Validate exact allowlist, regular-file type, sizes and streamed content hashes."""
    expected = expected_model_files()
    seen = set()
    with tarfile.open(path, 'r|*', bufsize=1024 * 1024) as archive:
        for item in archive:
            if item.name not in expected or item.name in seen or not item.isfile():
                raise ValueError('Unexpected/duplicate/non-regular model archive member')
            sha, size = expected[item.name]
            if item.size != size:
                raise ValueError('Model artifact size mismatch')
            stream = archive.extractfile(item)
            if stream is None or hashlib.file_digest(stream, 'sha256').hexdigest() != sha:
                raise ValueError('Model artifact hash mismatch')
            seen.add(item.name)
    if seen != set(expected):
        raise ValueError('Model archive is incomplete')
    return len(seen)


def capture(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Capture destination must be a new directory')
    # 24 GB model data plus archived images and headroom; no capacity stress test.
    if shutil.disk_usage(destination.parent).free < 45 * 1024**3:
        raise ValueError('At least 45 GiB free space is required for capture')
    for spec in LOCK['images'].values():
        actual = docker('image', 'inspect', spec['ref'], '--format', '{{.Id}}',
                        capture_output=True, text=True).stdout.strip()
        if actual != spec['id']:
            raise ValueError('Running recovery image identity differs from runtime-lock.json')
    before = docker('exec', 'ollama', 'cat', '/root/.ollama/' + LOCK['model_manifest_path'],
                    capture_output=True).stdout
    if before != MODEL_MANIFEST:
        raise ValueError('Active alias differs from the accepted recovery manifest')
    destination.mkdir(mode=0o700)
    print('Saving the three accepted service images...', flush=True)
    docker('image', 'save', '-o', str(destination / 'runtime-images.tar'),
           *[s['ref'] for s in LOCK['images'].values()])
    print('Saving only the selected immutable model artifacts...', flush=True)
    with (destination / 'model.tar').open('wb') as f:
        docker('exec', 'ollama', 'tar', '-C', '/root/.ollama', '-cf', '-',
               *expected_model_files(), stdout=f)
    after = docker('exec', 'ollama', 'cat', '/root/.ollama/' + LOCK['model_manifest_path'],
                   capture_output=True).stdout
    if after != before:
        raise ValueError('Alias changed during capture; preserve this incomplete capture for review')
    print('Verifying model artifact contents...', flush=True)
    verify_model_archive(destination / 'model.tar')
    manifest = {'schema': 1, 'recorded_date': LOCK['recorded_date'],
                'model_manifest_sha256': LOCK['model_manifest_sha256'],
                'images': LOCK['images'], 'files': {}}
    for name in ('runtime-images.tar', 'model.tar'):
        p = destination / name
        print('Hashing ' + name + '...', flush=True)
        manifest['files'][name] = {'sha256': digest(p), 'bytes': p.stat().st_size}
    (destination / 'assets.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (destination / 'SHA256SUMS').write_text(''.join(
        f"{v['sha256']}  {n}\n" for n, v in manifest['files'].items()))
    print('Capture verified. Copy this directory AND the repository ZIP off this machine.', flush=True)


def verify(destination):
    destination = Path(destination).resolve()
    meta = json.loads((destination / 'assets.json').read_text())
    if meta.get('schema') != 1 or meta.get('images') != LOCK['images']:
        raise ValueError('Recovery metadata does not match the accepted runtime')
    if meta.get('model_manifest_sha256') != LOCK['model_manifest_sha256']:
        raise ValueError('Recovery model identity mismatch')
    if set(meta.get('files', {})) != {'runtime-images.tar', 'model.tar'}:
        raise ValueError('Unexpected asset inventory')
    for name, item in meta['files'].items():
        path = destination / name
        if path.is_symlink() or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('Recovery asset integrity check failed: ' + name)
    count = verify_model_archive(destination / 'model.tar')
    print(f'Verified both archives and all {count} model artifacts.', flush=True)


def restore(destination):
    """Fresh-host operation; never replace a model volume or existing app/container."""
    for name in LOCK['images']:
        probe = subprocess.run(['docker', 'container', 'inspect', name], capture_output=True, check=False)
        if probe.returncode == 0:
            raise ValueError('Restore requires no existing service containers; use a fresh host')
    probe = subprocess.run(['docker', 'volume', 'inspect', VOLUME], capture_output=True, check=False)
    if probe.returncode == 0:
        raise ValueError('Refusing to modify an existing model volume')
    store = json.loads(docker('info', '--format', '{{json .DriverStatus}}',
                              capture_output=True, text=True).stdout)
    if ['driver-type', 'io.containerd.snapshotter.v1'] not in store:
        raise ValueError('Exact OCI recovery requires the containerd image store; see the setup guide')
    verify(destination)
    destination = Path(destination).resolve()
    docker('image', 'load', '-i', str(destination / 'runtime-images.tar'))
    for spec in LOCK['images'].values():
        actual = docker('image', 'inspect', spec['ref'], '--format', '{{.Id}}',
                        capture_output=True, text=True).stdout.strip()
        if actual != spec['id']:
            raise ValueError('Loaded image identity mismatch; no model volume was created')
    docker('volume', 'create', VOLUME, stdout=subprocess.DEVNULL)
    # The archive has already passed the strict member allowlist and hash checks.
    # Python 3.11 supports the data extraction filter used here.
    code = "import tarfile; t=tarfile.open('/backup/model.tar'); t.extractall('/restore',filter='data')"
    docker('run', '--rm', '--network', 'none', '--memory', '256m', '--memory-swap', '256m',
           '--ulimit', 'core=0', '--entrypoint', 'python',
           '--mount', f'type=volume,src={VOLUME},dst=/restore',
           '--mount', f'type=bind,src={destination},dst=/backup,readonly',
           LOCK['images']['ephemeral-app']['id'], '-c', code)
    print('Images and selected model restored. No inference service has been started.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['capture', 'verify', 'restore-assets'])
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        {'capture': capture, 'verify': verify, 'restore-assets': restore}[args.action](args.directory)
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        parser.exit(1, f'Recovery stopped: {exc}\n')


if __name__ == '__main__':
    main()
