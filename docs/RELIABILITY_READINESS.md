# CURRENT local chat-media guard — September 10, 2026

Installed and independently reviewed runtime source:
`5af7b37919dc55caa1c8aeca3dfba921b35d17a6` on local branch
`codex/local-chat-media-guard`, based on tokenizer handoff
`3fe04d3bd29795b82a25aa6248420304aa24bc5e`. Image:
`hfs-ai-ephemerai:media-5af7b37`. All **17 runtime Python files** match source.
Subsequent handoff/publication commits change documentation and Git metadata only.
Publication branch: `codex/token-counting-chat-media`, based on freshly verified
main `d98f804378eae3bc4dca3faa2995122824065e72` (the merge of PR #5). Its source
tree preserves both the tested tokenizer correction and media guard. The review
SHAs above/below identify immutable local review commits. This is a tested local
candidate proposed for review, not a merged release.

Confirmed issue: message Markdown could automatically fetch image URLs through
Streamlit, including during streaming. The display guard renders image-bearing
messages literally, closes secondary tooltip and attachment-label routes, and
restricts upload previews to bounded in-memory image data. Ordinary Markdown,
explicit links, uploaded previews, model requests, token admission, retained
content and copy source are preserved. Whole-message literal display deliberately
sacrifices Markdown styling when image syntax is present. See
[CHAT_MEDIA_GUARD.md](CHAT_MEDIA_GUARD.md) for behavior and reproductions.

Actual validation:

- Both required pytest entry points: **325 passed each**; syntax compilation passed.
- Controlled Chromium positive control fetched a local canary from unguarded
  Streamlit. **64 guarded chat/label cases** and actual app user/stream/final/copy
  paths made **zero media requests**. Ordinary formatting, explicit link clicks,
  exact clipboard source and narrow composer checks passed. Outside requests were
  intercepted; no external server or private conversation was used.
- Fresh-context read-only review of the immutable runtime commit above found
  **no actionable findings**. The reviewer checked the pinned Streamlit renderer
  and independently ran **27 focused tests**, all passing.
- Installed real browser → app → Tika/model: **8 groups passed**, including TXT,
  long-document retrieval/follow-up, supported-image display/answer, scanned PDF
  OCR, unreadable-file follow-up, copy/export, one-turn Thinking and two sessions.
- Installed empty desktop/mobile smoke, runtime/privacy checks, requirements
  satisfaction, pip check, app-only build, relative links and diff checks passed.
- Ruff: **55 remaining pre-existing findings; no additions** against the starting
  baseline of 56. Consolidating duplicate image paths removed one existing finding.
  Full-repository lint therefore still exits nonzero; no broad cleanup performed.

The pre-task tokenizer app/configuration is preserved in ignored
`.local/compose.pre-media.json`; exact recovery commands and current configuration
are in `.local/RECOVERY.md`. Shared backend IDs, images, start times and mounts are
unchanged. The separate dirty live checkout was not edited. No new production
dependency, backend/model, network/authentication or unrelated repository change.

These tests confirm and block the rendering route. They do not establish that
private information previously leaked or that a malicious document successfully
induced the live model. Plain Markdown copied into another application may be
rendered differently. This is targeted testing, not a security certification.
Earlier reports below describe historical candidates.

---

# HISTORICAL local context-counting candidate — September 10, 2026

Runtime source: `be9e08c136f04628d5790ff9571dc5bd708f7f70` on local branch
`codex/local-model-token-count`, based on the installed/published feedback candidate
`29f2607fbe000addf4f735f7589a584500d4e934`. Local-only work: nothing pushed and no
PR created or updated. The later handoff documentation commit changes no runtime code.
The app image is `hfs-ai-ephemerai:tokens-be9e08c`. All 16 runtime Python files
were hash-verified against the source. The prior feedback app/configuration is
preserved in ignored `.local/compose.pre-tokenizer.json`; current recovery details
are in `.local/RECOVERY.md`. Shared Ollama/Tika identities, start times and mounts
remain unchanged, and the original dirty checkout was not edited.

The real byte-per-token admission rule was overly restrictive. The replacement
uses the installed model's verified vocabulary/merge rules and pinned renderer
formatting locally. Output allowance/reserve stays 32,768; context stays 131,072.
The UI caption/help/layout are unchanged. See [TOKEN_COUNTING.md](TOKEN_COUNTING.md)
for method, provenance, reproduction commands, and remaining conservative cases.

Actual validation:

- Both required pytest entry points: **298 passed each**.
- Independent test-only tokenizer/Unicode oracles: **1,005 cases passed**.
- **9 synthetic real-backend input counts and rendered prompts matched exactly**.
  The old 103,398 estimate became 19,499, matching Ollama, and is admitted.
- Exact/one-token-over boundaries tested locally near 98,000 input tokens without
  a full-context generation. Input and output allowance are not lowered.
- Final controlled Chromium failure/retry runner: **13 groups passed**.
- Real installed browser → app → Tika/model runner: **8 groups passed**, including
  a >98-KB document with both-end retrieval and retained-document follow-up.
- Installed desktop/mobile smoke, syntax compilation, requirements satisfaction,
  pip check, app-only build, runtime/privacy checks, relative links and diff checks
  passed. Ruff remains **56 identical pre-existing findings**, with no additions.
- Fresh-context read-only review at `8a442cde893b0cfdb5be1664094c79fd6f2387c7`
  found a metadata retry under the conversation lock. Corrected in
  `a1232527158f8131dd60f0ed0bf0a3e07b861855`; reviewer independently ran all 36
  tokenizer tests and verified the fix. Final reviewed runtime `be9e08c136f04628d5790ff9571dc5bd708f7f70`
  has **no remaining actionable findings**. The correction also guards retained
  result publication by owner liveness and content revision.

No production dependency, model, framework, network/security setting or shared
backend changed. Tokenizer metadata alone is cached in memory; chat text/token IDs
are not cached or logged. Image allowance and exceptional oversized/unassigned-
Unicode text bounds remain conservative. Separate message/upload/storage limits
remain. Full-context/full-output stress, arbitrary future renderer versions and
exact image token counts are not claimed. Earlier results below are historical.

---

# HISTORICAL reliability review and minimal feedback candidate — September 9, 2026

## Source, review and deployment state

Starting main: `88a05d1a447186e1608fcfb1b01a9567b8c91f31`, freshly verified through
GitHub's authenticated Git API. CLI Git had no login; fetched commit/tree hashes
and all cached blob hashes were checked before the isolated checkout was created.
Branch: `codex/reliability-review-feedback`. Historical review-only base:
`06b0a167114a07bba0db2f26d93c28179d174d96`.

**Tested and installed application source:**
`e3093c23df510f79f545bb6a23cefdd3f46e1828`.
The handoff documentation update changes no runtime source. This is a tested
candidate installed locally, not a merged GitHub release or security certification.
Publication uses the authenticated Git API; the remote tree and runtime source
hashes are checked against the local candidate, independently of commit metadata.

Two separate read-only reviewers were used. The first reviewed the cumulative
historical-to-main implementation before edits. A fresh reviewer reviewed both
historical-to-candidate and main-to-candidate at `119efbd7564bb8cb00defc12a014fce565373afc`,
then verified corrections through the final source commit above. Source stayed
immutable during each pass. Its final disposition was **no actionable findings**.
Exact review commits, reproductions, fixes and limits are in
[RELIABILITY_REVIEW.md](RELIABILITY_REVIEW.md).

Discovery confirmed that the pre-task app ran the installed quiet UI source
`f3531450b15d66a30c391e485fd9e09a3fff2cb1`; all 19 inspected runtime/source/config
files matched freshly fetched main. Container-only differences were generated
bytecode and the existing mounted no-dump library, not live-only application edits.
The separate dirty live checkout and its older EphemerAl remote were preserved.
Current app image/configuration, the pre-task image, service identities and the
exact app-only rollback command are retained in ignored `.local/RECOVERY.md` and
its adjacent records. Do not use the dirty checkout's full-stack Compose to manage
this candidate. Shared Ollama/Tika IDs, image identities, start times and mounts
were unchanged. No HFS Knowledge, model, network or authentication changes.

## Resulting behavior

Confirmed reliability fixes cover late preparation publication after owner release,
last-slot retry, lost retries when process capacity is occupied, silent preparation
timeouts, premature incomplete warnings, and logical-event/SDK-frame/compressed
response bounds. The canonical serializer and conservative estimator, 32768 output
allowance, server limits, pinned model/profile and attachment display acknowledgement
remain intact. No production dependency changed.

The existing worker and polling fragment provide a small stage caption with whole
elapsed seconds. File ordinals refer to the submitted batch. Thinking requires
observed nonempty dedicated reasoning; only presence reaches feedback state.
Filtered visible answer text removes the caption and streams normally. A truly
interrupted reply is marked incomplete and excluded from model history/export.
Only actual stage text is a polite live region; timer ticks are excluded. No typing
counter, max_chars, prominent waiting bar, queue estimate, reasoning text or new
framework. Content-width native captions keep the timer beside its stage.

An immutable numeric budget snapshot is cached by conversation identity and content
revision. Active requests show their actual preflight estimate; at rest it describes
retained content, with one answer reserve, excluding the unsent draft. Completion
and rejection/failure recompute retained content; failed context verification stays
unavailable. New Chat drops the snapshots. Percentages are floored, with informative
80%/95% warnings and an explicit distinction between exactly full and over limit.
No per-refresh counting/probes or new admission rules. Keyboard/touch help explains
conservative estimation and that New Chat carries no conversation/files forward.

## Actual final validation

All content-bearing fixtures were fictional and in memory. Only empty-session
screenshots and content-free results were retained. Tests use the existing isolated
test image; Playwright is absent from the installed application image.

| Check | Actual result |
|---|---|
| Starting main, both pytest entry points | 135 passed each |
| Final `python -m pytest -q` | **262 passed** |
| Final `pytest -q` | **262 passed** |
| Python/app/module/browser-runner compilation | Passed |
| Requirements install/satisfaction and `pip check` | Passed; production dependencies unchanged |
| Native-filesystem `ruff check .` | **56 pre-existing findings, unchanged; no added findings. Full lint still exits nonzero.** |
| `git diff --check`; README/deployment relative links | Passed |
| App-only image build and Compose resolution | Passed, using the preserved production runtime; no framework/OS upgrade |
| `scripts/reliability_failures.py` | **13 controlled Chromium groups passed**, including final caption spacing |
| `scripts/reliability_browser.py` | **7 real-backend groups passed**, both isolated candidate and installed final app |
| `scripts/ui_smoke.py` | Passed on installed app; empty desktop/mobile captures |
| Independent final correction verification | 93 SDK framing cases passed at `36e3979`; final presentation diff reviewed at `e3093c2`, no actionable findings |
| Installed source identity | All **15 Python file hashes** match the final reviewed runtime source |
| `scripts/verify_runtime.py` after installation | Passed; shared service/model identity and app protections preserved; zero swap/OOM kills |

Ruff was compared using actual Git file modes. The prior historical report's 54
omitted two EXE001 findings on the tracked non-executable browser runners; current
main and this candidate both have 56. This debt was reported, not skipped or
removed through an unrelated cleanup.

Real paths include TXT → Tika → model, scanned PDF OCR, supported image input,
unreadable-upload follow-up, one-turn Thinking Mode, two separate browser sessions,
and copy/export through the real browser button with an in-memory clipboard sink.
Empty captures in the test image are `artifacts/ui-smoke/home-desktop.png` and
`artifacts/ui-smoke/home-mobile.png`; handoff copies are separate output artifacts.

Controlled paths cover same-name/partial/omitted attachments, aggregate limits,
metadata mismatch/unavailability, busy/timeout/interrupted requests, retry at the
last slot and after process-capacity rejection, release/publication races, hidden
reasoning sentinels in UI/state/export/logging, pre-dispatch acknowledgement, stage
timing without repeated live-region changes, healthy versus incomplete streaming,
budget 80%/95%/exact/over-limit boundaries, stale/missing/invalid measurements,
retained/request snapshot equality, rejection restoration and New Chat. Ninety
short CR/LF separator/chunk-partition combinations and surplus-newline exact
boundaries use the installed SDK as the framing oracle. Compressed-response tests
exercise the actual HTTPX/OpenAI path; they are not normal-backend acceptance claims.

## Remaining evidence limits

The ordinary real model/Tika paths passed without exhausting resources. A full
131072-token request, full 32768-token completion, extreme file/concurrency stress,
physical model cold reload and fresh-host/Internet-base-image installation were
not repeated. The estimator was not retuned; historical tiny calibration is not
proof for every input. OS clipboard and actual screen-reader speech were not
verified; browser clipboard behavior, keyboard help and live-region DOM mutation
were checked. Cleanup releases application references, not forensic byte erasure;
UI cancellation does not prove backend cancellation. All earlier deployment and
publication narratives below are historical.

---

# Historical reliability candidate — September 9, 2026

## Scope and source

Implemented backlog **1, 2, 3 and 6 only**: attachment truthfulness, complete-request
admission, bounded resources, and recoverable slow/failed work. No networking/auth
changes, CI/review/monitoring infrastructure, model changes, installers, public
product generalization, saved chats or HFS Knowledge changes. Nothing was pushed,
merged or submitted as a PR. This is a local candidate, not a launch certification.

Fetched HFS-ai main: `06b0a167114a07bba0db2f26d93c28179d174d96`.
Branch: `codex/hfs-reliability-readiness`.
Implementation commit: `76e8498` (the final handoff commit is reported in chat).
Origin: `https://github.com/eowensai/HFS-ai.git`.

The native Git CLI lacked authentication. The existing authenticated GitHub
connector fetched main's reference, signed commit and recursive tree. All 67
cached blobs were checked against those freshly fetched object hashes; the Git
commit and tree hashes were reconstructed and verified exactly in a separate
shallow checkout. Main was checked again at handoff and was unchanged.

Discovery confirmed a Windows/WSL/Docker deployment. The live checkout still has
its older EphemerAl remote and uncommitted changes. It was preserved. Its core
application source matched the fetched baseline; deployment/install docs, Compose
and other source-publication files differ. Four deployed core Python files were
also hashed. Ignored `.local/` holds the detailed source comparison, image IDs,
mount/configuration records, live status and recovery procedure. No user content,
model weights or volume contents were backed up.

## Decisions and defaults

- Attachments have unique IDs and explicit **available / partial / unavailable**
  receipts in both UI and model messages, including follow-ups and rejected
  submissions. Same-name files remain distinct. JSON encodes names/text as data;
  system instructions deny them application authority. Export reads generated
  metadata rather than parsing document text as filenames. Partial/unavailable
  statuses are displayed before model dispatch. All-failed uploads without an
  explicit question cause no automatic inference.
- Tika uses its supported `/tika/text` JSON response with `writeLimit` and
  `throwOnWriteLimitReached=false`. Parser exception/write-limit metadata marks
  partial extraction. JSON is bounded before decoding, and returned UTF-8 text
  is bounded again. HTTP/format failures become unavailable. The server's parser
  configuration, native helpers and container protections are unchanged.
- Budget the **same messages/request object sent to the SDK**: system text, all
  retained history, receipts, extracted text, images, template/role overhead and
  the full generation reserve. Nothing is silently truncated or replaced with
  older attachment content. Oversized turns retain only bounded unavailable
  receipts; prior usable history is preserved. Missing context metadata retains
  a bounded pending turn for explicit retry.
- Fresh `/api/show` alias `num_ctx` and `/api/ps` running context are checked on
  each request. Observed runtime and alias: **131072**; family metadata: **262144**.
  Running mismatches, missing metadata, or an app hint above the alias fail closed.
  An observed empty runner list uses the verified alias's cold-load configuration.
  Existing immutable model identity/capability checks remain enforced.
- Ollama 0.32.15 has no public `/api/tokenize` route (installed probe returned 404).
  Admission uses a **conservative estimate**, not exact tokenization: UTF-8 bytes
  for text, 512 fixed template tokens, 64 per message plus role bytes, 32 per
  content part, and 8192 per normalized image. Images are capped at a 1024-pixel
  edge even if the operator requests a larger rendition. Prior usage is not
  admission control; legacy tokenizer/heuristic knobs cannot disable admission.
  Reserve is `max(LLM_OUTPUT_RESERVE_TOKENS, request.max_tokens)`, normally 32768.
  The existing output ceiling and medium/xhigh one-turn profile are unchanged.
- One active operation per browser session and four per app process; excess work
  is rejected without queuing. Workers capture conversation ownership and never
  use another session's state. New Chat/disconnection release the old owner;
  late results cannot populate the new conversation. Explicit retry reuses one
  user turn. Automatic SDK retries and speculative request retries are disabled.
- Only an explicit `finish_reason=stop`, nonempty filtered answer, and clean
  stream completion enter history. Interrupted, length-limited or unclosed-thought
  replies stay visibly incomplete and are excluded from model history/export.
  SSE event/total limits apply before the SDK decoder buffers an oversized event.

Defaults are positive integer environment variables, except the existing model
request timeout. No new production dependencies were added.

| Setting | Default |
|---|---:|
| `MAX_UPLOAD_COUNT` / `MAX_UPLOAD_TOTAL_BYTES` | 8 files / 64 MiB per submission |
| `MAX_UPLOAD_BYTES` | 50 MiB per file (Streamlit transport cap also remains 50 MiB) |
| `MAX_EXTRACTED_BYTES` / `MAX_EXTRACTED_TOTAL_BYTES` | 256 KiB per file / 512 KiB per submission |
| Parser JSON buffer | 6 × text allowance + 64 KiB metadata, checked in 4 KiB reads |
| `MAX_IMAGE_PIXELS` / `MAX_IMAGE_EDGE` | 16 million pixels / 8192 pixels, before decode |
| `MAX_IMAGE_OUTPUT_EDGE` / `MAX_IMAGE_OUTPUT_BYTES` | 1024 pixels / 1 MiB JPEG rendition |
| `MAX_CONVERSATION_MESSAGES` / `MAX_CONVERSATION_BYTES` | 80 messages / 16 MiB of counted payload per session |
| `MAX_PROMPT_BYTES` / `MAX_RESPONSE_BYTES` | 64 KiB / 512 KiB |
| `MAX_STREAM_EVENT_BYTES` / `MAX_STREAM_TOTAL_BYTES` | 64 KiB per event / 32 MiB total, including hidden deltas |
| `TIKA_TIMEOUT_S` / `UPLOAD_PROCESS_TIMEOUT_S` | 180 seconds per parser request / 600 seconds preparation deadline |
| `LLM_REQUEST_TIMEOUT_S` / `MAX_ACTIVE_REQUESTS` | existing 1800 seconds / 4 |

Submitted Streamlit upload-manager entries are detached by current session ID and
file ID, then wrappers are closed after preparation/rejection. Only normalized
images and bounded text are retained. Superseded work is disowned and cleared.
Payload-byte limits are not exact Python heap/RSS limits. Native/browser/network
buffers have additional lifetimes; releasing references is not forensic erasure.
Streamlit receives upload bodies before submission-level aggregate checks; its
per-file transport cap remains the first bound. Per-session retained limits and
four active workers do not certify unlimited simultaneous browser sessions.

Deadlines are checked between reads; an already blocked socket read can last up
to its configured timeout. New Chat stays responsive, but another submission in
that session waits for its old local worker to exit. Neither closing the UI nor
closing a client stream is represented as verified backend cancellation.

## Actual validation

Tests used synthetic fixtures only. Test tooling/Chromium ran in a separate test
image, not the candidate/production image. Native temporary source copies with
Git file modes avoided Windows-mount executable-bit artifacts in Ruff.

| Command/check | Actual result |
|---|---|
| Baseline `python -m pytest -q` | 99 passed; two existing Tika deprecation warnings |
| Four new baseline regressions | 4 failed before implementation: all-failed inference, follow-up status, original-buffer retention, forged export filename |
| Candidate `python -m pytest -q` | **135 passed** |
| Candidate `pytest -q` | **135 passed** |
| Final `python -m pytest -q tests/test_reliability_boundaries.py` | **34 passed** after final lint-only simplification |
| `python -m py_compile ephemeral_app.py ephemeral/*.py` and browser runners | Passed |
| `pip install -r requirements.txt -r requirements-dev.txt`; `pip check` | Installed/satisfied; no broken requirements; production requirements unchanged |
| `ruff check .` | **54 remaining pre-existing findings**, versus 81 on the fetched base; no added file/code findings. Full lint still exits nonzero. |
| `git diff --check` | Passed |
| Candidate Compose resolution/build | Passed; one candidate service, external existing network, no published ports, one read-only no-dump mount |
| `python scripts/reliability_browser.py` with `EPHEMERAL_UI_URL` | Passed all seven live browser groups |
| `python scripts/reliability_failures.py` | Passed all ten controlled browser groups |
| `python scripts/ui_smoke.py` with `EPHEMERAL_UI_URL` | Passed desktop/mobile empty-session captures under ignored `artifacts/ui-smoke/` |
| `python scripts/verify_runtime.py` | Production privacy/model checks passed; original app/backend images retained; zero swap/OOM kills |
| Candidate cgroup / test-tool check | 2 GiB memory, zero swap/OOM events; Playwright absent |

**Live:** real browser → app → Tika → supported model for TXT and scanned PDF
(code 731), real supported-image use (731), unreadable upload and follow-up,
Thinking Mode reset and subsequent ordinary turn, and two isolated browser
sessions with one session reset while the other's state remained intact. Copy/
export used the real browser button and an in-memory intercepted clipboard API;
the operating-system clipboard was not used as evidence. Empty-only screenshots:
`artifacts/ui-smoke/home-desktop.png`, `artifacts/ui-smoke/home-mobile.png`.

Live synthetic estimator calibration, using backend usage only after generation:
text estimate **722** versus **35** reported prompt tokens; image estimate **8969**
versus **130**. Both retained 32768 output reserve against 131072 runtime context.
These examples support conservatism for the fixtures, not exact counts or a proof
for every possible input. The installed Tika write-limit and ordinary extraction
paths were also probed directly with tiny text fixtures.

**Doubles/reduced limits:** parser timeout/failure/partial/oversized response,
all-failed and mixed/same-name uploads, unsupported/invalid images, hostile names
and document markers, image pixel rejection before decode, aggregate upload
rejection before reads/parsing, history/resource rejection and release, complete
request equality/one-token-over boundaries, generation reserve, cold/missing/
mismatched metadata, busy/unavailable model, interrupted/limited/oversized stream,
manual retry, duplicate admission, status-before-dispatch, New Chat while pending,
and late-result isolation. Failure browsers ran the real app and Chromium against
local HTTP doubles; they never broke the shared services.

## Handoff and remaining limits

The candidate was built on the retained production app runtime image to avoid an
OS/dependency upgrade. This tested a production application image with the changed
source, not a fresh Internet rebuild of the floating Python base. Production was
left on its original image. The isolated candidate and test containers are stopped
after acceptance; their images/configuration and local recovery notes remain.
Shared Ollama/Tika container IDs, image identities and mounts were preserved.

Not verified: a physical shared-model unload/cold reload; a full 131072-token
request or 32768-token completion; extreme concurrency/large-file memory stress;
every document format; new-host installation or peer-network access. These were
not substituted with mock evidence. Existing Ruff debt remains. Review the local
diff against the fetched base before a separate deployment/push decision.

Protocol references inspected for this implementation:
[Ollama 0.32.15 routes](https://github.com/ollama/ollama/blob/v0.32.15/server/routes.go),
[Tika 3.3.2 resource and write-limit behavior](https://github.com/apache/tika/blob/3.3.2/tika-server/tika-server-core/src/main/java/org/apache/tika/server/core/resource/TikaResource.java),
[Tika partial/error metadata](https://github.com/apache/tika/blob/3.3.2/tika-core/src/main/java/org/apache/tika/metadata/TikaCoreProperties.java).

## Follow-up: quieter request UI (2026-09-09)

After PR #3 was merged and installed, user feedback requested removal of the
composer counter and prominent waiting bar, and continuous visibility of the
submitted prompt. Base: merged main `75c473cb1dacc25efcaa3981ec98cbbd690b62a5`.

Removed the composer `max_chars` option; the existing server-side UTF-8 text limit
and complete-request budget remain unchanged. Normal request stages now use a
small caption. The polling fragment renders newly accepted messages and a preview
of the submitted text during parsing; the preview does not enter model history.
Attachment badges still appear before dispatch. Errors, incomplete-response
handling, explicit retry, New Chat isolation and all original limits are retained.

The expanded `python scripts/reliability_failures.py` first reproduced the missing
prompt during controlled parsing, then passed all **11 browser groups** after the
fix. It checks prompt visibility during reading and model waiting, no duplicate
prompt after completion, no counter, and no alert-style waiting bar. Both pytest
commands passed **135 tests**; compilation and `pip check` passed. Native-filesystem
Ruff still reports the same **54 existing findings**, with no new file/code findings.
`git diff --check` passed. The installed app passed all **7 real-backend browser
groups** and `python scripts/ui_smoke.py` (empty desktop/mobile screenshots).

Runtime source commit `f3531450b15d66a30c391e485fd9e09a3fff2cb1` was installed as an
app-only update using the previous runtime image. Installed source hashes match
the commit. Existing app settings and mounts were preserved; shared Ollama/Tika
identities and start times are unchanged. Prior image/configuration references and
rollback commands are retained in ignored local recovery notes. Earlier stress,
fresh-install and physical-clipboard limitations still apply.
