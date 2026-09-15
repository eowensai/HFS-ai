> Historical engineering evidence carried into HFS-ai. For the current private-repository port and its fresh validation, see [HFS-ai port](HFS_AI_FP4_PORT.md). GPU measurements below were collected before this source port.

> Historical September 13 record. For the current deployed build and weights-free
> archive scope, read [Current deployment](CURRENT_DEPLOYMENT.md).

# Reproducible FP4 deployment, with Ollama retained

This file records the September 13 preservation baseline. The subsequent local
qualification and implementation are tracked in `FP4_QUALIFICATION.md`; its
measurements and profiles supersede the historical launch settings below.

This review captures the installed September 13 application in one source tree.
`LLM_BACKEND=ollama` remains the default. The alternative is the exact RadixArk
NVFP4 profile qualified on two RTX 5060 Ti 16 GB GPUs under WSL2. This branch
does not migrate anyone's installation and is not a published release.

The source includes accumulated local work since public `main`: model-matched
token counting, medium/default and one-turn maximum reasoning, privacy/session
lifecycle protection, bounded document/image handling, Tika 4, Python 3.14.7,
Streamlit 1.63, and the current presentation. These dependencies are needed to
reproduce the installed app; this is therefore larger than an inference-only PR.
That larger comparison was against the public fork. HFS-ai already contains most
of those application changes; this port retains them and adds the backend delta.
The public fork's July implementation roadmap is not included here.

## The two profiles

| | Ollama default | Optional FP4 |
|---|---|---|
| Model | Unsloth UD-Q6_K_M GGUF | RadixArk NVFP4 |
| Engine | Ollama 0.32.15 | vLLM commit `6fe67cbbf3e43da89bebf6ab0eeaca4ba6c75663`, b12x 1.3.0 |
| Model identity | Exact GGUF/vision/template/config blobs and alias manifest | Revision `319f741cce68d7914884900c138a1fbb70a42f30`, every file SHA-256 checked |
| Total context | 131,072 | 131,072 |
| Main attention cache | Q8_0 | FP8 E4M3, main and draft; 2.75 GiB reserved per card |
| Drafting | Existing two-token MTP setting | Three-token MTP |
| GPU placement | Existing forced 66-layer profile | PP2 / TP1, 33/31 layers; weights and inference caches on GPUs |
| Images | Retained | Retained, including image follow-ups and 16-image history checks |

FP4's recurrent state remains FP32 and convolution state BF16. Its original
unit cache scales are retained: the calibration follow-up did not demonstrate
a consistent quality improvement. The engine's 999-image admission setting
removes the former artificial two-image ceiling; it is not a promise that 999
images fit. The app's upload and context limits still apply. Video is excluded.

## Evidence from the unchanged machine

| Matched workload | Ollama Q6 | Selected FP4 |
|---|---:|---:|
| Fresh ~64K input, exactly 1,024 generated tokens | 162.29 s, one fresh control | Median 59.45 s, range 59.27–60.68, three runs |
| Fresh ~2K input, exactly 1,024 generated tokens | 33.94 s, one control | Median 20.92 s, two runs |
| Cached document follow-up | 5.61 s | 4.89 s |

Follow-up rows are single complete-answer observations with different generated
lengths, not evidence of a reliable cached-query winner. Generated counts include
reasoning. The long fixed probes used 65,131 versus 65,132 rendered input tokens,
zero saved-prefix hits on FP4, and showed ~48.43 versus 26.86 generated tokens/s.
FP4 accepted 2,055 of 3,054 proposed draft tokens (67.3%). Sampled memory peaked
at 15,631 and 15,795 MiB. Native SM120a FP4 and FP8 instructions were verified on
both GPUs in separate profiling traces. These are whole-configuration comparisons,
not a claim that reducing weight precision alone caused the speed difference.

The newer live basic-query check measured 46.52 tokens/s on FP4 versus 31.66
on Ollama (three runs each). It used identical input but variable output lengths.
Near-capacity input, images, document extraction, conversation reuse, cancellation
and application integration were qualified before this preservation task.
Small practical answer checks do not establish general Q6/FP4 accuracy equivalence.

## What makes the build reproducible

* The engine starts from a digest-pinned official CUDA 13 vLLM image.
* Seven changed wheels are frozen by version, download URL, size and SHA-256.
  Installation uses `--no-deps --require-hashes`, followed by `pip check`.
* The one remaining source patch removes unused stage-two target embeddings and
  the duplicated vision encoder. The separate MTP embeddings remain intact.
  Applying the patch verifies both the upstream file and replacement hashes.
* Launch arguments, SM120 kernel selection, PP placement, FP8 cache precision,
  memory reservations and privacy supervisor are tracked.
* App dependencies have a constraints lock. Static public tokenizer metadata is
  compressed deterministically, with its original vocabulary fingerprint checked
  on load. It contains no conversations or uploaded content.
* The deployment script writes the newly built engine identity into the app's
  readiness manifest and pins local Compose images to their resulting IDs.

Model files, wheel binaries, compiled libraries, machine paths, private inventory,
recovery archives and voice experiments are excluded from Git. Public model
provisioning downloads exact revisions and rejects checksum mismatches. Ollama's
manifest is installed byte-for-byte, avoiding identity drift from recreating an
alias against an updated upstream model tag.

The official base and wheel pins reproduce engine inputs; Docker timestamps,
compiler output and OS package updates can change image bytes. The private recovery
archive contains the exact original images when byte-for-byte recovery is needed.
That archive also preserves model licenses and full model files for offline recovery.

## Review and maintenance limits

The FP4 profile is specific to the tested dual SM120 system. It is not a general
consumer-hardware preset. Keep the upstream pin until a candidate update passes
images, MTP acceptance, long context, cache reuse and the placement regression.
Do not update the wheel independently of FlashInfer/b12x. More aggressive batching,
four-token MTP and finer cache matching previously exposed memory/stalled-worker
failures. The conservative profile intentionally retains headroom for stability.

The preservation task validates builds, package and file identities, both adapters,
archive integrity and isolated restoration inputs. It does not interrupt production
to perform a fresh GPU failover. A real GPU cutover remains a separately scheduled
acceptance step before merging/deploying a replacement image. See the attached PR
validation report for exact checks and remaining limitations.

No release, public model upload, voice feature, HFS change or production switch is
included. The original local checkout and stopped Ollama containers are retained.
