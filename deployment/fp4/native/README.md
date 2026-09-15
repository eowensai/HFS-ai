# Native attention build provenance

The public repository contains our adapter and small patches, source/compiler
identities, and an exact expected object hash. It excludes the compiled
`native-nhd.o` and the full upstream source. Private recovery preserves the exact
installed software, so the owner's restoration does not require recompiling.

The pinned [upstream file](https://github.com/flashinfer-ai/flashinfer/blob/af78f8fc17a9654563a619974de56e79257aaea6/flashinfer/cute_dsl/attention/fmha/sm120/fmha_prefill_fp8_tma.py)
has a BSD-3-Clause header plus a restrictive NVIDIA notice on its helper section.
We have not established how those notices interact. Fetching from upstream does
not settle permission to use or redistribute that material. Do not publish derived
binaries or call licensing cleared without resolving this upstream ambiguity.
The patch does not copy or modify that helper section.

For a compatible, authorized local build, `scripts/deployment.py prepare fp4
--profile dflash` builds dependencies, fetches the exact upstream archive, applies
hash-checked patches, and compiles in an isolated 4.7.1 environment if the qualified
object is missing. Source compilation requires an idle SM120 GPU. The serving
compiler stays at 4.6.2 with only the separate 4.7.1 runtime library installed.
An unexpected output hash stops preparation; it never substitutes a new kernel.

For the owner restoring a private backup, copy its qualified object to
`.local/native-rebuild/native-nhd.o` in the new review checkout before preparation,
or simply use the recovery helper to load the exact saved images. The object is
verified before any use. Do not copy a randomly rebuilt object over a running one.
