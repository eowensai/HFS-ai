#!/usr/bin/env python3
"""Check this checkout's deployment without generating requests or restarting it."""
import argparse
import json
import subprocess

import deployment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', choices=['ollama', 'fp4'])
    args = parser.parse_args()
    project = 'ephemerai-review-fp4' if args.backend == 'fp4' else 'ephemerai-review'
    ids = deployment.docker('ps', '-aq', '--filter',
                            'label=com.docker.compose.project=' + project, capture=True).split()
    if not ids:
        raise SystemExit('This review deployment has no containers.')
    containers = json.loads(deployment.docker('inspect', *ids, capture=True))
    names = set()
    for c in containers:
        service = c['Config']['Labels']['com.docker.compose.service']
        names.add(service)
        if not c['State']['Running']:
            raise SystemExit(service + ' is not running')
        host = c['HostConfig']
        assert host['Memory'] > 0 and host['MemorySwap'] == host['Memory']
        assert any(x['Name'] == 'core' and x['Hard'] == x['Soft'] == 0 for x in host['Ulimits'])
        if service != 'ephemeral-app':
            assert not host['PortBindings'] and host['LogConfig']['Type'] == 'none'
        if service == 'vllm':
            identity = json.loads((deployment.LOCAL / 'deployment.json').read_text())
            assert c['Image'] == identity['engine_image_id']
        if service == 'ephemeral-app':
            deployment.docker('exec', c['Id'], 'python', '-c',
                              'from ephemeral import llm_client; assert llm_client.llm_alive()')
        print(service, c['Image'], c['State'].get('Health', {}).get('Status', 'running'))
    assert names == {'ephemeral-app', 'tika-server', 'vllm' if args.backend == 'fp4' else 'ollama'}


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, subprocess.CalledProcessError, OSError, ValueError):
        raise SystemExit('Deployment verification failed; no configuration was changed.') from None
