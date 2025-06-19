# ══════════════════════════════════════════════════════════════════
# File:         kiosk_app.py
# Project:      HFS-ai Assistant
# Version:      13.3  (robot logo, fullscreen hidden, uploader_key guard)
# Last updated: 2025-06-19
# ══════════════════════════════════════════════════════════════════

# ── Imports ───────────────────────────────────────────────────────
import os, base64, pathlib
from datetime import datetime
import streamlit as st
import requests, pytz, tika
from tika import parser
from tika.tika import TikaException
from openai import OpenAI

# ── Page / theme ──────────────────────────────────────────────────
st.set_page_config(page_title="HFS-ai", layout="wide",
                   initial_sidebar_state="expanded")

def load_css(path="theme.css"):
    css = pathlib.Path(path)
    if css.exists():
        st.markdown(f"<style>{css.read_text()}</style>", unsafe_allow_html=True)
    else:
        st.error(f"❌ CSS missing: {path}")
load_css()

# ── Constants ────────────────────────────────────────────────────
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.87.64:11434/v1")
MODEL_NAME   = os.getenv("LLM_MODEL_NAME", "local-model")
TIKA_URL     = os.getenv("TIKA_URL",  "http://tika-server:9998")
TIMEZONE     = pytz.timezone("America/Los_Angeles")

TEMPERATURE, TOP_K, TOP_P = 1.0, 64, 0.95
MIN_P, XTC_THRESHOLD, REPEAT_PENALTY = 0.0, 1.0, 1.0

# ── External services ────────────────────────────────────────────
os.environ["TIKA_CLIENT_ONLY"] = "true"
try:
    tika.initVM();  TIKA_OK = True
except TikaException:
    TIKA_OK = False

# ── Session defaults (uploader_key seeded!) ──────────────────────
for k, v in {
    "messages":      [],
    "pending_files": [],
    "show_uploader": False,
    "uploader_key":  0,          # ← prevents KeyError
}.items():
    st.session_state.setdefault(k, v)

# ── Helper functions ─────────────────────────────────────────────
def backend_up() -> bool:
    base = LLM_BASE_URL.split("/v1")[0]
    for ep in ("", "/api/tags", "/v1/models"):
        try:
            if requests.get(base + ep, timeout=2).ok:
                return True
        except requests.RequestException:
            pass
    return False

def human_timestamp(tz) -> str:
    now = datetime.now(tz)
    fmt = "%-I:%M %p on %A, %B %-d, %Y"
    if os.name == "nt":
        fmt = fmt.replace("%-I", "%#I").replace("%-d", "%#d")
    return now.strftime(fmt)

def preview_text(parts: list) -> str:
    for p in reversed(parts):
        if isinstance(p, dict) and p.get("type") == "text":
            return p["text"]
    return "[Attachment: image / doc]"

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.image("static/UW-HFS-AI.png", use_container_width=True)

    if not backend_up():
        st.error("⚠️ LLM backend offline")

    if st.button("New Conversation", use_container_width=True):
        st.session_state.clear();  st.rerun()

    if st.button("Attach Files", use_container_width=True):
        st.session_state.show_uploader = not st.session_state.show_uploader
        st.rerun()

    if st.session_state.show_uploader:
        uploads = st.file_uploader("Select files:",
                                   accept_multiple_files=True,
                                   key=f"uploader_{st.session_state['uploader_key']}")
        if uploads:
            st.session_state.pending_files.clear()
            for f in uploads:
                data = f.getvalue()
                if f.type and f.type.startswith("image/"):
                    st.session_state.pending_files.append({
                        "name": f.name, "type": "image", "mime": f.type,
                        "data": base64.b64encode(data).decode(),
                    })
                else:
                    if not TIKA_OK:
                        st.warning("📄 Document parsing unavailable");  continue
                    with st.spinner(f"Parsing {f.name}…"):
                        try:
                            parsed = parser.from_buffer(data, serverEndpoint=TIKA_URL)
                            txt = parsed.get("content", "").strip()
                            if txt:
                                st.session_state.pending_files.append({
                                    "name": f.name, "type": "doc", "data": txt,
                                })
                            else:
                                st.warning(f"⚠️ {f.name}: no text found")
                        except Exception as e:
                            st.error(f"❌ {f.name}: {str(e)[:100]}")
            # bump uploader_key SAFELY
            st.session_state["uploader_key"] = st.session_state.get("uploader_key", 0) + 1
            st.session_state.show_uploader = False
            st.rerun()

    if st.session_state.pending_files:
        st.markdown("---");  st.markdown("**Attached:**")
        for i, f in enumerate(st.session_state.pending_files):
            col1, col2 = st.columns([4,1])
            with col1:
                icon = "🖼️" if f["type"] == "image" else "📄"
                st.markdown(f"{icon} {f['name']}")
            with col2:
                if st.button("❌", key=f"del_{i}", help=f"Remove {f['name']}"):
                    st.session_state.pending_files.pop(i);  st.rerun()

# ── Main chat ────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown(
        "<div class='welcome-text' style='font-size:2.2em;font-weight:500;'>"
        "Welcome to <span class='hfs'>HFS</span><span class='ai'>-ai</span>"
        "</div>", unsafe_allow_html=True)

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"] if isinstance(m["content"], str)
                    else preview_text(m["content"]))

if prompt := st.chat_input("Ask me anything…"):
    with st.chat_message("user"): st.markdown(prompt)

    system_prompt = (
        "You are HFS-ai, a helpful, neutral assistant.\n"
        f"- Current date/time: {human_timestamp(TIMEZONE)}.\n"
        "- Use only provided context; do not fabricate details."
    )

    msgs = [{"role": "system", "content": system_prompt},
            *st.session_state.messages]
    user_msg = {"role": "user", "content": prompt}

    # Attachments (optional)
    if st.session_state.pending_files:
        parts = []
        docs = [f for f in st.session_state.pending_files if f["type"] == "doc"]
        if docs:
            doc_ctx = "\n\n".join(f"--- {d['name']} ---\n{d['data']}" for d in docs)
            parts.append({"type":"text","text":f"Context:\n{doc_ctx}"})
        for f in st.session_state.pending_files:
            if f["type"] == "image":
                parts.append({"type":"image_url",
                              "image_url":{"url":f"data:{f['mime']};base64,{f['data']}"},
                             })
        parts.append({"type":"text","text":prompt})
        user_msg["content"] = parts

    st.session_state.messages.append(user_msg)
    st.session_state.pending_files.clear()
    msgs.append(user_msg)

    # Call the LLM
    with st.chat_message("assistant"), st.spinner("Thinking…"):
        try:
            client = OpenAI(base_url=LLM_BASE_URL, api_key="not-needed")
            acc, box = "", st.empty()
            stream = client.chat.completions.create(
                model=MODEL_NAME, messages=msgs, stream=True,
                temperature=TEMPERATURE, top_p=TOP_P,
                extra_body={
                    "top_k": TOP_K, "min_p": MIN_P,
                    "xtc_threshold": XTC_THRESHOLD,
                    "repeat_penalty": REPEAT_PENALTY,
                },
            )
            for chunk in stream:
                acc += chunk.choices[0].delta.content or ""
                box.markdown(acc + "▌")
            box.markdown(acc)
            st.session_state.messages.append({"role":"assistant","content":acc})
            st.rerun()
        except Exception as e:
            st.error(f"❌ LLM API: {e}")
