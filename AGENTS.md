# HFS-ai: maintained departmental deployment

This repository is **eowensai/HFS-ai**, the owner's departmental instance on this machine. EphemerAl is a separate public repository. HFS Knowledge and voice are separate applications and remain outside this deployment. Do not publish to EphemerAl as a side effect of HFS-ai work.

## Current selection: September 15, 2026

Read `docs/CURRENT_DEPLOYMENT.md`, `deployment/selected/README.md`, and `docs/FP4_QUALIFICATION.md` first. The selected installation is the exact qualified stable-prefix frontend with the unchanged corrected DFlash/native-attention engine. Runtime image and source hashes are pinned in `deployment/selected/qualified-runtime.json`. The UI retains its qualified EphemerAI branding; changing it would be a separate runtime change.

Maintained source on this machine: `/home/eko/hfsai`. Historical releases, model stores and recovery containers remain under `/home/eko/ephemeral-llm` and Docker. Raw evidence remains outside Git. Do not treat a research checkout or an old restoration script as the operational entry point.

Normal commands from this repository:

```bash
python3 scripts/deployment.py current status
python3 scripts/deployment.py current start
python3 scripts/deployment.py current stop
python3 scripts/deployment.py current rollback
```

Use `wsl.exe -d Ubuntu-24.04 -- ...` explicitly from Windows. `start` resumes the recorded selection after interruption; `rollback` selects the retained old frontend with the same engine. `adopt` explicitly returns to stable-prefix. Only the selected manager may switch these retained profiles. It verifies identities, serializes transitions and never runs two GPU engines. Do not use bare Compose to switch profiles. Tika is retained and is not stopped by this manager.

## Immutable current engineering contract

- Engine image `sha256:8b6b56ae42e195d662d7d09c99ed4fcd405b4a4d6684b26f13423f7b39901452`.
- Frontend image `sha256:32bd1e140e88eed3b2fb5b0f77eefce5515194114091c8d580f076e6f4547aa6`.
- RadixArk Qwen3.8-27B NVFP4 revision `319f741cce68d7914884900c138a1fbb70a42f30`; syvai DFlash2 W4A16 revision `4d30ec736ffc6b8688dc2ae2b502d9b48bdec279`.
- PP2/TP1, target layers 32/32, one request, prompt batch 1,024, seven proposals.
- Total context 131,072; application output limit/reserve 32,768. Admission includes images and complete rendered payload.
- Target/draft attention KV FP8 E4M3; recurrent state FP32; convolution state BF16; explicit cache bytes 3,060,164,198.
- Native FP8 prefill, existing FlashInfer/XQA/graphs, `EPHEMERAI_FP8_UNSPLIT=1`, BF16 reduced-precision reductions disabled before load/compile.
- Native images and existing extraction/image limits. Medium reasoning by default; xhigh only for the explicit one-turn Thinking Mode selection. Normal sampling unchanged.
- No deliberate model/KV CPU offload. Do not change clocks, drivers, weights or dependencies as a deployment repair.

## Qualification and limits

The exact frontend passed the frozen 16-case qualification, actual multi-turn and cached multimodal history, capacity boundary, cancellation/New Chat/isolation, explicit reasoning, more than 60 minutes mixed use, recovery and abrupt engine-loss observations. Do not rerun that campaign merely to update source control. A new runtime-code change cannot inherit this qualification automatically.

The candidate does not fix historical source-grounding failures. Native attention is approximate. Separate no-draft and DFlash target paths are not proven bit-identical; later-generation divergence remains unresolved, with no serving defect/fix established. Read the qualification ledger before making quality claims.

The 2026-09-11 through 2026-09-15 Qwen3.8 local inference optimization round is closed. Further engine optimization requires new evidence, a successor model, a supported upstream simplification, or a demonstrated consequential regression.

Closed hypotheses and re-entry conditions are in `docs/OPTIMIZATION_CLOSEOUT_20260915.md`. No open-ended optimization queue remains. Seeded sampling warmup is an optional manual operational note, never an automatic serving change.

## Privacy, safety and source publication

- Local processing; no chat database or content-bearing durable logs. Do not persist user prompts, uploads, extracted text, history or answers. Use public/synthetic fixtures for diagnostics.
- New Chat clears conversation-owned state and rotates model-invisible request metadata salts. Logical isolation is not physical/forensic erasure.
- Keep reasoning-delta filtering and incomplete-answer history exclusion. Keep cancellation, source availability and omissions truthful.
- Preserve read-only containers, no-new-privileges, dropped capabilities, bounded RAM/tmpfs, zero Linux container swap and no-dump controls. Retain departmental host/origin configuration and private backend endpoints.
- Preserve images, copy/export, accessibility and the existing Streamlit 1.63 behavior. Do not add external fonts, analytics, CDNs, persistent storage or broad UI redesign.
- Keep model weights, native objects, software archives, raw traces/tensors, credentials, private work data and recovery archives outside Git. The native helper license-notice ambiguity is unresolved; its exact binary is retained privately and must not be redistributed.
- Do not prune Docker, delete model/recovery volumes, remove frozen images or rewrite public history. Preserve unrelated dirty historical checkouts.
- Source commits/PRs belong only to HFS-ai. Deployment and merge still require an explicit owner task authorization; September 15 finalization provides it for this release.

## Validation for maintained changes

Use the pinned dependencies and an isolated CPU test environment. Run the full pytest suite, Ruff, Python compilation, dependency checks, Compose configs, `python3 scripts/verify_selected.py`, and applicable focused manager tests. Verify exact image/runtime hashes with `--live` after adoption. Browser adoption smoke uses the normal production path with synthetic content; no diagnostic imports or mounts belong in production.

Tests must exercise failure/refusal and recovery behavior, not merely mirror constants. Prove a pre-existing failure against the appropriate baseline before accepting it. Do not change qualified runtime bytes to satisfy packaging tests. Keep all five frozen file hashes exact.
