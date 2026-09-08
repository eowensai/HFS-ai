# Current system — September 8, 2026

This is a dated recovery baseline, not a claim that every listed version remains
the latest indefinitely. Read-only inspection confirmed the deployed source and
container configuration. GitHub's previous `main` was `904e56f6cd9d2fb404ebbaeb878dcee74dac51f5`;
the user-supplied ZIP matched all 38 files in that commit. This update imports the
current EphemerAI implementation and adds recovery packaging/documentation.

## Workstation and runtime

| Item | Observed value |
|---|---|
| Host | Windows 11, 64 GiB physical RAM |
| GPU | 2 × NVIDIA RTX 5060 Ti, 16 GiB each; driver 610.88 |
| Distro | Ubuntu-24.04, Ubuntu 24.04.4 LTS |
| WSL / kernel | 2.7.13.0 / 6.18.33.2-microsoft-standard-WSL2 |
| WSL memory | Approximately 30.19 GiB |
| Docker / Compose | 29.8.0 / 5.1.3 |
| containerd / runc | 2.3.4 / 1.5.1 |
| Live EphemerAI checkout | `/home/eko/ephemeral-llm` |
| Compose project / network | `ephemeral-llm` / `ephemeral-llm_llm-net` |
| Model volume | `ephemeral-llm_ollama-models` mounted at `/root/.ollama` |
| Windows pilot address | `172.16.64.243` |
| Startup script / task | `C:\Scripts\Start-EphemerAl.ps1` / `Monitor WSL Kiosk Service` |

The original checkout still has an older EphemerAl Git remote. Publication uses
`eowensai/HFS-ai` through a separate prepared tree; it does not rewrite the live
remote or deploy new services.

## Component identities

The complete machine-readable record is
[`deployment/runtime-lock.json`](../deployment/runtime-lock.json). It records
service image IDs, memory ceilings and the required model manifest SHA-256.
The accepted model manifest is included verbatim at
[`deployment/model/manifest.json`](../deployment/model/manifest.json).

The model is `hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072`, digest
`44d415f1e36e9aea1cca2baaaa79da8cef57f255c8dd91f1e9ef0abfc8a6c33d`.
It has a 23,088,409,504-byte GGUF and a 931,146,432-byte projector, plus small
configuration/template/parameter blobs. The manifest's `from` fields record
construction history; they are not substitutes for the immutable identity check.

Tika is a local 3.3.2 maintenance image on Ubuntu 26.04, preserving full-image OCR,
fonts and native helpers. Its OOXML compatibility configuration keeps the non-SAX
DOCX/PPTX extraction behavior previously accepted by both clients. It is not the
older 3.3.0 image named in the stale GitHub documentation.

## Shared clients outside this repository

- HFS Knowledge: `/home/eko/hfs-knowledge-lab/hfs-knowledge-lab-starter-v2-2`, runtime
  `/home/eko/hfs-knowledge-runtime`, user unit `hfs-knowledge.service`, UI 8503.
  It intentionally persists its own documents, jobs and answers.
- V3 prototype: source under the separate HFS project, runtime
  `/home/eko/hfs-knowledge-v3-runtime`, loopback UI 8513. The discovered process
  belongs to transient `hfs-v3-maintenance-restore.service`; this is not a newly
  established persistent startup policy.
- HFS v2.2 discovers/caches private backend addresses on startup. Current addresses
  were Ollama 172.18.0.2 and Tika 172.18.0.3; they are observations, not stable API
  configuration to copy into new clients.

V3 had a pre-existing hardcoded Ollama address mismatch at the privacy inspection.
That belongs to the HFS project and is not repaired or included here. Discover
current clients and state before maintenance rather than treating this dated
inventory as a live lock or permission to interrupt work.

## Security and persistence baseline

CORS/XSRF are enabled; Pillow is 12.3.0. The no-swap/core/tmpfs controls and session
cleanup are described in [privacy controls](../deployment/privacy/README.md).
Docker's built-in seccomp profile remains active. Only UI port 8501 is published by
this Compose project; Windows also forwards HFS 8503 in the existing ecosystem.
The site intentionally uses upstream network equipment as its client-access boundary.

Windows paging remains system-managed; the observed pagefile allocation was 9 GiB.
Automatic Windows memory dumps are configured. BitLocker inspection was denied,
so encryption status is unverified. This repository does not change those controls,
promise browser/OS forensic erasure, or erase any prior disk contents.

## Recovery scope

This Git repository contains code, configuration, scripts, documentation and a
fresh homepage screenshot. Exact image/model bytes belong in the separate archive
created by `scripts/recovery.py capture`. The recovery package has no HFS databases,
source documents, chat logs, credentials, or unrelated model aliases. Whole-machine
or whole-WSL recovery is a separate backup scope and may contain HFS operational data.
