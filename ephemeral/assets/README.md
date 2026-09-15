# Public tokenizer metadata

`qwen-tokenizer.json.gz` is deterministic gzip of the public GGUF tokenizer
metadata from the validated Unsloth UD-Q6_K_M model. It contains vocabulary,
merge rules and special-token IDs, not model weights or user data. The adapter
checks the original canonical metadata SHA-256 through `ModelTokenizer` before
use. The metadata fingerprint is
`1c86283d5ec7f949be9df2f76c443c32296008c6844b7146b674abe8dc3645e8`.

The originating Qwen model is distributed under Apache-2.0. Its complete license
is preserved with the model snapshot; see the pinned model repository and the
model provisioning manifests under `deployment/`.
