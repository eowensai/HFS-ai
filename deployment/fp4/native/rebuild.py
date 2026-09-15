"""Prepare pinned native sources, optionally rebuild in a disposable GPU container.

The public repository stores patches and hashes, not the compiled object. A rebuild stays in
.local/native-rebuild and never replaces a serving artifact automatically.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from deployment import download

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--image", default="ephemerai-review:native-build")
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.json").read_text())
    work = ROOT / ".local/native-rebuild"
    work.mkdir(parents=True, exist_ok=True)
    archive = work / "flashinfer.tar.gz"
    download(manifest["archive_url"], archive, manifest["archive_sha256"])
    source = work / ("flashinfer-" + manifest["flashinfer_commit"])
    if not source.exists():
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter="data")
    upstream = source / "flashinfer/cute_dsl/attention/fmha/sm120"
    for original, staged in [
        ("fmha_prefill_fp8_tma.py", "native_tma_nhd.py"),
        ("compile.py", "compile_nhd.py"),
    ]:
        expected = manifest["files"][
            "upstream_tma.py" if original.startswith("fmha") else "upstream_compile.py"
        ]
        if digest(upstream / original) != expected:
            raise SystemExit("Upstream source identity differs")
        shutil.copyfile(upstream / original, work / staged)
        subprocess.run(
            ["patch", "--batch", str(work / staged), str(HERE / (staged + ".patch"))],
            check=True,
        )
        if digest(work / staged) != manifest["files"][staged]:
            raise SystemExit("Patched source identity differs")
    for key in ("compiler_wheel", "compiler_base_wheel", "compiler_core_wheel", "compiler_source_wheel", "runtime_wheel"):
        wheel = manifest[key]
        download(wheel["url"], work / wheel["filename"], wheel["sha256"])
    print("Pinned sources and compiler wheels verified in", work, flush=True)
    if not args.compile:
        return
    running = subprocess.check_output(["docker", "ps", "-q"], text=True).split()
    if running:
        containers = json.loads(
            subprocess.check_output(["docker", "inspect", *running])
        )
        if any(c["HostConfig"].get("DeviceRequests") for c in containers):
            raise SystemExit(
                "Stop inference explicitly before compiling; no service was changed."
            )
    code = """import subprocess,sys
subprocess.run([sys.executable,'-m','venv','--system-site-packages','/tmp/compiler'],check=True)
subprocess.run(['/tmp/compiler/bin/python','-m','pip','install','--no-index','--no-deps',
    '/integration/COMPILER','/integration/BASE','/integration/CORE','/integration/SOURCE','/integration/RUNTIME'],check=True)
subprocess.run(['/tmp/compiler/bin/python','/integration/compile_nhd.py'],check=True)
""".replace("COMPILER", manifest["compiler_wheel"]["filename"]).replace(
        "RUNTIME", manifest["runtime_wheel"]["filename"]
    ).replace(
        "BASE", manifest["compiler_base_wheel"]["filename"]
    ).replace(
        "SOURCE", manifest["compiler_source_wheel"]["filename"]
    ).replace(
        "CORE", manifest["compiler_core_wheel"]["filename"]
    )
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--gpus",
        "all",
        "--shm-size",
        "1g",
        "--ulimit",
        "core=0",
        "-v",
        str(work) + ":/integration",
        "-v",
        str(source) + ":/source:ro",
        "-e",
        "PYTHONPATH=/integration:/source",
        "-e",
        "MAX_JOBS=2",
        "--entrypoint",
        "python3",
        args.image,
        "-c",
        code,
    ]
    subprocess.run(command, check=True)
    actual = digest(work / "native-nhd.o")
    result = {
        "sha256": actual,
        "qualified_sha256": manifest["files"]["native-nhd.o"],
        "matches_qualified": actual == manifest["files"]["native-nhd.o"],
        "automatic_promotion": False,
        "command": command,
    }
    (work / "rebuild-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not result["matches_qualified"]:
        raise SystemExit(
            "Rebuild differs: inspect disassembly and rerun numerical/runtime qualification before adoption."
        )


if __name__ == "__main__":
    main()
