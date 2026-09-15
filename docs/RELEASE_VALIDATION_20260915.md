# HFS-ai release validation: September 15, 2026

## Decision and scope

The exact qualified stable-prefix frontend is adopted. The corrected DFlash/native engine remains unchanged and was not restarted or recreated. This update belongs only to `eowensai/HFS-ai`; the separate EphemerAl repository and its closed PR159 were not changed. HFS-ai main at `90e0624536850b3a8b5cbd6648ad4bc3ee928ba4` (merged PR9) is the integration base.

Frontend: `hfsai-app-stable-prefix`, image `sha256:32bd1e140e88eed3b2fb5b0f77eefce5515194114091c8d580f076e6f4547aa6`.
Engine: `ephemerai-vllm-bounded`, image `sha256:8b6b56ae42e195d662d7d09c99ed4fcd405b4a4d6684b26f13423f7b39901452`.
The old `ephemeral-app-bounded` container and image remain stopped and recoverable. Tika remains healthy.

## Clean source and packaging validation

- Full CPU Python suite: **424 passed**. Ruff, Python compilation and `pip check` passed with the existing pinned Python 3.14.7 test image.
- All eight selected/build/recovery Compose configurations passed validation. The optional Ollama API overlay was checked with its retained shared-Ollama base and explicit verified image variables.
- The permanent frontend configuration equals the qualified clean adoption descriptor after accounting for project/container names, labels and same-byte permanent mount paths. Its image was reused directly, never rebuilt.
- Five frozen runtime hashes match the qualified image. All **26** maintained application Python/CSS/static/requirements assets compared against the running frontend match. The original stage-1 Dockerfile also matches maintained source.
- **23** installed engine/runtime/patch/native hashes match. Native build-only sources are represented by pinned provenance; the object and runtime library are checked privately. The native object is not distributed here.
- Baseline and candidate have identical Python 3.14.7, 49 Python packages and 87 Debian packages. The old repository inventory incorrectly listed 27 additional Debian packages; inventory metadata was corrected from both immutable images. No installed dependency changed.
- The patch manifest now preserves its exact installed build-time bytes. Its historical status sentence is not the current release decision; current qualification belongs in the deployment and qualification documents.
- Manager checks cover wrong image/config refusal, missing recovery containers, foreign/multiple GPU engines, preserving an already-running engine, recorded intent before stopping, interruption-resume behavior, startup-failure rollback and isolated fallback identities/cache.

Two validation-harness failures were retained and corrected: the old default-Compose test needed the renamed Ollama fallback path; a new static packaging test initially imported an unavailable YAML package and was corrected to use the standard library. Compose preflight also initially treated an overlay as standalone and lacked required pinned interpolation values. Serialized empty core-limit objects were normalized to the actual zero limit. No qualified application runtime bytes changed to resolve these setup failures.

## Production-path adoption smoke

A CPU browser drove the normal port8501 UI with synthetic content. Cache counters were observed externally; no observer was mounted/imported into either production container.

| Path | Result |
| --- | --- |
| Frontend, engine, Tika and exact identities | Healthy; exactly one GPU engine |
| Short text | Completed; zero reuse in a fresh conversation |
| Synthetic document plus blue image | Correct code/color; Tika receipt and image preview available |
| Natural follow-up across a minute boundary, actual prior answer retained | Correct code/color; **6,656 cached tokens** |
| New Chat with identical document/image uploads | Correct response; **zero inherited cached tokens** |
| Explicit Thinking Mode | Correct arithmetic response; control reset after the submitted turn |
| Cancellation via New Chat while engine request was verified active | Queue drained; subsequent clean text request completed |
| Production configuration | Read-only/security/resource policies retained; only the two permanent read-only app mounts; no research hooks |

These are short adoption checks, not a repeat performance or quality campaign. The retained 24,960-token cross-minute result and its prefill/first-token timings remain the performance finding. Smoke UI completion times are not substituted for that controlled result. Historical grounding failures remain in FP4_QUALIFICATION.md. The frozen holdout, sustained-use test and abrupt-loss/recovery qualification were not rerun.

## Maintained operation and recovery

Use `python3 scripts/deployment.py current status|start|stop|rollback`. The single fast rollback action restores the old frontend on the same engine. `start` resumes recorded intent; `adopt` explicitly returns to stable-prefix. The retained September 14 local manager forwards its existing action names through the maintained manager; its original source/configuration is privately preserved. `scripts/verify_runtime.py` now checks the selected stack; explicit `--ollama-recovery` retains historical verification.

No GPU engine restart, new serving allocation, clock change, model change, automatic sampling warmup or optimizer change occurred. No recovery image/model/compiler volume or raw evidence archive was deleted. Temporary CPU test/browser containers removed themselves on exit. Historical dirty checkouts remain preserved and are not the maintained repository.

## Source safety and evidence

Only source, tests, permanent descriptors, pinned inventories and concise reports are included. Changed-file content and secret scans were completed before publication. No chats/uploads, credentials, raw inference logs, traces/tensors, software archives, model weights, compiled native objects or ambiguous full helper source were added.

The private finalization evidence inventory is under `/home/eko/ephemerai-evidence/finalization-20260915T181409Z`, including failed setup attempts, source/config comparisons, browser receipts, original legacy files and final Git/deployment alignment. Earlier raw archives remain at their original recorded locations with their hashes. The integration commit and final main SHA are recorded in that final receipt and Git history; this document does not claim a self-referential commit hash.

The 2026-09-11 through 2026-09-15 Qwen3.8 local inference optimization round is closed. Further engine optimization requires new evidence, a successor model, a supported upstream simplification, or a demonstrated consequential regression.
