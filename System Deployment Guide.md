# HFS-ai operator guide: selected September 15 deployment

## Scope and entry point

The departmental source is `/home/eko/hfsai`, repository `eowensai/HFS-ai`. Use **Ubuntu-24.04 explicitly**. The selected release uses the frozen stable-prefix frontend and retained corrected DFlash/native engine. Full identities and limits are in [current deployment](docs/CURRENT_DEPLOYMENT.md).

This guide operates the existing qualified installation. It does not download new weights, rebuild the adopted frontend, alter the engine, or clear model/recovery storage. Tika is retained. HFS Knowledge and voice remain separate.

## Status, start and stop

Run these from PowerShell:

```powershell
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current status
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current start
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current stop
```

Status shows the recorded profile, immutable container/image identities and the active GPU engine. Start resumes the last selected profile, including an interrupted transition. Stop shuts down the managed frontend/engine; Tika is left running. A container explicitly stopped by the operator remains stopped under Docker's unchanged `unless-stopped` policy. Existing Windows logon forwarding and Docker/systemd behavior are unchanged.

Wait for frontend and engine health before using port 8501. The manager waits for model readiness when an engine needs restarting. Do not start another GPU inference engine alongside it. If an identity check fails, preserve the reported state; do not recreate containers, change hashes or choose another model as a shortcut.

## One-command frontend rollback

```powershell
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current rollback
```

This stops the stable-prefix frontend and starts `ephemeral-app-bounded` from its retained image. It keeps the same `ephemerai-vllm-bounded` engine. It records the baseline selection, so a later `start` continues that rollback state. No image/container/model deletion occurs. Repeat the command after an interrupted restoration.

To return explicitly to the frozen qualified frontend:

```powershell
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/deployment.py current adopt
```

Adopt verifies the old identities and exact qualified image, changes only the frontend when the selected engine is already running, and restores the old frontend on a packaging/startup failure. The profile mounts only the permanent deployment manifest and Streamlit configuration. It includes no diagnostic scripts or result mounts.

## Engine recovery profiles

The manager also has explicit `mtp`, `previous-fp4`, `original-fp4`, and `ollama` actions. These are recovery choices, not normal current settings. See [profile details](deployment/selected/README.md) before using them. An explicit recovery transition stops the current app/engine before starting another; zero GPU engines during transition is expected. Retained current containers and images are not deleted. Returning with `adopt` restores the selected DFlash engine and stable-prefix app.

MTP uses its own container names and compiler-cache namespace; it cannot overwrite the selected engine or compiler cache. That descriptor preserves the previously qualified MTP settings. This release's adoption does not rerun GPU qualification for these historical fallback profiles.

## Verify after maintenance

```powershell
wsl.exe -d Ubuntu-24.04 -- python3 /home/eko/hfsai/scripts/verify_selected.py --live
```

For the stable-prefix selection this verifies source/image identities, installed engine/patch/native-object hashes, frontend mounts, health, one GPU engine, no active/waiting requests, and Tika HTTP health. Use the browser for a short synthetic text, document/image and follow-up check after maintenance. Do not use real departmental data in diagnostics or save its outputs.

Current UI limits remain 50 MiB per upload, eight files/64 MiB per submission,256 KiB extracted UTF-8 per file and 512 KiB per submission, subject to exact rendered admission. Total model context is 131,072; 32,768 is reserved for output. Native images count toward input admission. Thinking Mode selects xhigh for one turn; ordinary turns use medium.

## New host or missing recovery assets

Use the guarded [FP4 build/install guide](docs/FP4_DEPLOYMENT.md) only as a separate restoration/build workflow. The repository does not contain model weights, software images or the native attention object. Restore exact private software assets when available, verify hashes, and download only the pinned model revisions if missing. Rebuilding is not proof of qualification. Resolve any required licensing decision before compiling/redistributing the ambiguous native helper; do not infer permission from an available download.

Original shared Ollama Compose is preserved as `docker-compose.ollama-shared.yml`. Independent review/rebuild profiles are separate. Do not run `docker system prune`, `compose down -v`, delete release/model volumes, or remove the model-less recovery archive.

## Optional manual sampling warmup

The closed startup investigation identified missing seeded top-k/top-p and Gumbel Triton specializations as the roughly six-second first-use pause. If predictable first-use latency matters after a restart, an operator may issue one short synthetic normal request with a fresh metadata-only cache salt, then a separately salted seeded request if seeded API traffic is needed. Let each finish naturally and verify the queue drains. Preserve the compatible compiler cache. This moves initialization into a manual warmup phase; it does not improve steady-state speed. No automatic warmup is installed in serving or startup code.

## Limits and evidence

Read [qualification/current failures](docs/FP4_QUALIFICATION.md) and [optimization closeout](docs/OPTIMIZATION_CLOSEOUT_20260915.md). Historical source-grounding failures remain failures. Native attention is approximate; target-path bit identity and rare-error guarantees are unproven. Raw evidence and recovery assets remain local, with their hashes, outside Git.
