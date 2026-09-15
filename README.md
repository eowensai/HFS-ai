# HFS-ai

HFS-ai is this machine's departmental document-and-image chat deployment, maintained in **eowensai/HFS-ai**. Its qualified interface retains the EphemerAI name. The separate public EphemerAl repository and HFS Knowledge experiment are not this deployment.

## Selected deployment: September 15, 2026

The selected stack is the **qualified stable-prefix frontend plus the unchanged corrected DFlash/native-attention engine**. Windows 11, WSL 2 **Ubuntu-24.04**, Docker and the existing two RTX 5060 Ti 16 GiB GPUs remain the platform. Tika 4 handles document extraction.

| Component | Selection |
| --- | --- |
| Frontend | Frozen stable-prefix image 32bd1e140e88; exact source hashes in the release manifest |
| Engine | Corrected DFlash/native image 8b6b56ae42e1 |
| Target / draft | RadixArk Qwen3.8-27B NVFP4 / syvai Qwen3.8-27B DFlash2 W4A16, pinned revisions |
| Placement / requests | PP2/TP1, 32/32 layers, one request, batch 1,024, seven proposals |
| Context / output | 131,072 total; 32,768 application output limit and admission reserve |
| State | Target/draft KV FP8 E4M3; recurrent FP32; convolution BF16 |
| Application | Python 3.14.7 / Streamlit 1.63.0; unchanged dependencies, images and extraction limits |

Read [current deployment](docs/CURRENT_DEPLOYMENT.md) for full immutable identities, [operator guide](System%20Deployment%20Guide.md) for commands, and [qualification/current limitations](docs/FP4_QUALIFICATION.md) before making performance or quality claims.

## Normal operation on this machine

From PowerShell:

```powershell
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current status
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current start
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current stop
```

The single fast rollback command is:

```powershell
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current rollback
```

Rollback restores the retained old frontend against the same engine. `start` resumes the recorded selection; `current adopt` explicitly returns to the qualified stable-prefix frontend. The manager guards container/image identities and one-GPU-engine operation. Tika remains running. See [permanent profile and other recovery routes](deployment/selected/README.md).

## What stable-prefix changes

The initial system instructions and historical turn timestamps remain stable. Each newest user turn receives its own captured time without adding a late system message or changing the model's chat template. Actual assistant history and native images are preserved. Conversation salts remain outside model-visible text; New Chat starts a new logical cache owner.

In the established controlled cross-minute document follow-up, cached tokens changed from 0 to 24,960, server prefill from 7.947 s to 1.156 s, and first generated token from 7.829 s to 1.182 s. This is a workload-specific reuse result. Fresh requests are not claimed to be faster, and the model is not claimed to be universally 85% faster.

The exact frontend passed the frozen 16-case qualification, real multi-turn/multimodal reuse, exact capacity boundary, lifecycle/recovery and more than 60 minutes of mixed use. It does not eliminate unsupported source/attribution claims. Native attention is approximate; no-draft/speculative target bit identity and rare-error bounds remain unproven. The [closeout](docs/OPTIMIZATION_CLOSEOUT_20260915.md) records rejected ideas and the unresolved later-generation difference.

## Privacy and recovery assets

No chat database or intentional durable prompt/upload/history storage. Reasoning remains hidden. New Chat and cancellation release conversation-owned state; GPU/framework/browser/clipboard buffers have separate lifetimes, so this is not forensic erasure. The UI retains its approved departmental network/origin settings and has no new login/TLS layer. Model and Tika endpoints remain private. [Privacy details](deployment/privacy/README.md).

Only source, guarded recipes, hashes and concise evidence summaries belong here. Model weights, exact software images, raw traces/tensors, native binaries and recovery archives remain local. The native helper's licensing ambiguity is unresolved; repository access does not grant binary redistribution permission. See [native provenance](deployment/fp4/native/README.md).

## Development and installation

The root Compose descriptor represents the selected frontend; it does not recreate the retained engine or Tika. Use the manager for transitions. Original shared Ollama Compose is preserved as `docker-compose.ollama-shared.yml`; independent rebuild recipes remain `docker-compose.fp4.yml` and `docker-compose.ollama-recovery.yml`.

Use the [operator guide](System%20Deployment%20Guide.md) for this machine and [FP4 source build guidance](docs/FP4_DEPLOYMENT.md) for separately authorized new-host work. A rebuilt image is not automatically the qualified binary. Native compilation/licensing and new-host acceptance remain explicit prerequisites.

```bash
python -m pytest -q
ruff check .
python -m compileall -q ephemeral ephemeral_app.py scripts deployment/selected
python -m pip check
python scripts/verify_selected.py
```

No dependency upgrade is included. The [release validation record](docs/RELEASE_VALIDATION_20260915.md) distinguishes this final source/adoption validation from historical GPU campaigns.

The 2026-09-11 through 2026-09-15 Qwen3.8 local inference optimization round is closed. Further engine optimization requires new evidence, a successor model, a supported upstream simplification, or a demonstrated consequential regression.
