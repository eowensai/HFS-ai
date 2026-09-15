# HFS-ai FP4 review branch (September 14, 2026)

This repository is **eowensai/HFS-ai**, the owner's private departmental application.
EphemerAl is its separate public version. Create application PRs here unless the
owner explicitly requests the public repository. Do not confuse either with the
separate HFS Knowledge experiment.

The owner authorized porting the deployed FP4/DFlash build onto current HFS-ai main,
retaining Ollama support and this repository's departmental configuration. This
supersedes the Q6-only backend statements below for the explicit FP4 profile.
Read `docs/HFS_AI_FP4_PORT.md`, `docs/CURRENT_DEPLOYMENT.md`, and
`docs/FP4_DEPLOYMENT.md`. The original `docker-compose.yml` and recovery records
remain the shared Ollama path. The new profiles are opt-in and separate.

Preserve the departmental Streamlit host/origin settings and static assets.
Keep the running installation, model stores, Tika and HFS Knowledge unchanged
while preparing/reviewing source. Do not import EphemerAl's public roadmap.
Do not merge main or publish a release without owner authorization. Validation
is isolated; bounded historical GPU tests are not new tests of this port, and
the strict factual-grounding gate did not pass.

---

# AGENTS.md

## Project Overview
EphemerAl is a privacy-focused document chat application. It runs as a Docker Compose
stack inside WSL2 (Ubuntu) on Windows. Three containers make up the stack: a Streamlit
frontend, an Ollama LLM backend, and an Apache Tika document parsing server.

## Architecture
- **Streamlit app** (`ephemeral_app.py`): The web frontend. Connects to Ollama and Tika
  via Docker service names over an internal Docker network. Environment variables configure
  the endpoints.
- **Ollama**: Serves the LLM inside a container with GPU passthrough. API on port 11434.
- **Apache Tika Server**: Parses documents inside a container. API on port 9998.
- **Docker Compose** (`docker-compose.yml`): Defines the full stack. Containers communicate
  by Docker service name (`ollama`, `tika-server`) on a shared `llm-net` bridge network.

## Key Files
- `ephemeral_app.py` — Main application. All state is in-memory (session_state).
- `ephemeral/` — Mixed package: pure utility modules (`config`, `export`, `stream_filter`, `token_budget`) are import-safe with no Streamlit dependency, while client modules (`tika_client`, `llm_client`) are Streamlit-aware by design.
- `ephemeral/config.py` — Env parsing helpers and shared configuration constants.
- `ephemeral/export.py` — Conversation transcript/export builders (Markdown/HTML).
- `ephemeral/tika_client.py` — Tika health check and document parsing client helpers.
- `ephemeral/llm_client.py` — Ollama/OpenAI client helpers, model metadata probes, and token counting.
- `ephemeral/stream_filter.py` — Stateful think-block/thought-channel stream filter.
- `ephemeral/token_budget.py` — Token estimation helpers.
- `ephemeral/turn_options.py` — Pure one-shot composer-option state helpers.
- `docker-compose.yml` — Stack definition. Pins Ollama and Tika image versions.
- `Dockerfile` — Builds the Streamlit app container image.
- `requirements.txt` — Python dependencies (installed inside the app container).
- `requirements-dev.txt` — Development-only test/lint dependencies.
- `tests/` — Pytest suite for import-safe utility modules.
- `System Deployment Guide.md` — End-user deployment instructions (target audience: IT
  generalists, not developers). Written for WSL2 + Docker on Windows 11.
- `README.md` — Project overview, feature list, system requirements.
- `system_prompt_template.md` — LLM system prompt template. The default template is
  model-agnostic and omits `<|think|>`.
- `.streamlit/config.toml` — Streamlit theme and config. Server protections and theme are versioned together; the Dockerfile does not overwrite them.
- `theme.css` — Custom CSS loaded by the app.
- `.gitignore` — Git hygiene for local/dev artifacts (venvs, caches, editor files, secrets).
- `.dockerignore` — Docker build-context hygiene to keep non-runtime files out of images; must not exclude `.streamlit/config.toml`.
- `static/` — Logo and static assets.

## Conventions
- The deployment guide is written for non-technical IT staff. Use plain language,
  avoid jargon, explain every step, and provide copy-pasteable commands.
- The app runs inside Docker. Environment variable defaults in `ephemeral_app.py` MUST
  use Docker service names (`http://ollama:11434/v1` and `http://tika-server:9998`),
  NOT `localhost`. Using localhost as defaults will break the Docker Compose deployment.
- The only supported active LLM model is the shared local alias
  `hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072`, created from
  `hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_M`. Keep `LLM_MODEL_NAME` pinned to that
  alias; do not suggest arbitrary model retargeting as an operator workaround.
- The app uses Ollama's `/api/tags` endpoint to require the immutable production
  manifest digest and `/api/show` to verify Q6 metadata and supported capabilities.
  `details.parent_model` is construction history and is not a stable identity check.
  A generic healthy Ollama endpoint or a different installed model is not sufficient.

## Runtime and Branding Targets
- Target runtime is Python 3.14.7.
- Streamlit migration target is 1.63.0 for UI work.
- Repository/package names may remain `EphemerAl`, but user-facing UI copy should use
  **EphemerAI** unless a broader rename is explicitly requested.

## Streamlit 1.63 UI Guidance
- `st.set_page_config(initial_sidebar_state=304)` is valid in Streamlit 1.63 and should
  be used when a 304px default sidebar is needed while preserving auto behavior.
- `st.chat_message(..., width="stretch")` is valid in Streamlit 1.63; `"stretch"` is
  also the default.
- Streamlit 1.63's `max_upload_size` uses integer decimal MB in the browser.
  Round the widget allowance up to 53 MB to admit exactly 50 MiB; Python must
  enforce the actual 50 MiB limit before parsing/inference. The server's separate
  51 MiB allowance accommodates multipart framing. Keep `submit_mode="disable"`
  and the application's background-work guard together.
- Prefer `st.iframe` over `streamlit.components.v1.html`/`components.html` for the
  sidebar copy button behavior.
- Do not adopt `st.container(autoscroll=True)` unless chat history is moved into a
  fixed-height container. Avoid fixed-height chat containers unless explicitly requested.

## CSS and UI Constraints
- Preserve `theme.css` `:root` custom-property architecture.
- Preserve `st-key-{role}-` message wrapper patterns for user/assistant styling.
- No external fonts, web fonts, CDNs, or externally loaded assets; keep the app
  air-gapped friendly.
- Use a system font stack and standard font weights: 400, 500, 600, 700, 800.
- CSS targeting Streamlit internals, `data-testid`, or generated DOM is brittle; add
  comments on selectors that are new/changed for Streamlit 1.63.
- Keep **New chat** and **Copy conversation** visible in the sidebar.
- `st.menu_button` is allowed only for lower-frequency sidebar actions (Help, About,
  Settings, debug/status views).
- Do not hide the sidebar with aggressive mobile CSS; let Streamlit handle responsive
  sidebar behavior.

## Qwen3.8 Fixed Profile (Target Behavior)
- `Qwen3.8-27B` using Unsloth `UD-Q6_K_M` is the sole active target model, exposed
  through the shared local Ollama alias
  `hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072`. HFS Knowledge and EphemerAI
  use that one alias and one resident Ollama runner. Ollama 0.32.15 must receive
  `num_gpu=66`; automatic placement selected only 58/66 layers for this quant.
- Run Qwen with **medium reasoning** by default. EphemerAI request defaults are:
  - `reasoning_effort="medium"`
  - `temperature=1.0`
  - `top_p=0.95`
  - `presence_penalty=0.0`
  - timeout `1800` seconds
  - retries `0`
  - output limit `32768`
- The Thinking Mode switch uses the explicit highest OpenAI-compatible effort
  `LLM_THINKING_EFFORT=xhigh` for that turn. Native Ollama callers use
  `think: "max"`; it must not change the default for later turns or new chats.
- The Ollama alias `Modelfile` should define:
  - `FROM hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_M`
  - `REQUIRES 0.32.15`
  - `RENDERER qwen3.8`
  - `PARSER qwen3.5`
  - `PARAMETER num_ctx 131072`
  - `PARAMETER num_predict 32768`
  - `PARAMETER num_batch 128`
  - `PARAMETER num_gpu 66`
  - `PARAMETER draft_num_predict 2`
  - `PARAMETER temperature 1.0`
  - `PARAMETER top_p 0.95`
  - `PARAMETER top_k 20`
  - `PARAMETER min_p 0.0`
  - `PARAMETER presence_penalty 0.0`
  - `PARAMETER repeat_penalty 1.0`

## Context and Output Policy
- `PARAMETER num_ctx` in the alias Modelfile is the source of truth for actual Ollama
  model context.
- `LLM_CONTEXT_TOKENS` is the app's request-admission ceiling. Check it against fresh
  alias `num_ctx` and `/api/ps` running context; family maximum metadata is not runtime capacity.
- `OLLAMA_CONTEXT_LENGTH` is not the primary approach for this stack because Ollama may
  become a shared API backend.
- `PARAMETER num_ctx 131072` and `LLM_CONTEXT_TOKENS=131072` must remain aligned.
- `PARAMETER num_predict 32768` is the Ollama-side output ceiling.
- EphemerAI sends `max_tokens=32768` on both default medium-reasoning and maximum-reasoning
  turns, matching the alias-level `num_predict` ceiling.
- `LLM_OUTPUT_RESERVE_TOKENS` reserves input budget for large responses; it is not an
  output cap.

## Reasoning / Thinking Policy
- Qwen3.8 uses medium reasoning by default through explicit
  `reasoning_effort="medium"`, not prompt text.
- The Thinking Mode switch must select `LLM_THINKING_EFFORT=xhigh` only for the current
  turn. Do not send the native-only `max` value through the OpenAI-compatible route.
- Do not add `/nothink`, `<think>`, or "think step by step" to the system prompt.
- EphemerAI must always discard streamed reasoning deltas. Keep
  `LLM_SHOW_REASONING=false`; it must not expose chain-of-thought.
- Keep think-block stripping as defense-in-depth.

## Shared API Backend Policy
- Raw Ollama should remain internal by default.
- Optional API exposure should happen via a separate `docker-compose.api.yml`
  override.
- Keep `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_NUM_PARALLEL=1` unless capacity testing
  proves otherwise.
- Shared API users should call only model
  `hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072`.
- External OpenAI-compatible clients should send:
  - `reasoning_effort="medium"`
  - `temperature=1.0`
  - `top_p=0.95`
  - `presence_penalty=0.0`
  - `max_tokens=32768`

## Review Guidelines
When reviewing Codex changes, treat the following as high-priority checks:
- privacy regressions
- accidental logging of prompts, uploaded documents, or model output
- Docker networking exposure changes
- loss of medium-reasoning-by-default behavior or the per-turn maximum-reasoning switch
- incorrect context/output budgeting
- broken copy-paste commands in deployment docs
- changes that regress Streamlit 1.63 UI migration compatibility

## Testing
- Verify Python syntax: `python -m py_compile ephemeral_app.py ephemeral/*.py`
- Verify requirements install: `pip install -r requirements.txt && pip check`
- Verify test tooling + run tests: `pip install -r requirements-dev.txt && python -m pytest`
- Verify linting: `ruff check .`
- Verify Markdown links resolve: all relative links in README.md and the deployment
  guide should point to files that exist in the repo.
- On a host with the shared HFS backend, rebuild/recreate only EphemerAI with
  `docker compose up -d --build --no-deps --force-recreate ephemeral-app`, then access
  `http://localhost:8501`. Do not use a full-stack recreation as an app test.
- Keep pure utility modules import-safe (`config`, `export`, `stream_filter`,
  `token_budget`): no Streamlit imports or Streamlit side effects at import time, so
  tests run without Streamlit.
- `ephemeral/tika_client.py` and `ephemeral/llm_client.py` are Streamlit-aware by
  design and may use Streamlit caching decorators/session state.
- Manual UI validation checklist:
  - empty welcome state
  - text-only chat
  - file-upload chat
  - long assistant response rendering/streaming
  - mobile viewport behavior
  - backend-unavailable state, but only during an approved backend maintenance window

## Do Not
- Do not change environment variable defaults in `ephemeral_app.py` to use `localhost`.
  The defaults MUST remain Docker service names for container-to-container communication.
- Do not pull, delete, or recreate models or restart/reconfigure shared Ollama or Tika
  merely to deploy or test EphemerAI.
- Do not remove Docker, WSL2, or Linux content from the deployment guide or README.
  That is the supported deployment path.
- Do not modify `system_prompt_template.md` unless changing the LLM's system behavior.
- Do not add new Python dependencies beyond what's in `requirements.txt` without
  documenting the reason.
- Do not remove think-block/thought-channel filtering from `ephemeral/stream_filter.py` or from the streaming response path in `ephemeral_app.py`; it is required as defense-in-depth against leaked reasoning output.
- Do not persist prompts, uploaded files, parsed document text, or model output to disk.
- Do not log chat content, uploaded document content, or model output.

## Repository expectations

- This is a Streamlit 1.63 app.
- The package layout is flat. The `ephemeral/` package lives at the repository root.
- Pytest import resolution is configured in `pyproject.toml` with `pythonpath = ["."]`.
- Do not change `st.set_page_config(initial_sidebar_state=304)`. The integer is intentional Streamlit 1.63 behavior: auto sidebar behavior with a 304px initial sidebar width.
- Do not replace that value with `"auto"` unless the user explicitly asks for a sidebar UX change.
- Do not add production dependencies without explicit user approval.
- Prefer small, focused PRs.

## Required validation after Python changes

Run from the repository root:

1. `python -m pytest -q`
2. `pytest -q`
3. `python -m py_compile ephemeral_app.py ephemeral/*.py`
4. `ruff check .`

You may also run:

- `bash scripts/validate.sh`

## Browser/UI testing

- UI smoke testing requires the Python Playwright package **and** a Chromium browser installed in the environment.
- Playwright is a dev/test dependency only (in `requirements-dev.txt`), not a production dependency.
- Generated screenshots under `artifacts/ui-smoke/` are test artifacts and should not be committed.
- Browser smoke tests are useful for Streamlit UI and clipboard iframe behavior.
- For UI, Streamlit, `theme.css`, or clipboard changes, run:
  - `python scripts/ui_smoke.py`
  - or `bash scripts/validate_ui.sh`
- If UI smoke succeeds, report screenshot paths:
  - `artifacts/ui-smoke/home-desktop.png`
  - `artifacts/ui-smoke/home-mobile.png`
- Do not add Playwright, Selenium, Chrome, Chromium, WebKit, or browser binaries unless the user explicitly asks for browser automation in that PR.
- If browser automation/testing is unavailable in the Codex container, report that clearly as a manual smoke-test item instead of silently skipping validation or adding dependencies.


## Source publication and installation

- This repository is `eowensai/HFS-ai`. Do not rewrite the live checkout's remote
  or restart production services merely to publish a source update.
- Distribute source, configuration, tests, static assets and installation instructions.
  Download/build model weights, containers and Tika jars during installation;
  do not package image/model backups or HFS application data with the source ZIP.
- `deployment/runtime-lock.json` is a dated reference. Fresh Tika builds receive
  their own validated digest in the install's ignored `.env` as `TIKA_IMAGE`.
  Preserve the exact model identity/profile and application fail-closed check.
- Keep the model download and alias-creation recipe reproducible; test it in an
  isolated metadata-only environment without changing the production model store.
- Capture the homepage from an empty isolated browser session. Publish only the
  root `Ephemeral Screenshot.jpg`; disposable browser artifacts remain ignored.
