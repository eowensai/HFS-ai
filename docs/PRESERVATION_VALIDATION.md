> Historical engineering evidence carried into HFS-ai. For the current private-repository port and its fresh validation, see [HFS-ai port](HFS_AI_FP4_PORT.md). GPU measurements below were collected before this source port.

> Historical September 13 record. For the current deployed build and weights-free
> archive scope, read [Current deployment](CURRENT_DEPLOYMENT.md).

# Preservation and review validation — September 13, 2026

This review was prepared in an independent checkout against public `main`
`68427d3462106cdc8831bf71b1dbe74d50785924`. The installed checkout, model stores,
service configuration and running inference engine were not changed.

## Completed checks

* **388 tests passed** with both pytest entry points; Python compilation, Ruff
  and `pip check` passed in a disposable Python 3.14.7 application container.
  Both backend adapters are covered. Six added workflow tests protect foreign
  deployment isolation, immutable downloads, exact Ollama blobs, FP4 capacity,
  image/MTP settings and source/wheel hashes.
* The app, privacy library, Tika and FP4 engine build from the tracked sources.
  The complete FP4 prepare command was exercised with the checked local wheels.
  No GPU engine was started by preparation.
* The rebuilt engine matches all installed package versions of the working image,
  including vLLM, b12x, FlashInfer and NCCL. `pip freeze` differs only in the
  representation of vLLM's original direct URL versus its installed version.
  The placement patch and launch hashes match the working deployment.
* Both standalone Compose configurations validate. A real invocation of the new
  start command refused to interfere with the existing GPU container.
* Isolated Chromium desktop/mobile smoke checks passed. Synthetic browser checks
  passed exact 50 MiB upload boundaries, oversized-input rejection, Host/XSRF
  handling, native file/image paste/drop and real session-disconnect cleanup.
* All 21 FP4 provisioning sources match the pinned snapshot: small files were
  downloaded and SHA-256 checked; large shards' upstream LFS digests and sizes
  match the separately archived and fully read-back weights. Ollama's Q6 and
  BF16 vision upstream file hashes match its preserved manifest blobs.
* The original five-image archive successfully loaded through Docker. Both exact
  application images ran offline on CPU with their Compose privacy settings;
  Python/Streamlit, model metadata/tokenizer and core/dumpability checks passed.
* Every model-archive member was read back and checked. All 91 image-archive file
  members were read, with OCI content digests, manifest layer references and
  uncompressed RootFS identities checked against the original image metadata.
* Production app, FP4 engine and Tika retained their container IDs, images,
  configuration, mounts and start times; the app and engine remained healthy.
  Original Ollama and its rollback app remained stopped. Restart counts stayed zero.

## Recovery artifact scope

The private archive set contains the exact pre-FP4 and current FP4 application
source snapshots, deployment configuration, original images, full Q6/vision and
RadixArk/MTP weights, 251 static snapshot file hashes, original Git history and
dirty diff, the review Git bundle, relevant WSL/Docker startup configuration and
recovery scripts. The three payload archives total about **57.6 GiB**. No voice
experiments, HFS document/database content or live request logs are included.

The recovery ZIP and three payload archives belong together in one Google Drive
folder. Checksums and instructions accompany the set. Nothing is uploaded to
Google Drive by this task, and no release or merge is performed.

## Explicit verification boundary

Loading image archives and testing restored app images offline is an actual
recovery rehearsal, but it is **not a fresh live GPU cutover**. No second inference
engine was loaded while production was running. Existing on-machine FP4 qualification
is documented in `FP4_REVIEW.md`; the rebuilt image still needs an approved live
text/image/long-context/MTP acceptance window before deployment. Windows/driver
reinstallation and re-registering startup tasks are also not exercised here.

The archive is for the owner, while this branch is the portable source review.
Machine-specific recovery inventory and full weights are deliberately absent from
GitHub. Full preservation logs and hash manifests stay with the private artifact.
