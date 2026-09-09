# Current system — September 8, 2026

This is a dated installation baseline, not a claim that every listed version remains
the latest indefinitely. Read-only inspection confirmed the deployed source and
container configuration. GitHub's previous `main` was `904e56f6cd9d2fb404ebbaeb878dcee74dac51f5`;
the user-supplied ZIP matched all 38 files in that commit. This update imports the
current EphemerAI implementation and supplies source-only installation documentation.

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
| NVIDIA Container Toolkit / libnvidia-container | 1.19.0 / 1.19.0 |
| Docker default runtime / image store | nvidia / containerd snapshotter |
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
The small accepted model manifest is included as an identity reference at
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

## Source-only scope

This Git repository contains source, configuration, scripts, tests, documentation
and the fresh homepage screenshot. Ollama, Tika's jar/base image, app dependencies,
and the correct Unsloth quant/projector are downloaded or built during installation.
No saved Docker-image/model archive is needed or distributed. The model's immutable
identity check remains enabled; the install recipe recreates the required alias.
HFS's separate installation and persistent data are outside this repository.

## Environment changes confirmed across recent tasks

These records were read directly, including follow-up decisions and the completed
platform-update checkpoint; this is not inferred solely from the app directory.

| Task / record reviewed | Current setup consequence |
|---|---|
| **Replace and deploy shared Tika**, September 7 | Maintained Ubuntu 26.04 / released Java 21.0.12 / signed Tika 3.3.2; retained OCR/native tools and OOXML compatibility flags |
| **Harden EphemerAI browser access**, including the user's network-policy correction | CORS/XSRF enabled; Windows UI Any/Any access is intentional because routers control admission; logon scripts refresh forwards without creating firewall rules |
| Platform update within **Harden EphemerAI browser access**, completed checkpoint September 8 | WSL 2.7.13.0, kernel 6.18.33.2, Docker 29.8.0, containerd 2.3.4, runc 1.5.1; all intended services restored, no reboot/continuation pending |
| **Fix EphemerAI image decoder**, including its UI follow-up | Pillow 12.3.0 and wider responsive chat; retain Streamlit 1.56.0 |
| **Assess ephemeral app stack** | Historical findings checked against subsequent completed fixes, not treated as the current version inventory |
| **Build and evaluate HFS V3** and current HFS discovery | Separate persistent HFS runtime and loopback V3 prototype; shared infrastructure operations must account for their activity |
| **Implement EphemerAI privacy cleanup** | Explicit session cleanup, supported disconnect hook, 2/6/18 GiB container caps, zero Linux swap, bounded tmpfs and no-dump policy |

Host files outside the repository were also inspected: `/etc/wsl.conf` enables
systemd; Windows `.wslconfig` retains NAT/default memory and localhost forwarding;
`/etc/docker/daemon.json` selects NVIDIA by default and bounds json-file logs to
10 MB × 3. The [daemon example](../deployment/docker-daemon.example.json) and
Windows startup examples capture those settings without including HFS application
files. Docker uses its built-in seccomp profile; the platform update verified
AF_ALG restrictions. Do not add an unconfined seccomp workaround.

Windows startup is the interactive elevated **Monitor WSL Kiosk Service** task,
not an unattended pre-login service. Existing 8501/8503 firewall rules and Public
network profile remain accepted. Peer/router filtering needs an actual peer test.
