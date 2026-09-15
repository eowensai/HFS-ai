> Historical engineering evidence carried into HFS-ai. For the current private-repository port and its fresh validation, see [HFS-ai port](HFS_AI_FP4_PORT.md). GPU measurements below were collected before this source port.

# Dual RTX 5060 Ti: native FP8 attention and DFlash qualification

This is the owner-authorized September 14 local implementation on the existing
WSL2 machine. It is a review branch, not a public release or a generic GPU preset.
Ollama remains supported in this source tree. HFS Knowledge and voice experiments
are outside this change.

## Numerical-causality follow-up

The September 14 follow-up found two additional batch-shape arithmetic causes:
b12x small-row FP8 atomic split-K reductions, and PyTorch reduced-precision BF16
GEMM reductions. The review build now applies hash-checked corrections before
compilation; see `deployment/fp4/numerics/README.md`. The originally selected
image IDs remain preserved. Measurements below describe those earlier images
unless explicitly labeled as corrected-policy results.

After both corrections, five focused inputs spanning short text, 85K documents,
126,927-token document-plus-image input and eight full-resolution images
produced identical complete greedy answers under normal and deliberately bad
drafting. All 816 captured target hidden/logit positions matched. Three of those
requests also passed alternating-bad and repeated-normal controls. These are
five inputs, not a statistically representative quality sample.

The actual full-vocabulary GPU sampler also matched a known distribution under
three proposal patterns, including a zero-probability proposal (8,192 seeds per
pattern). This tests the standard one-hot verifier's first-token marginal; it
does not establish full model-distribution or rare-error equivalence.

A separately compiled non-drafting engine still produces different reasoning
tokens/distributions on some requests. Some differences precede drafting; the
remaining recurrent/compilation and long-prefill geometry contributions are not
fully isolated. Do not advertise empirically lossless output or dismiss large
matched-prefix probability differences as noise. The stronger control result is
that changing proposed future tokens did not change committed target state in
the inspected DFlash runs. Native attention's separate approximation limitations
and the previous source-grounding failures remain relevant.

The corrected clean DFlash image retained the speed advantage in three fresh
repetitions: 65K→1,024 median **38.27s** (38.18–38.67), TTFT 21.44s, decode
60.80 tok/s; 2K→1,024 median **14.92s** (14.41–15.14), decode 71.52 tok/s. These
fixed-length probes include reasoning and are not complete-answer quality tests.
The earlier 40.12s/14.68s DFlash results were not rerun as an interleaved control,
so small between-campaign changes should not be attributed to a particular fix.
The historical Ollama controls remain 162.29s/33.94s, respectively.

## Profiles

Both FP4 profiles use the unchanged RadixArk Qwen3.8-27B NVFP4 target at revision
`319f741cce68d7914884900c138a1fbb70a42f30`, two RTX 5060 Ti 16 GB cards, sequential
pipeline placement (PP2), TP1, and one scheduled request at a time. Neither uses
CPU inference offloading. The native SM120 prefill kernel operates on the qualified
Q24/KV4/D256 geometry. Decode and unsupported prefill shapes retain FlashInfer.

| Setting | Native MTP fallback | Selected local DFlash profile |
|---|---|---|
| Total context | 131,072 | 131,072 |
| Prompt-processing batch | 800 | 1,024 |
| Target layer split | 34/30 | 32/32 |
| Attention K/V | FP8 E4M3 | FP8 E4M3, target and drafter |
| Cache allocation | 2.75 GiB/card budget | 2.85 GiB/card budget; 2,912 MiB physical pool observed/card |
| Recurrent / convolution state | FP32 / BF16 | FP32 / BF16 |
| Drafting | Built-in MTP3 | DFlash2, seven proposals |
| Draft weights | Existing target checkpoint | syvai W4A16, revision below |
| Draft-only embedding | Existing MTP module | INT4 group32, FP16 scales, exact BF16 mask row |

The separate drafter is `syvai/Qwen3.8-27B-DFlash2-W4A16` revision
`4d30ec736ffc6b8688dc2ae2b502d9b48bdec279`. Its checkpoint SHA-256 is
`ec26996e6a0745ab5edb857117220ce1e219ad524f71e6e149b703804947d8e7`.
The target's stage-zero embedding and output head are unchanged. Compression of
the otherwise BF16 stage-one embedding affects only drafting. The fused gather
runs on the GPU; CPU staging occurs once while loading weights.

Images remain enabled, with the existing processor size limit. Sixteen-image
requests and image-bearing near-capacity requests have been exercised. The
999-image engine limit removes an artificial two-image ceiling; it is not a
promise that 999 full-resolution images fit. Context, upload and memory limits
still apply. Video is disabled. The app reserves 32,768 tokens for output, so its
admitted input budget is smaller than total context and includes image tokens.

## Matched measurements and functional qualification

These measurements use the final clean images, warmed kernels, one request at a
time and the same public Tika-extracted document packets and sampling settings.
Compilation, downloads and first-use startup were excluded. Reported generation
includes hidden reasoning. Ranges are the minimum and maximum of three repetitions.

| Workload | Ollama Q6 historical control | Native MTP | DFlash batch 1,024 |
|---|---:|---:|---:|
| ~65K input, exactly 1,024 generated | 162.29s, one control | 41.84s (40.37–41.88) | 40.12s (38.62–40.30) |
| First generated token on that workload | 124.19s | 19.98s median | 21.40s median |
| Generation after first token | 26.86 tok/s | 46.82 tok/s | 54.62 tok/s |
| ~2K input, exactly 1,024 generated | 33.94s, one control | 21.48s (20.86–21.67) | 14.68s (14.62–15.35) |
| Short-probe generation after first token | Historical control | 49.01 tok/s | 73.09 tok/s |
| Peak GPU memory during these probes | Historical control | 15,791 / 15,553 MiB | 15,491 / 15,229 MiB |

The median accepted-proposal fractions were 66.28% (MTP, long), 62.45%
(MTP, short), 34.64% (DFlash, long), and 44.00% (DFlash, short). Because
DFlash proposes seven tokens rather than three, the useful approximate tokens per
verification step including the target token were 3.42 long and 4.08 short, versus
2.99 and 2.87 for MTP. Publisher H200 acceptance-length figures were not transferred
to this machine.

DFlash reduces short-probe elapsed time by about 32% relative to native MTP. Its
roughly 4% long-probe advantage overlaps measurement variability; do not promise a
consistent long-prefill improvement over MTP. Against the historical Q6 control,
DFlash took about one quarter of the long-probe time. This is an end-to-end stack
comparison, not evidence that FP4 alone is four times faster. Ollama was not rerun
in this final campaign; its exact Unsloth UD-Q6_K_M weights and vision component
remain retained and identified in the Ollama profile.

The research 65K-to-8,192-token probes took 166.85s for DFlash and 183.43s for
native MTP. Both exhausted their budgets before completing a requested 40-section
synthesis. Those are sustained-throughput measurements, not quality successes.
A shorter six-section synthesis did complete; its source-quality findings below
remain part of the result. DFlash batch 800 measured 44.81s and batch 1536 measured
48.10s on the research long probe. Batch 1536 was rejected despite fitting.

Clean-image qualification covered twelve focused known-answer cases, sixteen
images, near-128K input with an image, long confusable identifiers and document
follow-ups. Eight 1,024×1,024 images also passed. The actual app's eight browser
flows passed, including document upload through Tika, a scanned PDF through OCR,
images, follow-ups, reset, copy/export and two sessions. A separate upload test
correctly distinguished quoted publications from the actual source filenames,
revision numbers and counts.

New Chat became ready in 0.515s during generation. Actual socket cancellation
released inference in 0.117s before generation and 0.116s during generation;
subsequent document and image requests passed. Deliberately killing an engine
worker caused one restart and restored readiness in 146.77s. The interrupted
request failed explicitly and its partial response was not treated as complete.
Fresh-cache startup took approximately 3.6 minutes for DFlash and 4.0 minutes for
MTP. Startup time is separate from inference latency.

A 20.2-minute mixed-load run completed 57 requests: ten near-128K image-bearing
requests, ten eight-image requests, ten long confusable-identifier requests, and
nine each of document follow-up, image history and 16K extraction. All known-answer
checks passed, with no restart. Observed GPU high-water marks were 15,549 and
15,251 MiB. Idle endpoint readings rose by 50/14 MiB over the run; this is recorded,
not claimed to prove either a leak or zero long-term growth. This is bounded local
testing, not a multi-day soak. The activated deployment identities are recorded
separately. NVML showed more apparent free memory than CUDA allocation
accounting in the research runs; neither a model-file size nor an NVML reading
alone establishes spare allocatable capacity.

## Source grounding and quality limits

Manual review caught a DFlash synthesis citing NIST-53 excerpts 47 and 50 even
though those excerpts came from NIST-34 quoting an older NIST-53 edition. That
answer is a failed citation result, despite passing simple keyword/completion
checks. The original attention control made a different error, reporting ten
controls where the supplied historical passage says nine and marks one withdrawn.

A matched original/DFlash test added a general rule to cite the source actually
provided, preserve editions, and distinguish examples from requirements. Both
completed and avoided nonexistent source/excerpt pairs. Manual review still found
an unrelated excerpt citation in the original answer and historical-scope
ambiguity in the DFlash answer. Neither synthesis is labeled error-free. The
useful rule is now included in the application's document-grounding instruction;
it is not a guarantee against hallucinations or evidence that a kernel repair is
unnecessary for every possible workload.

At one reconstructed identical source-decision prefix, the original/DFlash
next-token distribution difference was bounded between 0.00212% and 0.00502% TV;
both preferred the correct source. This omitted the natural generated reasoning
history and therefore does not prove why the complete answers differed. Together
with the earlier three-request final-logit screen and exact known-answer checks,
it supports limited local use, not general quality equivalence. Source-sensitive
answers still need verification against the supplied material.

## Numerical decision

Native attention rounds BF16 queries to E4M3 and packs softmax probability
operands to E4M3 after multiplying by 256, with compensating output scaling and
FP32 accumulation. It is an approximation, not a distribution-preserving change.
Executed disassembly established native QMMA rather than BF16 HMMA for this
specialization. Synthetic and real-row tests found probability mass loss and
query-rounding error; these limitations are preserved in the evidence.

A targeted three-request final-logit comparison at identical prefixes compared
original attention, query-rounding control and native attention. Nineteen unique
checkpoints were examined. Maximum first-position total variation was 0.52549%;
maximum earliest critical-field variation was 0.19909%. No critical correct-token
winner changed. This is proportionate application evidence, not proof about all
prompts. Speculative acceptance alone cannot certify target quality. Residual-Q
and tile-local probability rewrites are deferred unless downstream evidence
justifies their added numerical, compiler and register-pressure risk.

## Reproduce and operate

Use the normal deployment tool from the repository root, in an isolated checkout:

```bash
python3 scripts/deployment.py prepare fp4 --profile dflash
python3 scripts/deployment.py models fp4 --profile dflash
python3 scripts/deployment.py config fp4 --profile dflash
python3 scripts/deployment.py start fp4 --profile dflash
```

Do not start a second GPU engine beside a running one. The profile must match the
prepared deployment. Use `--profile mtp` to prepare the simpler fallback. Ollama
retains its separate prepare/models/start route and exact retained model manifest.
These generic commands provision their own Tika; the existing-machine cutover
uses its preserved Tika container instead and has separate recovery tooling.

The Docker build pins vLLM, b12x, FlashInfer and wheel hashes. DFlash carries seven
small hash-checked engine patches: target placement/embedding hook, PP auxiliary
feature relay, draft shared-module and packed-K/V loading, draft compile boundary,
Marlin load-time allocator cleanup, hybrid grouping, and resolved draft KV layout.
The native attention backend/adapter and compiled object have separate identities.
No research RPC, raw-logit capture, forced-history or model-tensor audit is shipped.

The exact compiled native object is retained privately and identified by SHA-256
`aeb3e7488e960cab7f48f5a609a5e466e970eadc7bce1b88e2aacffe172cb684`.
The public tree contains the adapter, patches, pinned source URL, compiler wheels
and hashes. It does not distribute the compiled object or the upstream helper.
The pinned upstream file has both a BSD header and a restrictive helper notice;
see [native build provenance](../deployment/fp4/native/README.md). This remains a
public-distribution limitation, not a claim that downloading resolves licensing.

`prepare fp4 --profile dflash` uses a privately restored exact object from
`.local/native-rebuild/native-nhd.o` or builds it from the pinned upstream inputs
in a disposable compiler container. Compilation requires an idle GPU and never
stops another installation. CUTLASS 4.7.1 compilation remains isolated from the
4.6.2 serving compiler packages. A previous source rebuild matched the exact
object hash; a different result fails closed and requires requalification.

## Reliability and privacy

Each request owns its HTTP connection. New Chat and the request deadline shut down
that connection even while the SDK is blocked waiting for headers or another
stream chunk. The app releases its work slot, excludes cancelled/partial answers
from future model history, and closes the client. DNS/connect stages retain a
five-second bound; this is not a guarantee of instantaneous cancellation at every
network layer. Automatic retries remain disabled to avoid replaying partial work.

The engine supervisor discards raw stdout/stderr, classifies only fixed failure
codes, and keeps a 128-entry numeric event ring on tmpfs. It never writes prompts,
attachments, reasoning, outputs or exception text. Fatal workers cause container
restart. A ten-minute active-progress watchdog counts generation including hidden
reasoning, tolerates full-context prefill, and never restarts an idle engine merely
for inactivity. This does not claim detection of every possible silent failure.
The ring is bounded and nonpersistent across a container restart.

Before upgrading this pinned stack, recheck 128K+images, cancellation/reuse, target
quality, draft acceptance, actual native dispatch and matched elapsed time. Keep
both the MTP fallback and original Ollama containers/model store recoverable.

## Final drafting screen and local decision

Natural greedy output was not token-identical to a no-drafting control on any of
three requests. The checked arithmetic, image values and long-document identifiers
remained correct. MTP also differed on these requests, although its different
batch/layer split prevents clean attribution. This implementation is not presented
as bit-identical or proven distribution-preserving.

A diagnostic-only comparison then held complete prefixes identical on the same
three requests. All seven preselected factual positions and three first predictions
preserved their winning tokens. Maximum full-vocabulary total variation was
0.005642 (0.5642 percentage points), below the predeclared 2% engineering screen.
The no-drafting replay also varied from its natural run: the largest top-five
probability residual was 0.801 percentage points, without a winner change. These
are selected-prefix results, not an answer-level error-rate bound.

One diagnostic assertion failed because it compared all sampler rows, including
work after EOS, with the API's trimmed output. The canonical prefix assertion had
already passed; every compared logit row preceded EOS and had the same complete
prefix hash. Raw failure evidence is retained. No diagnostic hooks enter either
clean serving image.

The selected local profile is DFlash batch 1024, retaining full 131,072 context
and images. Native MTP remains the simpler fallback. This decision rests on the
short-query gain, bounded quality checks, mixed load, cancellation and restart
evidence, with the numerical and citation limitations above explicitly retained.
It is not a claim that every conceivable optimization has been exhausted.

The corrected MTP fallback also started successfully and passed complete-answer
arithmetic, two-image and near-capacity document-plus-image controls. It was not
subjected to another full speed campaign. The earlier MTP timing table remains
historical to the numerical-policy follow-up.

The pinned configuration defaults to `draft_sample_method="greedy"` and
`rejection_sample_method="standard"`. Its DFlash speculator therefore leaves
`draft_logits=None`; the synthetic one-hot verifier test exercises the relevant
nonzero-temperature acceptance/resampling branch. The probabilistic-drafter
option is different and was not enabled or qualified.
