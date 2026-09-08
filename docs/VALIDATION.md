# Validation — September 8, 2026

This publication imports the currently deployed EphemerAI application and adds a
recovery kit. It was prepared outside the live checkout. Publication did not
recreate production containers, change the live Git remote, alter Windows settings,
modify the model profile, or modify HFS source/data.

## Repository checks

- Both `python -m pytest -q` and `pytest -q`: **113 passed**, with two existing
  Tika/pkg_resources deprecation warnings per run.
- Python compilation, shell syntax and `docker compose config -q`: passed.
- Existing development test environment: `pip check` passed; production dependencies
  remain unchanged. No test/browser tooling was added to the production image.
- PowerShell AST parsing passed for both Windows scripts. They were not registered
  or executed against the live host during this publication.
- The core-dump library compiled from the included source; a disposable local
  process reported `PR_GET_DUMPABLE=0`. The build now replaces its output atomically.
- Ruff reports **81 pre-existing findings** in imported application/tests. The new
  recovery scripts/tests have no findings. File permissions were normalized to the
  intended Git modes for linting, avoiding Windows-mount executable-bit artifacts.
- README/deployment-guide local links resolve. The homepage JPEG was captured from
  the actual deployed UI in a fresh isolated Chromium session with zero messages.

Fourteen recovery tests use tiny fictional archives. They cover exact valid model
members, corruption, incorrect size, missing/extra/duplicate members, traversal,
symlinks, manifest mismatch, unexpected outer inventory, refusal to overwrite a
capture destination, refusal of existing containers/production volume, and refusal
of a legacy Docker image store before loading images. Tests do not restore to a
production volume or start another model runner.

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
image store, matching the OCI index identities in the saved images.

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

## Recovery validation boundaries

The separate recovery set preserves the three exact service images and only the
selected model manifest plus its five content-addressed blobs. Archive hashes and
all model member paths, types, sizes and hashes are verified during capture. The
saved OCI index lists the same three identities as `deployment/runtime-lock.json`.
Copy the set off this machine and run `scripts/recovery.py verify` on that copy.

A full Windows replacement-host restore, Windows logon/peer-network test and fresh
GPU cold-start drill have **not** been executed here. The deployment guide supplies
those acceptance steps; source-only rebuilding can produce different binary
identities. Browser/OS remnants and old disk contents remain documented limitations,
not properties that this test suite certifies away.
