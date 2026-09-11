#!/usr/bin/env python3
"""Read-only, body-free deployment checks; no model generation or restart."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'deployment/runtime-lock.json').read_text())


def run(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def main():
    compose = json.loads(subprocess.check_output(
        ['docker', 'compose', '--project-directory', str(ROOT), '-f',
         str(ROOT / 'docker-compose.yml'), 'config', '--format', 'json'], text=True))
    tika_ref = compose['services']['tika-server']['image']
    assert '@sha256:' in tika_ref, 'Tika must be pinned to the validated local build digest'
    tika_id = tika_ref.rsplit('@', 1)[1]
    results = {}
    for name, limit in LOCK['memory_bytes'].items():
        info = json.loads(run('inspect', name))[0]
        raw = run('exec', name, 'sh', '-c',
                  'cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.swap.max '
                  '/sys/fs/cgroup/memory.swap.current; cat /sys/fs/cgroup/memory.events')
        fields = raw.splitlines()
        assert info['State']['Running'], f'{name} is not running'
        assert int(fields[0]) == limit and fields[1:3] == ['0', '0'], f'{name}: cgroup limits differ'
        assert not info['HostConfig']['Privileged'], f'{name}: privileged is not supported'
        if name != 'ephemeral-app':
            assert not info['HostConfig']['PortBindings'], f'{name}: backend port is published'
            expected = tika_id if name == 'tika-server' else LOCK['images'][name]['id']
            assert info['Image'] == expected, f'{name}: image differs from configured pin'
        limits = info['HostConfig']['Ulimits'] or []
        assert any(x['Name'] == 'core' and x['Hard'] == x['Soft'] == 0 for x in limits)
        for mount in ('/tmp', '/var/tmp'):
            assert 'size=' in info['HostConfig']['Tmpfs'].get(mount, ''), f'{name}: unbounded tmpfs'
        events = dict(line.split() for line in fields[3:])
        results[name] = {'memory_max': limit, 'swap_max': 0, 'swap_current': 0,
                         'oom_kills': int(events['oom_kill']), 'image': info['Image']}
    manifest = subprocess.check_output(['docker', 'exec', 'ollama', 'cat',
                                       '/root/.ollama/' + LOCK['model_manifest_path']])
    assert hashlib.sha256(manifest).hexdigest() == LOCK['model_manifest_sha256'], 'Model identity mismatch'
    probe = run('exec', 'ephemeral-app', 'python', '-c',
                'import ctypes,resource,sys,os;from streamlit import config;'
                'from importlib.metadata import version;'
                'assert sys.version_info[:3]==(3,14,7);'
                'assert version("streamlit")=="1.63.0";'
                'assert os.environ.get("PYTHON_DISABLE_REMOTE_DEBUG")=="1";'
                'assert ctypes.CDLL(None).prctl(3,0,0,0,0)==0;'
                'assert resource.getrlimit(resource.RLIMIT_CORE)==(0,0);'
                'assert config.get_option("server.enableCORS");'
                'assert config.get_option("server.enableXsrfProtection");'
                'assert config.get_option("server.disconnectedSessionTTL")==0;'
                'assert config.get_option("server.maxUploadSize")==51;'
                'assert config.get_option("server.allowedHosts")==["localhost","127.0.0.1","172.16.64.243"];'
                'print("app protections verified")')
    print(json.dumps({'containers': results, 'model_identity': 'verified', 'application': probe}, indent=2))
    print('After a fictional prompt, also inspect: docker exec ollama ollama ps')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, subprocess.CalledProcessError, OSError) as exc:
        sys.exit(f'Verification failed: {exc}')
