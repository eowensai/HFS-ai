"""
kiosk_app.py – V 11.7  (Improved UI spacing, removed file restrictions)

CHANGES IN V11.7:
- Increased top margin for HFS logo for better centering
- Made "-ai" text slightly larger (2.5em → 3em)
- Removed unused gold background code (keeping white background)
- Removed all file size restrictions
- Removed file type restrictions (accepts all file types)
- Updated comments to reflect changes

TABLE OF CONTENTS:
1.0 - IMPORTS AND DEPENDENCIES
2.0 - CONFIGURATION AND CONSTANTS
    2.1 - System Configuration
    2.2 - UI Color Scheme
    2.3 - Model Parameters
3.0 - INITIALIZATION
    3.1 - Tika Setup
    3.2 - Streamlit Page Config
4.0 - USER INTERFACE STYLING
    4.1 - Chrome Hiding
    4.2 - Sidebar Styling
    4.3 - Main Content Area
    4.4 - Component Styling
5.0 - SESSION STATE MANAGEMENT
6.0 - HELPER FUNCTIONS
    6.1 - Backend Health Check
    6.2 - Content Preview
7.0 - SIDEBAR INTERFACE
    7.1 - Logo Display
    7.2 - Status Indicators
    7.3 - Action Buttons
    7.4 - File Upload Handler
    7.5 - Attached Files Display
8.0 - MAIN CHAT INTERFACE
    8.1 - Welcome Screen
    8.2 - Chat History Display
    8.3 - User Input Handler
    8.4 - LLM Integration
"""

# ══════════════════════════════════════════════════════════════════
# 1.0 - IMPORTS AND DEPENDENCIES
# ══════════════════════════════════════════════════════════════════
import streamlit as st
import os
import base64
import requests
import tika
from tika import parser
from tika.tika import TikaException
from openai import OpenAI
from datetime import datetime
import pytz  # For timezone support

# ══════════════════════════════════════════════════════════════════
# 2.0 - CONFIGURATION AND CONSTANTS
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# 2.1 - System Configuration
# ──────────────────────────────────────────────────────────────────
# Service endpoints - these should be set via environment variables
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://llm-server:8080/v1")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "local-model")
TIKA_URL = os.getenv("TIKA_URL", "http://tika-server:9998")

# Timezone configuration for Seattle/Pacific Time
TIMEZONE = pytz.timezone('America/Los_Angeles')

# ──────────────────────────────────────────────────────────────────
# 2.2 - UI Color Scheme (University of Washington branding)
# ──────────────────────────────────────────────────────────────────
UW_PURPLE = "#4B2E83"       # Primary brand color
UW_LIGHT_PURPLE = "#EFEAF8" # Sidebar background

# ──────────────────────────────────────────────────────────────────
# 2.3 - Model Parameters (Gemma-optimized settings)
# ──────────────────────────────────────────────────────────────────
TEMPERATURE = 1.0      # Controls randomness (0=deterministic, 2=very random)
TOP_K = 64            # Limits vocab to top K tokens
TOP_P = 0.95          # Nucleus sampling threshold
MIN_P = 0.0           # Minimum probability threshold
XTC_THRESHOLD = 1.0   # XTC sampling threshold
REPEAT_PENALTY = 1.0  # Penalty for repeating tokens

# ══════════════════════════════════════════════════════════════════
# 3.0 - INITIALIZATION
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# 3.1 - Tika Setup (Document parsing service)
# ──────────────────────────────────────────────────────────────────
# Configure Tika to use REST API only (no local Java process)
os.environ["TIKA_CLIENT_ONLY"] = "true"
try:
    tika.initVM()
    TIKA_OK = True
except TikaException:
    # Tika service unavailable - document uploads will be disabled
    TIKA_OK = False

# ──────────────────────────────────────────────────────────────────
# 3.2 - Streamlit Page Config
# ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HFS AI Assistant",
    layout="wide",                      # Use full screen width
    initial_sidebar_state="expanded"    # Keep sidebar visible
)

# ══════════════════════════════════════════════════════════════════
# 4.0 - USER INTERFACE STYLING
# ══════════════════════════════════════════════════════════════════
st.markdown(
    f"""
<style>
/* ────────────────────────────────────────────────────────────────
   4.1 - Chrome Hiding (Remove all Streamlit UI elements)
   ──────────────────────────────────────────────────────────────── */
#MainMenu, header, footer {{visibility: hidden;}}
.stDeployButton {{display: none;}}
[data-testid="stToolbar"] {{display: none !important;}}
[data-testid="stStatusWidget"] {{display: none !important;}}

/* Hide sidebar collapse controls for kiosk mode */
button[aria-label*="sidebar"],
[data-testid="stSidebarCollapseControl"],
[data-testid="collapsedControl"],
[data-testid="baseButton-header"] {{
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}}

/* ────────────────────────────────────────────────────────────────
   4.2 - Sidebar Styling
   ──────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    width: 280px !important;
    min-width: 280px !important;
    max-width: 280px !important;
    transform: none !important;
    background: {UW_LIGHT_PURPLE};
    padding-top: 0.5rem;
}}

/* ────────────────────────────────────────────────────────────────
   4.3 - Main Content Area (Clean white background)
   ──────────────────────────────────────────────────────────────── */
.main .block-container {{
    background: white;
    padding: 2rem 2rem 2rem 0;
    max-width: 1200px;
}}

/* ────────────────────────────────────────────────────────────────
   4.4 - Component Styling
   ──────────────────────────────────────────────────────────────── */

/* Large sidebar logo with better spacing */
.hfs-logo {{
    text-align: center;
    margin: 0rem 0 5rem 0;  /* Increased top margin for better centering */
    padding: 0 1rem;
}}

.hfs-logo .hfs {{
    font-size: 5em;
    font-weight: 900;
    color: {UW_PURPLE};
    letter-spacing: -5px;
    line-height: 1;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2); /* Subtle shadow for contrast */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}

.hfs-logo .ai {{
    font-size: 3em;  /* Increased from 2.5em for better visibility */
    font-weight: 400;
    color: #666;
    letter-spacing: -1px;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.2); /* Subtle shadow for contrast */
    margin-left: 3px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}

/* Welcome text in main area */
.welcome-text {{
    text-align: center;
    padding: 3rem 0;
}}

.welcome-text .hfs {{
    font-size: 2.2em;
    font-weight: 900;
    color: {UW_PURPLE};
    letter-spacing: -5px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}

.welcome-text .ai {{
    font-size: 1.2em;
    font-weight: 400;
    color: #666;
    letter-spacing: -1px;
    margin-left: 2px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}

/* Button styling */
.stButton > button {{
    width: 100%;
    background: white;
    color: #333;
    border: 2px solid #4B2E83;
    font-weight: 600;
    font-size: 0.95rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 0.75rem;
    transition: all 0.2s;
    margin-bottom: 0.5rem;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); /* Subtle shadow for lift */
}}

.stButton > button:hover {{
    background: #6A4DAE;
    color: white;
    transform: translateY(-1px);
}}

/* Chat message containers */
.stChatMessage {{
    background: white;
    border-radius: 8px;
    margin: 0.5rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}

/* Avatar colors */
[data-testid="chatAvatarIcon-user"] {{
    background-color: {UW_PURPLE} !important;
}}

[data-testid="chatAvatarIcon-assistant"] {{
    background-color: #B7A57A !important;  /* UW Gold for assistant */
}}

/* Chat input box */
.stChatInput {{
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}}

.stChatInput > div {{
    background: white !important;
    border: 1px solid #ddd !important;
    border-radius: 4px !important;
    margin: 0 !important;
    padding: 0 !important;
}}

.stChatInput textarea {{
    border: none !important;
    background: white !important;
    padding: 0.75rem !important;
    margin: 0 !important;
}}

.stChatInput > div:focus-within {{
    border-color: {UW_PURPLE} !important;
    box-shadow: 0 0 0 1px {UW_PURPLE} !important;
}}

/* File uploader */
[data-testid="stFileUploader"] > div {{
    background: white;
    border: 2px solid {UW_PURPLE};
    border-radius: 4px;
    padding: 1rem;
}}

/* Attached files display */
.attached-file {{
    background: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    margin: 0.5rem 0;
    font-size: 0.9em;
    border: 1px solid #E0E0E0;
}}
</style>
""",
    unsafe_allow_html=True,  # This closes the CSS markdown
)

# ══════════════════════════════════════════════════════════════════
# 5.0 - SESSION STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════
# Initialize persistent state variables
for k, v in {
    "messages": [],          # Chat history
    "pending_files": [],     # Files awaiting attachment
    "show_uploader": False   # File uploader visibility
}.items():
    st.session_state.setdefault(k, v)

# Shorthand for cleaner code
rerun = st.rerun

# ══════════════════════════════════════════════════════════════════
# 6.0 - HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# 6.1 - Backend Health Check
# ──────────────────────────────────────────────────────────────────
def backend_up() -> bool:
    """
    Check if the LLM backend service is accessible.
    Tries common health check endpoints.

    Returns:
        bool: True if backend is responsive, False otherwise
    """
    base = LLM_BASE_URL.split("/v1")[0]
    for ep in ("/healthz", "/health"):
        try:
            if requests.get(base + ep, timeout=2).ok:
                return True
        except requests.RequestException:
            pass
    return False

# ──────────────────────────────────────────────────────────────────
# 6.2 - Content Preview
# ──────────────────────────────────────────────────────────────────
def preview_text(parts):
    """
    Extract text preview from multipart message content.
    Used for displaying complex messages in chat history.

    Args:
        parts: List of message parts (text, images, etc.)

    Returns:
        str: Text content or "[complex]" placeholder
    """
    for p in reversed(parts):
        if isinstance(p, dict) and p.get("type") == "text":
            return p["text"]
    return "[complex]"

# ══════════════════════════════════════════════════════════════════
# 7.0 - SIDEBAR INTERFACE
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    # ──────────────────────────────────────────────────────────────
    # 7.1 - Logo Display
    # ──────────────────────────────────────────────────────────────
    st.markdown(
        """<div class='hfs-logo'>
            <span class='hfs'>HFS</span><span class='ai'>-ai</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # ──────────────────────────────────────────────────────────────
    # 7.2 - Status Indicators
    # ──────────────────────────────────────────────────────────────
    if not backend_up():
        st.error("⚠️  LLM backend offline")

    # ──────────────────────────────────────────────────────────────
    # 7.3 - Action Buttons
    # ──────────────────────────────────────────────────────────────
    # Clear conversation and start fresh
    if st.button("New Conversation", use_container_width=True):
        st.session_state.clear()
        rerun()

    # Toggle file uploader visibility
    if st.button("Attach Files", use_container_width=True):
        st.session_state.show_uploader = not st.session_state.show_uploader
        rerun()

    # ──────────────────────────────────────────────────────────────
    # 7.4 - File Upload Handler
    # ──────────────────────────────────────────────────────────────
    if st.session_state.show_uploader:
        # Accept ALL file types - let Tika handle what it can
        uploads = st.file_uploader(
            "Select files:",
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.get('uploader_key', 0)}",
        )

        if uploads:
            st.session_state.pending_files.clear()

            for f in uploads:
                data = f.getvalue()

                # Process image files
                if f.type and f.type.startswith("image/"):
                    st.session_state.pending_files.append(
                        {
                            "name": f.name,
                            "type": "image",
                            "mime": f.type,
                            "data": base64.b64encode(data).decode(),
                        }
                    )

                # Process all other files with Tika
                else:
                    if not TIKA_OK:
                        st.warning("📄 Document parsing unavailable")
                        continue

                    # Try to extract text using Tika - no size limits
                    with st.spinner(f"Parsing {f.name}..."):
                        try:
                            txt = parser.from_buffer(
                                data, serverEndpoint=TIKA_URL
                            )["content"].strip()
                            if txt:
                                st.session_state.pending_files.append(
                                    {"name": f.name, "type": "doc", "data": txt}
                                )
                            else:
                                st.warning(f"⚠️ {f.name}: No text found")
                        except Exception as e:
                            st.error(f"❌ Error parsing {f.name}: {str(e)[:50]}")

            # Hide uploader and increment key to reset widget
            st.session_state.show_uploader = False
            st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
            rerun()

    # ──────────────────────────────────────────────────────────────
    # 7.5 - Attached Files Display
    # ──────────────────────────────────────────────────────────────
    if st.session_state.pending_files:
        st.markdown("---")
        st.markdown("**Attached:**")
        for i, f in enumerate(st.session_state.pending_files):
            col1, col2 = st.columns([4, 1])
            with col1:
                # Choose icon based on file type
                icon = "🖼️" if f['type'] == 'image' else "📄"
                st.markdown(
                    f"""<div class='attached-file'>
                        {icon} {f['name']}
                    </div>""",
                    unsafe_allow_html=True
                )
            with col2:
                if st.button("❌", key=f"del_{i}", help=f"Remove {f['name']}"):
                    st.session_state.pending_files.pop(i)
                    rerun()

# ══════════════════════════════════════════════════════════════════
# 8.0 - MAIN CHAT INTERFACE
# ══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# 8.1 - Welcome Screen
# ──────────────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown(
        """<div class='welcome-text'>
            <h2>Welcome to <span class='hfs'>HFS</span><span class='ai'>-ai</span></h2>
        </div>""",
        unsafe_allow_html=True
    )

# ──────────────────────────────────────────────────────────────────
# 8.2 - Chat History Display
# ──────────────────────────────────────────────────────────────────
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(
            m["content"]
            if isinstance(m["content"], str)
            else preview_text(m["content"])
        )

# ──────────────────────────────────────────────────────────────────
# 8.3 - User Input Handler
# ──────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask me anything…"):
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build system prompt with current Pacific Time
    pacific_now = datetime.now(TIMEZONE)
    current_time = pacific_now.strftime("%Y-%m-%d %H:%M:%S PST")

    system_prompt = f"""You are HFS-ai, an AI assistant. You are a general-purpose service and should be helpful, clear, and direct.
- Your knowledge is general; you do not have specific information about University of Washington departments, housing, dining, schedules, or events unless it is provided in an attached file.
- Base your responses only on the information you were trained on or the context provided in the user's query and attached files/images.
- Do not speculate, invent details, or create narratives.
- Maintain a professional, neutral tone.
The current date and time is {current_time}."""

    # Prepare message history
    msgs = [{"role": "system", "content": system_prompt}]
    msgs.extend(st.session_state.messages)
    user_msg = {"role": "user", "content": prompt}

    # Handle attached files
    if st.session_state.pending_files:
        parts = []

        # Add document content first
        docs = [f for f in st.session_state.pending_files if f["type"] == "doc"]
        if docs:
            parts.append(
                {
                    "type": "text",
                    "text": "\n\n".join(
                        f"--- {d['name']} ---\n{d['data']}" for d in docs
                    ),
                }
            )

        # Add images
        for f in st.session_state.pending_files:
            if f["type"] == "image":
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{f['mime']};base64,{f['data']}"
                        },
                    }
                )

        # Add user prompt at end
        parts.append({"type": "text", "text": prompt})
        user_msg["content"] = parts

    # Update conversation history
    st.session_state.messages.append(user_msg)
    st.session_state.pending_files.clear()
    msgs.append(user_msg)

    # ──────────────────────────────────────────────────────────────
    # 8.4 - LLM Integration
    # ──────────────────────────────────────────────────────────────
    with st.chat_message("assistant"), st.spinner("Thinking…"):
        try:
            # Initialize OpenAI-compatible client
            client = OpenAI(base_url=LLM_BASE_URL, api_key="not-needed")
            acc, box = "", st.empty()

            # Stream response with all model parameters
            for d in client.chat.completions.create(
                model=MODEL_NAME,
                messages=msgs,
                stream=True,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                extra_body={
                    "top_k": TOP_K,
                    "min_p": MIN_P,
                    "xtc_threshold": XTC_THRESHOLD,
                    "repeat_penalty": REPEAT_PENALTY
                }
            ):
                acc += d.choices[0].delta.content or ""
                box.markdown(acc + "▌")  # Show typing indicator

            # Display final response
            box.markdown(acc)

            # Save to history
            st.session_state.messages.append(
                {"role": "assistant", "content": acc}
            )
            rerun()

        except Exception as e:
            st.error(f"❌ LLM Error: {str(e)}")
