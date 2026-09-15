# Selected departmental profile: stable-prefix-20260915

The normal selection is the qualified stable-prefix frontend and unchanged corrected DFlash/native engine. The adopted app is an exact existing image; this manager never builds or pulls it. The mounted deployment.json and Streamlit configuration are byte-identical copies of the prior selected configuration, at permanent repository-relative paths.

## Commands

From `/home/eko/hfsai`:

```bash
python3 scripts/deployment.py current status
python3 scripts/deployment.py current start
python3 scripts/deployment.py current stop
python3 scripts/deployment.py current rollback
```

From Windows prefix the full command with `wsl.exe -d Ubuntu-24.04 --` and use `/home/eko/hfsai/scripts/deployment.py`.

- `status`: show selection, retained identities, health and active GPU engines.
- `start`: resume the profile recorded in ignored `.local/selected-state.json`, including interrupted transitions.
- `stop`: stop managed frontends/engines, retaining every container/image/volume; Tika remains running.
- `rollback`: restore the retained old frontend against the same selected engine. This is the single supported fast rollback command.
- `adopt`: explicitly return to the frozen qualified stable-prefix frontend. If it cannot start, the manager restores the old frontend.
- `bind`: one-time identity binding after the installation has been checked; existing bindings are verified, never silently replaced.

The manager stores intent before stopping containers, holds a process lock and verifies immutable image/container configuration bindings. A subsequent `start` resumes the target. It refuses unknown GPU engines or identity drift. An already-running wanted engine is not stopped or recreated. No diagnostic mounts/imports or automatic sampling warmup are included.

## Retained recovery profiles

| Action | Frontend / engine | Purpose |
| --- | --- | --- |
| `rollback` | ephemeral-app-bounded / ephemerai-vllm-bounded | Previous frontend; same corrected engine |
| `mtp` | hfsai-app-mtp-recovery / hfsai-vllm-mtp-recovery | Corrected MTP fallback, separate names/cache |
| `previous-fp4` | ephemeral-app-qualified / ephemerai-vllm-qualified | Earlier DFlash/native deployment |
| `original-fp4` | ephemeral-app / ephemerai-vllm | Original September 13 FP4/MTP deployment |
| `ollama` | ephemeral-app-ollama-rollback-20260913 / ollama | Original preserved Ollama application/model store |

Use these as explicit recovery decisions after draining users. Each switch stops the prior frontend and engine before starting another GPU engine. Exact hashes are in profiles.json. `adopt` returns to the normal selection. The original retained containers are never deleted or recreated. MTP creates its distinct containers and compiler volume only when explicitly selected; no MTP engine is launched during stable-prefix adoption. Its settings match the previous MTP descriptor. Existing Ollama and prior FP4 images/configurations remain historical qualified recovery assets; they are not newly requalified by this app release.

`engine.compose.json` records the selected engine's unchanged descriptor for verification and disaster-recovery reference. The normal app descriptor does not declare or recreate that engine. Tika and the external network/model volumes retain their existing identities. Do not start recovery descriptors directly alongside a GPU engine.

## Source/build versus binary identity

qualified-runtime.json pins the five adopted application files and immutable images. The engine's public patches and runtime inputs are verified by `scripts/verify_selected.py --live`. The DFlash patch-manifest status string is preserved from image build time; current qualification is recorded in documentation, not retroactively written into the image. Build-only native source/compiler inputs are not installed runtime files. Their source relation and the private binary hash remain in the native manifest.

Raw traces, synthetic diagnostic tensors and recovery archives are private local evidence outside Git. The selected compiler cache, frozen app, old frontend, current/fallback engines and model volumes must not be deleted. See [current deployment](../../docs/CURRENT_DEPLOYMENT.md), [qualification](../../docs/FP4_QUALIFICATION.md), and [operator guide](../../System%20Deployment%20Guide.md).

## Existing local compatibility entry point

The retained `/home/eko/ephemeral-llm/deployment/fp4-20260914-bounded/manage.py` now contains the maintained `legacy_manage.py` shim. Its `dflash`, `mtp`, `previous`, and `status` actions map to current `adopt`, `mtp`, `previous-fp4`, and `status`. The previous manager, root instructions/configuration and state were copied into the private finalization evidence before replacement. Other old campaign scripts remain historical and should not select production.
