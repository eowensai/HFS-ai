> September15 update: the selected departmental frontend/engine and current commands are in [CURRENT_DEPLOYMENT.md](CURRENT_DEPLOYMENT.md) and the [operator guide](../System%20Deployment%20Guide.md). Historical shared-stack commands below require the explicit `docker-compose.ollama-shared.yml`; bare Compose no longer selects Ollama. Earlier evidence retains its original cutoff.

# FP4 / DFlash and isolated Ollama recovery


This addendum is for the private HFS-ai repository. Keep the existing
[Windows/WSL installation guide](../System%20Deployment%20Guide.md) for prerequisite
setup. Clone **HFS-ai**, not EphemerAl, into a new WSL directory:

```bash
git clone --branch codex/hfsai-fp4-dflash-reproducible https://github.com/eowensai/HFS-ai.git ~/hfsai-fp4-review
cd ~/hfsai-fp4-review
```

GitHub authentication for this private repository is required. Alternatively,
download this branch's ZIP while signed into GitHub and extract it into WSL.
Do not overwrite `/home/eko/ephemeral-llm` or change its remote.

`docker-compose.yml` retains the original HFS-ai Ollama named volumes and shared
services. The new helper uses `docker-compose.fp4.yml` or
`docker-compose.ollama-recovery.yml`, with separate `.local` model storage and
project names. Bare `docker compose up` therefore still selects the original
Ollama stack, **not FP4**. Use the explicit helper commands below.

The departmental `.streamlit/config.toml` is preserved. The isolated profiles
bind to loopback unless `.env` explicitly sets `EPHEMERAI_BIND_ADDRESS=0.0.0.0`.
For the existing Windows port-forwarding arrangement, copy the new keys from
`.env.example` into your operator `.env`, retaining the existing network access
controls. Do not replace an existing `.env` blindly. Do not forward inference
or Tika ports. The preserved Windows startup script wakes WSL and updates UI
forwarding; Docker restarts containers previously started with `unless-stopped`.
It does not select a backend or start a container explicitly stopped by you.

These instructions run inside Linux/WSL2 with Docker Engine, Docker Compose v2,
BuildKit and NVIDIA container support already installed. Use the WSL filesystem
for the checkout and model storage. Initial provisioning needs internet access;
inference is local/offline afterward. The optional FP4 recipe targets the tested
two RTX 5060 Ti 16 GB cards, not arbitrary hardware.

## Preserve your existing installation first

Do not run these commands inside the active installation or point `.local` at a
production model store. Clone the review branch into a separate directory. The
scripts only manage the `ephemerai-review` and `ephemerai-review-fp4` projects and
refuse to start while another Docker GPU container is running. They do not stop
other installations for you. Bare host GPU processes still require an operator
check before a future cutover.

The default UI port is 8501 on localhost. Ollama and Tika APIs are not published.
Do not start both inference profiles together on the same pair of cards.

## Ollama Q6

From the new checkout:

```bash
python3 scripts/deployment.py prepare ollama
python3 scripts/deployment.py models ollama
python3 scripts/deployment.py config ollama
```

Preparation builds the application, Tika and privacy library. The model command
provisions the exact Q6 weights, BF16 vision component and preserved Ollama alias
manifest into `.local/ollama`. Downloads are revision-pinned and SHA-256 checked;
partial downloads can resume. It does not recreate the alias from a mutable tag.

Only after an approved cutover, with the other engine stopped:

```bash
python3 scripts/deployment.py start ollama
python3 scripts/verify_deployment.py ollama
```

Open http://localhost:8501. On first use Ollama must load its model before full
readiness becomes available. The app verifies the required model metadata and
actual context instead of accepting a generic healthy API.

## FP4 with DFlash, or the simpler MTP fallback

The current machine uses DFlash. Choose one profile explicitly in a new checkout:

```bash
python3 scripts/deployment.py prepare fp4 --profile dflash
python3 scripts/deployment.py models fp4 --profile dflash
python3 scripts/deployment.py config fp4 --profile dflash
```

Use `--profile mtp` instead for the simpler fallback. Preparation changes files
and builds software in this checkout; it does not change another installation.
This source distribution excludes the native compiled object because its upstream
helper has conflicting license notices. Read
[native build provenance](../deployment/fp4/native/README.md) before a new source build.
A missing object triggers a pinned source build in a disposable compiler container;
that step requires an idle compatible GPU and refuses to run beside inference.
Your private recovery archive already contains the qualified object and exact images.

The build pins the CUDA 13 base, engine wheels, native attention adapter, DFlash
patches and numerical corrections. The model command downloads the complete RadixArk
target and, for DFlash, the pinned W4A16 drafter, including vision metadata.
All files are SHA-256 checked. Allow substantial disk space for software images,
compiler downloads and model files. No weights are stored in GitHub.

The generated `.local/images.env` selects images and layer placement;
`.local/deployment.json` ties readiness to the engine, model and context profile.
Keep both files with this checkout. Keep them out of Git, including this private repository.

Only after a planned cutover, with the existing GPU engine stopped:

```bash
python3 scripts/deployment.py start fp4 --profile dflash
python3 scripts/verify_deployment.py fp4
```

The first startup checks model identities and builds runtime caches. It can take
several minutes. DFlash uses seven proposals, batch 1024, a 32/32 layer split and
about 2.85 GiB of attention/cache pool per GPU; MTP uses three proposals and its
separately pinned profile. Both retain 131,072 total tokens, images, and FP8 K/V.
The app reserves 32,768 tokens for output; image tokens also consume context.

## Stop, inspect, or switch later

```bash
python3 scripts/deployment.py status fp4
python3 scripts/deployment.py stop fp4
python3 scripts/deployment.py start ollama
```

Substitute `ollama` for inspection/stopping that profile. Switching requires a
planned idle window and both profiles already prepared. `stop` preserves containers,
images and model files. No command removes production volumes or HFS data.
Do not use `docker system prune`, `compose down -v`, or old benchmark restore
scripts as a recovery mechanism.

To recover the exact original installation rather than a rebuilt equivalent, use
the separately prepared recovery archive's `RECOVERY.md` and `recover.py`.
The refreshed private package includes the original Ollama and current FP4 source,
configuration, checksums, and software images, plus the MTP fallback. It excludes
model weights. Model recovery requires internet access and continued availability
of the pinned files. Loading the saved images avoids rebuilding the exact software.

## Before adopting a rebuilt image

Verify a synthetic text question, paired images, an image follow-up, a Tika-parsed
document, streaming, New Chat, exact context and MTP acceptance. Confirm GPU memory
placement and compare a short and long-input timing control. The September 14 deployment passed bounded runtime and browser checks; see
[current results and unresolved quality limitations](CURRENT_DEPLOYMENT.md).
Packaging this review does not restart production or substitute rebuilt images.

This is the private `eowensai/HFS-ai` application, not the separate HFS Knowledge experiment. The public EphemerAl roadmap is not part of this port. Voice is excluded.
