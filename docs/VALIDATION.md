> **Historical validation:** these results predate the FP4 port. See [the port record](HFS_AI_FP4_PORT.md) for current branch checks and their limits.

# Validation — September 8, 2026

> Current application validation: [Python 3.14 / Streamlit 1.63](APPLICATION_UPGRADE.md).
> Parser validation: [TIKA4_UPGRADE.md](TIKA4_UPGRADE.md).
> The dated results below remain historical evidence.

This publication imports the currently deployed EphemerAI application and adds a
source-only installation guide. It was prepared outside the live checkout. Publication did not
recreate production containers, change the live Git remote, alter Windows settings,
modify the model profile, or modify HFS source/data.

## Repository checks

- Both `python -m pytest -q` and `pytest -q`: **99 passed**, with two existing
  Tika/pkg_resources deprecation warnings per run.
- Python compilation, shell syntax and `docker compose config -q`: passed.
- Existing development test environment: `pip check` passed; production dependencies
  remain unchanged. No test/browser tooling was added to the production image.
- PowerShell AST parsing passed for both Windows scripts. They were not registered
  or executed against the live host during this publication.
- The core-dump library compiled from the included source; a disposable local
  process reported `PR_GET_DUMPABLE=0`. The build now replaces its output atomically.
- Ruff reports **81 pre-existing findings** in imported application/tests. The new
  installation/verifier changes have no findings. File permissions were normalized to the
  intended Git modes for linting, avoiding Windows-mount executable-bit artifacts.
- README/deployment-guide local links resolve. The homepage JPEG was captured from
  the actual deployed UI in a fresh isolated Chromium session with zero messages.

## Effective deployed configuration rechecked

The read-only `scripts/verify_runtime.py` check passed against the running services:

| Service | Effective `memory.max` | `memory.swap.max` / current | OOM kills |
|---|---:|---:|---:|
| EphemerAI | 2,147,483,648 | 0 / 0 | 0 |
| Tika | 6,442,450,944 | 0 / 0 | 0 |
| Ollama | 19,327,352,832 | 0 / 0 | 0 |

It also checked core limits, bounded tmpfs declarations, private backend ports,
backend image identities, exact model manifest, app process dumpability,
CORS/XSRF enabled, and disconnected-session TTL zero. The host uses the containerd
image store, with the current Tika digest matching its configured pin.

## Functional evidence from the deployed privacy remediation

The preceding September 8 deployment validation used only bounded fictional data:

- Two real browser sessions: New Chat released that conversation's messages,
  uploads and caches while the other session remained intact. Browser disconnection
  released the tested owner in about **0.062 seconds** on a clean closure.
- An ordinary upload through the application/Tika and native shared-model inference
  succeeded; the recorded small inference took about **6.07 seconds**.
- Fresh fictional PNG and PDF OCR fixtures worked through both the EphemerAI and
  HFS parsing adapters and returned the expected fictional code `731`.
- Service/worker mappings and core limits were inspected, and a tiny disposable
  crash probe produced no core artifact. GPU/model placement retained the accepted
  shared profile. There were no OOM kills or new Linux container swap use.

The captured screenshot and read-only runtime checks were repeated for this
repository publication. Real HFS documents, stored answers and databases were not
used as publication fixtures or copied into the kit.

## Source installation checks and boundaries

The current public Hugging Face manifest and file metadata match the deployed
Unsloth UD-Q6_K_M GGUF and BF16 projector SHA-256 identities. Only 696 bytes of
public config/parameter blobs were downloaded for the recipe check, alongside the
small manifest. No model weights were downloaded for this publication.

The two-step alias recipe ran successfully under Ollama 0.32.15 in a disposable,
network-isolated container with `--runtime=runc`, no GPUs, 1 GiB RAM, zero swap and
128 MiB tmpfs. The check used public GGUF headers and sparse temporary stand-ins
to exercise metadata construction without copying full weights. It reproduced
manifest `44d415f1e36e9aea1cca2baaaa79da8cef57f255c8dd91f1e9ef0abfc8a6c33d`
exactly, and `ollama ps` showed no inference runner. This checks the creation recipe;
it is not an inference test using the stand-ins. Production model storage was
mounted read-only. The actual model already passed the earlier functional checks.

Recent task records were reviewed directly, including Tika migration, image/UI
fixes, the corrected firewall policy and the completed WSL/Docker update checkpoint.
The environment record lists what each contributed to the installation guide.

The Tika build recipe itself was deployed and functionally validated on September 7;
this publication did not rebuild/redeploy Tika. Source installation now pins each
validated local build digest in `.env`; the live-host fallback digest is preserved.
The artifact fetcher retains checksum/signer checks and adds Apache archive fallback.

A complete fresh Windows install, full model redownload, GPU cold-start and new
logon/peer-network acceptance test have not been repeated here. The guide includes
those steps. Browser/OS remnants and previous disk contents remain outside the
privacy guarantee. No large model/container backup is part of this deliverable.
