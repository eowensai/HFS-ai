import streamlit as st
import requests
from tika import parser

from ephemeral.config import TIKA_TIMEOUT_S, TIKA_URL


@st.cache_data(ttl=5, show_spinner=False)
def tika_alive() -> bool:
    """Lightweight health check for the Tika server."""
    try:
        base = TIKA_URL.rstrip("/")
        endpoints = (f"{base}/tika", f"{base}/version", base)
        for url in endpoints:
            r = requests.get(url, timeout=2)
            if r.ok:
                return True
        return False
    except Exception:
        return False


def parse_with_tika(data: bytes, filename: str) -> str:
    """Parse in memory. Conversation messages own the result; no duplicate cache."""
    with st.spinner(f"Reading {filename}…"):
        # The pinned Tika client supports requestOptions. Never retry without
        # the timeout: an API mismatch should fail visibly, not retain buffers.
        parsed = parser.from_buffer(
            data,
            serverEndpoint=TIKA_URL,
            requestOptions={"timeout": TIKA_TIMEOUT_S},
        )

    text = (parsed.get("content") or "").strip()
    return text
