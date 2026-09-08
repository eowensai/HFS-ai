# Recovery and backup

A Git checkout restores the application source and instructions. Exact offline
recovery also requires the **separate service-image and model archives**. The local
Tika image cannot be pulled from Docker Hub, and an upstream model tag may change.
Keep both the repository ZIP and recovery assets on another device or managed
backup service. A copy on the same Windows disk does not survive that disk failing.

## Prepare a recovery copy while this host is healthy

From the repository in Ubuntu, choose a **new** destination on a backup disk or
Windows-accessible folder. At least 45 GiB free space is required by the script:

```bash
python3 scripts/recovery.py capture /mnt/d/HFS-ai-recovery/assets
```

Replace `/mnt/d/...` with your actual destination. Capture reads the three accepted
immutable service images and only the selected alias manifest plus its five blobs.
It verifies the active alias before/after copying and verifies content hashes.
It neither stops services nor scans/copies HFS runtimes. It does cause substantial
read I/O; run it during a quiet period. An existing destination is refused so an
older recovery set is never overwritten.

Capture produces:

| File | Purpose |
|---|---|
| `runtime-images.tar` | Exact EphemerAI, shared Ollama and shared Tika images |
| `model.tar` | Exact selected alias manifest, GGUF, projector and small model blobs |
| `assets.json` | Accepted identities, archive sizes and SHA-256 values |
| `SHA256SUMS` | Portable archive integrity checks |

Keep a downloaded ZIP of this exact repository revision beside `assets/`.
The full model volume is deliberately not archived: unrelated aliases and Ollama
private identity keys are not needed to recover this service profile. Model weights
and packaged upstream components retain their own licenses.

Verify a transferred copy, not just the original:

```bash
python3 scripts/recovery.py verify /mnt/d/HFS-ai-recovery/assets
```

Verification checks archive hashes and streams every expected model member to
validate its path, type, size and content digest. It rejects additional members,
links, duplicates, missing blobs and corruption. These checks establish integrity
against the recorded manifest, not the trustworthiness of an unknown backup source.

## Restore to a replacement host

1. Install Windows/WSL2, the Windows NVIDIA driver, Docker and Container Toolkit
   using the [deployment guide](../System%20Deployment%20Guide.md).
2. Extract/clone the exact repository revision to `~/ephemeral-llm` and copy the
   asset directory to the new machine.
3. Before creating any service containers or model volume, run:

   ```bash
   python3 scripts/recovery.py restore-assets /mnt/d/HFS-ai-recovery/assets
   ```

4. The command refuses existing service containers or the existing production model
   volume. It requires the containerd image store, loads and checks accepted images,
   creates only the absent model volume,
   and restores only the verified model artifacts. It starts no model server.
5. Build the no-dump policy and start the accepted images without a build/pull:

   ```bash
   sh deployment/privacy/build-nodump.sh
   docker compose up -d --no-build --pull never ollama tika-server ephemeral-app
   python3 scripts/verify_runtime.py
   ```

6. Complete the fictional prompt/upload, model/GPU, New Chat, second-session and
   browser-origin checks in the setup guide. Then configure the new Windows address,
   approved UI access boundary and logon task. Rebuild only the app if its browser
   address configuration changed.
7. Restore HFS Knowledge separately through its own approved recovery procedure if
   required. Do not treat this EphemerAI kit as an HFS database backup.

A partial restore is preserved for review; the tool does not delete a newly created
volume on failure. Do not remove an existing volume to bypass a guard. Resolve the
failure on a separate recovery host with an explicit preservation plan.

## Source-only recovery

If the separate assets are lost, this repository is still useful but is **not an
exact binary backup**:

- The app can be built from the pinned Python requirements and Dockerfile. Base
  OS packages may advance; this produces a new image requiring validation.
- The Tika recipe downloads the pinned signed 3.3.2 jar and verifies its SHA-512
  and Apache signer fingerprint. Its OS package repositories advance and its exact
  Java-version assertion deliberately fails rather than silently accepting drift.
  See [Tika rebuilding](../deployment/tika/README.md#rebuilding-a-candidate).
- The Modelfile records the intended model/profile, but pulling an upstream tag
  and creating an alias may change manifest construction history or bytes. Keep
  the exact manifest and restore its content-addressed blobs from trusted retained
  artifacts where possible. Do not edit the app's immutable digest check to hide a
  mismatch. Any newly built model requires a coordinated model-acceptance change
  across all clients, not an EphemerAI-only fallback.

For Tika candidate preparation (do not run on a live service as an update):

```bash
bash deployment/tika/fetch-artifact.sh
docker build -t shared-tika:3.3.2-candidate deployment/tika
```

If the Java assertion fails, review the changed signed Ubuntu package version and
security notices before editing it. Validate the new image, record its digest,
and update the accepted recovery record/Compose together. Never mislabel a new
candidate as the exact saved image. Preserving the current archive avoids this
uncertain reconstruction path after a machine failure.

## Backup refresh and rollback

After a validated service-image/model change, update `deployment/runtime-lock.json`
and its exact model manifest as appropriate, then capture into a new directory.
The tool refuses a changed image/alias under the old lock. Keep the preceding
verified recovery set until the new set is copied off-host and verified.

For an application regression, finish active EphemerAI requests and select the
last accepted app image with an image-only Compose override and `--no-build`.
Keep current memory/tmpfs/core settings when possible. Container recreation clears
app sessions. Shared-image rollback requires a coordinated idle window; never
restore/delete HFS databases or model volumes as part of an app rollback.

No restore drill here intentionally overwrites production, starts a second GPU
runner, replays real documents, disables Windows paging or erases old disk contents.
