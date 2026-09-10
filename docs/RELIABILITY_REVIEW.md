# Reliability review

## Published implementation — reviewed before editing

Historical base: `06b0a167114a07bba0db2f26d93c28179d174d96`.
Freshly fetched main/candidate: `88a05d1a447186e1608fcfb1b01a9567b8c91f31`.
The cumulative review includes the original reliability work and quieter UI fix.
A fresh-context, read-only subagent reviewed implementation and surrounding code;
source remained immutable until its findings returned. The implementation agent
also inspected these paths. This is a code review, not a security certification.

### Confirmed defects (locations on the reviewed commit)

| Finding | Reproduction / consequence | Source |
|---|---|---|
| P2: late preparation retains released content | Release the owner inside `available_count`, between the stop check and user publication. History/ownership clear, but `gate.active.user_message` receives extracted text afterward. No cross-session display leak demonstrated. | `ephemeral/request_lifecycle.py:126–132` |
| P2: retry double-counts its user slot | Start with 78 of 80 messages, fail the last allowed turn, then retry with 79 retained messages. Admission reserves two more slots although only an assistant slot is needed. | `ephemeral/request_lifecycle.py:105–107,119,144` |
| P2: silent preparation timeout | Expire the preparation deadline during `model_ready`. The worker returns without dispatch or error, leaving a stored unanswered prompt and no visible Retry action. | `ephemeral/request_lifecycle.py:161–169`; `ephemeral_app.py:517` |
| P2: SSE event bound bypass | Separate data fields with an unknown one-character `x` line. The bound resets, but the SDK keeps accumulating the same event. An 80,058-byte JSON event passed a 65,536-byte cap. | `ephemeral/bounded_transport.py:28–30` |
| P2: compressed event bound bypass | A 2,000-byte gzip body expands to a 2,000,023-byte event after the raw transport bound. Conditional on encoded upstream responses; not observed from ordinary Ollama. | `ephemeral/bounded_transport.py:43–47`; `ephemeral/llm_client.py:109` |
| P2: healthy streaming labeled incomplete | Any filtered partial answer immediately renders “Incomplete reply,” even before an interruption. The implementation agent confirmed this directly in the rendering path. | `ephemeral_app.py:510–513` |

### Missing evidence and optional improvements

The independent review's synthetic reproductions exercised real lifecycle and
transport functions with unused imports stubbed because its venv lacked runtime
dependencies. SDK and browser reproductions must additionally run in the complete
test image. Transport cases are controlled upstream fixtures, not claims about
normal model behavior. Published tests passed but omitted these specific races,
retry boundary and framing cases. No further attachment-status, request-equality,
reserve or capacity defect was substantiated. Extreme-context calibration,
physical cold reload and resource exhaustion remain unverified; deliberately
exhausting shared resources is unnecessary. No unrelated optional refactor is
proposed.

## Feedback protocol evidence

The installed Ollama 0.32.15 and OpenAI 1.97.2 stream produced a nonempty dedicated
`delta.reasoning`, visible answer content and a clean stop in a tiny synthetic
probe. Only three booleans were recorded. The pinned
[Ollama adapter](https://github.com/ollama/ollama/blob/v0.32.15/openai/openai.go)
maps native thinking to that dedicated field. Feedback may inspect its presence
at the stream boundary; the text must never enter feedback state or output.
The installed SDK's SSE decoder ignores unknown fields, and HTTPX's
[response decoding](https://www.python-httpx.org/quickstart/#binary-response-content)
occurs after the raw byte stream, confirming the reviewed boundary assumptions.

## Fix verification

The first candidate passes 167 tests through both pytest commands. The new
regressions use the actual SDK SSE decoder and actual HTTPX/OpenAI client for
transport failures, reduced message limits for final-slot retry, deterministic
release/deadline hooks and behavioral reasoning sentinels. Existing source-string
reasoning checks were replaced by lifecycle/UI/export/logging behavior checks.
Controlled Chromium verifies stage timing/announcements, private filtered
streaming, interrupted output, explicit retry, cached captions and keyboard/mobile
help. Full lint remains at the starting 56 findings, with no added debt.

## Final candidate review

A separate fresh-context read-only reviewer inspected both the cumulative changes
and the new diff at `119efbd7564bb8cb00defc12a014fce565373afc`. Source was immutable
throughout that review. It confirmed the six original fixes and reproduced two
additional P2 defects using the complete installed dependencies:

- `ephemeral_app.py:452–464`: if process capacity is occupied when Retry is clicked,
  clearing the old work before admission loses its retry state. The fix retains
  the previous work until the replacement is admitted. An AppTest regression
  occupies the semaphore, rejects Retry, frees it and successfully retries the
  same single user turn.
- `ephemeral/bounded_transport.py:33`: logical mixed LF/CR SSE separators reset the
  event bound but do not release the pinned SDK's raw frame buffer. 6,000 tiny
  synthetic events accumulated 114,000 bytes despite the 65,536 event cap; the
  total transport cap still applied. A separate bound now matches the SDK's
  three raw frame terminators, with an actual SDK regression.

The reviewer independently ran the first candidate's **168 tests**. It did not
repeat the implementation agent's live browser/backend tests or extreme resource
cases. The two follow-up fixes pass **70 targeted tests**. Final exact-commit
verification of those fixes and acceptance results are recorded below at handoff.

The follow-up review at `1cd912fe0a17c7e85d97c363aedc2da9792edd65`
verified the Retry correction but found that a CRCRLF delimiter substring could
still reset the raw-frame counter before the SDK completed its CRLF line.
The final correction checks delimiters only at the actual SDK split-line/raw-chunk
boundaries, without copying those lines. Ninety CR/LF separator and chunk-partition
combinations use the installed SDK as the oracle. All **160 affected tests** and
lint for the changed transport/test files passed. Final review disposition follows.

Verification at `8287da301947360978069d19db424e38f47b16e0` blocked both P2
framing reproductions and passed 126 feedback/transport tests. It found one P3
exact-boundary overrun: a surplus newline inherited the previous frame suffix,
allowing a 101-byte SDK frame at a 100-byte cap. The suffix now clears with the
frame counter, with exact/over-limit checks for whole and bytewise chunks.

The independent reviewer verified `36e3979b30e46ccde62b5566fef55508c02486ff`:
**93 focused SDK framing tests passed**, cumulative diff check passed, and no
remaining actionable findings were reported. The implementation agent's final
layout measurement then caught a wide native-caption gap; content-width captions
keep stage/timer and budget/help together. The browser runner now checks the gap
numerically as well as timing, announcements and keyboard/mobile access.

Final source disposition: `e3093c23df510f79f545bb6a23cefdd3f46e1828`,
**no actionable findings**. The independent reviewer checked the final presentation
diff and diff whitespace; lifecycle, transport and budgeting were unchanged from
its verified corrections. Final implementation validation: both pytest commands
**262 passed**, 13 controlled browser groups and 7 real-backend groups passed,
including on the installed app. Lint remains at the 56 starting findings. Only
handoff/readiness documentation changes follow this reviewed runtime source.
