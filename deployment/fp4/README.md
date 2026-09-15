# Pinned FP4 engine

Build from the repository root using `python3 scripts/deployment.py prepare fp4`.
This downloads the seven hash-locked wheels and builds an isolated engine image;
it does not start the engine. `models fp4` provisions the complete pinned checkpoint
separately. The normal app image supports both backends.

The public upstream source copied as `qwen3_5.py` retains its Apache-2.0/SPDX header.
`upstream-patch.json` guards its exact input/output hashes. Only the first PP stage
keeps target embeddings and vision; the MTP model still loads its own embeddings
on the last stage. Do not apply this file to a different vLLM commit.

`validated-pip-freeze.txt` records the original working environment, including
upstream tools inherited from the official image. `requirements.lock` contains
only the seven changes relative to that digest-pinned base. `wheels.json` provides
independent download checksums. No ambient pip dependency resolution is used.

The supervisor checks every checkpoint file before starting vLLM and discards
raw worker output so failures cannot persist request content. Fatal failures exit
the container for Docker's restart policy. `healthcheck.py` verifies engine health,
the served name and actual capacity. Model caches are in GPU memory; the durable
kernel-cache volume stores compiled code, not a saved conversation database.

Model and upstream licenses remain their respective upstream licenses. This
repository does not redistribute model weights or claim ownership of those files.
