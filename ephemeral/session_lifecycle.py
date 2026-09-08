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
