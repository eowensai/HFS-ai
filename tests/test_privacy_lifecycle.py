"""Fictional regression cases; no operational documents or model requests."""
import io
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest
from test_ephemeral_app import _install_synthetic_backend, _submit, settle

from ephemeral.privacy import (
    ConversationMessages,
    ConversationPayloads,
    ConversationTokenCache,
)

ROOT = Path(__file__).resolve().parents[1]


def test_release_drops_payloads_and_rejects_late_responses():
    owner = ConversationPayloads()
    messages = ConversationMessages(owner, [{"content": "Fictional document"}])
    cache = owner.own({"fictional-hash": (0, "Fictional parsed text")})
    upload = owner.own(io.BytesIO(b"Fictional upload"))
    other = ConversationMessages(ConversationPayloads(), [{"content": "Other user"}])
    owner.release()
    owner.release()  # Idempotent across disconnect and explicit reset.
    messages.append({"content": "Late fictional response"})
    late = owner.own({"content": "Late parsed text"})
    assert not messages and not cache and not late
    assert upload.closed
    assert other == [{"content": "Other user"}]


def test_late_token_result_cannot_repopulate_released_cache():
    from ephemeral.llm_client import _cache_put
    owner = ConversationPayloads()
    cache = ConversationTokenCache(owner)
    _cache_put(cache, "fictional-hash", 12)
    owner.release()
    _cache_put(cache, "late-fictional-hash", 34)
    assert not cache


def test_new_chat_clears_owned_payloads_and_preserves_another_session(monkeypatch):
    # AppTest hardcodes one session ID; supply distinct identities to the real
    # resource cache. The browser regression also checks actual WebSockets.
    from streamlit.runtime.caching import cache_resource_api
    identity = ["fictional-first"]
    monkeypatch.setattr(cache_resource_api, "get_session_id_or_throw", lambda: identity[0])
    calls = []
    _install_synthetic_backend(monkeypatch, calls)
    first = AppTest.from_file(str(ROOT / "ephemeral_app.py")).run()
    identity[0] = "fictional-second"
    second = AppTest.from_file(str(ROOT / "ephemeral_app.py")).run()
    identity[0] = "fictional-first"
    _submit(first, "First fictional conversation")
    identity[0] = "fictional-second"
    _submit(second, "Second fictional conversation")
    old_messages = first.session_state["messages"]
    old_parse = {"fictional": (0, "Fictional legacy parse")}
    old_tokens = {"fictional-hash": 12}
    first.session_state["_tika_cache"] = old_parse
    first.session_state["_token_count_cache"] = old_tokens
    first.session_state["operator_preference"] = "preserved"
    identity[0] = "fictional-first"
    first.run()  # Adopt legacy caches into this session's lifecycle owner.
    first.button(key="sidebar_new").click().run()
    assert not first.exception
    assert not old_messages and not old_parse and not old_tokens
    assert not first.session_state["messages"]
    assert "_tika_cache" not in first.session_state
    assert "_token_count_cache" not in first.session_state
    assert first.session_state["operator_preference"] == "preserved"
    assert second.session_state["messages"]
    identity[0] = "fictional-second"
    second.run()
    assert not second.exception and second.session_state["messages"]
    identity[0] = "fictional-first"
    _submit(first, "New fictional conversation")
    assert calls[-1]["extra_body"]["reasoning_effort"] == "medium"
    assert "First fictional conversation" not in str(calls[-1]["messages"])


def test_uploaded_buffers_close_on_new_chat(monkeypatch):
    import streamlit as st
    calls = []
    _install_synthetic_backend(monkeypatch, calls)
    from ephemeral import tika_client
    monkeypatch.setattr(tika_client, "parse_with_tika", lambda *a, **k: tika_client.ParsedText("Fictional document"))
    upload = io.BytesIO(b"fictional document")
    upload.name, upload.type, upload.size = "fictional.txt", "text/plain", 18
    pending = [SimpleNamespace(text="Read fictional file", files=[upload])]
    monkeypatch.setattr(st, "chat_input", lambda *a, **k: pending.pop() if pending else None)
    app = AppTest.from_file(str(ROOT / "ephemeral_app.py")).run()
    settle(app)
    assert not app.exception and calls
    app.button(key="sidebar_new").click().run()
    assert not app.exception and upload.closed
    assert not app.session_state["messages"]
