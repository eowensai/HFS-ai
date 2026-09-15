#!/usr/bin/env python3
"""Prepare the two pinned backends without operating another installation.

All mutable files live below this checkout's .local directory. Start/stop are
explicit actions; prepare never stops or recreates a running service.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
REVISION = '319f741cce68d7914884900c138a1fbb70a42f30'
BASE = 'python:3.14.7-slim-trixie@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(16 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def docker(*args, capture=False):
    if capture:
        return subprocess.check_output(['docker', *args], text=True).strip()
    subprocess.run(['docker', *args], check=True, cwd=ROOT)


def download(url, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(target) != expected:
            raise ValueError(f'Existing file has the wrong identity: {target}')
        return
    partial = target.with_name(target.name + '.partial')
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
    with urllib.request.urlopen(request, timeout=120) as response:
        append = offset and response.status == 206
        if append and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
            raise ValueError('Unexpected download resume offset')
        with partial.open('ab' if append else 'wb') as stream:
            for chunk in iter(lambda: response.read(8 * 1024 * 1024), b''):
                stream.write(chunk)
    if sha(partial) != expected:
        raise ValueError(f'Download failed its SHA-256 check: {target.name}')
    partial.replace(target)


def provision(backend, profile='mtp'):
    if backend == 'fp4':
        for name, info in read('deployment/fp4/model-files.json').items():
            print('Verify/download', name, flush=True)
            download('https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4/resolve/' +
                     REVISION + '/' + urllib.parse.quote(name),
                     LOCAL / 'models/radixark' / name, info['sha256'])
        if profile == 'dflash':
            for name, info in read('deployment/fp4/dflash/draft-files.json').items():
                download('https://huggingface.co/syvai/Qwen3.8-27B-DFlash2-W4A16/resolve/'
                         '4d30ec736ffc6b8688dc2ae2b502d9b48bdec279/' + urllib.parse.quote(name),
                         LOCAL / 'models/dflash' / name, info['sha256'])
        return
    root = LOCAL / 'ollama/models'
    manifest_bytes = (ROOT / 'deployment/ollama-manifest.json').read_bytes()
    profile = read('deployment/ollama-profile.json')
    if hashlib.sha256(manifest_bytes).hexdigest() != profile['manifest_sha256']:
        raise ValueError('Ollama manifest identity mismatch')
    sources = {
        '493301830a596b8ad56dc1329f80bbcb578c8e910da395feafdc9cd8263430bb': 'Qwen3.8-27B-UD-Q6_K_M.gguf',
        '83ee4f4f205fa514161778c41df1ea14144faa0f713510893b63c2395f5c2d53': 'mmproj-BF16.gguf',
    }
    for digest, name in sources.items():
        download('https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/'
                 '4ca720788d1e01f1bff70c033e0d0028fd02e502/' + name,
                 root / 'blobs' / ('sha256-' + digest), digest)
    for digest, encoded in read('deployment/ollama-small-blobs.json').items():
        data = base64.b64decode(encoded, validate=True)
        if hashlib.sha256(data).hexdigest() != digest.removeprefix('sha256:'):
            raise ValueError('Ollama configuration blob identity mismatch')
        p = root / 'blobs' / digest.replace(':', '-')
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and p.read_bytes() != data:
            raise ValueError('Existing Ollama configuration differs')
        p.write_bytes(data)
    p = root / 'manifests/registry.ollama.ai/library' / profile['model'] / 'latest'
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_bytes() != manifest_bytes:
        raise ValueError('Existing Ollama alias differs')
    p.write_bytes(manifest_bytes)


def compose(backend, *args):
    env = os.environ.copy()
    envfile = LOCAL / 'images.env'
    command = ['docker', 'compose', '--project-directory', str(ROOT)]
    if (ROOT / '.env').is_file():
        command += ['--env-file', str(ROOT / '.env')]
    if envfile.exists():
        command += ['--env-file', str(envfile)]
    command += ['-f', str(ROOT / ('docker-compose.fp4.yml' if backend == 'fp4' else 'docker-compose.ollama-recovery.yml'))]
    return subprocess.run([*command, *args], check=True, cwd=ROOT, env=env)


def other_gpu_containers(allowed_project):
    ids = docker('ps', '-q', capture=True).split()
    if not ids:
        return []
    containers = json.loads(docker('inspect', *ids, capture=True))
    return [c['Name'] for c in containers if c['HostConfig'].get('DeviceRequests') and
            c['Config'].get('Labels', {}).get('com.docker.compose.project') != allowed_project]


def prepare_native_object():
    """Use only the exact qualified object, built locally or privately restored."""
    target = LOCAL / 'native-rebuild/native-nhd.o'
    expected = read('deployment/fp4/native/manifest.json')['files']['native-nhd.o']
    if target.exists():
        if sha(target) != expected:
            raise ValueError('Native object differs from qualified build; refusing substitution')
        return target.parent
    if other_gpu_containers('no-running-gpu-allowed'):
        raise SystemExit('Native object missing. Stop inference explicitly before source compilation, '
                         'or restore the qualified object from your private backup; no service was changed.')
    docker('build', '--target', 'engine-deps',
           '--build-context', f'wheelhouse={LOCAL / "wheels"}',
           '-f', str(ROOT / 'deployment/fp4/Dockerfile'),
           '-t', 'ephemerai-review:native-build', str(ROOT))
    subprocess.run([sys.executable, str(ROOT / 'deployment/fp4/native/rebuild.py'),
                    '--compile', '--image', 'ephemerai-review:native-build'], check=True)
    if sha(target) != expected:
        raise ValueError('Source rebuild differs; separate numerical qualification is required')
    return target.parent


def prepare(backend, profile='mtp'):
    LOCAL.mkdir(exist_ok=True)
    docker('build', '--output', f'type=local,dest={LOCAL / "privacy"}',
           str(ROOT / 'deployment/privacy'))
    docker('build', '-t', 'ephemerai-review:app', str(ROOT))
    docker('build', '-t', 'ephemerai-review:tika4', str(ROOT / 'deployment/tika'))
    engine_id = None
    if backend == 'ollama':
        docker('pull', 'ollama/ollama:0.32.15@sha256:57d60e686821ea81a7748a3ec8141308c8b8f95b27105713954abf7a6529e700')
    if backend == 'fp4':
        for item in read('deployment/fp4/wheels.json'):
            download(item['url'], LOCAL / 'wheels' / item['filename'], item['sha256'])
        native = read('deployment/fp4/native/manifest.json')
        item = native['runtime_wheel']
        wheel = LOCAL / 'wheels' / item['filename']
        download(item['url'], wheel, item['sha256'])
        subprocess.run([sys.executable, str(ROOT / 'deployment/fp4/native/prepare_runtime.py'),
                        str(wheel), str(LOCAL / 'native-runtime'),
                        str(ROOT / 'deployment/fp4/native/manifest.json')], check=True)
        native_object = prepare_native_object()
        docker('build', '--build-context', f'native-object={native_object}',
               '--build-context', f'native-runtime={LOCAL / "native-runtime"}',
               '--build-context', f'wheelhouse={LOCAL / "wheels"}',
               '-f', str(ROOT / 'deployment/fp4/Dockerfile'), '-t', 'ephemerai-review:fp4', str(ROOT))
        engine_id = docker('image', 'inspect', 'ephemerai-review:fp4', '--format', '{{.Id}}', capture=True)
        if profile == 'dflash':
            # Dockerfile FROM accepts a reference/manifest digest, not a local
            # image-config SHA. Give this exact local image an identity-derived tag.
            base_tag = 'ephemerai-build-base:' + engine_id.removeprefix('sha256:')
            docker('tag', engine_id, base_tag)
            docker('build', '--build-arg', f'MTP_IMAGE={base_tag}',
                   '-f', str(ROOT / 'deployment/fp4/Dockerfile.dflash'),
                   '-t', 'ephemerai-review:dflash', str(ROOT))
            engine_id = docker('image', 'inspect', 'ephemerai-review:dflash', '--format', '{{.Id}}', capture=True)
        identity = {'model': 'ephemerai-qwen3.8-27b-nvfp4-131072', 'model_revision': REVISION,
                    'context': 131072, 'kv_cache': 'fp8_e4m3', 'mtp_tokens': 3,
                    'engine_image_id': engine_id, 'engine_image_ref': engine_id,
                    'model_files_sha256': sha(ROOT / 'deployment/fp4/model-files.json'),
                    'placement_patch_sha256': sha(ROOT / 'deployment/fp4/qwen3_5.py'),
                    'native_manifest_sha256': sha(ROOT / 'deployment/fp4/native/manifest.json'),
                    'numerics_manifest_sha256': sha(ROOT / 'deployment/fp4/numerics/manifest.json'),
                    'inference_profile': profile,
                    'launch': read('deployment/fp4/dflash/launch.json' if profile == 'dflash'
                                   else 'deployment/fp4/launch.json')}
        if profile == 'dflash':
            identity.pop('mtp_tokens')
            identity.update(speculative_method='dflash', speculative_tokens=7,
                            draft_model_revision='4d30ec736ffc6b8688dc2ae2b502d9b48bdec279',
                            draft_embedding='int4-group32-fp16-scales-bf16-mask',
                            dflash_patch_manifest_sha256=sha(ROOT / 'deployment/fp4/dflash/patch-manifest.json'))
        (LOCAL / 'deployment.json').write_text(json.dumps(identity, indent=2) + '\n')
        (LOCAL / 'engine-profile.json').write_text(json.dumps({'profile':profile})+'\n')
    settings = {key: docker('image', 'inspect', tag, '--format', '{{.Id}}', capture=True)
                for key, tag in [('EPHEMERAI_APP_IMAGE', 'ephemerai-review:app'),
                                 ('EPHEMERAI_TIKA_IMAGE', 'ephemerai-review:tika4')]}
    # Preparing Ollama must not destroy an existing FP4 image selection.
    if (LOCAL / 'images.env').exists():
        old = dict(line.split('=', 1) for line in (LOCAL / 'images.env').read_text().splitlines() if '=' in line)
        if 'EPHEMERAI_ENGINE_IMAGE' in old:
            settings['EPHEMERAI_ENGINE_IMAGE'] = old['EPHEMERAI_ENGINE_IMAGE']
        if 'EPHEMERAI_PP_PARTITION' in old:
            settings['EPHEMERAI_PP_PARTITION'] = old['EPHEMERAI_PP_PARTITION']
    if engine_id:
        settings['EPHEMERAI_ENGINE_IMAGE'] = engine_id
        settings['EPHEMERAI_PP_PARTITION'] = '32,32' if profile == 'dflash' else '34,30'
    (LOCAL / 'images.env').write_text(''.join(f'{k}={v}\n' for k, v in settings.items()))
    print('Build complete. Provision models separately, then explicitly start the selected backend.')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'current':
        subprocess.run([sys.executable, str(ROOT / 'deployment/selected/manage.py'), *sys.argv[2:]], check=True)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'models', 'start', 'stop', 'status', 'config'])
    parser.add_argument('backend', choices=['ollama', 'fp4'])
    parser.add_argument('--profile', choices=['mtp', 'dflash'],
                        help='FP4 only; otherwise reuse this checkout\'s prepared profile, default MTP.')
    args = parser.parse_args()
    if args.profile and args.backend != 'fp4':
        parser.error('--profile applies only to fp4')
    profile = args.profile or (json.loads((LOCAL / 'engine-profile.json').read_text())['profile']
                              if (LOCAL / 'engine-profile.json').exists() else 'mtp')
    if profile not in ('mtp', 'dflash'):
        raise SystemExit('Prepared profile is invalid')
    if args.profile and args.action in ('start', 'stop', 'status', 'config'):
        prepared = (json.loads((LOCAL / 'engine-profile.json').read_text())['profile']
                    if (LOCAL / 'engine-profile.json').exists() else 'mtp')
        if profile != prepared:
            raise SystemExit('Run prepare for the selected profile first; no service was changed.')
    if args.action == 'prepare':
        prepare(args.backend, profile)
    elif args.action == 'models':
        project = 'ephemerai-review-fp4' if args.backend == 'fp4' else 'ephemerai-review'
        if docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + project, capture=True):
            raise SystemExit('Stop this review stack before provisioning its model files.')
        provision(args.backend, profile)
    elif args.action == 'start':
        project = 'ephemerai-review-fp4' if args.backend == 'fp4' else 'ephemerai-review'
        if other_gpu_containers(project):
            raise SystemExit('Another GPU inference installation is running. Stop it explicitly first; nothing was changed.')
        if not (LOCAL / 'images.env').is_file():
            raise SystemExit('Run prepare first.')
        compose(args.backend, 'up', '-d', '--no-build', '--pull', 'never')
    else:
        compose(args.backend, {'stop': 'stop', 'status': 'ps', 'config': 'config'}[args.action])


if __name__ == '__main__':
    main()
