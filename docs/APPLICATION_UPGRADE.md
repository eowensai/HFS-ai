# Combined application upgrade — September 11, 2026

The application upgrade preserves the deployed `tika4-20260911` release, including
its unpublished Tika 4 client, privacy and reliability fixes. Python and library
changes passed an independent checkpoint before the Streamlit integration changes.
The final production image passed integrated browser acceptance against the existing
Tika 4.0.0 and Ollama 0.32.15 services. No model, prompt, authentication, stored-data,
backend or host migration is included.

## Versions and dependency reproducibility

| Component | Previous | This release |
|---|---|---|
| Python | 3.11.16 | 3.14.7, standard interpreter |
| Streamlit | 1.56.0 | 1.63.0 |
| Requests | 2.32.5 | 2.34.2 |
| pytz | 2025.2 | 2026.3.post1 |
| Pillow | 12.3.0 | Retained |
| OpenAI SDK | 1.97.2 | Retained |
| HTTPX / urllib3 | 0.28.1 / 2.7.0, indirect | Same versions, explicit direct dependencies |
| streamlit-browser-engine | 0.0.3, inactive import | Removed |

The Dockerfile pins `python:3.14.7-slim-trixie` to verified index digest
`sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6`.
`requirements.lock` pins all 48 runtime dependencies, including Streamlit's new
Starlette/Uvicorn/multipart server dependencies and the compatible compiled wheels.
The image installs under these constraints and runs `pip check` during the build.
The actual image, rollback image and runtime are recorded in
[runtime-lock.json](../deployment/runtime-lock.json); [app-packages.json](../deployment/app-packages.json)
records all installed Python packages, build tools and Debian packages. OS package
updates during a future rebuild can produce a different image; retain the accepted
image ID as the deployment/rollback checkpoint rather than assuming bit-for-bit rebuilds.

Tests use pytest 9.1.1, pytest-cov 7.1.0, pytest-timeout 2.4.0, Ruff 0.16.7 and
Playwright 1.62.0. Tokenizers 0.22.1 and regex 2025.7.34 are separate test-only
oracles. None of these tools or Chromium is installed in the production image.
Use Python 3.14.7 and install `-r requirements.txt -c requirements.lock
-r requirements-dev.txt`; install `requirements-oracles.txt` only for parity checks.

## Application changes

- Public `st.bottom` replaces private `st._bottom`. CSS uses the observed 1.63 DOM,
  preserves the 304-pixel sidebar and responsive composer, and leaves conversations
  in the natural page scroll. Header/toolbar hiding is narrowed because the native
  sidebar opener now lives inside it; collapsed desktop/mobile sidebars can be
  reopened. New Chat and Copy retain their existing behavior.
- `submit_mode="disable"` immediately disables a submitted composer. The existing
  background-worker guard still prevents duplicate work; native Stop is deferred
  because it does not cancel this application's inference worker by itself.
- Native pasted files/images and OS drag/drop use the existing attachment pipeline.
  No second upload processor or additional client package was introduced.
- Streamlit's default server is used without an ASGI rewrite. CORS/XSRF remain on;
  WebSocket `allowedHosts` is limited to localhost, 127.0.0.1 and 172.16.64.243.
  This option protects WebSocket admission, not static HTTP requests or authentication.
- Server upload transport permits 51 MiB for multipart overhead. Streamlit 1.63's
  browser widget uses integer **decimal MB**, so its allowance is rounded up to
  53 MB to accept exactly 50 MiB. Python still rejects files over **52,428,800 bytes**
  before parsing/inference, and retains eight-file and 64 MiB aggregate limits.
  The UI states the actual limits; oversized attachments receive the existing
  failure status. An explicit text prompt can still be answered without its rejected
  attachment. Rejected file-only submissions do not invoke inference.
- Mermaid-bearing messages, including incomplete and entity-encoded streamed fences,
  use literal text rendering. This conservative guard prevents native diagram/media
  interpretation; ordinary Markdown/code still uses the safe existing renderer.
  Attachment labels cannot open diagram fences. Original message/Copy/export content
  remains unchanged. No diagram rendering or unrelated visual features were added.
- Payload cleanup detaches ownership first and continues closing other resources if
  one cleanup operation fails, without logging payloads or exception contents.
  Python remote debugging is disabled with `PYTHON_DISABLE_REMOTE_DEBUG=1`; the
  existing no-dump library, core limits, tmpfs mounts and no-swap controls remain.
- Python's Unicode 16 changes were checked against the pinned backend. Tested new
  Unicode 15/16 letters, marks and digits matched; no tokenizer change was necessary.
  Existing conservative byte bounds remain for unsupported/special-token paths.

## Acceptance evidence

Tests used fictional inputs and the unchanged production model. Conversation content,
traces, cookies and document payloads were not saved as artifacts. Native drag fixtures
and parser temporary buffers used the isolated containers' RAM-backed `/tmp` mounts.
Only empty homepage screenshots and pass/fail metadata were retained.

| Check | Result |
|---|---|
| Python-only checkpoint, Streamlit 1.56 retained | 365 tests passed through each pytest entry point; Ruff, compilation and dependency consistency passed |
| Final application unit/regression suite | **371 passed** through each required entry point; Ruff, compilation and `pip check` passed |
| Independent tokenizer oracles | **1,005 cases passed** under Python 3.14 |
| Real pinned-backend tokenizer comparison | **10 cases passed**, including new Unicode characters; exact/over-limit local context checks passed |
| Failure/reliability browser suite | All **13 groups passed**: duplicate submit, cancellation/New Chat, backend errors/timeouts, parser failures, limits and metadata mismatch |
| Media browser suite | **72 guarded cases**, user/stream/final/Copy/mobile checks passed; no external media requests, positive control detected the canary |
| Clean production-image browser acceptance | All **8 groups passed**: TXT/Tika/model, Copy, large document/full follow-up, supported image, scanned PDF OCR, unreadable file/follow-up, one-turn Thinking, isolated sessions |
| Representative parser inputs | Ten fictional DOCX/PDF/XLSX/PNG/JPEG/PPTX files returned nonempty, nonpartial extraction |
| Native upload and server transition | 50 MiB minus one / exact uploads passed; one-byte-over rejected before parser/model; rounded widget limit and 51 MiB transport rejection passed; missing XSRF and invalid WebSocket Host rejected |
| Paste/drop and lifecycle | File paste, PNG paste and native Chromium file drop passed through processing; real WebSocket disconnect released buffers/messages and rejected late state |
| Desktop/mobile | Existing smoke suite passed at 1440×900 and 390×844; sidebar collapse/reopen and New Chat access checked; empty homepage screenshots inspected |

Run the additional isolated acceptance with
`TOKENIZER_TEST_METADATA=/path/to/public-tokenizer-metadata.json python scripts/verify_upgrade.py`.
It requires the test dependencies, Chromium, and a validation container with `/tmp`
mounted as tmpfs. It starts fake services on loopback ports 18505/18506; it does not
send its boundary probes to production. The real integration runner is
`scripts/reliability_browser.py`; failure and media runners are
`scripts/reliability_failures.py` and `scripts/verify_chat_media.py`.
Use their documented environment variables and retain the real backend's fixed profile.

These are automated acceptance results, not a claim that a human has completed a
spot test, a fresh Windows install, GPU cold start, or a remote peer/router test.

## Application-only rollout and rollback

The canonical installation is `/home/eko/ephemeral-llm/docker-compose.yml`.
The tested source snapshot is `releases/python314-streamlit163-20260911` and the
candidate tag is `ephemerai:python314-streamlit163-20260911`. Preserve the previous
Compose file and `releases/tika4-20260911`, and retain old app image
`sha256:98a5ed85eca15665b0be99d6c4f082bfb08ace063b243c7c36e8854e02809a54`
under `ephemerai:pre-python314-streamlit163`.

After active requests finish, change only the app image/build/static-source paths,
validate the resolved Compose configuration, and run from the canonical directory:

```bash
docker compose up -d --no-deps --no-build --pull never --force-recreate ephemeral-app
```

Verify health, runtime/package identities, no-dump/no-swap/tmpfs controls and a
fictional chat/document follow-up. Confirm Ollama/Tika image IDs and start times
are unchanged and the fixed model is still resident with the accepted profile.
An app recreation clears its in-memory sessions.

To roll back this release, restore the three app image/build/static paths from the
saved Compose checkpoint (or restore that checkpoint only if no later unrelated
changes exist), validate `docker compose config -q`, and repeat the same app-only
recreation command. Use the retained image without rebuilding. Do not run the
older paired Tika 3 rollback for a Python/Streamlit problem. No backend recreation,
model modification, broad pruning or volume removal is part of either operation.

## Separate maintenance decisions

| Component | Decision after this release |
|---|---|
| OpenAI SDK 3.13.0 | Separate port of bounded transport and streaming protections to its `httpx2` stack; retain 1.97.2 here |
| Ollama 0.34.0 | Separate tokenizer/renderer, cancellation, quality and GPU evaluation; retain exact 0.32.15 |
| Tika 4.0.0 | Retain the recently validated image and Java/OCR components; complete automated integrated acceptance with this application |
| containerd 2.3.5, Compose 5.5.1, NVIDIA toolkit 1.20.0 | Group in a separate host maintenance round with companion packages, two-GPU checks and an independent rollback checkpoint |
| Docker Engine/CLI 29.8.0, runc 1.5.1 | Retain |
| Buildx 0.37.1, WSL 2.7.14 | Defer the just-released versions; no requirement for this application release |
| NVIDIA Windows driver 616.92 | Evaluate separately with WSL/GPU maintenance; retain 610.88 here |

Model weights, quantization, context/output limits, GPU allocation and the host OS
release are unchanged. The next host round must test this accepted application on
the changed host; it is not included in the app-only release.

Framework references: [2026 release notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2026),
[bottom container](https://docs.streamlit.io/develop/api-reference/layout/st.bottom),
[chat input](https://docs.streamlit.io/develop/api-reference/chat/st.chat_input),
[Python 3.14 changes](https://docs.python.org/3.14/whatsnew/3.14.html),
[Requests changes](https://requests.readthedocs.io/en/latest/community/updates/).
