# Reliability candidate — September 9, 2026

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
