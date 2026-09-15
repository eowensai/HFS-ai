> Historical engineering evidence carried into HFS-ai. For the current private-repository port and its fresh validation, see [HFS-ai port](HFS_AI_FP4_PORT.md). GPU measurements below were collected before this source port.

# Current deployed build — September 14, 2026

This review reflects the corrected DFlash deployment selected by the owner.
Application source at activation: `789d0071c2f10ec17d6ca97280fdf821a7eaca96`.
The new review changes packaging/documentation, not the active application or
engine arithmetic. HFS-ai's current main is the base for this private-repository port;
the public EphemerAl roadmap is not included.

| Component | Pinned identity |
| --- | --- |
| Current engine | `sha256:8b6b56ae42e195d662d7d09c99ed4fcd405b4a4d6684b26f13423f7b39901452` |
| MTP fallback | `sha256:8601ca3e55990b33594cc3254f5f16248140acd278fe5e24ba122756d82a04e0` |
| Application | `sha256:7209450b54fc5144399cf8dbb7aa9999d94ae94505afdee282a8b773b22dc184` |
| Target | RadixArk Qwen3.8-27B NVFP4, revision `319f741cce68d7914884900c138a1fbb70a42f30` |
| Drafter | syvai Qwen3.8-27B DFlash2 W4A16, revision `4d30ec736ffc6b8688dc2ae2b502d9b48bdec279` |

Two RTX 5060 Ti 16 GB GPUs under WSL2; PP2/TP1, 32/32 target layers,
one request, batch 1024, seven proposals, 131,072 total context. Main/draft
attention caches use FP8 E4M3; recurrent state remains FP32. Images remain enabled;
video is disabled. The app reserves 32,768 tokens for output. Neither inference
weights nor caches are deliberately offloaded to the CPU. Exact software images
are in the private recovery archive, not a public registry release.

## Measurements and limitations

Final corrected-image measurements: ~65K input to exactly 1,024 generated tokens
had a median 38.27 s (38.18–38.67), first token 21.44 s, generation 60.80 tok/s.
The earlier Ollama Q6 control was 162.29 s. Short ~2K probes measured 14.92 s versus
an earlier 33.94 s Q6 control. These are end-to-end stack comparisons; historical
GPU memory-clock settings were not recorded, and Q6 was not remeasured alongside
the final corrected image. They do not isolate the benefit of FP4 precision.

A later clean memory-clock comparison used 1,814 input / exactly 1,024 generated
tokens, one warm-up and three measured seed pairs with no prefix-cache hits.
At +0: 17.79 s total, 59.82 tok/s; at +2000: 16.04 s, 66.55 tok/s. All paired
output hashes and acceptance counts matched. Overclocking is optional and is not
applied by these scripts; short tests are not a stability guarantee.

An hour of mixed use passed 67/67 checks without restart or GPU failure. Current
browser checks covered text, Tika tables/OCR, eight images, image follow-up, reset,
mobile layout and streaming. Images are demonstrably processed even though one
capabilities answer incorrectly described them as text-only. 139 deployed source
files and original rollback identities were verified at final activation.

The bounded quality campaign did not pass its strict grounding gate: DFlash
retrieved 42/42 requested fact fields but had two conservatively classified source
or completeness errors; Q6 retrieved 41/42 and also made unsupported claims.
A short matched follow-up answered the problematic approved-record query correctly
in four runs, with drafting enabled/disabled, but cannot estimate rare-error rates.
The owner subsequently authorized the fast build for local use and trial users.
Do not relabel the failed gate as passed or call these profiles universally certified.

The numerical corrections avoid atomic low-precision partial reductions and use
full BF16 reduction policy. Adversarial-draft controls matched at 816 inspected
positions across five requests, not 816 independent quality cases. Native attention
still approximates queries/probabilities; separate no-draft greedy runs can differ.
See [numerical policy](../deployment/fp4/numerics/README.md) and
[qualification](FP4_QUALIFICATION.md) for evidence and known limits.

## Recovery and repository scope

The original HFS-ai Compose file remains the Ollama path. Native MTP and DFlash are opt-in
hardware-specific recipes sharing one application. The current machine's LAN bind
is operator-specific; new checkouts default to localhost. Tika, model stores,
original images and rollback source remain preserved. No voice or HFS Knowledge
application changes are included. Main and release publication remain untouched.

The refreshed private backup preserves exact current and original software and
configuration without target, drafter, vision or GGUF weight files. Its recovery
helper redownloads only the selected hash-pinned models. Keep the archive private.
