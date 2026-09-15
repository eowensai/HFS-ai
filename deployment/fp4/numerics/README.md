# Numerical consistency policy

This policy is part of the pinned dual-SM120 build. It does not change model
weights, KV precision, context, images, drafting depth, or application sampling.

Two measured causes of batch-shape differences are addressed:

* The b12x 1.3.0 low-SM FP8 policy used four atomic BF16 split-K partial sums for
  some small projections. Repeated one-row calls differed, while eight-row
  calls used unsplit accumulation. `EPHEMERAI_FP8_UNSPLIT=1` selects one slice;
  four actual checkpoint-matrix controls then matched FP32 GEMM rounded BF16
  across both shapes and repeated exactly. Do not substitute the unrelated
  `B12X_DENSE_SPLITK_TURBO=0` switch.
* PyTorch's permitted reduced-precision BF16 GEMM reductions made the first
  recurrent-gate projection differ between one-row and verification-batch
  calls. `allow_bf16_reduced_precision_reduction=False`, applied before model
  loading and compilation, made the measured M1/M8/M89 calls match an FP64
  reference rounded BF16. It does not replace BF16 weights with FP32 weights.

`manifest.json` pins both input and output hashes. The installer validates all
changes before writing any file. The DFlash patch manifest names the resulting
base runner hash, so the derived image cannot silently skip the policy.
`VLLM_CACHE_ROOT=/root/.cache/ephemerai-numerics-v1` avoids reusing previously
compiled graphs with the old arithmetic policy. No tracing hook is installed.

The September 14 investigation tested normal, all-rejected, and alternating-bad
draft proposals with the normal target verifier and rollback code. Complete
greedy answers and 249 captured target distributions were identical across all
four short/image/85K control arms. An additional 126,927-token input and eight
full-resolution images matched under normal and all-bad drafting at another
567 positions. These are five requests, not 816 independent quality examples.

This is evidence for causal verification and rollback on those inputs. It is
not a guarantee of bitwise equivalence to a separately compiled non-drafting
engine, a factual-error-rate bound, or a nonzero-temperature distribution test.
Native FP8 attention's separate approximation limits remain documented in
`docs/FP4_QUALIFICATION.md`.
