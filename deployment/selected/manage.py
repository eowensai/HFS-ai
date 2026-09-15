"""Operate the retained departmental installation; never rebuild an adopted image."""
import argparse
import contextlib
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOCAL = ROOT / '.local'


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def inspect(name):
    result = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def profiles():
    return read(HERE / 'profiles.json')


def fingerprint(container):
    payload = {key: container[key] for key in ('Config', 'HostConfig')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def check_identity(name, expected, bindings):
    container = inspect(name)
    if container is None:
        if expected.get('compose'):
            return None
        raise RuntimeError('Retained container is missing: ' + name)
    if container['Image'] != expected['image']:
        raise RuntimeError('Image identity mismatch: ' + name)
    prior = bindings.get(name)
    if prior and (container['Id'] != prior['id'] or fingerprint(container) != prior['config_sha256']):
        raise RuntimeError('Retained container/configuration changed: ' + name)
    return container


def check_gpu(allowed):
    ids = docker('ps', '-q').split()
    rows = json.loads(docker('inspect', *ids)) if ids else []
    gpu = [row['Name'].lstrip('/') for row in rows if row['HostConfig'].get('DeviceRequests')]
    if len(gpu) > 1 or any(name not in allowed for name in gpu):
        raise RuntimeError('Unexpected GPU engine(s); no transition authorized: ' + ', '.join(gpu))
    return gpu


def healthy(name, timeout=900):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = inspect(name)
        if not row or not row['State']['Running']:
            raise RuntimeError('Container stopped before health: ' + name)
        health = row['State'].get('Health', {}).get('Status')
        if health == 'healthy':
            return
        if health is None:
            if name == 'ollama':
                docker('exec', name, 'ollama', 'list')
            else:
                docker('exec', name, 'python3', '-B', '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=5)")
            return
        time.sleep(2)
    raise RuntimeError('Health timeout: ' + name)


def idle(name):
    row = inspect(name)
    if not row or not row['State']['Running']:
        return
    if name == 'ollama':
        # Original recovery app is single-user; stop its frontend before switching.
        return
    code = "import urllib.request; t=urllib.request.urlopen('http://127.0.0.1:8000/metrics',timeout=10).read().decode(); a=[s for s in t.splitlines() if s.startswith(('vllm:num_requests_running{','vllm:num_requests_waiting{'))]; assert len(a)==2 and all(float(s.rsplit(' ',1)[1])==0 for s in a), 'Requests remain active'"
    docker('exec', name, 'python3', '-B', '-c', code)


def stop(name):
    row = inspect(name)
    if row and row['State']['Running']:
        docker('stop', '-t', '40', name)


def bindings():
    path = LOCAL / 'selected-installation.json'
    if not path.exists():
        raise RuntimeError('Run bind once after checking the retained installation.')
    return read(path)


def all_components():
    components = {}
    for profile in profiles().values():
        components.update({profile[key]['name']: profile[key] for key in ('app', 'engine')})
    return components


def bind():
    path = LOCAL / 'selected-installation.json'
    if path.exists():
        prior = read(path)
        for name, expected in all_components().items():
            check_identity(name, expected, prior)
        return
    check_gpu({'ephemerai-vllm-bounded'})
    records = {}
    for name, expected in all_components().items():
        row = check_identity(name, expected, {})
        if row:
            records[name] = {'id': row['Id'], 'image': row['Image'], 'config_sha256': fingerprint(row)}
    write(path, records)


def start_component(component, bound):
    name = component['name']
    row = check_identity(name, component, bound)
    if row is None:
        descriptor = HERE / component['compose']
        # Only explicit new fallback compiler namespaces may be created here.
        for volume in component.get('create_volumes', []):
            docker('volume', 'create', volume)
        docker('compose', '-f', str(descriptor), 'up', '-d', '--no-deps', '--no-build', '--pull', 'never', component['service'])
        row = inspect(name)
        if not row or row['Image'] != component['image']:
            raise RuntimeError('Created container has unexpected identity: ' + name)
        bound[name] = {'id': row['Id'], 'image': row['Image'], 'config_sha256': fingerprint(row)}
        write(LOCAL / 'selected-installation.json', bound)
    elif not row['State']['Running']:
        docker('start', name)
    healthy(name)


def select(target):
    catalog = profiles()
    profile = catalog[target]
    bound = bindings()
    components = all_components()
    for name, expected in components.items():
        check_identity(name, expected, bound)
    engines = {p['engine']['name'] for p in catalog.values()}
    check_gpu(engines)
    for name in engines:
        idle(name)
    # Persist intent first: `start` resumes this target after interruption.
    write(LOCAL / 'selected-state.json', {'profile': target, 'phase': 'transitioning'})
    wanted_app = profile['app']['name']
    wanted_engine = profile['engine']['name']
    for app in {p['app']['name'] for p in catalog.values()} - {wanted_app}:
        stop(app)
    for engine in engines - {wanted_engine}:
        stop(engine)
    check_gpu({wanted_engine})
    start_component(profile['engine'], bound)
    check_gpu({wanted_engine})
    start_component(profile['app'], bound)
    write(LOCAL / 'selected-state.json', {'profile': target, 'phase': 'ready'})


def status():
    state = LOCAL / 'selected-state.json'
    result = {'selection': read(state) if state.exists() else {'profile': 'unbound'}}
    result['containers'] = []
    for name in [*all_components(), 'tika-server']:
        row = inspect(name)
        if row:
            result['containers'].append({'name': name, 'id': row['Id'], 'image': row['Image'], 'running': row['State']['Running'], 'health': row['State'].get('Health', {}).get('Status')})
    result['gpu_engines'] = check_gpu({p['engine']['name'] for p in profiles().values()})
    print(json.dumps(result, indent=2))


@contextlib.contextmanager
def transition_lock():
    LOCAL.mkdir(exist_ok=True)
    with (LOCAL / 'selected.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bind', 'adopt', 'start', 'stop', 'status', 'rollback', 'mtp', 'previous-fp4', 'original-fp4', 'ollama'])
    args = parser.parse_args()
    if args.action == 'status':
        status()
        return
    with transition_lock():
        if args.action == 'bind':
            bind()
        elif args.action == 'stop':
            bound = bindings()
            for name, expected in all_components().items():
                check_identity(name, expected, bound)
            check_gpu({p['engine']['name'] for p in profiles().values()})
            for profile in profiles().values():
                stop(profile['app']['name'])
            for profile in profiles().values():
                stop(profile['engine']['name'])
        else:
            target = {'adopt': 'stable-prefix', 'rollback': 'baseline'}.get(args.action, args.action)
            if target == 'start':
                path = LOCAL / 'selected-state.json'
                target = read(path)['profile'] if path.exists() else 'stable-prefix'
            try:
                select(target)
            except Exception:
                if args.action == 'adopt':
                    # The fast fallback uses the same retained engine and old app.
                    select('baseline')
                raise


if __name__ == '__main__':
    main()
