"""Verify qualified source and installed hashes without modifying the engine."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SELECTED = ROOT / 'deployment/selected'


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_checks():
    identity = load(SELECTED / 'qualified-runtime.json')
    for name, expected in identity['runtime_files'].items():
        assert sha(ROOT / name) == expected, name
    for name, expected in identity['mounted_files'].items():
        assert sha(SELECTED / name) == expected, name
    native = load(ROOT / 'deployment/fp4/native/manifest.json')
    assert sha(ROOT / 'deployment/fp4/native/native_adapter.py') == native['adapter_sha256']
    assert sha(ROOT / 'deployment/fp4/native/flashinfer_backend.py') == native['vllm_backend']['patched_sha256']
    assert native['files']['native-nhd.o'] == identity['native_object_sha256']
    for item in load(ROOT / 'deployment/fp4/dflash/patch-manifest.json')['patches']:
        assert sha(ROOT / 'deployment/fp4/dflash' / item['patch']) == item['patch_sha256']
    placement = load(ROOT / 'deployment/fp4/upstream-patch.json')
    assert sha(ROOT / 'deployment/fp4/qwen3_5.py') == placement['patched_sha256']
    launch = load(ROOT / 'deployment/fp4/dflash/launch.json')
    def option(name):
        return launch[launch.index(name) + 1]
    assert option('--max-model-len') == '131072'
    assert option('--max-num-seqs') == '1'
    assert option('--max-num-batched-tokens') == '1024'
    assert option('--kv-cache-memory-bytes') == '3060164198'
    assert json.loads(option('--speculative-config'))['num_speculative_tokens'] == 7
    app = load(SELECTED / 'app.compose.json')['services']['ephemeral-app']
    assert app['image'] == identity['frontend_image'] and app['pull_policy'] == 'never'
    assert 'build' not in app and 'deploy' not in app
    assert {x['target'] for x in app['volumes']} == {'/opt/ephemerai/deployment.json', '/app/.streamlit/config.toml'}
    assert 'PYTHONPATH' not in app['environment']
    assert app['read_only'] and app['init']
    assert app['environment']['LLM_OUTPUT_RESERVE_TOKENS'] == '32768'
    return identity


def engine_expectations():
    root = ROOT / 'deployment/fp4'
    expected = {}
    site = '/usr/local/lib/python3.12/dist-packages/'
    for item in load(root / 'numerics/manifest.json')['patches']:
        expected[site + item['path']] = item['patched_sha256']
    # DFlash applies after the base numerical policy; its composite hash wins.
    for item in load(root / 'dflash/patch-manifest.json')['patches']:
        expected[site + item['path']] = item['patched_sha256']
    native = load(root / 'native/manifest.json')
    expected[site + native['vllm_backend']['path']] = native['vllm_backend']['patched_sha256']
    expected['/opt/ephemerai/native/native_adapter.py'] = native['adapter_sha256']
    for name, digest in native['files'].items():
        if name in ('native-nhd.o', 'libcute_dsl_runtime-4.7.1.so'):
            expected['/opt/ephemerai/native/' + name] = digest
    for name in ('supervise.py', 'healthcheck.py', 'watchdog.py', 'diagnostics.py', 'model-files.json'):
        expected['/opt/ephemerai/' + name] = sha(root / name)
    for directory in ('dflash', 'native', 'numerics'):
        for name in ('manifest.json', 'patch-manifest.json', 'draft_embedding.py'):
            source = root / directory / name
            if source.exists():
                expected['/opt/ephemerai/' + directory + '/' + name] = sha(source)
    expected['/opt/ephemerai/launch.json'] = sha(root / 'dflash/launch.json')
    expected['/models/radixark/chat_template.jinja'] = load(SELECTED / 'qualified-runtime.json')['chat_template_sha256']
    return expected


def hashes_in_container(name, paths):
    code = "import hashlib,json; from pathlib import Path; paths=" + repr(paths) + "; print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}))"
    return json.loads(subprocess.check_output(['docker', 'exec', name, 'python3', '-B', '-c', code]))


def live_checks(identity):
    app_name = 'hfsai-app-stable-prefix'
    engine_name = 'ephemerai-vllm-bounded'
    rows = json.loads(subprocess.check_output(['docker', 'inspect', app_name, engine_name, 'tika-server']))
    app, engine, tika = rows
    assert app['Image'] == identity['frontend_image']
    assert engine['Image'] == identity['engine_image']
    assert tika['Image'] == identity['tika_image']
    for row in rows:
        host = row['HostConfig']
        assert host['Memory'] > 0 and host['MemorySwap'] == host['Memory']
        assert not host['Privileged']
        assert any(x['Name'] == 'core' and x['Hard'] == x['Soft'] == 0 for x in host['Ulimits'])
        if row is not app:
            assert not host['PortBindings']
    assert app['HostConfig']['ReadonlyRootfs'] and engine['HostConfig']['ReadonlyRootfs']
    assert all(x['State']['Running'] for x in rows)
    assert app['State']['Health']['Status'] == engine['State']['Health']['Status'] == 'healthy'
    assert {x['Destination'] for x in app['Mounts']} == {'/app/.streamlit/config.toml', '/opt/ephemerai/deployment.json'}
    assert all(not x['RW'] for x in app['Mounts'])
    assert all('/outputs/' not in x['Source'] and '/work/' not in x['Source'] for x in app['Mounts'])
    app_hashes = hashes_in_container(app_name, ['/app/' + p for p in identity['runtime_files']])
    assert app_hashes == {'/app/' + p: h for p, h in identity['runtime_files'].items()}
    expected = engine_expectations()
    actual = hashes_in_container(engine_name, list(expected))
    assert actual == expected, {p: (expected[p], actual.get(p)) for p in expected if actual.get(p) != expected[p]}
    ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
    active = json.loads(subprocess.check_output(['docker', 'inspect', *ids]))
    assert [x['Name'] for x in active if x['HostConfig'].get('DeviceRequests')] == ['/' + engine_name]
    code = "import urllib.request; t=urllib.request.urlopen('http://127.0.0.1:8000/metrics').read().decode(); a=[s for s in t.splitlines() if s.startswith(('vllm:num_requests_running{','vllm:num_requests_waiting{'))]; assert len(a)==2 and all(float(s.rsplit(' ',1)[1])==0 for s in a); urllib.request.urlopen('http://tika-server:9998/tika',timeout=10); print('idle; Tika HTTP healthy')"
    subprocess.run(['docker', 'exec', engine_name, 'python3', '-B', '-c', code], check=True)
    return {'app_id': app['Id'], 'engine_id': engine['Id'], 'tika_id': tika['Id'], 'engine_files_verified': len(expected), 'app_files_verified': len(app_hashes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    identity = source_checks()
    result = {'source_passed': True, 'runtime_files': identity['runtime_files']}
    if args.live:
        result['live'] = live_checks(identity)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
