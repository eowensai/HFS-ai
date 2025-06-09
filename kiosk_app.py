# kiosk_app.py – V12.6
#
# TABLE OF CONTENTS:
# 1.0 – IMPORTS AND DEPENDENCIES
# 2.0 – CONFIGURATION AND CONSTANTS
#    2.1 – System Configuration
#    2.2 – UI Color Scheme
#    2.3 – Model Parameters
# 3.0 – INITIALIZATION
#    3.1 – Tika Setup
# 4.0 – USER INTERFACE STYLING
#    4.1 – Chrome Hiding
#    4.2 – Sidebar Styling
#    4.3 – Main Content Area
#    4.4 – Component Styling
# 5.0 – SESSION STATE MANAGEMENT
# 6.0 – HELPER FUNCTIONS
#    6.1 – Backend Health Check
#    6.2 – Content Preview
# 7.0 – SIDEBAR INTERFACE
#    7.1 – Logo Display
#    7.2 – Status Indicators
#    7.3 – Action Buttons
#    7.4 – File Upload Handler
#    7.5 – Attached Files Display
# 8.0 – MAIN CHAT INTERFACE
#    8.1 – Welcome Screen
#    8.2 – Chat History Display
#    8.3 – User Input Handler
#    8.4 – LLM Integration
# 9.0 – NAVIGATION CONTROLS
#    9.1 – Go Back Button

"""
kiosk_app.py v12.6 – HFS AI Assistant

A Streamlit-based chat interface that:
  • Connects to a local LLM backend via OpenAI-compatible API  
  • Parses user-uploaded documents through an external Tika service  
  • Renders a clean UW-branded UI with custom CSS  

Dependencies:
  • Python 3.11  
  • streamlit, openai, tika, requests, pytz  
"""

# ══════════════════════════════════════════════════════════════════
# 1.0 – IMPORTS AND DEPENDENCIES
# ══════════════════════════════════════════════════════════════════

# Standard library
import os
import base64
from datetime import datetime

# Third-party
import streamlit as st
import requests
import pytz
import tika
from tika import parser
from tika.tika import TikaException
from openai import OpenAI

# ══════════════════════════════════════════════════════════════════
# 1.1 – Streamlit Page Config
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="HFS AI Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════
# 2.0 – CONFIGURATION AND CONSTANTS
# ══════════════════════════════════════════════════════════════════

# 2.1 – System Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://llm-server:8080/v1")
MODEL_NAME   = os.getenv("LLM_MODEL_NAME", "local-model")
TIKA_URL     = os.getenv("TIKA_URL", "http://tika-server:9998")
TIMEZONE     = pytz.timezone("America/Los_Angeles")

# 2.2 – UI Color Scheme (UW branding)
UW_PURPLE       = "#4B2E83"
UW_LIGHT_PURPLE = "#EFEAF8"

# 2.3 – Model Parameters
TEMPERATURE    = 1.0
TOP_K          = 64
TOP_P          = 0.95
MIN_P          = 0.0
XTC_THRESHOLD  = 1.0
REPEAT_PENALTY = 1.0

# ══════════════════════════════════════════════════════════════════
# 3.0 – INITIALIZATION
# ══════════════════════════════════════════════════════════════════
os.environ["TIKA_CLIENT_ONLY"] = "true"
try:
    tika.initVM()
    TIKA_OK = True
except TikaException:
    TIKA_OK = False

# ══════════════════════════════════════════════════════════════════
# 4.0 – USER INTERFACE STYLING   (FULL original CSS)
# ══════════════════════════════════════════════════════════════════
st.markdown(
    f"""
<style>
/* 4.1 – Chrome Hiding */
#MainMenu, header, footer {{visibility:hidden;}}
.stDeployButton{{display:none;}}
[data-testid="stToolbar"],[data-testid="stStatusWidget"]{{display:none!important;}}

/* Collapse controls hidden */
button[aria-label*="sidebar"],[data-testid="stSidebarCollapseControl"],
[data-testid="collapsedControl"],[data-testid="baseButton-header"]{{
  display:none!important;visibility:hidden!important;opacity:0!important;pointer-events:none!important;}}

/* 4.2 – Sidebar */
section[data-testid="stSidebar"]{{width:280px!important;background:{UW_LIGHT_PURPLE};
  padding-top:0.5rem;border-right:2px solid {UW_PURPLE}!important;}}

/* 4.3 – Main area */
.main .block-container{{background:white;padding:2rem 2rem 2rem 0;max-width:1200px;}}

/* 4.4 – Components (logo, buttons, chat, etc.) */
.hfs-logo{{text-align:center;margin:0 0 5rem 0;padding:0 1rem;}}
.hfs-logo .hfs{{font-size:5em;font-weight:900;color:{UW_PURPLE};letter-spacing:-5px;line-height:1;
  text-shadow:2px 2px 4px rgba(0,0,0,0.2);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}}
.hfs-logo .ai{{font-size:3em;font-weight:400;color:#666;letter-spacing:-1px;text-shadow:1px 1px 2px rgba(0,0,0,0.2);
  margin-left:3px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}}

.welcome-text{{text-align:center;padding:3rem 0;}}
.welcome-text .hfs{{font-size:2.2em;font-weight:900;color:{UW_PURPLE};letter-spacing:-5px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}}
.welcome-text .ai{{font-size:1.2em;font-weight:400;color:#666;letter-spacing:-1px;margin-left:3px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}}

.stButton>button{{width:100%;background:white;color:#333;border:2px solid {UW_PURPLE};
  font-weight:600;font-size:0.95rem;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  padding:0.75rem;margin-bottom:0.5rem;transition:all .2s;box-shadow:0 2px 4px rgba(0,0,0,0.1);}}
.stButton>button:hover{{background:#6A4DAE;color:white;transform:translateY(-1px);}}
.stButton>button:focus{{background:white!important;color:{UW_PURPLE}!important;border:2px solid {UW_PURPLE}!important;
  box-shadow:0 0 0 2px rgba(75,46,131,0.2)!important;outline:none!important;}}
.stButton>button:focus:not(:focus-visible){{box-shadow:none!important;}}
.stButton>button:active{{background:{UW_PURPLE}!important;color:white!important;border:2px solid {UW_PURPLE}!important;}}

.stChatMessage{{background:white;border-radius:8px;margin:0.5rem 0;box-shadow:0 1px 3px rgba(0,0,0,0.05);}}
[data-testid="chatAvatarIcon-user"]{{background-color:{UW_PURPLE}!important;}}
[data-testid="chatAvatarIcon-assistant"]{{background-color:#B7A57A!important;}}

.stChatInput{{border:none!important;background:transparent!important;padding:0!important;}}
.stChatInput>div{{background:white!important;border:2px solid #8a8a8a!important;border-radius:4px!important;
  margin:0!important;padding:0!important;}}
.stChatInput textarea{{border:none!important;background:white!important;padding:0.75rem!important;margin:0!important;}}
.stChatInput>div:focus-within{{border-color:{UW_PURPLE}!important;box-shadow:0 0 0 1px {UW_PURPLE}!important;}}

[data-testid="stFileUploader"]>div{{background:white;border:2px solid {UW_PURPLE};border-radius:4px;padding:1rem;}}
.attached-file{{background:white;padding:0.5rem 1rem;border-radius:4px;margin:0.5rem 0;font-size:0.9em;
  border:1px solid #E0E0E0;}}
</style>""",
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════
# 5.0 – SESSION STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════
for k, v in {
    "messages": [],
    "pending_files": [],
    "show_uploader": False,
}.items():
    st.session_state.setdefault(k, v)

rerun = st.rerun

# ══════════════════════════════════════════════════════════════════
# 6.0 – HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════
def backend_up() -> bool:
    base = LLM_BASE_URL.split("/v1")[0]
    for ep in ("/healthz", "/health"):
        try:
            if requests.get(base + ep, timeout=2).ok:
                return True
        except requests.RequestException:
            pass
    return False

def preview_text(parts):
    for p in reversed(parts):
        if isinstance(p, dict) and p.get("type") == "text":
            return p["text"]
    return "[complex]"

# ══════════════════════════════════════════════════════════════════
# 7.0 – SIDEBAR INTERFACE
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    # 7.1 – Logo Display
    st.markdown(
        "<div class='hfs-logo'><span class='hfs'>HFS</span><span class='ai'>-ai</span></div>",
        unsafe_allow_html=True,
    )

    # 7.2 – Status Indicators
    if not backend_up():
        st.error("⚠️  LLM backend offline")

    # 7.3 – Action Buttons
    if st.button("New Conversation", use_container_width=True):
        st.session_state.clear()
        rerun()

    if st.button("Attach Files", use_container_width=True):
        st.session_state.show_uploader = not st.session_state.show_uploader
        rerun()

    # 7.4 – File Upload Handler
    if st.session_state.show_uploader:
        uploads = st.file_uploader(
            "Select files:",
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.get('uploader_key', 0)}",
        )

        if uploads:
            st.session_state.pending_files.clear()
            for f in uploads:
                data = f.getvalue()

                # Images
                if f.type and f.type.startswith("image/"):
                    st.session_state.pending_files.append({
                        "name": f.name,
                        "type": "image",
                        "mime": f.type,
                        "data": base64.b64encode(data).decode(),
                    })
                # Docs
                else:
                    if not TIKA_OK:
                        st.warning("📄 Document parsing unavailable")
                        continue
                    with st.spinner(f"Parsing {f.name}…"):
                        try:
                            txt = parser.from_buffer(
                                data, serverEndpoint=TIKA_URL
                            )["content"].strip()
                            if txt:
                                st.session_state.pending_files.append({
                                    "name": f.name,
                                    "type": "doc",
                                    "data": txt,
                                })
                            else:
                                st.warning(f"⚠️ {f.name}: No text found")
                        except Exception as e:
                            st.error(f"❌ Error parsing {f.name}: {str(e)[:50]}")

            # Reset uploader widget
            st.session_state.show_uploader = False
            st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
            rerun()

    # 7.5 – Attached Files Display
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
                    rerun()

# ══════════════════════════════════════════════════════════════════
# 8.0 – MAIN CHAT INTERFACE
# ══════════════════════════════════════════════════════════════════
if not st.session_state.messages:
    st.markdown(
        "<div class='welcome-text' style='font-size:2.2em;font-weight:500;'>"
        "Welcome to <span class='hfs'>HFS</span><span class='ai'>-ai</span>"
        "</div>",
        unsafe_allow_html=True,
    )

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(
            m["content"] if isinstance(m["content"], str)
            else preview_text(m["content"])
        )

if prompt := st.chat_input("Ask me anything…"):
    with st.chat_message("user"):
        st.markdown(prompt)

    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S PST")
    system_prompt = (
        "You are HFS-ai, an AI assistant. You are a general-purpose service and should be helpful, clear, and direct.\n"
        "- Your knowledge is general; you do not have specific information about University of Washington departments, housing, dining, schedules, or events unless it is provided in an attached file.\n"
        "- Base your responses only on the information you were trained on or the context provided in the user's query and attached files/images.\n"
        "- Do not speculate, invent details, or create narratives.\n"
        "- Maintain a professional, neutral tone.\n"
        f"The current date and time is {now}."
    )

    msgs = [{"role": "system", "content": system_prompt}, *st.session_state.messages]
    user_msg = {"role": "user", "content": prompt}

    # Attach files
    if st.session_state.pending_files:
        parts = []
        docs = [f for f in st.session_state.pending_files if f["type"] == "doc"]
        if docs:
            parts.append({
                "type": "text",
                "text": "\n\n".join(f"--- {d['name']} ---\n{d['data']}" for d in docs),
            })
        for f in st.session_state.pending_files:
            if f["type"] == "image":
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{f['mime']};base64,{f['data']}"},
                })
        parts.append({"type": "text", "text": prompt})
        user_msg["content"] = parts

    st.session_state.messages.append(user_msg)
    st.session_state.pending_files.clear()
    msgs.append(user_msg)

    with st.chat_message("assistant"), st.spinner("Thinking…"):
        try:
            client = OpenAI(base_url=LLM_BASE_URL, api_key="not-needed")
            acc, box = "", st.empty()
            for chunk in client.chat.completions.create(
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
            ):
                acc += chunk.choices[0].delta.content or ""
                box.markdown(acc + "▌")
            box.markdown(acc)
            st.session_state.messages.append({"role": "assistant", "content": acc})
            rerun()
        except Exception as e:
            st.error(f"❌ LLM Error: {e}")

# ══════════════════════════════════════════════════════════════════
# 9.0 – NAVIGATION CONTROLS  (Step-4 change only)
# ══════════════════════════════════════════════════════════════════
if "code" in st.query_params:
    if st.button("Go Back", use_container_width=True):
        st.query_params.clear()
        st.rerun()
