"""Fail closed if any native runtime, binary, adapter or engine input differs."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent
info=json.loads((root/'manifest.json').read_text())
checks={'native-nhd.o':info['files']['native-nhd.o'],
        'libcute_dsl_runtime-4.7.1.so':info['files']['libcute_dsl_runtime-4.7.1.so'],
        'native_adapter.py':info['adapter_sha256'],
        'flashinfer_backend.py':info['vllm_backend']['patched_sha256']}
for name,expected in checks.items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Native component identity mismatch: '+name)
target=Path('/usr/local/lib/python3.12/dist-packages')/info['vllm_backend']['path']
if hashlib.sha256(target.read_bytes()).hexdigest()!=info['vllm_backend']['upstream_sha256']:
    raise SystemExit('Native patch engine input differs')
target.write_bytes((root/'flashinfer_backend.py').read_bytes())
