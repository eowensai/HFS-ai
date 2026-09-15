"""Apply exact, hash-checked hunks to the pinned MTP image; no fuzzy patching."""

import hashlib
import json
from pathlib import Path
import re


def sha(data):
    return hashlib.sha256(data).hexdigest()


def apply_hunks(original, patch):
    source = original.splitlines(keepends=True)
    lines = patch.splitlines(keepends=True)
    output, cursor, pos = [], 0, 2
    while pos < len(lines):
        match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[pos])
        if match is None:
            raise ValueError("Invalid exact patch header")
        start = int(match[1]) - 1
        if start < cursor:
            raise ValueError("Overlapping patch hunks")
        output.extend(source[cursor:start])
        cursor, pos = start, pos + 1
        before, after = 0, 0
        while pos < len(lines) and not lines[pos].startswith("@@"):
            line = lines[pos]
            if line[0] not in " +-":
                raise ValueError("Unsupported patch line")
            if line[0] in " -":
                if cursor >= len(source) or source[cursor] != line[1:]:
                    raise ValueError("Patch context differs")
                cursor += 1
                before += 1
            if line[0] in " +":
                output.append(line[1:])
                after += 1
            pos += 1
        if before != int(match[2] or 1) or after != int(match[4] or 1):
            raise ValueError("Patch hunk length differs")
    return "".join(output + source[cursor:])


def main():
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / "patch-manifest.json").read_text())
    if sha((root / "draft_embedding.py").read_bytes()) != metadata["embedding_sha256"]:
        raise SystemExit("Draft embedding helper identity differs")
    replacements = []
    for item in metadata["patches"]:
        target = Path("/usr/local/lib/python3.12/dist-packages") / item["path"]
        original, patch = target.read_bytes(), (root / item["patch"]).read_bytes()
        if (
            sha(original) != item["upstream_sha256"]
            or sha(patch) != item["patch_sha256"]
        ):
            raise SystemExit("DFlash patch input differs: " + item["path"])
        changed = apply_hunks(original.decode(), patch.decode()).encode()
        if sha(changed) != item["patched_sha256"]:
            raise SystemExit("DFlash patch result differs: " + item["path"])
        replacements.append((target, changed))
    for target, changed in replacements:
        target.write_bytes(changed)


if __name__ == "__main__":
    main()
