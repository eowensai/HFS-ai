"""Replace only the exact upstream file used to qualify this placement patch."""
import hashlib
import json
from pathlib import Path

root = Path('/opt/ephemerai')
record = json.loads((root / 'upstream-patch.json').read_text())
target = Path('/usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/qwen3_5.py')
source = root / 'qwen3_5.py'
for path, key in ((target, 'upstream_sha256'), (source, 'patched_sha256')):
    if hashlib.sha256(path.read_bytes()).hexdigest() != record[key]:
        raise SystemExit('Placement patch input differs from the qualified build')
target.write_bytes(source.read_bytes())
