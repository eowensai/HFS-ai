"""Supported Streamlit 1.56 session resource lifecycle; no global cache clears."""
import streamlit as st

from ephemeral.privacy import ConversationMessages, ConversationPayloads
from ephemeral.turn_options import reset_thinking_mode


@st.cache_resource(scope="session", on_release=ConversationPayloads.release,
                   show_spinner=False)
def conversation_payloads():
    return ConversationPayloads()


def prepare_conversation():
    owner = conversation_payloads()
    messages = st.session_state.get("messages", [])
    if not isinstance(messages, ConversationMessages) or messages.owner is not owner:
        st.session_state["messages"] = ConversationMessages(owner, messages)
    for key in ("_tika_cache", "_token_count_cache"):
        if key in st.session_state:
            owner.own(st.session_state[key])
    return owner


def reset_conversation():
    """Drop only this conversation, including legacy caches and composer values."""
    conversation_payloads.clear()
    for key in ("messages", "_tika_cache", "_token_count_cache", "main_chat"):
        st.session_state.pop(key, None)
    st.session_state["show_welcome"] = True
    st.session_state["last_token_count"] = 0
    st.session_state["tokenizer_available"] = None
    st.session_state["_vision_supported"] = None
    reset_thinking_mode(st.session_state)
    prepare_conversation()


def detach_framework_uploads(files):
    """Drop submitted originals from Streamlit's session-specific upload manager.

    Pinned Streamlit 1.56 API: remove only the current session's submitted IDs.
    The worker owns the UploadedFile wrappers until preparation closes them.
    """
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    ctx = get_script_run_ctx()
    if ctx is not None:
        remove = getattr(ctx.uploaded_file_mgr, 'remove_file', None)
        if remove is not None:
            for upload in files:
                if getattr(upload, 'file_id', None):
                    remove(ctx.session_id, upload.file_id)
