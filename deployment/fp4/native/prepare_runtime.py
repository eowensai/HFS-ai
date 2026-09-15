"""Extract only the hash-pinned runtime; do not install the newer compiler in serving."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile


def extract(wheel, destination, manifest):
    info = json.loads(Path(manifest).read_text())
    wheel = Path(wheel)
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != info['runtime_wheel']['sha256']:
        raise ValueError('Native runtime wheel identity mismatch')
    with zipfile.ZipFile(wheel) as archive:
        names = [n for n in archive.namelist() if n.endswith('/lib/libcute_dsl_runtime.so')]
        if len(names) != 1:
            raise ValueError('Ambiguous native runtime archive')
        blob = archive.read(names[0])
    if hashlib.sha256(blob).hexdigest() != info['files']['libcute_dsl_runtime-4.7.1.so']:
        raise ValueError('Native runtime identity mismatch')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / 'libcute_dsl_runtime-4.7.1.so'
    if target.exists() and target.read_bytes() != blob:
        raise ValueError('Existing native runtime differs')
    target.write_bytes(blob)

if __name__ == '__main__':
    extract(*sys.argv[1:])
