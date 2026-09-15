# FP4 / DFlash port to the private HFS-ai repository

The owner corrected the repository destination: **eowensai/HFS-ai** is the
departmental application; **eowensai/EphemerAl** is its separate public version.
EphemerAl PR #159 was prepared in the wrong repository. This branch ports its
backend work onto HFS-ai's current main instead of copying the public fork over it.
HFS Knowledge is a separate experiment and is not changed.

## Exact bases

- HFS-ai main: `c45e79e5e97e517ded1a1351f1e36959cc3f2185`.
- Verified base tree: `19170ffd101f07f688012850fc9186d5d7b2bc56`, all 94 file
  contents and executable modes matched GitHub before edits.
- Imported backend source: EphemerAl PR #159 revision
  `b9a758099dad7321365ab6ed7a8be76c929b0d1a`.
- Local work was performed in an isolated checkout. The GitHub commit uses the
  real HFS-ai main commit as its parent; no public-fork history is merged.

## What changes

The same application can select Ollama or pinned vLLM. FP4 readiness checks the
model, context and deployment identity; request-owned connections support prompt
cancellation and deadlines. The selected FP4 profile uses the RadixArk NVFP4
target, W4A16 DFlash2, seven proposals, PP2/TP1, FP8 attention caches, 131,072 total
tokens, images and medium reasoning. The native attention, compiler/runtime,
draft embedding, cache-placement and numerical-policy patches retain their
original hashes. MTP3 remains the simpler prepared fallback.

The citation/source-label clarification in the deployed system prompt is included.
It does not establish that the model always grounds answers correctly. Other
HFS-ai prompt content is retained.

## What is preserved or adapted

- Departmental Streamlit host/origin settings, static branding, UI source, CSS,
  Windows startup/forwarding scripts and existing runtime/package records.
- Original `docker-compose.yml`, its named model volume, service/container names,
  Tika settings, internal API boundary and optional loopback API override.
- The atomic `deployment/privacy/build-nodump.sh` implementation already on HFS-ai
  main, rather than the public branch's older in-place library write.
- Existing operational and validation records, labeled as the earlier Ollama
  baseline where needed. The original setup guide remains available.

`scripts/deployment.py` explicitly selects `docker-compose.fp4.yml` or the new
`docker-compose.ollama-recovery.yml`. Both use isolated review projects and
checkout-local model storage. Neither replaces the shared-stack Compose file.
The helper refuses to start beside another Docker GPU inference installation.
Operator `.env` settings remain separate from generated image identities.

The new [FP4 installation guide](FP4_DEPLOYMENT.md) uses the private repository's
branch and explains Windows/WSL startup and departmental LAN configuration.
Bare `docker compose up` still refers to the preserved Ollama stack.

## Evidence and validation boundaries

See [current deployment](CURRENT_DEPLOYMENT.md) and
[qualification](FP4_QUALIFICATION.md) for the historical GPU/runtime results.
These measurements belong to the September 14 deployed binaries; they are not a
new inference run of this source port. The strict factual-grounding gate failed
on both tested backends, and that limitation is retained.

Fresh validation of this port (Python 3.14.7, isolated CPU-only containers):

- `python -m pytest -q`: **407 passed** (12.64 s).
- `pytest -q`: **407 passed** (11.93 s).
- Python syntax compilation, Ruff and `pip check`: passed.
- Application Docker build: passed with a separate test image tag.
- Desktop and mobile UI smoke tests: passed with networking disabled. The
  expected backend-unavailable notices were present; this did not query a model
  or Tika. Screenshots are local ignored artifacts, not repository assets.
- All three Compose configurations render successfully. FP4 rendering used the
  recorded DFlash image identity and 32/32 partition as explicit test inputs;
  generated per-install image identities remain required before starting it.
- 28 application runtime files and 36 engine/build inputs match the retained
  tested FP4 source byte-for-byte. Eighteen HFS-ai configuration/runtime-record
  files, including departmental origins and the shared Compose, remain unchanged.
- 74 relative documentation links resolve. The tracked-file audit excludes
  weights, native objects, software archives and credential patterns.

No GPU experiment,
service cutover, main merge or release publication is part of this correction.
The existing model-less recovery archive remains the recovery record for the
unchanged live installation. It predates this corrected PR destination.

Model weights, native objects, wheels, software images, private operational data
and voice experiments are excluded. The upstream native helper's unresolved
license-notice ambiguity remains documented in
[native provenance](../deployment/fp4/native/README.md); moving the recipe to a
private repository does not settle that ambiguity.
