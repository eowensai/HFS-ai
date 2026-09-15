# EphemerAI

EphemerAI is a local document-and-image chat application running on a Windows 11
workstation through WSL2 and Docker. Prompts and files are processed by local
Ollama or the optional pinned vLLM FP4 backend, plus Apache Tika. This is
**eowensai/HFS-ai**, the private departmental source repository. EphemerAl is the
separate public version.

The new [FP4/DFlash profile](docs/FP4_DEPLOYMENT.md) reproduces the selected fast
build while retaining the original Ollama stack. Start with the
[port and validation record](docs/HFS_AI_FP4_PORT.md) and
[current deployment / quality limitations](docs/CURRENT_DEPLOYMENT.md). The
remaining stack and setup sections below describe the preserved September 11
Ollama baseline; they are not the FP4 launch recipe.

![EphemerAI homepage](Ephemeral%20Screenshot.jpg)

Start with the [System Deployment Guide](System%20Deployment%20Guide.md).
The [current-system record](docs/CURRENT_SYSTEM.md) distinguishes deployed facts
from host-specific setup choices and remaining limitations.

## What is included

- The deployed Streamlit UI, responsive layout, document/image handling, readable
  assistant formatting, copy controls, and fictional regression tests.
- The fixed shared Qwen model definition and exact accepted model manifest.
- Docker Compose, the pinned Tika 4 full-image build, core-dump policy source,
  bounded RAM/tmpfs, and zero Linux container swap configuration.
- Windows logon/WSL forwarding scripts and detailed fresh-host installation,
  app-update and verification instructions.

HFS Knowledge and its V3 prototype are separate applications. Their source,
documents, databases, jobs, answers and credentials are **not included**. They may
share the same Ollama/Tika services; see [shared-service operations](docs/OPERATIONS.md).
The word `hfs` in the model alias is part of the required shared model identity,
not a dependency on the HFS Knowledge application.

## Preserved Ollama stack

| Component | Accepted baseline |
|---|---|
| Application | Python 3.14.7, Streamlit 1.63.0, Pillow 12.3.0 |
| Model server | Ollama 0.32.15 |
| Model | Qwen3.8-27B, Unsloth UD-Q6_K_M |
| Required alias | `hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072` |
| Context / output ceiling | 131,072 / 32,768 tokens |
| GPU profile | 66 layers, Q8 KV, Flash Attention, batch 128, embedded MTP 2 |
| Parallelism | One loaded model and one parallel inference slot |
| Parser | Tika 4.0.0 full image; Markdown extraction, OCR/native helpers |
| Linux memory caps | App 2 GiB; Tika 6 GiB; Ollama 18 GiB; zero container swap |

The validated host has two RTX 5060 Ti 16 GiB GPUs and approximately 30 GiB
available to WSL. Plan for **32 GiB total NVIDIA VRAM and at least 30 GiB WSL RAM**
for this fixed profile; the actual workstation has 64 GiB host RAM. These are
measured pilot requirements, not a guarantee for unlimited concurrent uploads.
EphemerAI verifies the accepted manifest digest and Q6/vision capabilities and
fails closed if they differ. It does not silently select another model.

Ordinary requests explicitly use medium reasoning. **Thinking Mode** selects
`xhigh` for one submission and resets off; native callers use `think: "max"` for
that one request. Reasoning deltas and embedded thought blocks are filtered from
visible answers. The output ceiling is 32,768 tokens in either mode.

See the [combined application upgrade record](docs/APPLICATION_UPGRADE.md) for
version decisions, native file/image paste, validation and app-only rollback.

## Document extraction

Tika 4 supplies Markdown headings, lists and tables to the model. EphemerAI keeps
Word comment authors in a labeled attribution section and preserves usable partial
results with a warning. OCR and supported formats remain available; this is not a
guarantee of better answers or perfect layout recognition. The model is unchanged.

Limits remain 50 MiB per upload, eight files / 64 MiB per submission, 180 seconds
per parse, 256 KiB extracted UTF-8 text per file and 512 KiB per submission. The
server separately limits extracted characters to 262,144 and worker tasks to 150
seconds. Markdown syntax consumes some text budget. HFS Knowledge is parked
pending its own Tika 4 adapter and ingestion-limit decision. See the
[Tika 4 change record](docs/TIKA4_UPGRADE.md).

## Privacy and access

EphemerAI has no chat database and does not intentionally save chat/document
content. New Chat clears its conversation-owned messages, upload buffers and
caches without clearing another user's session. Parsing no longer retains a
second parsed-text cache. A supported Streamlit session-resource hook releases
app-owned payloads on detected WebSocket disconnection; reconnect TTL is zero.

All three services handling EphemerAI data enforce zero Linux container swap,
bounded temporary filesystems, and process core-dump controls. Clean browser
closure triggered cleanup in about 0.06 seconds in a fictional test; silent
network loss normally takes up to about 60 seconds plus scheduling to detect.
In-flight requests, framework buffers, native/GPU memory, browser storage,
clipboard, exports and Windows paging/crash dumps have additional lifetimes.
There is **no forensic-erasure guarantee**, and these controls do not erase old
swap, dumps or disk contents. [Privacy details](deployment/privacy/README.md).

CORS and XSRF protections are **enabled**. The UI has no login or TLS layer.
The current installation relies on upstream network equipment to control access
to the UI; that policy is not created by this repository. Docker publishes only
8501. Ollama 11434 and Tika 9998 remain internal. Browser-origin checks do not
replace network access control. Do not expose this deployment to the public
internet without a separately designed authentication/TLS boundary.

## Install or update

- **Fresh workstation:** follow the [complete setup guide](System%20Deployment%20Guide.md).
- **Downloads during setup:** pull Ollama, build Tika from the digest-pinned official full distribution,
  and download `unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_M` from Hugging Face. Model weights
  and container images are not part of the repository or source ZIP.
- **Update an existing shared installation:** finish active requests, then rebuild
  only EphemerAI with `docker compose up -d --build --no-deps --force-recreate ephemeral-app`.
  Do not restart shared backends or recreate the alias as an app-update test.
- **Verify a deployment:** run `python3 scripts/verify_runtime.py`, then check the
  GPU/model state and one fictional upload as described in the setup guide.
- **Stop only EphemerAI:** `docker compose stop ephemeral-app`. A WSL shutdown stops
  HFS and other prototypes too and belongs to a coordinated maintenance window.

## Development

Use Python 3.14.7 and an isolated environment. Production dependencies are declared
in `requirements.txt` and fully pinned in `requirements.lock`; pytest, Ruff and
Playwright are development-only. The Docker base image is pinned by digest.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -c requirements.lock -r requirements-dev.txt
python -m pytest -q
pytest -q
python -m py_compile ephemeral_app.py ephemeral/*.py scripts/verify_runtime.py
ruff check .
```

For browser tests, install the Playwright Chromium runtime in the development
environment, then run `python scripts/ui_smoke.py`. Never test with real HFS data
or restart shared services merely to test this UI. See [validation](docs/VALIDATION.md)
for the published baseline. The [reliability handoff](docs/RELIABILITY_READINESS.md)
records the scoped candidate changes, limits, current checks and validation history.

The application code is MIT-licensed; model weights and bundled upstream software
retain their own licenses. See [LICENSE.md](LICENSE.md).
