# ══════════════════════════════════════════════════════════════════
# File:         kiosk_app.py
# Project:      HFS AI Assistant
# Version:      13.0
# Last Updated: 2025-06-15
# ══════════════════════════════════════════════════════════════════
#
# == DESCRIPTION ==
# A Streamlit-based web application that provides a user-friendly chat
# interface for a local Large Language Model (LLM). It is designed to
# be a self-contained front-end with support for document and image
# uploads for multimodal interactions.
#
# == EXTERNAL FILE DEPENDENCIES ==
#
# • docker-compose.yml:
#   Manages this application as a containerized service. Sets crucial
#   environment variables (LLM_BASE_URL, TIKA_URL, etc.).
#
# • requirements.txt:
#   Lists the Python libraries needed to run this script.
#
# • theme.css:
#   Provides all custom CSS for the UW-branded user interface.
#
# • .streamlit/config.toml:
#   Sets the base Streamlit theme to "light" to ensure a consistent
#   appearance and prevent OS-level dark mode from interfering.
#
# ══════════════════════════════════════════════════════════════════
#
# == TABLE OF CONTENTS ==
#
# --- PART 1: SETUP & CONFIGURATION ---
# 1.1  IMPORTS
# 1.2  PAGE & THEME CONFIGURATION
# 1.3  APPLICATION CONSTANTS & PARAMETERS
# 1.4  SERVICE INITIALIZATION
# 1.5  SESSION STATE
#
# --- PART 2: HELPER FUNCTIONS ---
# 2.1  BACKEND HEALTH CHECK
# 2.2  HUMAN-READABLE TIMESTAMP
# 2.3  CONTENT PREVIEW FOR COMPLEX MESSAGES
#
# --- PART 3: USER INTERFACE ---
# 3.1  SIDEBAR LAYOUT & CONTROLS
# 3.2  MAIN CHAT INTERFACE
#
# ══════════════════════════════════════════════════════════════════

# PART 1.1: IMPORTS
# --------------------------------------------------------------------
import os
import base64
import pathlib
from datetime import datetime
import streamlit as st
import requests
import pytz
import tika
from tika import parser
from tika.tika import TikaException
from openai import OpenAI


# PART 1.2: PAGE & THEME CONFIGURATION
# --------------------------------------------------------------------
# Configure the Streamlit page's title, layout, and initial state.
st.set_page_config(
    page_title="HFS AI Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load the external CSS file for custom UW branding.
def load_css(path: str = "theme.css") -> None:
    """Reads a CSS file and injects its content into the app."""
    css_path = pathlib.Path(path)
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    else:
        st.error(f"❌ Styling file missing: {path}")

load_css()


# PART 1.3: APPLICATION CONSTANTS & PARAMETERS
# --------------------------------------------------------------------
# --- System & Network Configuration ---
# These are loaded from environment variables set in docker-compose.yml.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.87.64:11434/v1")
MODEL_NAME   = os.getenv("LLM_MODEL_NAME", "local-model")
TIKA_URL     = os.getenv("TIKA_URL", "http://tika-server:9998")
TIMEZONE     = pytz.timezone("America/Los_Angeles")

# --- LLM Generation Parameters ---
# These values control the behavior of the model's text generation.
TEMPERATURE    = 1.0
TOP_K          = 64
TOP_P          = 0.95
MIN_P          = 0.0
XTC_THRESHOLD  = 1.0
REPEAT_PENALTY = 1.0


# PART 1.4: SERVICE INITIALIZATION
# --------------------------------------------------------------------
# Configure the Tika client and check for its availability.
# TIKA_CLIENT_ONLY prevents Tika from downloading a new JAR file.
os.environ["TIKA_CLIENT_ONLY"] = "true"
try:
    tika.initVM()
    TIKA_OK = True
except TikaException:
    TIKA_OK = False


# PART 1.5: SESSION STATE
# --------------------------------------------------------------------
# Initialize session state keys. Streamlit reruns the script on each
# interaction, so session state is used to persist data (like the
# chat history) across these reruns.
for k, v in {
    "messages": [],
    "pending_files": [],
    "show_uploader": False,
}.items():
    st.session_state.setdefault(k, v)


# ══════════════════════════════════════════════════════════════════
#                      PART 2: HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def backend_up() -> bool:
    """
    Checks if the LLM backend is responsive by probing common API endpoints.
    Returns True if any endpoint returns a successful status code.
    """
    base = LLM_BASE_URL.split("/v1")[0]
    for ep in ("", "/api/tags", "/v1/models"):
        try:
            if requests.get(base + ep, timeout=2).ok:
                return True
        except requests.RequestException:
            pass
    return False

def human_timestamp(tz: pytz.BaseTzInfo) -> str:
    """
    Returns a human-readable timestamp for the given timezone.
    Example: '3:45 PM on Sunday, June 15, 2025'
    """
    now = datetime.now(tz)
    # Use platform-aware formatting for no-padding integers.
    fmt = "%-I:%M %p on %A, %B %-d, %Y"
    if os.name == "nt":  # Windows uses '#' for no-padding.
        fmt = fmt.replace("%-I", "%#I").replace("%-d", "%#d")
    return now.strftime(fmt)

def preview_text(parts: list) -> str:
    """
    Extracts the text content from a complex (multimodal) message
    for display in the chat history.
    """
    for p in reversed(parts):
        if isinstance(p, dict) and p.get("type") == "text":
            return p["text"]
    return "[Attachment: Image or other complex content]"


# ══════════════════════════════════════════════════════════════════
#                        PART 3: USER INTERFACE
# ══════════════════════════════════════════════════════════════════

# PART 3.1: SIDEBAR LAYOUT & CONTROLS
# --------------------------------------------------------------------
with st.sidebar:
    # --- Logo Display ---
    st.markdown(
        "<div class='hfs-logo'><span class='hfs'>HFS</span><span class='ai'>-ai</span></div>",
        unsafe_allow_html=True,
    )

    # --- Status Indicators ---
    if not backend_up():
        st.error("⚠️  LLM backend offline")

    # --- Action Buttons ---
    if st.button("New Conversation", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    if st.button("Attach Files", use_container_width=True):
        st.session_state.show_uploader = not st.session_state.show_uploader
        st.rerun()

    # --- File Upload Handler ---
    if st.session_state.show_uploader:
        uploads = st.file_uploader(
            "Select files:",
            accept_multiple_files=True,
            # Incrementing the key forces the widget to reset after uploads.
            key=f"uploader_{st.session_state.get('uploader_key', 0)}",
        )

        if uploads:
            st.session_state.pending_files.clear()
            for f in uploads:
                data = f.getvalue()

                # Handle images for multimodal input.
                if f.type and f.type.startswith("image/"):
                    st.session_state.pending_files.append({
                        "name": f.name,
                        "type": "image",
                        "mime": f.type,
                        "data": base64.b64encode(data).decode(),
                    })
                # Handle other file types as documents for text extraction.
                else:
                    if not TIKA_OK:
                        st.warning("📄 Document parsing unavailable")
                        continue
                    with st.spinner(f"Parsing {f.name}…"):
                        try:
                            parsed = parser.from_buffer(data, serverEndpoint=TIKA_URL)
                            txt = parsed.get("content", "").strip()
                            if txt:
                                st.session_state.pending_files.append({
                                    "name": f.name,
                                    "type": "doc",
                                    "data": txt,
                                })
                            else:
                                st.warning(f"⚠️ {f.name}: No text found")
                        except Exception as e:
                            st.error(f"❌ Error parsing {f.name}: {str(e)[:100]}")

            # Hide and reset the uploader widget after processing.
            st.session_state.show_uploader = False
            st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
            st.rerun()

    # --- Attached Files Display ---
    if st.session_state.pending_files:
        st.markdown("---")
        st.markdown("**Attached:**")
        for i, f in enumerate(st.session_state.pending_files):
            col1, col2 = st.columns([4, 1])
            with col1:
                icon = "🖼️" if f["type"] == "image" else "📄"
                st.markdown(
                    f"<div class='attached-file'>{icon} {f['name']}</div>",
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("❌", key=f"del_{i}", help=f"Remove {f['name']}"):
                    st.session_state.pending_files.pop(i)
                    st.rerun()


# PART 3.2: MAIN CHAT INTERFACE
# --------------------------------------------------------------------
# --- Welcome Screen ---
# Show a welcome message if the chat history is empty.
if not st.session_state.messages:
    st.markdown(
        "<div class='welcome-text' style='font-size:2.2em;font-weight:500;'>"
        "Welcome to <span class='hfs'>HFS</span><span class='ai'>-ai</span>"
        "</div>",
        unsafe_allow_html=True,
    )

# --- Chat History Display ---
# Render previous messages from session state.
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        # Use preview_text for complex messages, otherwise show content directly.
        content_to_display = (
            m["content"] if isinstance(m["content"], str)
            else preview_text(m["content"])
        )
        st.markdown(content_to_display)

# --- User Input Handler ---
# Capture user input from the chat box at the bottom of the screen.
if prompt := st.chat_input("Ask me anything…"):
    # Display the user's prompt immediately.
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- Prepare a system prompt for the LLM ---
    # This instructs the model on its persona, capabilities, and limitations.
    now_iso = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S %Z")
    system_prompt = (
        "You are HFS-ai, an AI assistant. You are a general-purpose service "
        "and should be helpful, clear, and direct.\n"
        "- Your knowledge is general; you do not have specific information "
        "about University of Washington departments, housing, dining, schedules, "
        "or events unless it is provided in an attached file.\n"
        "- Base your responses only on the information you were trained on or "
        "the context provided in the user's query and attached files/images.\n"
        "- Do not speculate, invent details, or create narratives.\n"
        "- Maintain a professional, neutral tone.\n"
        f"- The current date and time is {human_timestamp(TIMEZONE)} ({now_iso})."
    )

    # --- Assemble the full message history for the API call ---
    # The history includes the system prompt and all previous user/assistant turns.
    msgs = [{"role": "system", "content": system_prompt}, *st.session_state.messages]
    user_msg = {"role": "user", "content": prompt}

    # --- Handle Attachments (Multimodal Payloads) ---
    if st.session_state.pending_files:
        parts = []
        # Combine all document text into a single context block.
        docs = [f for f in st.session_state.pending_files if f["type"] == "doc"]
        if docs:
            doc_context = "\n\n".join(
                f"--- Attached Document: {d['name']} ---\n{d['data']}" for d in docs
            )
            parts.append({"type": "text", "text": f"Context from attached documents:\n{doc_context}"})

        # Add each image as a separate part.
        for f in st.session_state.pending_files:
            if f["type"] == "image":
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{f['mime']};base64,{f['data']}"},
                })
        
        # Add the user's text prompt at the end.
        parts.append({"type": "text", "text": prompt})
        user_msg["content"] = parts

    # Add the final user message to history and clear pending files.
    st.session_state.messages.append(user_msg)
    st.session_state.pending_files.clear()
    msgs.append(user_msg)

    # --- Stream the LLM Response ---
    with st.chat_message("assistant"), st.spinner("Thinking…"):
        try:
            client = OpenAI(base_url=LLM_BASE_URL, api_key="not-needed")
            acc, box = "", st.empty()
            
            # The extra_body parameter is used for API options not standard to
            # the OpenAI library, such as top_k, min_p, etc.
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=msgs,
                stream=True,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                extra_body={
                    "top_k": TOP_K,
                    "min_p": MIN_P,
                    "xtc_threshold": XTC_THRESHOLD,
                    "repeat_penalty": REPEAT_PENALTY,
                },
            )

            for chunk in stream:
                acc += chunk.choices[0].delta.content or ""
                box.markdown(acc + "▌")

            box.markdown(acc)
            st.session_state.messages.append({"role": "assistant", "content": acc})
            st.rerun()

        except Exception as e:
            st.error(f"❌ LLM API Error: {e}")
