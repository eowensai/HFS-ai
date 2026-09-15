import json

import pytest

from ephemeral import config, vllm_backend as adapter
from ephemeral.token_budget import ContextError


@pytest.mark.parametrize("profile", ["mtp", "dflash"])
def test_pinned_profile_manifest_and_wrong_draft_rejected(
    tmp_path, monkeypatch, profile
):
    value = {
        "model": config.PINNED_VLLM_MODEL_NAME,
        "model_revision": config.PINNED_VLLM_MODEL_REVISION,
        "context": 131072,
        "kv_cache": "fp8_e4m3",
        "engine_image_id": "sha256:" + "a" * 64,
        "inference_profile": profile,
    }
    if profile == "mtp":
        value["mtp_tokens"] = 3
        wrong = "mtp_tokens"
    else:
        value.update(
            speculative_method="dflash",
            speculative_tokens=7,
            draft_model_revision="4d30ec736ffc6b8688dc2ae2b502d9b48bdec279",
            draft_embedding="int4-group32-fp16-scales-bf16-mask",
        )
        wrong = "draft_model_revision"
    path = tmp_path / "deployment.json"
    monkeypatch.setattr(config, "LLM_DEPLOYMENT_MANIFEST", str(path))
    path.write_text(json.dumps(value))
    assert adapter.manifest() == value
    value[wrong] = "unexpected"
    path.write_text(json.dumps(value))
    with pytest.raises(ContextError):
        adapter.manifest()


@pytest.fixture
def identity(monkeypatch):
    value = {
        "model": config.PINNED_VLLM_MODEL_NAME,
        "model_revision": config.PINNED_VLLM_MODEL_REVISION,
        "context": 131072,
        "kv_cache": "fp8_e4m3",
        "mtp_tokens": 3,
        "engine_image_id": "sha256:" + "a" * 64,
    }
    monkeypatch.setattr(adapter, "manifest", lambda: value)
    monkeypatch.setattr(config, "LLM_MODEL_NAME", value["model"])
    monkeypatch.setattr(config, "LLM_BACKEND", "vllm")
    return value


def request(identity):
    return {
        "model": identity["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,fixture"},
                    }
                ],
            }
        ],
        "max_tokens": 32768,
        "extra_body": {"reasoning_effort": "xhigh"},
    }


def test_exact_multimodal_budget_and_output_reserve(monkeypatch, identity):
    seen = {}

    def reply(method, path, **kwargs):
        seen.update(method=method, path=path, **kwargs)
        return {"count": 100001}

    monkeypatch.setattr(adapter, "_json", reply)
    req = request(identity)
    budget = adapter.measure(req, 131072, 32768)
    assert budget.input_tokens == 100001 and not budget.fits
    assert budget.reserve_tokens == 32768
    assert seen["body"]["messages"] == req["messages"]
    assert seen["body"]["chat_template_kwargs"] == {
        "enable_thinking": True,
        "reasoning_effort": "xhigh",
    }
    assert seen["path"] == "/tokenize"


@pytest.mark.parametrize("count", [True, "123", -1, None])
def test_invalid_count_never_uses_estimate(monkeypatch, identity, count):
    monkeypatch.setattr(adapter, "_json", lambda *a, **k: {"count": count})
    with pytest.raises(ContextError):
        adapter.measure(request(identity), 131072, 32768)


def test_wrong_request_model_rejected_before_network(monkeypatch, identity):
    monkeypatch.setattr(
        adapter, "_json", lambda *a, **k: pytest.fail("Unexpected network call")
    )
    req = request(identity)
    req["model"] = "another-model"
    with pytest.raises(ContextError):
        adapter.measure(req, 131072, 32768)


class Response:
    def __init__(self, payload=b"{}"):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def raise_for_status(self):
        return None

    def iter_content(self, size):
        yield self.payload


def test_wrong_running_context_fails_readiness(monkeypatch, identity):
    monkeypatch.setattr(adapter.requests, "get", lambda *a, **k: Response())
    monkeypatch.setattr(
        adapter,
        "_json",
        lambda *a, **k: {"data": [{"id": identity["model"], "max_model_len": 65536}]},
    )
    assert not adapter.alive()


def test_large_tokenizer_reply_is_bounded(monkeypatch):
    monkeypatch.setattr(
        adapter.requests, "request", lambda *a, **k: Response(b"x" * 65)
    )
    with pytest.raises(ContextError):
        adapter._json("GET", "/v1/models", limit=64)


def test_manifest_requires_exact_revision(tmp_path, monkeypatch):
    p = tmp_path / "deployment.json"
    p.write_text(
        json.dumps({"model": config.PINNED_VLLM_MODEL_NAME, "model_revision": "wrong"})
    )
    monkeypatch.setattr(config, "LLM_DEPLOYMENT_MANIFEST", str(p))
    with pytest.raises(ContextError):
        adapter.manifest()


def test_vllm_request_matches_measured_template_and_sampler(monkeypatch):
    from ephemeral import llm_client

    monkeypatch.setattr(config, "LLM_BACKEND", "vllm")
    for thinking, effort in [(False, "medium"), (True, "xhigh")]:
        req = llm_client.build_chat_completion_request(
            [{"role": "user", "content": "hello"}], thinking
        )
        assert req["extra_body"]["chat_template_kwargs"] == {
            "enable_thinking": True,
            "reasoning_effort": effort,
        }
        assert req["extra_body"]["top_k"] == 20
        assert req["extra_body"]["min_p"] == 0.0
        assert req["extra_body"]["repetition_penalty"] == 1.0
        assert req["max_tokens"] == 32768


def test_packaged_public_tokenizer_loads_without_backend():
    tokenizer = adapter.raw_text_tokenizer()
    assert tokenizer.count("hello") > 0
