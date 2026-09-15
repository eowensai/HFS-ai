> **FP4/DFlash:** this guide preserves the original HFS-ai Ollama installation and recovery path. For the new backend, use [FP4 deployment](docs/FP4_DEPLOYMENT.md). Do not use the shared-stack commands below to switch a running FP4 installation.

# EphemerAI — System Deployment Guide

This guide rebuilds the September 11, 2026 deployment on a Windows 11 workstation.
It also explains safe updates when HFS Knowledge already shares its backend.
Commands marked **PowerShell (Admin)** run on Windows. Commands marked **Ubuntu**
run inside WSL. Do not run fresh-host installation steps on a working shared host.

## 1. What you will install

This is a source-only installation. Clone/download this repository, install the
prerequisites, build the application and maintained Tika image, and download the
correct Unsloth quant from Hugging Face. No saved model or container archive is
required. Internet access is needed during setup; inference stays local afterward.

The repository contains no HFS Knowledge application or operational data. A fresh
standalone EphemerAI installation works without HFS. The model alias keeps its
shared name either way. If HFS is separately installed, coordinate all backend,
Docker, GPU and WSL maintenance with its operator. Existing installations should
use [the app-only update procedure](#8-update-or-stop-an-existing-installation).

## 2. Prepare Windows, WSL and the GPU

The measured host uses Windows 11, 64 GiB RAM, two RTX 5060 Ti 16 GiB cards, and
about 30 GiB RAM allocated to WSL. Keep at least 30 GiB available to WSL and adequate
Windows headroom; smaller hosts are not certified for this model profile. Allow
at least 70 GiB free disk for the model, container images and build workspace.
The small repository ZIP excludes those installation downloads.

Install a current supported NVIDIA **Windows** driver. Do not install a Linux
display driver inside WSL. The verified driver was 610.88. In PowerShell, check:

```powershell
nvidia-smi
wsl --version
wsl --list --verbose
```

On a fresh host without WSL, run **PowerShell (Admin)**:

```powershell
wsl --install -d Ubuntu-24.04
```

Reboot if prompted and complete Ubuntu's first-run username/password setup. The
verified WSL baseline is 2.7.13.0 with kernel 6.18.33.2; use current supported
security updates and verify them before admitting users. Update WSL during setup
with `wsl --update`. Require VERSION 2 for Ubuntu-24.04 in `wsl --list --verbose`.

In **Ubuntu**, check that systemd is active:

```bash
ps -p 1 -o comm=
```

Expected: `systemd`. If needed, merge the `[boot] systemd=true` setting from
[the example](deployment/windows/wsl.conf.example) into `/etc/wsl.conf` using
`sudoedit /etc/wsl.conf`. Restart this new distro before continuing. On an existing
host, a WSL restart requires a shared maintenance window.

Keep WSL NAT and `localhostForwarding=true`; merge the
[Windows-side example](deployment/windows/wslconfig.example) into
`%UserProfile%\.wslconfig` only if needed. Do not disable Windows paging, change
encryption or erase old swap/dumps as an installation shortcut.

## 3. Install Docker and NVIDIA Container Toolkit

These are **fresh-host Ubuntu commands**. Work on the Linux filesystem, such as
`~/ephemeral-llm`, rather than under `/mnt/c`, for runtime performance.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git gnupg build-essential python3 python3-venv
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Create Docker's signed repository definition:

```bash
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF_DOCKER
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF_DOCKER
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Close this Ubuntu terminal and reopen it so the group change takes effect.
The verified baseline is Docker 29.8.0, Compose 5.1.3, containerd 2.3.4 and runc
1.5.1. Current signed security updates may be newer; record versions and validate
rather than restoring an old security exposure just to match a version number.
The Docker group grants administrative control over Docker; use a trusted operator.

Add NVIDIA's signed repository and configure the runtime:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker --set-as-default
sudo systemctl restart docker
```

The existing host uses NVIDIA as Docker's default runtime and the daemon's
`json-file` logs are bounded to 10 MB × 3 files. Merge those log settings from
[the daemon example](deployment/docker-daemon.example.json) using
`sudoedit /etc/docker/daemon.json`; preserve the runtime entry written by
`nvidia-ctk` and any unrelated settings. Restart Docker on this new host after
editing. The Compose services override daemon logging as appropriate: no Tika or
Ollama Docker logs, and bounded app logs. The observed toolkit/libnvidia-container
version was 1.19.0; use a supported signed version, not an old vulnerable package.

Verify before proceeding:

```bash
docker version
docker compose version
docker info -f '{{ .DriverStatus }}'
docker run --rm --gpus all --memory=256m --memory-swap=256m --ulimit core=0 \
  --entrypoint nvidia-smi ollama/ollama:0.32.15
```

Require `driver-type io.containerd.snapshotter.v1` from `docker info`. The current
installation uses the containerd image store (default for fresh Docker Engine 29+
installs), including its OCI image indexes/digest identities. If this check differs
on a **new host**, follow [Docker's image-store instructions](https://docs.docker.com/engine/storage/containerd/)
before building and pinning service images. Do not switch a working shared host as a setup shortcut.

These instructions use Docker Engine **inside Ubuntu**, not a second Docker
Desktop daemon. Use one daemon for this stack. Official references:
[Docker on Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html),
[WSL systemd](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## 4. Get the source and build the services

The private repository is [eowensai/HFS-ai](https://github.com/eowensai/HFS-ai).
Use your normal GitHub account or download its ZIP; never embed a token in a clone
command. In **Ubuntu**:

```bash
git clone https://github.com/eowensai/HFS-ai.git ~/ephemeral-llm
cd ~/ephemeral-llm
```

Use the tested release branch or the accepted default branch after publication. Keep the entire extracted repository,
including hidden files such as `.streamlit/config.toml`. Compose fixes the project
name at `ephemeral-llm`, so its volume/network names do not depend on the ZIP folder.

The application Dockerfile pins Python **3.14.7** by image digest and installs
Streamlit **1.63.0** and the complete tested dependency set from `requirements.lock`.
The container supplies Python; upgrading Ubuntu's system Python is unnecessary.
Development/tests use Python 3.14.7 as well. See the
[application upgrade record](docs/APPLICATION_UPGRADE.md) for acceptance and rollback.

Before building for a different site address, update both `server.allowedHosts`
and `server.corsAllowedOrigins` in `.streamlit/config.toml`. The former contains
hostnames/IPs without schemes or ports; the latter contains full UI origins.
Keep localhost entries and CORS/XSRF protections enabled. The recorded deployment
supports localhost, 127.0.0.1 and 172.16.64.243; it does not allow arbitrary Host names.

For a **fresh installation**, first build the no-dump policy and the configured Tika 4 full image:

```bash
sh deployment/privacy/build-nodump.sh
docker build -t ephemerai-tika:4.0.0-local deployment/tika
docker pull ollama/ollama:0.32.15
```

The generated library is small and intentionally not committed. It must exist
before service creation. It sets process dumpability and core limits to zero;
core-file size limits alone do not stop WSL's piped crash handler.

The Tika recipe starts from the digest-pinned official 4.0.0 full distribution,
keeps its OCR/fonts/native tools, and updates signed Ubuntu 26.04 packages.
The validated September 11 build uses OpenJDK 25.0.4 and Tesseract 5.5.0.
The distribution includes the launcher, libraries and plugins; a standalone Tika
4 jar is insufficient. Configuration is JSON. See [Tika build details](deployment/tika/README.md).

Inspect the newly built image without starting a parser or publishing ports:

```bash
docker run --rm --runtime=runc --network none --memory 512m --memory-swap 512m \
  --ulimit core=0 --entrypoint sh ephemerai-tika:4.0.0-local -c \
  'cat /etc/os-release; java -version; tesseract --list-langs'
```

Require Ubuntu 26.04, supported Java 17 or later (validated: 25.0.4), and OCR data `eng`, `deu`, `fra`, `ita`,
`jpn`, `spa`, `osd`. A local rebuild has its own image digest. Record that digest in
an ignored `.env` rather than pretending it is byte-identical to the old host's
image. The following **fresh-install-only** command refuses an existing `.env`:

```bash
python3 - <<'PY_PIN'
import subprocess
from pathlib import Path
image_id = subprocess.check_output(
    ['docker', 'image', 'inspect', 'ephemerai-tika:4.0.0-local', '--format', '{{.Id}}'],
    text=True).strip()
assert image_id.startswith('sha256:') and len(image_id) == 71
with Path('.env').open('x') as f:
    f.write('TIKA_IMAGE=ephemerai-tika:4.0.0-local@' + image_id + '\n')
print('Pinned the local Tika image in .env')
PY_PIN
docker compose config -q
docker compose build ephemeral-app
```

On an existing host, preserve `.env`; only update its `TIKA_IMAGE` after an accepted
parser build and a shared maintenance window. Compose requires that variable and never silently pulls an arbitrary Tika tag.
A Tika 3-to-4 upgrade must deploy the compatible app and parser together; preserve
the previous pair for rollback. See the [upgrade record](docs/TIKA4_UPGRADE.md).

## 5. Download the model, create its alias, and start the app

The required download is **Unsloth Qwen3.8-27B UD-Q6_K_M**. It includes the BF16
vision projector. Do not select the model card's example Q4 quant, ordinary Q6_K,
a different Qwen version, or a separate draft model. The embedded MTP tensors are
already in the required GGUF.

Only on this new installation, start Ollama and Tika, then pull the model:

```bash
docker compose up -d --no-build --pull never ollama tika-server
docker exec ollama ollama pull hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_M
```

The model download is about 24 GB. It goes into Docker's model volume, not Git or
the source ZIP. These are the verified upstream files:

| File on Hugging Face | Size | SHA-256 |
|---|---:|---|
| `Qwen3.8-27B-UD-Q6_K_M.gguf` | 23,088,409,504 bytes | `493301830a596b8ad56dc1329f80bbcb578c8e910da395feafdc9cd8263430bb` |
| `mmproj-BF16.gguf` | 931,146,432 bytes | `83ee4f4f205fa514161778c41df1ea14144faa0f713510893b63c2395f5c2d53` |

[Unsloth model repository](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) ·
[Hugging Face's Ollama instructions](https://huggingface.co/docs/hub/en/ollama).

Create the profile and shared alias in the same two steps used by the current
installation. The intermediate name is construction history stored in the manifest;
changing it produces a different manifest digest even when the weights match.
These aliases share the same downloaded blobs, so they do not duplicate the model
or start extra GPU runners. Run these commands only on the fresh installation:

```bash
docker cp Modelfile.hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072 ollama:/tmp/ephemerai-profile.Modelfile
docker exec ollama ollama create hfs-benchmark-qwen3.8-27b-ud-q6km-131072-force66 -f /tmp/ephemerai-profile.Modelfile
docker exec ollama sh -c 'sed "s|^FROM .*|FROM hfs-benchmark-qwen3.8-27b-ud-q6km-131072-force66|" /tmp/ephemerai-profile.Modelfile > /tmp/ephemerai-shared.Modelfile'
docker exec ollama ollama create hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072 -f /tmp/ephemerai-shared.Modelfile
docker exec ollama sh -c 'echo "44d415f1e36e9aea1cca2baaaa79da8cef57f255c8dd91f1e9ef0abfc8a6c33d  /root/.ollama/models/manifests/registry.ollama.ai/library/hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072/latest" | sha256sum -c -'
```

Require `OK` from the last command before starting EphemerAI. This two-step recipe
was checked with Ollama 0.32.15 against the current public HF metadata and recreated
the exact accepted digest in isolation. It retains 66 GPU layers, 131072 context,
32768 output, batch 128, embedded MTP 2, and the configured sampling profile.
If an upstream tag changes and the hash differs, stop and compare the file hashes,
Ollama version, template and recipe. Do not disable the app's identity check. The
[small manifest reference](deployment/model/manifest.json) contains no weights.

Now start only the application and verify the effective settings:

```bash
docker compose up -d --no-build --no-deps --pull never ephemeral-app
python3 scripts/verify_runtime.py
docker compose ps
```

The verifier checks cgroup memory/swap, bounded tmpfs declarations, core limits,
the locally configured Tika digest, accepted Ollama/model identities and browser/
disconnect settings. It sends no prompt. Tika may need a few seconds to initialize.

Open **http://localhost:8501** in a fresh browser window. Submit one fictional
prompt, such as “Fictional lighthouse code is 731. Reply with the number only.”
The first model load may take a few minutes. Then check:

```bash
docker exec ollama ollama ps
docker top ollama -eo pid,args
```

Require the accepted alias, `100% GPU`, context `131072`, one runner, `-ngl 66`,
`--cache-type-k q8_0`, `--cache-type-v q8_0`, `--flash-attn on`, `-b 128`, `-ub 128`,
and `--spec-draft-n-max 2`. The alias output limit remains 32768. Do not silently
lower context, change quantization or retarget the model for one shared client.

Upload a small fictional TXT/PDF/DOCX or image. Confirm a relevant answer, ordinary
streaming, no visible reasoning, and working Copy conversation. Click New Chat:
messages/attachments should disappear. Test two browser sessions to confirm one
session's reset preserves the other. On a phone/narrow window, confirm sidebar and
composer usability. [Recorded validation and limits](docs/VALIDATION.md).

## 6. Configure the browser address and Windows network access

The recorded pilot address is `172.16.64.243`. For another host, edit
`.streamlit/config.toml`: set `browser.serverAddress` to the actual Windows host
name/address and update `server.corsAllowedOrigins` while retaining localhost.
Keep `enableCORS=true` and `enableXsrfProtection=true`, then rebuild only the app.
Streamlit compares hostnames and has built-in accepted local/server origins; this
is not strict scheme/port-origin isolation or client authorization.

The existing site intentionally relies on router/network equipment to decide which
clients may reach Windows UI ports. Its Windows rules are Profile Any / RemoteAddress
Any. Preserve that accepted policy on the existing host. On a replacement host,
establish and test the upstream access boundary before enabling LAN access.

For a **new standalone host**, an administrator can provision the one required
Windows UI rule once (this is not part of the logon script):

```powershell
if (-not (Get-NetFirewallRule -DisplayName 'EphemerAI UI 8501' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName 'EphemerAI UI 8501' -Direction Inbound `
        -Protocol TCP -LocalPort 8501 -Action Allow -Profile Any -RemoteAddress Any
}
```

Inspect existing/overlapping rules instead of deleting them. Do not add rules or
forwarding for Tika 9998 or Ollama 11434. The optional API Compose override remains
available for separately reviewed use, defaulting to loopback; it is not an installation
requirement and does not add authentication.

## 7. Restore Windows logon startup

The currently deployed task is **Monitor WSL Kiosk Service**, running
`C:\Scripts\Start-EphemerAl.ps1` under the logged-on user with highest privileges.
The script starts/keeps WSL alive and refreshes UI forwarding. Docker's enabled
systemd service and container `restart: unless-stopped` policies start the stack
when WSL starts. Intentionally stopped containers stay stopped until started again.

Copy the repository to a Windows-accessible location. From **PowerShell (Admin)**,
run its registration script using your actual extracted repository path:

```powershell
& 'C:\path\to\HFS-ai\deployment\windows\Register-StartupTask.ps1'
```

For the existing ecosystem **only when HFS Knowledge is independently installed
on 8503**, use:

```powershell
& 'C:\path\to\HFS-ai\deployment\windows\Register-StartupTask.ps1' -UiPorts '8501,8503'
```

The default forwards only EphemerAI 8501. Both scripts are parameterized for the
WSL distro name. Registration copies the script to `C:\Scripts`, uses a logon
trigger delayed 30 seconds, and an interactive elevated principal. It does not
create firewall rules. It does not install HFS, add an HFS database, expose V3, or
run before Windows login. No automatic Windows login is configured.

Test the task from Task Scheduler, then test a fresh Windows logon in a maintenance
window. Confirm localhost and an approved peer reach 8501, backend ports stay
unreachable from Windows, and an unapproved peer is blocked by the upstream policy.
Server-local tests alone do not certify router/peer filtering.

## 8. Update or stop an existing installation

Read [operations](docs/OPERATIONS.md) before touching shared services. Preserve
uncommitted changes and the old app image. Confirm active requests have finished.
For a normal EphemerAI code/config update:

```bash
cd ~/ephemeral-llm
sh deployment/privacy/build-nodump.sh
docker compose up -d --build --no-deps --force-recreate ephemeral-app
python3 scripts/verify_runtime.py
```

The policy build replaces its output atomically, preserving already mapped
inodes. If the policy source or toolchain changes, verify the candidate and
coordinate recreation of all affected services; an app-only restart does not
apply a new policy to the shared backends. Retain the verified library when its
source is unchanged; the build command is required if that generated file is absent.
App recreation clears in-memory sessions. It must not restart Ollama/Tika, pull or
recreate models, change HFS data, or stop WSL merely to update this application.

To stop/start only the app:

```bash
docker compose stop ephemeral-app
docker compose start ephemeral-app
```

Shared backend, Docker, driver or WSL changes require an idle maintenance window
covering HFS and all active prototypes. Never use `docker compose down -v`, model
removal, broad Docker pruning, or WSL unregistration as a troubleshooting shortcut.

## 9. Troubleshooting

- A missing model or wrong digest: check the exact quant, recipe and upstream content hashes; don't
  change the allowlisted digest or use a different alias as a workaround.
- Tika image unavailable: it is a local maintenance image, not a pullable Docker
  Hub tag. Build it from the included digest-pinned full-image recipe and pin its local digest. See [Tika maintenance](deployment/tika/README.md).
- Missing preload library: build it before creating containers and verify the
  mounted file. Never ignore loader errors or claim RLIMIT_CORE alone is sufficient.
- Memory failure: inspect cgroup `memory.events`, peaks and model/GPU placement.
  Keep swap disabled; use a measured capacity review rather than unlimited RAM.
- Logs: Ollama/Tika Docker logging is disabled. The app has bounded rotated logs.
  Do not enable content logging or paste real documents/prompts into diagnostic tools.
- Lost machine: clone/download this repository and follow the fresh installation
  steps, including redownloading the model. HFS Knowledge has its own installation
  and intentionally persistent data; it is outside this repository.
