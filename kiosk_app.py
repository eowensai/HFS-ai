# ══════════════════════════════════════════════════════════════════
# File:         kiosk_app.py
# Project:      HFS-ai Assistant
# Version:      14.0 (Updated to use Streamlit 1.46.0 chat_input with accept_file)
# Last updated: 2025-06-22
# ══════════════════════════════════════════════════════════════════

# ── Imports ───────────────────────────────────────────────────────
import os
import base64
import pathlib
from datetime import datetime
import string # For safe string formatting of the system prompt
import streamlit as st
import requests
import pytz
import tika
from tika import parser
from tika.tika import TikaException
from openai import OpenAI

# ── Page / theme ──────────────────────────────────────────────────
st.set_page_config(page_title="HFS-ai", layout="wide",
                   initial_sidebar_state="expanded")

def load_css(path="theme.css"):
    css_path = pathlib.Path(path)
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    else:
        st.error(f"❌ CSS file missing: {path}")
load_css()

# ── Constants ────────────────────────────────────────────────────
LLM_BASE_URL      = os.getenv("LLM_BASE_URL", "http://192.168.87.64:11434/v1")
MODEL_NAME        = os.getenv("LLM_MODEL_NAME", "local-model")
TIKA_URL          = os.getenv("TIKA_URL", "http://tika-server:9998")
TIMEZONE          = pytz.timezone("America/Los_Angeles")

TEMPERATURE, TOP_K, TOP_P = 1.0, 64, 0.95
MIN_P, XTC_THRESHOLD, REPEAT_PENALTY = 0.0, 1.0, 1.0

SYSTEM_PROMPT_FILE_PATH = pathlib.Path(__file__).parent / "system_prompt_template.md"

# ── Global TIKA Status (as per v13.3 style) ──────────────────────
TIKA_OK = False

# ── Function to load system prompt template safely ───────────────
def load_system_prompt_template(file_path: pathlib.Path) -> string.Template:
    """Loads the system prompt from a file and returns it as a string.Template object."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return string.Template(f.read())
    except FileNotFoundError:
        st.error(f"❌ System prompt template file not found: {file_path}. Using a basic fallback.")
    except Exception as e:
        st.error(f"❌ Error loading system prompt template: {e}. Using a basic fallback.")
    return string.Template( # Fallback prompt if loading fails
        "You are HFS-ai, a helpful, neutral assistant.\n"
        "- Current Pacific Time: ${current_time_pacific}.\n"
        "- Use only provided context; do not fabricate details."
    )

FULL_SYSTEM_PROMPT_TEMPLATE = load_system_prompt_template(SYSTEM_PROMPT_FILE_PATH)

# ── External services (Tika initialization reverted to v13.3 style) ─────
os.environ["TIKA_CLIENT_ONLY"] = "true" # As in v13.3
try:
    tika.initVM();  TIKA_OK = True # As in v13.3
except TikaException: # As in v13.3
    TIKA_OK = False   # As in v13.3

# ── Session defaults ─────────────────────────────────────────────
# Ensures essential session state keys are initialized.
DEFAULT_SESSION_STATE = {
    "messages":      [],
    "pending_files": [],
    "show_uploader": False,
    "uploader_key":  0,
}
for k, v in DEFAULT_SESSION_STATE.items():
    st.session_state.setdefault(k, v)

# ── Helper functions ─────────────────────────────────────────────
def backend_up() -> bool: # Reverted to v13.3 logic
    base = LLM_BASE_URL.split("/v1")[0]
    for ep in ("", "/api/tags", "/v1/models"): # Exact endpoints from v13.3
        try:
            if requests.get(base + ep, timeout=2).ok:
                return True
        except requests.RequestException:
            pass
    return False

def human_timestamp(tz) -> str:
    """Formats the current time for display and system prompt."""
    now = datetime.now(tz)
    fmt = "%-I:%M %p on %A, %B %-d, %Y"
    if os.name == "nt":
        fmt = fmt.replace("%-I", "%#I").replace("%-d", "%#d")
    return now.strftime(fmt)

def preview_text(content_parts: list) -> str:
    """Generates a short preview for multi-part messages in chat history (v13.3 style)."""
    for p in reversed(content_parts): # v13.3 used reversed
        if isinstance(p, dict) and p.get("type") == "text":
            return p["text"][:150] + ("..." if len(p["text"]) > 150 else "")
    return "[Attachment: image / doc]" # v13.3 style fallback

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.image("static/UW-HFS-AI.png", use_container_width=True)

    if not backend_up(): # Uses reverted backend_up
        st.error("⚠️ LLM backend offline")
    if not TIKA_OK and TIKA_URL and TIKA_URL != "http://tika-server:9998": # Tika warning
         st.warning("⚠️ Document parsing service (Tika) may be unavailable.")

    if st.button("New Conversation", use_container_width=True):
        st.session_state.clear()
        for key, value in DEFAULT_SESSION_STATE.items():
            st.session_state[key] = value
        st.rerun()

    # File uploader logic reverted to exact v13.3 behavior
#    if st.button("Attach Files", use_container_width=True):
#        st.session_state.show_uploader = not st.session_state.show_uploader
#        st.rerun()

    if st.session_state.show_uploader:
        uploads = st.file_uploader("Select files:",
                                   accept_multiple_files=True, # v13.3 used True
                                   key=f"uploader_{st.session_state['uploader_key']}")
        if uploads: # This block is processed if user uploads files
            st.session_state.pending_files.clear() # KEY: v13.3 cleared pending files here
            for f in uploads: # Process each uploaded file
                data = f.getvalue()
                if f.type and f.type.startswith("image/"):
                    st.session_state.pending_files.append({
                        "name": f.name, "type": "image", "mime": f.type,
                        "data": base64.b64encode(data).decode(),
                    })
                else: # Assumed to be a document for Tika
                    if not TIKA_OK:
                        st.warning("📄 Document parsing unavailable"); continue # v13.3 style
                    with st.spinner(f"Parsing {f.name}…"):
                        try:
                            parsed = parser.from_buffer(data, serverEndpoint=TIKA_URL) # v13.3 style
                            txt = parsed.get("content", "").strip()
                            if txt:
                                st.session_state.pending_files.append({
                                    "name": f.name, "type": "doc", "data": txt,
                                })
                            else:
                                st.warning(f"⚠️ {f.name}: no text found") # v13.3 style
                        except Exception as e:
                            st.error(f"❌ {f.name}: {str(e)[:100]}") # v13.3 style
            # After processing all files in the batch:
            st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1 # v13.3 style
            st.session_state.show_uploader = False # v13.3 style
            st.rerun() # v13.3 style

    if st.session_state.pending_files:
        st.markdown("---");  st.markdown("**Attached:**") # v13.3 style
        for i, f_data in enumerate(st.session_state.pending_files):
            col1, col2 = st.columns([4,1])
            with col1:
                icon = "🖼️" if f_data["type"] == "image" else "📄"
                st.markdown(f"{icon} {f_data['name']}")
            with col2:
                # Ensuring unique key for delete buttons
                if st.button("❌", key=f"del_pending_{f_data['name']}_{i}", help=f"Remove {f_data['name']}"):
                    st.session_state.pending_files.pop(i);  st.rerun()

# ── Main chat ────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown(
        "<div class='welcome-text' style='font-size:2.2em;font-weight:500;'>"
        "Welcome to <span class='hfs'>HFS</span><span class='ai'>-ai</span>"
        "</div>", unsafe_allow_html=True)

# Display chat history (v13.3 style content check)
for msg_data in st.session_state.messages:
    with st.chat_message(msg_data["role"]):
        if isinstance(msg_data["content"], str):
            st.markdown(msg_data["content"])
        else: # Assumed list of parts for multimodal messages
            st.markdown(preview_text(msg_data["content"]))

# Updated chat input with file attachment support
prompt_input = st.chat_input(
    "Ask me anything…",
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "pdf", "doc", "docx", "txt"]
)

if prompt_input:
    # Handle both text-only (string) and text+files (dict-like) inputs
    if isinstance(prompt_input, str):
        # Backward compatibility - text only input
        prompt_input_text = prompt_input
        chat_uploaded_files = []
    else:
        # New format with files - prompt_input is dict-like
        prompt_input_text = prompt_input.text or ""
        chat_uploaded_files = prompt_input.files or []

    # Process any files uploaded through chat input
    for uploaded_file in chat_uploaded_files:
        data = uploaded_file.getvalue()

        if uploaded_file.type and uploaded_file.type.startswith("image/"):
            st.session_state.pending_files.append({
                "name": uploaded_file.name,
                "type": "image",
                "mime": uploaded_file.type,
                "data": base64.b64encode(data).decode(),
            })
        else:
            # Process documents with Tika
            if not TIKA_OK:
                st.warning(f"📄 Document parsing unavailable for {uploaded_file.name}")
            else:
                with st.spinner(f"Parsing {uploaded_file.name}…"):
                    try:
                        parsed = parser.from_buffer(data, serverEndpoint=TIKA_URL)
                        txt = parsed.get("content", "").strip()
                        if txt:
                            st.session_state.pending_files.append({
                                "name": uploaded_file.name,
                                "type": "doc",
                                "data": txt,
                            })
                        else:
                            st.warning(f"⚠️ {uploaded_file.name}: no text found")
                    except Exception as e:
                        st.error(f"❌ {uploaded_file.name}: {str(e)[:100]}")

    with st.chat_message("user"): # Display user's typed message
        st.markdown(prompt_input_text)

    # Prepare system prompt
    current_time_str = human_timestamp(TIMEZONE)
    try:
        system_prompt_content = FULL_SYSTEM_PROMPT_TEMPLATE.substitute(current_time_pacific=current_time_str)
    except KeyError:
        system_prompt_content = FULL_SYSTEM_PROMPT_TEMPLATE.safe_substitute(current_time_pacific=current_time_str)

    # Construct user message for LLM, including attachments (v13.3 style)
    # This `user_message_for_llm_and_history` will be stored and sent.
    user_message_parts_for_llm = []

    if st.session_state.pending_files:
        docs = [f for f in st.session_state.pending_files if f["type"] == "doc" and f.get("data")]
        if docs: # Document context formatting as in v13.3
            doc_ctx = "\n\n".join(f"--- {d['name']} ---\n{d['data']}" for d in docs)
            user_message_parts_for_llm.append({"type":"text","text":f"Context:\n{doc_ctx}"})

        for f_data in st.session_state.pending_files: # Images
            if f_data["type"] == "image":
                user_message_parts_for_llm.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{f_data['mime']};base64,{f_data['data']}"}
                })

    user_message_parts_for_llm.append({"type": "text", "text": prompt_input_text}) # User's typed text

    # If there were attachments, content is the list of parts. Otherwise, just the plain prompt text.
    final_user_content = user_message_parts_for_llm if st.session_state.pending_files else prompt_input_text

    st.session_state.messages.append({"role": "user", "content": final_user_content})
    st.session_state.pending_files.clear() # Clear after incorporating into message

    # Prepare the full list of messages for the LLM
    messages_for_llm = [
        {"role": "system", "content": system_prompt_content},
        *st.session_state.messages # Contains all history including current user message
    ]

    # Call the LLM
    with st.chat_message("assistant"), st.spinner("Thinking…"):
        try:
            client = OpenAI(base_url=LLM_BASE_URL, api_key="not-needed")
            accumulated_response, response_box = "", st.empty()
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages_for_llm,
                stream=True,
                temperature=TEMPERATURE, top_p=TOP_P,
                extra_body={
                    "top_k": TOP_K, "min_p": MIN_P,
                    "xtc_threshold": XTC_THRESHOLD,
                    "repeat_penalty": REPEAT_PENALTY,
                },
            )
            for chunk in stream:
                accumulated_response += chunk.choices[0].delta.content or ""
                response_box.markdown(accumulated_response + "▌")
            response_box.markdown(accumulated_response)
            st.session_state.messages.append({"role": "assistant", "content": accumulated_response})
            st.rerun()
        except Exception as e:
            st.error(f"❌ LLM API Error: {e}")
