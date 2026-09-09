import hashlib
import json
from collections import OrderedDict
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI


def _token_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def test_cache_eviction_is_partial_not_total():
    """Eviction should remove the oldest quarter, not clear the whole cache."""
    from ephemeral import llm_client

    cache = OrderedDict()
    max_entries = llm_client.TOKEN_CACHE_MAX_ENTRIES
    evict_count = max(1, max_entries // 4)

    for i in range(max_entries + 4):
        llm_client._cache_put(cache, str(i), i)

    assert len(cache) == max_entries + 4 - evict_count
    assert "0" not in cache
    assert str(max_entries + 3) in cache


def test_get_token_cache_migrates_plain_dict(monkeypatch):
    """_get_token_cache should upgrade a plain dict to OrderedDict."""
    from ephemeral import llm_client

    session = {"_token_count_cache": {"x": 10}}
    monkeypatch.setattr(llm_client, "st", SimpleNamespace(session_state=session))

    result = llm_client._get_token_cache()

    assert isinstance(result, OrderedDict)
    assert result["x"] == 10
    assert session["_token_count_cache"] is result


def test_count_text_tokens_cache_hit_promotes_entry(monkeypatch):
    """count_text_tokens should promote a cache hit to most-recently-used."""
    from ephemeral import llm_client

    key_a = _token_key("a")
    key_b = _token_key("b")
    session = {
        "_token_count_cache": OrderedDict([(key_a, 1), (key_b, 2)]),
        "tokenizer_available": False,
    }
    monkeypatch.setattr(llm_client, "st", SimpleNamespace(session_state=session))

    assert llm_client.count_text_tokens("a") == 1
    assert list(session["_token_count_cache"].keys()) == [key_b, key_a]


def test_token_estimator_never_calls_an_unsupported_tokenizer_route(monkeypatch):
    from ephemeral import llm_client
    session = {"_token_count_cache": OrderedDict(), "tokenizer_available": None}
    monkeypatch.setattr(llm_client, "st", SimpleNamespace(session_state=session))
    def unexpected_request(*a, **k):
        pytest.fail("Text must not be sent to an unsupported tokenizer route")
    monkeypatch.setattr(llm_client.requests, "post", unexpected_request)
    assert llm_client.count_text_tokens("hello") == 5
    assert session["tokenizer_available"] is False


def _valid_pinned_model_payloads(llm_client, *, tagged=True):
    name = llm_client.LLM_MODEL_NAME + (":latest" if tagged else "")
    details = {
        "family": llm_client.PINNED_LLM_MODEL_FAMILY,
        "parameter_size": llm_client.PINNED_LLM_MODEL_PARAMETER_SIZE,
        "quantization_level": llm_client.PINNED_LLM_MODEL_QUANTIZATION,
        # Construction history is deliberately not part of identity validation.
        "parent_model": "removed-benchmark-alias:latest",
    }
    tags = {
        "models": [
            {
                "name": name,
                "model": name,
                "digest": llm_client.PINNED_LLM_MODEL_DIGEST,
                "details": dict(details),
            }
        ]
    }
    show = {
        "details": dict(details),
        "capabilities": ["completion", "tools", "thinking", "vision"],
    }
    return tags, show


@pytest.mark.parametrize("tagged", [False, True])
def test_llm_alive_accepts_exact_manifest_with_optional_latest_tag(tagged):
    from ephemeral import llm_client

    tags, show = _valid_pinned_model_payloads(llm_client, tagged=tagged)
    assert llm_client.model_matches_pinned_profile(tags, show) is True


def test_llm_alive_rejects_missing_or_ambiguous_alias():
    from ephemeral import llm_client

    tags, show = _valid_pinned_model_payloads(llm_client)
    tags["models"][0]["name"] = "some-other-model:latest"
    tags["models"][0]["model"] = "some-other-model:latest"
    assert llm_client.model_matches_pinned_profile(tags, show) is False

    tags, show = _valid_pinned_model_payloads(llm_client)
    tags["models"].append(dict(tags["models"][0]))
    assert llm_client.model_matches_pinned_profile(tags, show) is False


@pytest.mark.parametrize("digest", ["0" * 64, "44d415f1e36e"])
def test_llm_alive_rejects_wrong_or_short_digest(digest):
    from ephemeral import llm_client

    tags, show = _valid_pinned_model_payloads(llm_client)
    tags["models"][0]["digest"] = digest
    assert llm_client.model_matches_pinned_profile(tags, show) is False


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("family", "qwen3"),
        ("parameter_size", "35B"),
        ("quantization_level", "Q5_K_S"),
    ],
)
@pytest.mark.parametrize("payload_name", ["tags", "show"])
def test_llm_alive_rejects_wrong_model_metadata(field, wrong_value, payload_name):
    from ephemeral import llm_client

    tags, show = _valid_pinned_model_payloads(llm_client)
    payload = tags["models"][0] if payload_name == "tags" else show
    payload["details"][field] = wrong_value
    assert llm_client.model_matches_pinned_profile(tags, show) is False


@pytest.mark.parametrize("capability", ["completion", "thinking", "vision"])
def test_llm_alive_rejects_missing_required_capability(capability):
    from ephemeral import llm_client

    tags, show = _valid_pinned_model_payloads(llm_client)
    show["capabilities"].remove(capability)
    assert llm_client.model_matches_pinned_profile(tags, show) is False


@pytest.mark.parametrize("capabilities", [None, "vision", ["completion", ["vision"]]])
def test_llm_alive_rejects_malformed_capabilities(capabilities):
    from ephemeral import llm_client

    tags, show = _valid_pinned_model_payloads(llm_client)
    show["capabilities"] = capabilities
    assert llm_client.model_matches_pinned_profile(tags, show) is False


def test_llm_alive_fails_closed_when_either_api_probe_fails(monkeypatch):
    from ephemeral import llm_client

    tags, show = _valid_pinned_model_payloads(llm_client)
    llm_client.llm_alive.clear()
    monkeypatch.setattr(llm_client, "_ollama_tags", lambda: None)
    monkeypatch.setattr(llm_client, "_ollama_show", lambda: show)
    assert llm_client.llm_alive() is False

    llm_client.llm_alive.clear()
    monkeypatch.setattr(llm_client, "_ollama_tags", lambda: tags)
    monkeypatch.setattr(llm_client, "_ollama_show", lambda: None)
    assert llm_client.llm_alive() is False
    llm_client.llm_alive.clear()


def test_ollama_tags_probe_returns_none_on_non_ok_or_exception(monkeypatch):
    from ephemeral import llm_client

    llm_client._ollama_tags.clear()
    monkeypatch.setattr(
        llm_client.requests,
        "get",
        lambda *args, **kwargs: SimpleNamespace(ok=False),
    )
    assert llm_client._ollama_tags() is None

    def fail(*args, **kwargs):
        raise llm_client.requests.ConnectionError("synthetic connection failure")

    llm_client._ollama_tags.clear()
    monkeypatch.setattr(llm_client.requests, "get", fail)
    assert llm_client._ollama_tags() is None
    llm_client._ollama_tags.clear()


def test_request_builder_uses_exact_profile_and_turn_reasoning(monkeypatch):
    from ephemeral import llm_client

    monkeypatch.setattr(
        llm_client,
        "LLM_MODEL_NAME",
        "hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072",
    )
    monkeypatch.setattr(llm_client, "LLM_TEMPERATURE", 1.0)
    monkeypatch.setattr(llm_client, "LLM_TOP_P", 0.95)
    monkeypatch.setattr(llm_client, "LLM_PRESENCE_PENALTY", 0.0)
    monkeypatch.setattr(llm_client, "LLM_MAX_TOKENS", 32768)

    messages = [{"role": "user", "content": "Synthetic test question"}]
    default_request = llm_client.build_chat_completion_request(messages, False)
    thinking_request = llm_client.build_chat_completion_request(messages, True)

    assert default_request == {
        "model": "hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072",
        "messages": messages,
        "stream": True,
        "temperature": 1.0,
        "top_p": 0.95,
        "presence_penalty": 0.0,
        "max_tokens": 32768,
        "extra_body": {"reasoning_effort": "medium"},
    }
    assert thinking_request["extra_body"] == {"reasoning_effort": "xhigh"}
    assert thinking_request["max_tokens"] == 32768


@pytest.mark.parametrize(
    "messages",
    [
        pytest.param(
            [{"role": "user", "content": "Synthetic text question"}],
            id="text",
        ),
        pytest.param(
            [{"role": "user", "content": "Context:\nSynthetic upload text"}],
            id="upload",
        ),
        pytest.param(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this synthetic image"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,AA=="},
                        },
                    ],
                }
            ],
            id="image",
        ),
        pytest.param(
            [
                {"role": "user", "content": "Synthetic first turn"},
                {"role": "assistant", "content": "Synthetic prior answer"},
                {"role": "user", "content": "Synthetic follow-up"},
            ],
            id="conversation-history",
        ),
    ],
)
def test_every_default_message_shape_explicitly_uses_medium_reasoning(messages):
    from ephemeral import llm_client

    request = llm_client.build_chat_completion_request(messages, False)

    assert "extra_body" in request
    assert request["extra_body"] == {"reasoning_effort": "medium"}
    assert request["extra_body"]["reasoning_effort"] != "none"


@pytest.mark.parametrize(
    ("thinking_mode_enabled", "expected_effort"),
    [(False, "medium"), (True, "xhigh")],
)
def test_sdk_extra_body_serializes_effort_as_top_level_wire_field(
    thinking_mode_enabled, expected_effort
):
    from ephemeral import llm_client

    wire_bodies = []

    def handle_request(request):
        wire_bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b"data: [DONE]\n\n",
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handle_request))
    client = OpenAI(
        base_url="http://synthetic-ollama.invalid/v1",
        api_key="not-needed",
        http_client=http_client,
    )
    try:
        request_kwargs = llm_client.build_chat_completion_request(
            [{"role": "user", "content": "Synthetic wire-format check"}],
            thinking_mode_enabled,
        )
        list(client.chat.completions.create(**request_kwargs))
    finally:
        client.close()

    assert len(wire_bodies) == 1
    assert wire_bodies[0]["reasoning_effort"] == expected_effort
    assert "extra_body" not in wire_bodies[0]


@pytest.fixture(autouse=True)
def isolated_payload_owner(monkeypatch):
    # Unit tests use a plain mapping, without a Streamlit execution thread.
    from ephemeral import session_lifecycle
    from ephemeral.privacy import ConversationPayloads

    owner = ConversationPayloads()
    monkeypatch.setattr(session_lifecycle, "conversation_payloads", lambda: owner)
