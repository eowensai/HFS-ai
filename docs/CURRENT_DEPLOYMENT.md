# Current departmental deployment: September 15, 2026

Repository: **eowensai/HFS-ai**. Maintained checkout: `/home/eko/hfsai`. This is the departmental instance on the owner's Windows 11/Ubuntu-24.04 machine. The public EphemerAl repository, HFS Knowledge and voice experiments are separate.

## Exact selected artifacts

| Component | Immutable image |
| --- | --- |
| Stable-prefix frontend, hfsai-app-stable-prefix | `sha256:32bd1e140e88eed3b2fb5b0f77eefce5515194114091c8d580f076e6f4547aa6` |
| Corrected DFlash/native engine, ephemerai-vllm-bounded | `sha256:8b6b56ae42e195d662d7d09c99ed4fcd405b4a4d6684b26f13423f7b39901452` |
| Retained frontend rollback, ephemeral-app-bounded | `sha256:7209450b54fc5144399cf8dbb7aa9999d94ae94505afdee282a8b773b22dc184` |

Frozen frontend tag: `ephemerai-stable-prefix-qualification:20260915`. The adopted binary is reused directly; it is not rebuilt. Exact qualified source hashes are in [qualified-runtime.json](../deployment/selected/qualified-runtime.json). All five files are maintained in this repository. Other runtime Python/CSS files retain their matching deployed-baseline bytes.

Target: `RadixArk/Qwen3.8-27B-NVFP4`, revision `319f741cce68d7914884900c138a1fbb70a42f30`.
Drafter: `syvai/Qwen3.8-27B-DFlash2-W4A16`, revision `4d30ec736ffc6b8688dc2ae2b502d9b48bdec279`.

## Configuration contract

Two RTX 5060 Ti 16 GiB GPUs; PP2/TP1, target layers 32/32, one request, prompt batch 1,024, seven proposals. Total context 131,072; application output limit and admission reserve 32,768. Exact rendered admission includes documents, historical turns and images. Application limits remain eight files/64 MiB per submission, 50 MiB per file, 256 KiB extracted text per file and 512 KiB per submission. Native images remain enabled; the existing engine processor/image-count policy is unchanged and does not promise that 999 full-resolution images fit.

Target/draft attention KV is FP8 E4M3, recurrent state FP32 and convolution state BF16. The explicit cache setting remains 3,060,164,198 bytes. Native FP8 prefill, FlashInfer/XQA and CUDA graphs remain as selected. `EPHEMERAI_FP8_UNSPLIT=1`; BF16 reduced-precision GEMM reductions are disabled before model loading/compilation. No weights, precision, speculation, dependencies, clocks, drivers, extraction limits or CPU offload policy changed.

Default reasoning is medium. Explicit Thinking Mode selects xhigh for one submission and resets afterward. Normal sampling remains temperature 1, top_p 0.95, top_k 20, min_p 0 and repetition_penalty 1. Reasoning stays hidden; output reserve/limit remains 32,768 in either mode.

## Stable-prefix behavior and evidence

Initial system instructions are frozen for a conversation. Each user turn's application time is captured once and placed in that user turn; past timestamps and actual prior answers remain stable during request rebuilding. No late system message or custom chat template was introduced. Native images stay in their existing user-message structure. A conversation salt is request metadata, never model-visible text; New Chat rotates logical ownership, not physical memory erasure.

The established controlled cross-minute document follow-up measured:

| Metric | Previous frontend | Stable-prefix |
| --- | ---: | ---: |
| Cached tokens | 0 | 24,960 |
| Server prefill | 7.947 s | 1.156 s |
| First generated token | 7.829 s | 1.182 s |
| First visible answer | 10.196 s | 2.917 s |
| Natural completion | 10.981 s | 3.456 s |

These are retained workload-specific measurements, not a new campaign or a general model speed claim. Fresh requests are not claimed faster. Natural-answer times also reflect stochastic reasoning/answer length; verified reuse and prefill/first-token latency support attribution.

The frozen 16-case qualification, actual cross-minute multi-turn history, cache reuse through image-conditioned state, exact 98,304-input + 32,768-reserve boundary, cancellations, New Chat/isolation, eight images, explicit reasoning, >60-minute mixed use, rollback/recovery and abrupt-engine-loss behavior passed their bounded functional gates. The frozen app also produced disclosed minor grounding failures. Adoption only adds a short production-path smoke; it does not rerun the release holdout or soak.

## Known limitations

Historical strict source-grounding failures remain open, including ownership loss, invented/misattributed source locators and unsupported corroboration. Candidate qualification had three candidate-only minor findings and one fewer completely clean case than baseline. It is not a quality-improvement claim.

Native attention approximates queries/probabilities. No-draft/speculative target bit identity, universal quality equivalence, losslessness and rare-error bounds are not established. Remaining later-generation numerical divergence is unresolved, not a qualified serving defect/fix. The structured grounding contract was rejected. Native helper binary redistribution/licensing remains unresolved. See [qualification/current failures](FP4_QUALIFICATION.md) and [closeout](OPTIMIZATION_CLOSEOUT_20260915.md).

## Operations and recovery

Use `python3 scripts/deployment.py current status|start|stop|rollback` from this checkout. `rollback` restores the old frontend with the same engine; `start` resumes the recorded profile. `adopt` explicitly selects stable-prefix. [Permanent manager and fallback profiles](../deployment/selected/README.md) retain MTP, previous/original FP4 and original Ollama recovery without deleting the selected containers/images.

The normal root Compose file now represents the selected frontend against retained external engine/Tika services. Original shared Ollama Compose is `docker-compose.ollama-shared.yml`; review/rebuild recipes remain separate. Do not use an old campaign restoration script to select production. Windows logon forwarding, departmental origins, logging/security, read-only/resource policies and Tika integration are preserved.

Private evidence is under `/home/eko/ephemerai-evidence`; historical originals and recovery archives remain at their recorded local locations. Repository source contains hashes and concise summaries, not raw tensors/traces, software images, user data or the native object. The final source/adoption checks are recorded in [release validation](RELEASE_VALIDATION_20260915.md).
