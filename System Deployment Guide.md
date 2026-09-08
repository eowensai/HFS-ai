# EphemerAI — System Deployment Guide

This guide rebuilds the September 8, 2026 deployment on a Windows 11 workstation.
It also explains safe updates when HFS Knowledge already shares its backend.
Commands marked **PowerShell (Admin)** run on Windows. Commands marked **Ubuntu**
run inside WSL. Do not run fresh-host installation steps on a working shared host.

## 1. Choose the right path

| Situation | Start here |
|---|---|
| Working host, update EphemerAI only | [App-only update](#8-update-or-stop-an-existing-installation) |
| Replacement host with the recovery archives | Install prerequisites below, then [restore assets](#4-restore-the-exact-images-and-model) |
| Source repository only, no recovery archives | Read [source-only recovery limits](docs/RECOVERY.md#source-only-recovery) first |

The repository contains no HFS Knowledge application or operational data.
A fresh standalone EphemerAI installation works without HFS. The required alias
keeps its shared name either way. If HFS is installed separately, coordinate all
Ollama/Tika, Docker, GPU and WSL maintenance with its operator.

## 2. Prepare Windows, WSL and the GPU

The measured host uses Windows 11, 64 GiB RAM, two RTX 5060 Ti 16 GiB cards, and
about 30 GiB RAM allocated to WSL. Keep at least 30 GiB available to WSL and adequate
Windows headroom; smaller hosts are not certified for this model profile. Allow
at least 100 GiB free disk for images, the model, builds and a recovery copy.

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
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify before proceeding:

```bash
docker version
docker compose version
docker info -f '{{ .DriverStatus }}'
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
```

Require `driver-type io.containerd.snapshotter.v1` from `docker info`. The saved
images use OCI indexes, so exact restoration requires the containerd image store
(default for fresh Docker Engine 29+ installs). An upgraded legacy store can lose
the recorded index identities. If this check differs on a **new recovery host**,
follow [Docker's image-store instructions](https://docs.docker.com/engine/storage/containerd/)
before loading assets. Do not switch a working shared host as a setup shortcut.

These instructions use Docker Engine **inside Ubuntu**, not a second Docker
Desktop daemon. Use one daemon for this stack. Official references:
[Docker on Ubuntu](https://docs.docker.com/engine/install/ubuntu/),
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html),
[WSL systemd](https://learn.microsoft.com/en-us/windows/wsl/systemd).

## 4. Restore the exact images and model

Obtain the repository branch/merged `main` from
[github.com/eowensai/HFS-ai](https://github.com/eowensai/HFS-ai). It is currently
private: authenticate with your normal GitHub account or download the ZIP in the
web UI. Never embed a token in a clone command or commit it.

In **Ubuntu**, after authentication:

```bash
git clone https://github.com/eowensai/HFS-ai.git ~/ephemeral-llm
cd ~/ephemeral-llm
```

Before the recovery branch is merged, select that branch in GitHub's ZIP download
or run `git switch recovery/current-system-2026-09-08` after cloning. Do not
accidentally deploy the older `main` snapshot.
Compose explicitly names the project `ephemeral-llm`, preserving its model-volume
and network identities regardless of the checkout folder name.

Transfer the separately retained recovery `assets/` directory to the new host.
It contains `runtime-images.tar`, `model.tar`, `assets.json` and `SHA256SUMS`.
Set this shell variable to its actual path:

```bash
RECOVERY_ASSETS=/mnt/d/HFS-ai-recovery/assets
python3 scripts/recovery.py verify "$RECOVERY_ASSETS"
python3 scripts/recovery.py restore-assets "$RECOVERY_ASSETS"
```

`/mnt/d/...` is an example backup-drive path; replace it before running. Restore
refuses any existing `ephemeral-app`, `ollama` or `tika-server` container and refuses
an existing `ephemeral-llm_ollama-models` volume. It verifies archive checksums,
model artifact names/types/content hashes, and loaded image identities. It creates
only the absent model volume and starts no inference service. Never delete an
existing volume to get past this check; use a genuinely fresh recovery host.

Build the core-dump policy before **any** container is started:

```bash
sh deployment/privacy/build-nodump.sh
docker compose config -q
```

The compiled library is generated locally and is not a Git asset. It uses the
containers' existing libc and is mounted read-only. A zero core-file size limit
alone is insufficient for WSL's piped crash handler. The library sets process
dumpability to zero too. Reverify after image or architecture changes.

The saved model manifest preserves the **exact** accepted alias identity.
The Modelfile is included for understanding/reviewed rebuilding; a new alias made
from an upstream mutable tag is not guaranteed to produce the same digest. Do not
weaken the application's identity check to make a mismatched model start.

## 5. Start the recovered stack and verify it

On this **new host**, start the restored images without a build or pull:

```bash
docker compose up -d --no-build --pull never ollama tika-server ephemeral-app
python3 scripts/verify_runtime.py
```

The verifier checks effective cgroup memory/swap values, bounded tmpfs settings,
core limits, accepted backend images, model manifest and CORS/XSRF/disconnect
settings. It makes no inference request. Check container states with
`docker compose ps`. Tika may need several seconds to initialize.

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

If you changed the host address in the Streamlit configuration, rebuild only the
app using the update command in section 8 after this baseline test. The saved app
image contains the original pilot address; localhost works for initial recovery.

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
available for separately reviewed use, defaulting to loopback; it is not a recovery
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

## 9. Troubleshooting and durable recovery

- A missing model or wrong digest: restore the exact selected artifacts; don't
  change the allowlisted digest or use a different alias as a workaround.
- Tika image unavailable: it is a local maintenance image, not a pullable Docker
  Hub tag. Load the verified archive. See [Tika maintenance](deployment/tika/README.md).
- Missing preload library: build it before creating containers and verify the
  mounted file. Never ignore loader errors or claim RLIMIT_CORE alone is sufficient.
- Memory failure: inspect cgroup `memory.events`, peaks and model/GPU placement.
  Keep swap disabled; use a measured capacity review rather than unlimited RAM.
- Logs: Ollama/Tika Docker logging is disabled. The app has bounded rotated logs.
  Do not enable content logging or paste real documents/prompts into diagnostic tools.
- Lost machine: Git supplies source and instructions, not large artifacts or HFS
  data. Keep a verified recovery archive on another device/service. [Recovery guide](docs/RECOVERY.md).
