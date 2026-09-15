> **Historical baseline:** this records the September 11 Ollama system. See [current FP4 deployment](CURRENT_DEPLOYMENT.md) and [installation](FP4_DEPLOYMENT.md) for the later backend; this record is retained for recovery.

# Current system — September 11, 2026

This record combines the September 11 Tika 4 deployment and the subsequent Python
3.14 / Streamlit 1.63 application upgrade. The application started from the deployed
`tika4-20260911` source, preserving fixes beyond GitHub main. Platform inventory was
last comprehensively verified September 8; service identities and protections were
rechecked for the application release. See [application changes and acceptance](APPLICATION_UPGRADE.md)
and [the earlier Tika record](TIKA4_UPGRADE.md). Automated acceptance does not claim
a human spot test or a fresh Windows installation.

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
| Deployment / tested source snapshot | `/home/eko/ephemeral-llm/docker-compose.yml` / `releases/python314-streamlit163-20260911` |
| Compose project / network | `ephemeral-llm` / `ephemeral-llm_llm-net` |
| Model volume | `ephemeral-llm_ollama-models` mounted at `/root/.ollama` |
| Windows pilot address | `172.16.64.243` |
| Startup script / task | `C:\Scripts\Start-EphemerAl.ps1` / `Monitor WSL Kiosk Service` |

The old source tree and its existing changes remain. Canonical local Compose now
builds EphemerAI from the tested release snapshot and selects the app release tag and pins the parser digest.
The former separate `hfs-ai-live` app Compose is superseded. Publication is prepared
in a separate HFS-ai branch; the old checkout's remote was not rewritten.

## Component identities

The application uses Python **3.14.7**, Streamlit **1.63.0**, Requests **2.34.2**
and pytz **2026.3.post1**. Pillow 12.3.0 and OpenAI SDK 1.97.2 are retained.
Production dependencies are fully pinned; [package inventory](../deployment/app-packages.json)
includes the resulting image's Python/build-tool and Debian package versions.

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

Tika is **4.0.0 full**, based on the pinned official distribution with signed Ubuntu
26.04 package updates. Validated runtime: Ubuntu 26.04.1, Java 25.0.4, Tesseract 5.5.0.
OCR languages and native helpers remain available. Office uses the supported
SAX/event parsers. EphemerAI requests JSON/Markdown, flags partial results and adds
bounded Word comment attribution. Limits are documented in the
[Tika build guide](../deployment/tika/README.md).

## Shared clients outside this repository

- HFS Knowledge: `/home/eko/hfs-knowledge-lab/hfs-knowledge-lab-starter-v2-2`, runtime
  `/home/eko/hfs-knowledge-runtime`, user unit `hfs-knowledge.service`, UI 8503.
  It intentionally persists its own documents, jobs and answers. **Stopped and
  disabled September 11** pending Tika 4 compatibility work POC-B056; data retained.
- V3 prototype: source under the separate HFS project, runtime
  `/home/eko/hfs-knowledge-v3-runtime`, loopback UI 8513. The discovered process
  belongs to transient `hfs-v3-maintenance-restore.service`; this is not a newly
  established persistent startup policy.
- HFS v2.2 discovers/caches private backend addresses on startup. September 8 addresses
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
No saved Docker-image/model archive is needed or distributed. Retained local
rollback images are deliberately excluded from source publication. The model's immutable
identity check remains enabled; the install recipe recreates the required alias.
HFS's separate installation and persistent data are outside this repository.

## Environment changes confirmed across recent tasks

These records were read directly, including follow-up decisions and the completed
platform-update checkpoint; this is not inferred solely from the app directory.

| Task / record reviewed | Current setup consequence |
|---|---|
| **Combined application upgrade**, September 11 | Python 3.14.7, Streamlit 1.63.0, Requests/timezone updates; app-only rollout, shared backends retained |
| **Upgrade local EphemerAI to Tika 4**, September 11 | Tika 4.0.0/Java 25.0.4; Markdown client, bounded workers and comment attribution; HFS parked with data preserved |
| **Replace and deploy shared Tika**, September 7 (historical) | Maintained Ubuntu 26.04 / released Java 21.0.12 / signed Tika 3.3.2; retained OCR/native tools and OOXML compatibility flags |
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
