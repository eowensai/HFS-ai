"""Pinned local vLLM readiness and exact multimodal request admission.

Only public deployment/tokenizer metadata is cached. Request content and token
lists are transient; failures never fall back to an estimated context budget.
"""

import gzip
import json
from pathlib import Path

import requests

from ephemeral import config
from ephemeral.token_budget import ContextError, RequestBudget


def enabled():
    return config.LLM_BACKEND == "vllm"


def manifest():
    try:
        value = json.loads(Path(config.LLM_DEPLOYMENT_MANIFEST).read_text())
        expected = {
            "model": config.PINNED_VLLM_MODEL_NAME,
            "model_revision": config.PINNED_VLLM_MODEL_REVISION,
            "context": 131072,
            "kv_cache": "fp8_e4m3",
        }
        if any(value.get(k) != v for k, v in expected.items()):
            raise ValueError("Deployment differs from the pinned profile")
        profile = value.get("inference_profile", "mtp")
        if profile == "mtp":
            if value.get("mtp_tokens") != 3:
                raise ValueError("MTP profile differs")
        elif profile == "dflash":
            if (value.get("speculative_method") != "dflash"
                    or value.get("speculative_tokens") != 7
                    or value.get("draft_model_revision") != "4d30ec736ffc6b8688dc2ae2b502d9b48bdec279"
                    or value.get("draft_embedding") != "int4-group32-fp16-scales-bf16-mask"):
                raise ValueError("DFlash profile differs")
        else:
            raise ValueError("Unqualified inference profile")
        if not value.get("engine_image_id", "").startswith("sha256:"):
            raise ValueError("Missing immutable engine identity")
        return value
    except (OSError, ValueError, TypeError, AttributeError):
        raise ContextError("Model deployment identity could not be verified.") from None


def _json(method, path, *, body=None, limit=8 * 1024 * 1024):
    base = config.LLM_BASE_URL.rstrip("/").removesuffix("/v1")
    try:
        with requests.request(
            method, base + path, json=body, stream=True, timeout=(5, 30)
        ) as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_content(64 * 1024):
                if len(raw) + len(chunk) > limit:
                    raise ValueError("Metadata response exceeded its limit")
                raw.extend(chunk)
        return json.loads(raw)
    except (requests.RequestException, ValueError, TypeError):
        raise ContextError("Model metadata or token counting is unavailable.") from None


def runtime_context():
    identity = manifest()
    if (
        identity["model"] != config.LLM_MODEL_NAME
        or identity["context"] != config.LLM_CONTEXT_TOKENS
    ):
        raise ContextError("Model configuration differs from its verified deployment.")
    try:
        base = config.LLM_BASE_URL.rstrip("/").removesuffix("/v1")
        with requests.get(base + "/health", timeout=5) as response:
            response.raise_for_status()
        models = _json("GET", "/v1/models", limit=64 * 1024)["data"]
        matches = [m for m in models if m.get("id") == identity["model"]]
        if len(matches) != 1 or matches[0].get("max_model_len") != identity["context"]:
            raise ValueError("Wrong model or capacity")
        return identity["context"]
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
        raise ContextError(
            "The required model and running context are unavailable."
        ) from None


def alive():
    try:
        return runtime_context() == 131072
    except ContextError:
        return False


def measure(request, capacity, reserve):
    identity = manifest()
    if request.get("model") != identity["model"] or capacity != identity["context"]:
        raise ContextError("Request does not match the verified model deployment.")
    body = {
        "model": request["model"],
        "messages": request["messages"],
        "add_generation_prompt": True,
        "chat_template_kwargs": {
            "enable_thinking": True,
            "reasoning_effort": request.get("extra_body", {}).get(
                "reasoning_effort", "medium"
            ),
        },
    }
    result = _json("POST", "/tokenize", body=body)
    count = result.get("count") if isinstance(result, dict) else None
    if type(count) is not int or count < 0:
        raise ContextError("Model token counting returned an invalid result.")
    return RequestBudget(count, max(reserve, request["max_tokens"]), capacity)


def raw_text_tokenizer():
    from ephemeral.model_tokenizer import ModelTokenizer

    try:
        return ModelTokenizer(
            json.loads(gzip.decompress(
                (Path(__file__).parent / "assets/qwen-tokenizer.json.gz").read_bytes()
            ))
        )
    except (OSError, ValueError, KeyError, TypeError):
        raise ContextError("The required model tokenizer is unavailable.") from None
