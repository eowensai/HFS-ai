"""Install the measured numerical policy on the exact pinned engine sources."""

import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / "manifest.json").read_text())
    replacements = []
    for item in metadata["patches"]:
        path = Path("/usr/local/lib/python3.12/dist-packages") / item["path"]
        original = path.read_bytes()
        if sha(original) != item["upstream_sha256"]:
            raise SystemExit("Numerical policy input differs: " + item["path"])
        before, after = item["before"].encode(), item["after"].encode()
        if original.count(before) != 1:
            raise SystemExit("Numerical policy anchor differs: " + item["path"])
        changed = original.replace(before, after)
        if sha(changed) != item["patched_sha256"]:
            raise SystemExit("Numerical policy output differs: " + item["path"])
        replacements.append((path, changed))
    for path, changed in replacements:
        path.write_bytes(changed)


if __name__ == "__main__":
    main()
