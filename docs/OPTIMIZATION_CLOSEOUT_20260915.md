# Qwen3.8 local inference optimization closeout: September 15

This is a September 15 addendum. Earlier September 14 technical debriefs retain their original evidence cutoff. No result below retroactively changes an earlier failed gate.

## Closed decisions

| Lead | Disposition |
| --- | --- |
| Timestamp invalidates conversation prefix | Fixed by qualified application design: stable system/history and per-turn captured time |
| Specific 64-versus-1664 resumed-state indexing hypothesis | Not reproduced on the observed selected runtime; no indexing patch |
| Q power-of-two scaling S=2/4/8 | Negative numerical screening; no serving integration |
| Missing CUDA-graph replay | False; actual replay observed |
| Missing target XQA | False; actual execution observed |
| Feature concatenation optimization | Measured contribution too small for a worthwhile candidate |
| Selector optimization | Measured contribution too small |
| Switch to original attention | Rejected on current final-stack evidence; native remains selected |
| Current structured grounding contract | Rejected as a correctness safeguard; mechanical quote/source checks did not prove semantic support |
| Seeded sampling first-use delay | Missing-signature Triton compilation in top-k/top-p and Gumbel; optional manual warmup only |
| No-draft/DFlash exactness | Later-generation difference unresolved; no serving defect or fix qualified |

The sampling pause was approximately 5.6 seconds within a traced seeded sampling call, with approximately 5.589 seconds in nested compilation. Compatible cached processes did not repeat a fixed six-second delay for the tested signatures. Normal unseeded application sampling used FlashInfer. Other first-normal-request initialization was not fully localized. No sampling math, loading policy or automatic serving warmup changed.

The matched image_pair used 1,424 tokens, 733 + 691 chunks, identical images/positions/weights/auxiliary contract, and two repeats per arm. First two target predictions matched exactly. First later difference was offset 2 before rollback: TV 0.00094234; largest among 32 verified common-prefix positions was 0.201654 at offset 6. Both arms selected the same 32 greedy tokens; this is not an answer-quality equivalence result. The first observed auxiliary change was between boundaries 34 and 48 in stage 1. Rounded hidden-plus-residual sums do not establish equality of separate operands/recurrent state, so exact causal operation remains unresolved. Fine probes failed reproducer preservation and were stopped. The historical 19 non-selected final prompt-output elements are not consumed in generation on that fixture. None of this explains away every historical comparable-prefix TV around 0.196–0.329.

The final native/original characterization favored native on the measured long fixed-output workload (39.267 s versus 48.853 s). Both retained the seven tested required-fact sets; image-ID attribution coverage was limited. This is a performance/quality characterization of approximate implementations, not proof that one is universally correct.

## Quality failures remain failures

Historical ownership loss, invented NIST locators, source/edition mixing, unsupported image corroboration and risk-register attribution findings remain open. Passing a later case does not close them. Native attention is approximate; there is no universal quality, lossless-attention, bit-identity, hallucination-elimination or rare-error guarantee. See FP4_QUALIFICATION.md for the release failure record.

## Re-entry conditions

There is no open-ended engine-optimization queue. Resume only with new evidence: a repeatable consequential decision regression; a supported upstream implementation that removes custom patches; a successor model; a newly measured material bottleneck; or a security/correctness issue. Any future localization must first prove that its instrumentation preserves the reproducer. No engine research, Q scaling, attention tournament or grounding refinement is part of finalization.

The 2026-09-11 through 2026-09-15 Qwen3.8 local inference optimization round is closed. Further engine optimization requires new evidence, a successor model, a supported upstream simplification, or a demonstrated consequential regression.
