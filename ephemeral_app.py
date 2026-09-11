import base64
import inspect
import os
import pathlib
import string
import uuid
from contextlib import contextmanager
from datetime import datetime, tzinfo
from html import escape as html_escape
from typing import Union

import pytz
import streamlit as st

from ephemeral import config as cfg
from ephemeral.chat_display import image_preview_bytes, label_html, render_chat_text
from ephemeral.clipboard import render_copy_button, render_turn_copy_button
from ephemeral.config import (
    APP_VERSION,
    DEBUG_MODE,
    LLM_BASE_URL,
    LLM_CONTEXT_TOKENS,
    LLM_MODEL_NAME,
    LLM_PRESENCE_PENALTY,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    max_tokens_for_turn,
    reasoning_effort_for_turn,
)
from ephemeral.export import (
    build_conversation_html,
    build_conversation_markdown,
    build_message_html,
    build_message_markdown,
)
from ephemeral.llm_client import (
    build_chat_completion_request,
    get_llm_client,
    get_model_ctx,
    llm_alive,
    measure_model_request,
    model_supports_images,
)
from ephemeral.request_lifecycle import (
    TurnWork,
    WorkGate,
    record_rejected_uploads,
    run_turn,
)
from ephemeral.session_lifecycle import (
    detach_framework_uploads,
    prepare_conversation,
    reset_conversation,
)
from ephemeral.tika_client import parse_with_tika, tika_alive
from ephemeral.turn_options import (
    THINKING_MODE_KEY,
    capture_thinking_mode_for_submission,
    consume_submitted_thinking_mode,
)

# EphemerAl main Streamlit application.
# - Provides an ephemeral chat UI for working with uploaded documents and images.
# - Talks to an LLM backend and an Apache Tika server over HTTP endpoints configured via environment variables.
# - Uses Streamlit's in-memory session_state only, this script does not write chat content or uploads to disk.

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="EphemerAI",
    layout="wide",
    initial_sidebar_state=304,
    menu_items={
        "Get help": None,
        "Report a Bug": None,
        "About": "EphemerAI is a privacy-focused document chat assistant.",
    },
)

def load_css(path: str = "theme.css") -> None:
    """Load optional CSS overrides to customize Streamlit's default look."""
    css_path = pathlib.Path(path)
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


load_css()

# ── Backend configuration ─────────────────────────────────────────
DEFAULT_UPLOAD_PROMPT = os.getenv("DEFAULT_UPLOAD_PROMPT", "Please analyze the uploaded files.")


def get_local_timezone() -> tzinfo:
    """
    Resolve the timezone used for UI timestamps and the system prompt.
    Priority:
      1. EPHEMERAL_TIMEZONE env var if valid.
      2. The system's local timezone.
    """
    env_tz = os.getenv("EPHEMERAL_TIMEZONE")
    if env_tz:
        try:
            return pytz.timezone(env_tz)
        except Exception:
            if DEBUG_MODE:
                try:
                    st.warning(
                        f"EPHEMERAL_TIMEZONE={env_tz!r} is not a valid timezone, falling back to system time."
                    )
                except Exception:
                    pass

    sys_tz = datetime.now().astimezone().tzinfo
    return sys_tz or pytz.UTC


TIMEZONE = get_local_timezone()


def timestamp_local() -> str:
    """Return a human-readable local timestamp string."""
    now = datetime.now(TIMEZONE)
    fmt = "%-I:%M %p on %A, %B %-d, %Y"
    if os.name == "nt":
        fmt = fmt.replace("%-I", "%#I").replace("%-d", "%#d")
    return now.strftime(fmt)


tmpl_path = pathlib.Path(__file__).parent / "system_prompt_template.md"
if tmpl_path.exists():
    # Default system template is model-agnostic and omits <|think|>.
    # Ordinary requests use medium reasoning; Thinking Mode selects maximum reasoning
    # for one submitted turn. Keep think-block filtering as defense-in-depth.
    SYSTEM_TMPL = string.Template(tmpl_path.read_text(encoding="utf-8"))
else:
    SYSTEM_TMPL = string.Template(
        "You are a helpful AI assistant. The current local time is ${current_time_local}. "
        "Answer concisely and accurately based on the context provided."
    )


@st.cache_data(show_spinner=False)
def _load_logo_b64(path: str = "static/ephemeral_logo.png") -> str:
    """Read and base64-encode the logo once, cached across reruns."""
    logo_path = pathlib.Path(path)
    if logo_path.exists():
        return base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return ""


# ── Chat message wrapper for CSS styling ──────────────────────────
@contextmanager
def styled_chat_message(role: str, message_id: str = None):
    """Yield a chat_message wrapped in keyed containers for stable role CSS hooks."""
    normalized_role = "user" if role == "user" else "assistant"
    key = f"{normalized_role}-{message_id}" if message_id else f"{normalized_role}-{uuid.uuid4()}"
    chat_kwargs = {
        "avatar": ":material/account_circle:" if normalized_role == "user" else ":material/assistant:",
    }
    if "width" in inspect.signature(st.chat_message).parameters:
        # Keep the chat row as stretch-width for both roles.
        # User bubble sizing/alignment is handled by CSS. Using "content" for the
        # user row can trigger transient min-content collapse during first-turn
        # reruns while the assistant spinner is mounted.
        chat_kwargs["width"] = "stretch"

    with st.container(key=key):
        if normalized_role == "user":
            if "horizontal_alignment" in inspect.signature(st.container).parameters:
                with st.container(horizontal_alignment="right"):
                    with st.chat_message(normalized_role, **chat_kwargs):
                        yield
            else:
                with st.chat_message(normalized_role, **chat_kwargs):
                    yield
        else:
            with st.chat_message(normalized_role, **chat_kwargs):
                yield


def main():
    # ── Session state ─────────────────────────────────────────────────
    payloads = prepare_conversation()
    gate = st.session_state.setdefault("_work_gate", WorkGate())
    work = gate.active if gate.active and gate.active.owner is payloads else None
    busy = gate.running

    st.session_state.setdefault("show_welcome", True)
    st.session_state.setdefault("last_token_count", 0)
    st.session_state.setdefault("tokenizer_available", None)
    st.session_state.setdefault("_vision_supported", None)
    st.session_state.setdefault(THINKING_MODE_KEY, False)


    def _capture_turn_options() -> None:
        """Capture one-shot composer options before Streamlit reruns on submission."""
        capture_thinking_mode_for_submission(st.session_state)


    def reset_chat_session() -> None:
        """Reset conversation-scoped state while preserving app/runtime settings."""
        reset_conversation()

    # ── Sidebar ───────────────────────────────────────────────────────
    with st.sidebar:
        logo_b64 = _load_logo_b64()
        if logo_b64:
            st.markdown(
                f"""
                <div class="sidebar-brand">
                    <img src="data:image/png;base64,{logo_b64}" alt="EphemerAI logo" class="sidebar-brand-logo">
                    <div class="sidebar-brand-title">EphemerAI</div>
                    <div class="sidebar-brand-subtitle">Private AI Assistant</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="sidebar-brand">
                    <div class="sidebar-brand-fallback">E</div>
                    <div class="sidebar-brand-title">EphemerAI</div>
                    <div class="sidebar-brand-subtitle">Private AI Assistant</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Friendly status messages for non-technical users.
        if not llm_alive():
            st.error("The AI service is not available right now. Please try again in a moment.")
        if not tika_alive():
            st.info("Document reading is temporarily unavailable. You can still chat, but uploads may not be readable.")

        st.button("New Chat", key="sidebar_new", width="stretch", on_click=reset_chat_session)

        if st.session_state.messages:
            export_md = build_conversation_markdown(st.session_state.messages)
            export_html = build_conversation_html(st.session_state.messages)
            render_copy_button(export_md, export_html)

        st.caption(f"Uploads: {cfg.MAX_UPLOAD_COUNT} files, "
                   f"{min(50, cfg.MAX_UPLOAD_BYTES / (1024 * 1024)):g} MiB per file, "
                   f"{cfg.MAX_UPLOAD_TOTAL_BYTES / (1024 * 1024):g} MiB total. "
                   "Limits are checked on submission.")

        if DEBUG_MODE:
            with st.expander("System status", expanded=False):
                dbg_thinking_mode = bool(st.session_state.get(THINKING_MODE_KEY, False))
                dbg_effective_reasoning_effort = reasoning_effort_for_turn(dbg_thinking_mode)
                dbg_effective_max_tokens = max_tokens_for_turn(dbg_thinking_mode)
                st.caption(f"App version: {APP_VERSION}")
                st.caption(f"Model: {LLM_MODEL_NAME}")
                st.caption(f"LLM base URL: {LLM_BASE_URL}")
                st.caption(f"Configured context ceiling: {LLM_CONTEXT_TOKENS:,}; verified before each request.")
                st.caption(
                    "Request settings: "
                    f"temperature={LLM_TEMPERATURE}, top_p={LLM_TOP_P}, "
                    f"presence_penalty={LLM_PRESENCE_PENALTY}, "
                    f"reasoning_effort={dbg_effective_reasoning_effort!r}"
                )
                st.caption(
                    "LLM_MAX_TOKENS: "
                    + (str(dbg_effective_max_tokens) if dbg_effective_max_tokens is not None else "not set (max_tokens omitted)")
                )

                st.caption("Token counting: conservative complete-request estimate (UTF-8 bytes + template/image allowances).")

    # ── Chat input ───────────────────────────────────────────────────
    prompt_in = st.chat_input(
        "Ask a question or attach files...",
        accept_file="multiple",
        height=68,
        # Streamlit 1.63's browser checks decimal MB, but the app's reviewed
        # limit is in bytes (50 MiB). Round the browser allowance up; Python
        # rejects anything above the exact byte limit before parsing/inference.
        max_upload_size=max(1, (min(50 * 1024 * 1024, cfg.MAX_UPLOAD_BYTES) + 999_999) // 1_000_000),
        disabled=busy,
        submit_mode="disable",
        key="main_chat",
        on_submit=_capture_turn_options,
    )

    turn_thinking_mode = (
        consume_submitted_thinking_mode(st.session_state) if prompt_in is not None else False
    )

    # Streamlit's public bottom dock also contains st.chat_input. Keeping the toggle here avoids
    # viewport-fixed overlays that can interfere with chat streaming layout.
    with st.bottom:
        with st.container(key="composer_toggle_row"):
            st.toggle(
                "Thinking Mode",
                value=False,
                help=(
                    "Ordinary requests use medium reasoning. Turn this on for maximum "
                    "reasoning on this submitted turn; it may be much slower. "
                    "The switch turns off automatically afterward."
                ),
                key=THINKING_MODE_KEY,
                disabled=busy,
            )

    # Hide the welcome shell in the same run as the first submitted prompt so
    # initial-turn layout and composer spacing remain stable.
    if prompt_in is not None and st.session_state.show_welcome:
        st.session_state.show_welcome = False


    # ── Welcome banner ────────────────────────────────────────────────
    if st.session_state.show_welcome:
        st.markdown(
            """
            <section class="welcome-shell" aria-label="Welcome">
              <h1 class="welcome-heading">Welcome to <span class="welcome-heading-brand">EphemerAI</span></h1>
              <p class="welcome-subtitle">Your private workspace for focused, ephemeral conversations.</p>

              <div class="welcome-card">
                <div class="welcome-features" role="list">
                  <div class="welcome-feature" role="listitem">
                    <div class="feature-badge feature-badge-blue">+</div>
                    <div class="feature-copy">
                      <div class="feature-copy-strong">Attach files, not just prompts</div>
                      <div class="feature-copy-muted">Images, PDFs, Office files, spreadsheets, text, and more.</div>
                    </div>
                  </div>
                  <div class="welcome-feature" role="listitem">
                    <div class="feature-badge feature-badge-indigo">↺</div>
                    <div class="feature-copy">
                      <div class="feature-copy-strong">Local and session-only</div>
                      <div class="feature-copy-muted">No account or saved chat history in this app. New Chat clears messages and uploads.</div>
                    </div>
                  </div>
                  <div class="welcome-feature" role="listitem">
                    <div class="feature-badge feature-badge-amber">!</div>
                    <div class="feature-copy">
                      <div class="feature-copy-strong">Verify important answers</div>
                      <div class="feature-copy-muted">This local model has no live web access and may be wrong, especially on current facts.</div>
                    </div>
                  </div>
                </div>
              </div>

            </section>
            """,
            unsafe_allow_html=True,
        )


    # ── Helper: render chat content ───────────────────────────────────
    def render_content(content: Union[str, list]) -> None:
        """
        Render either plain markdown or structured content (text + images).
        Synthetic context blocks (marked with _synthetic flag) are hidden from display.
        """
        def _format_file_size(num_bytes: int) -> str:
            if num_bytes <= 0:
                return ""
            units = ["B", "KB", "MB", "GB"]
            size = float(num_bytes)
            unit_idx = 0
            while size >= 1024 and unit_idx < len(units) - 1:
                size /= 1024.0
                unit_idx += 1
            if unit_idx == 0:
                return f"{int(size)} {units[unit_idx]}"
            return f"{size:.1f} {units[unit_idx]}"

        def _render_attachment_badge(meta: dict) -> None:
            filename = label_html(meta.get("name", "Attachment"))
            size_label = _format_file_size(int(meta.get("size", 0) or 0))
            kind = meta.get("kind", "document")
            icon = "🖼️" if kind == "image" else "📄"
            subtitle = f"{kind.title()} upload"
            if meta.get("id"):
                filename += f" [{meta['id'][:8]}]"
                subtitle += f" • {meta['status']} • {meta['reason']}"
            if size_label:
                subtitle = f"{subtitle} • {size_label}"
            st.markdown(
                (
                    '<div class="attachment-card" role="group" aria-label="Uploaded file">'
                    f'<div class="attachment-icon">{icon}</div>'
                    '<div class="attachment-copy">'
                    f'<div class="attachment-name">{filename}</div>'
                    f'<div class="attachment-meta">{label_html(subtitle)}</div>'
                    "</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

        if isinstance(content, list):
            for part in content:
                ptype = part.get("type")
                if ptype == "text":
                    if not part.get("_synthetic"):
                        attachment = part.get("_attachment")
                        if attachment:
                            _render_attachment_badge(attachment)
                        else:
                            render_chat_text(part.get("text", ""), st)
                elif ptype in ("image", "image_url"):
                    try:
                        st.image(image_preview_bytes(part), width=180)
                    except Exception:
                        st.error("I couldn't display one of the images in the chat UI.")
        else:
            render_chat_text(content or "", st)


    def render_message(m):
        with styled_chat_message(m["role"], m.get("id")):
            render_content(m["content"])
            turn_copy_md = build_message_markdown(m)
            turn_copy_html = build_message_html(m)
            turn_copy_id = m.get("id") or str(uuid.uuid4())
            render_turn_copy_button(turn_copy_md, turn_copy_html, turn_copy_id)

    # Keep existing history outside the polling fragment. Newly accepted messages
    # are rendered inside it until the next full rerun incorporates them here.
    with payloads._lock:
        history = list(st.session_state.messages)
    rendered_ids = {m.get("id") for m in history}
    for m in history:
        render_message(m)


    def execute(current):
        run_turn(current, parse=parse_with_tika, model_ready=llm_alive,
                 vision_ready=model_supports_images, context=get_model_ctx,
                 request_builder=build_chat_completion_request, client=get_llm_client,
                 measure=measure_model_request)

    def start_work(text, files, thinking, retry_message=None):
        if gate.running:
            record_rejected_uploads(st.session_state.messages, files,
                                    "Unavailable: a request is already active; this submission was not sent.")
            for upload in files:
                upload.close()
            return
        previous = gate.active
        current = TurnWork(payloads, st.session_state.messages, text, files, thinking,
                           SYSTEM_TMPL.safe_substitute(current_time_local=timestamp_local()),
                           DEFAULT_UPLOAD_PROMPT)
        current.user_message = retry_message
        current.require_display_ack = True
        if not gate.start(current, execute):
            record_rejected_uploads(st.session_state.messages, files,
                                    "Unavailable: app request limit reached; this submission was not sent.")
            current.clear()
            payloads.disown(current)
            st.error("The app is busy with its bounded number of active requests. Try submitting again shortly.")
            return
        if previous:
            previous.owner.disown(previous)
            previous.clear()
        st.rerun()

    if prompt_in is not None:
        user_text = prompt_in.text if hasattr(prompt_in, "text") else prompt_in
        user_text = (user_text or "").strip()
        files = list(prompt_in.files) if hasattr(prompt_in, "files") else []
        detach_framework_uploads(files)
        if user_text or files:
            start_work(user_text, files, turn_thinking_mode)

    if busy and work is None:
        st.caption("The previous request is still closing locally. New Chat cleared its conversation. "
                "Stopping this UI does not confirm that backend work has stopped.")

    @st.fragment(run_every=0.5 if busy else None)
    def show_request():
        current = gate.active
        snapshot = current.snapshot() if current and current.owner is payloads else None
        if current is None or current.owner is not payloads:
            if busy and not gate.running:
                st.rerun()
            return
        stage, partial, error, notice, done = (
            snapshot.stage, snapshot.partial, snapshot.error, snapshot.notice, snapshot.done)
        latest = snapshot.messages
        for message in latest:
            if message.get("id") not in rendered_ids:
                render_message(message)
        # Show the submitted text even while attachments are still being read.
        # This preview does not add unvalidated content to model history.
        pending = snapshot.pending
        if (not done and pending and pending.get("content")
                and not any(m.get("id") == pending["id"] for m in latest)):
            with styled_chat_message("user", pending["id"]):
                render_content(pending["content"])
        if snapshot.expired and not done:
            st.warning("The request deadline has expired; waiting for the connection to close. "
                       "No incomplete reply will enter conversation history.")
        elif not done and stage and not partial.strip():
            # Only the stage is a polite live region. Timer ticks are visual,
            # excluded from the accessibility tree, and never steal focus.
            with st.container(horizontal=True, gap="small"):
                st.caption(f'<span role="status" aria-live="polite" aria-atomic="true">{html_escape(stage)}</span>',
                           unsafe_allow_html=True, width="content")
                st.caption(f'<span aria-hidden="true"> · {snapshot.elapsed}s</span>',
                           unsafe_allow_html=True, width="content")
            if stage == "Waiting for the AI…":
                st.caption("Large documents or other requests can add to the wait.")
        if not done and snapshot.waiting_for_display:
            # The user turn and its attachment badges above precede model dispatch.
            current.acknowledge_display()
        if partial.strip():
            with styled_chat_message("assistant", current.id + "-partial"):
                if error:
                    st.caption("Incomplete reply — excluded from conversation history")
                render_chat_text(partial, st)
        if error:
            st.error(error)
        if notice and DEBUG_MODE:
            st.caption(notice)
        if done and not busy and error and snapshot.retryable:
            st.caption("Retry sends the same user turn once. Backend work from an interrupted connection may still be finishing.")
            if st.button("Retry response", key="retry_response"):
                retry = snapshot.pending
                thinking = current.thinking
                start_work("", [], thinking, retry)
        if done and busy:
            st.rerun()
    show_request()


main()
