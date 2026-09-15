import hashlib
import logging
import re
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

import httpx
import requests
import streamlit as st
from openai import OpenAI

from ephemeral import vllm_backend
from ephemeral.bounded_transport import BoundedTransport
from ephemeral.config import (
    IMG_TOKEN_COST_DEFAULT,
    LLM_BASE_URL,
    LLM_CONTEXT_TOKENS,
    LLM_MAX_TOKENS,
    LLM_MODEL_NAME,
    LLM_PRESENCE_PENALTY,
    LLM_REQUEST_TIMEOUT_S,
    LLM_SUPPORTS_VISION,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    PINNED_LLM_MODEL_DIGEST,
    PINNED_LLM_MODEL_FAMILY,
    PINNED_LLM_MODEL_PARAMETER_SIZE,
    PINNED_LLM_MODEL_QUANTIZATION,
    PINNED_LLM_REQUIRED_CAPABILITIES,
    TOKEN_CACHE_MAX_ENTRIES,
    _ollama_base_url,
    reasoning_effort_for_turn,
)
from ephemeral.model_tokenizer import ModelTokenizer
from ephemeral.token_budget import (
    ContextError,
    _heuristic_token_estimate,
    budget_request,
)

_tokenizer_lock = threading.Lock()
_model_tokenizer = None


def get_model_tokenizer():
    """Cache public vocabulary only, never conversation text or token IDs.

    One bounded metadata fetch per app process; no inference, model loading,
    disk cache, or per-turn/polling fetch. A failed load is retryable.
    """
    global _model_tokenizer
    with _tokenizer_lock:
        if vllm_backend.enabled():
            if _model_tokenizer is None:
                _model_tokenizer = vllm_backend.raw_text_tokenizer()
            return _model_tokenizer
        if _model_tokenizer is None:
            try:
                started = time.monotonic()
                with requests.get(f'{_ollama_base_url()}/api/version', timeout=5) as version:
                    version.raise_for_status()
                    if version.json().get('version') != '0.32.15':
                        raise ValueError('Unsupported prompt renderer version')
                with requests.post(f'{_ollama_base_url()}/api/show',
                                   json={'model': LLM_MODEL_NAME, 'verbose': True},
                                   stream=True, timeout=(5, 15)) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_content(64 * 1024):
                        if len(data) + len(chunk) > 32 * 1024 * 1024 or time.monotonic() - started > 30:
                            raise ValueError('Tokenizer metadata limit exceeded')
                        data.extend(chunk)
                    import json
                    _model_tokenizer = ModelTokenizer(json.loads(data)['model_info'])
            except (requests.RequestException, ValueError, KeyError, TypeError):
                raise ContextError('Model token counting is unavailable. Request not sent; retry shortly.') from None
        return _model_tokenizer


def measure_model_request(request, capacity, reserve):
    """Canonical admission, supplied with a verified, offline model tokenizer."""
    if vllm_backend.enabled():
        return vllm_backend.measure(request, capacity, reserve)
    try:
        return budget_request(request, capacity, reserve, tokenizer=get_model_tokenizer())
    except (ValueError, KeyError, TypeError):
        raise ContextError('Model token counting is unavailable. Request not sent; retry shortly.') from None


@st.cache_data(ttl=5, show_spinner=False)
def llm_alive() -> bool:
    """
    Return True only when the required immutable alias and profile are present.

    A generic Ollama health response is insufficient: EphemerAI must fail closed
    instead of silently sending a turn to a missing or retargeted model alias.
    """
    if vllm_backend.enabled():
        return vllm_backend.alive()
    return model_matches_pinned_profile(_ollama_tags(), _ollama_show())


def _normalized_model_name(value: object) -> str | None:
    """Normalize Ollama's implicit latest tag without accepting other retargets."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().removesuffix(":latest")


def model_matches_pinned_profile(
    tags_payload: dict | None, show_payload: dict | None
) -> bool:
    """Validate the alias's immutable manifest identity and required Q6 features."""
    if not isinstance(tags_payload, dict) or not isinstance(show_payload, dict):
        return False

    models = tags_payload.get("models")
    if not isinstance(models, list):
        return False

    expected_name = _normalized_model_name(LLM_MODEL_NAME)
    matches = []
    for model in models:
        if not isinstance(model, dict):
            continue
        names = (model.get("name"), model.get("model"))
        if any(_normalized_model_name(name) == expected_name for name in names):
            matches.append(model)

    if len(matches) != 1:
        return False

    model = matches[0]
    if model.get("digest") != PINNED_LLM_MODEL_DIGEST:
        return False

    for payload in (model, show_payload):
        details = payload.get("details")
        if not isinstance(details, dict):
            return False
        if details.get("family") != PINNED_LLM_MODEL_FAMILY:
            return False
        if details.get("parameter_size") != PINNED_LLM_MODEL_PARAMETER_SIZE:
            return False
        if details.get("quantization_level") != PINNED_LLM_MODEL_QUANTIZATION:
            return False

    capabilities = show_payload.get("capabilities")
    if not isinstance(capabilities, list) or not all(
        isinstance(capability, str) for capability in capabilities
    ):
        return False
    return PINNED_LLM_REQUIRED_CAPABILITIES.issubset(set(capabilities))


# ── Request-owned OpenAI client ──────────────────────────────────────────
def get_llm_client() -> OpenAI:
    """A fresh turn-owned connection can be interrupted without harming another turn."""
    from ephemeral.request_abort import RequestAbort
    guard = RequestAbort()
    timeout = httpx.Timeout(LLM_REQUEST_TIMEOUT_S, connect=5.0, pool=5.0)
    transport = BoundedTransport(abort_guard=guard, http2=False,
                                 limits=httpx.Limits(max_connections=1, max_keepalive_connections=0))
    result = OpenAI(
        base_url=LLM_BASE_URL,
        api_key="not-needed",
        timeout=timeout,
        max_retries=0,  # Explicit UI retry only; never duplicate a submission automatically.
        http_client=httpx.Client(transport=transport, timeout=timeout),
    )
    result._ephemerai_abort_guard = guard
    return result


def build_chat_completion_request(
    messages: list[dict], thinking_mode_enabled: bool
) -> dict[str, Any]:
    """Build the exact shared-profile request for one EphemerAI turn."""
    request = {
        "model": LLM_MODEL_NAME,
        "messages": messages,
        "stream": True,
        "temperature": LLM_TEMPERATURE,
        "top_p": LLM_TOP_P,
        "presence_penalty": LLM_PRESENCE_PENALTY,
        "max_tokens": LLM_MAX_TOKENS,
        "extra_body": {
            "reasoning_effort": reasoning_effort_for_turn(thinking_mode_enabled),
        },
    }

    if vllm_backend.enabled():
        request["extra_body"].update(
            top_k=20, min_p=0.0, repetition_penalty=1.0,
            chat_template_kwargs={"enable_thinking": True, "reasoning_effort": reasoning_effort_for_turn(thinking_mode_enabled)},
        )
    return request


# ── Ollama model metadata ─────────────────────────────────────────
@st.cache_data(ttl=5, show_spinner=False)
def _ollama_tags() -> dict | None:
    """Cached wrapper for Ollama /api/tags. Returns JSON dict on success."""
    try:
        tags_url = f"{_ollama_base_url()}/api/tags"
        resp = requests.get(tags_url, timeout=2)
        if resp.ok:
            return resp.json()
    except (requests.RequestException, ValueError) as e:
        logging.debug("Ollama /api/tags probe failed: %s", e)
    return None


@st.cache_data(ttl=60, show_spinner=False)
def _ollama_show() -> Optional[Dict]:
    """Cached wrapper for Ollama /api/show. Returns JSON dict on success, else None."""
    try:
        show_url = f"{_ollama_base_url()}/api/show"
        resp = requests.post(show_url, json={"model": LLM_MODEL_NAME}, timeout=2)
        if resp.ok:
            return resp.json()
    except Exception as e:
        logging.debug("Ollama /api/show probe failed: %s", e)
    return None


@st.cache_data(ttl=60, show_spinner=False)
def model_supports_images() -> bool:
    """
    Return True if the configured model appears to support vision inputs.

    Uses:
      1) LLM_SUPPORTS_VISION env var if provided.
      2) Ollama /api/show capabilities (preferred).
      3) Ollama model_info heuristics as a fallback.
    """
    if vllm_backend.enabled():
        return vllm_backend.alive()
    if LLM_SUPPORTS_VISION is not None:
        return LLM_SUPPORTS_VISION.strip().lower() in {"1", "true", "yes", "y", "on"}

    payload = _ollama_show()
    if not payload:
        return False

    capabilities = payload.get("capabilities")
    if isinstance(capabilities, list) and "vision" in capabilities:
        return True

    model_info = payload.get("model_info") or {}
    for key in model_info.keys():
        if not isinstance(key, str):
            continue
        key_lower = key.lower()
        if "vision" in key_lower or "clip" in key_lower or "projector" in key_lower:
            return True

    return False


def resolve_context(show, running, configured=LLM_CONTEXT_TOKENS):
    """Require alias runtime settings; never substitute the family's maximum."""
    if not isinstance(show, dict) or not isinstance(running, dict):
        raise ContextError('Model context metadata is unavailable. Request not sent; retry shortly.')
    match = re.search(r'^num_ctx\s+(\d+)\s*$', show.get('parameters', ''), re.MULTILINE)
    if not match:
        raise ContextError('The model alias context could not be verified. Request not sent.')
    alias_ctx = int(match.group(1))
    if not alias_ctx or configured > alias_ctx:
        raise ContextError('App context configuration exceeds the model alias context. Request not sent.')
    models = running.get('models')
    if not isinstance(models, list):
        raise ContextError('Running context metadata is unavailable. Request not sent.')
    matches = [m for m in models if isinstance(m, dict) and
               _normalized_model_name(m.get('name', m.get('model'))) == _normalized_model_name(LLM_MODEL_NAME)]
    if not matches:
        # Observed cold start: immutable alias num_ctx is the load configuration.
        return min(configured, alias_ctx)
    if (len(matches) != 1 or matches[0].get('digest') != PINNED_LLM_MODEL_DIGEST or
            matches[0].get('context_length') != alias_ctx):
        raise ContextError('The running model context or identity differs from its alias configuration. Request not sent.')
    return min(configured, alias_ctx)


def get_model_ctx() -> int:
    """Fresh per-request probes; an unavailable ps probe is not a cold start."""
    if vllm_backend.enabled():
        return vllm_backend.runtime_context()
    try:
        with requests.post(f'{_ollama_base_url()}/api/show', json={'model': LLM_MODEL_NAME}, timeout=5) as response:
            response.raise_for_status()
            show = response.json()
        with requests.get(f'{_ollama_base_url()}/api/ps', timeout=5) as response:
            response.raise_for_status()
            running = response.json()
        return resolve_context(show, running)
    except (requests.RequestException, ValueError, TypeError) as exc:
        if isinstance(exc, ContextError):
            raise
        raise ContextError('Model context metadata is unavailable. Request not sent; retry shortly.') from exc


@st.cache_data(ttl=60, show_spinner=False)
def get_image_token_cost() -> int:
    """Return tokens-per-image if provided by model metadata, else default."""
    payload = _ollama_show()
    if not payload:
        return IMG_TOKEN_COST_DEFAULT

    model_info = payload.get("model_info") or {}
    for key, value in model_info.items():
        if not isinstance(key, str):
            continue
        if key.endswith("mm.tokens_per_image"):
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)

    return IMG_TOKEN_COST_DEFAULT


# ── Token counting ────────────────────────────────────────────────
def _get_token_cache() -> OrderedDict:
    """Return the session-scoped LRU token cache, creating it if needed."""
    from ephemeral.privacy import ConversationTokenCache
    from ephemeral.session_lifecycle import conversation_payloads

    owner = conversation_payloads()
    cache = st.session_state.get("_token_count_cache", {})
    if not isinstance(cache, ConversationTokenCache) or cache.owner is not owner:
        cache = ConversationTokenCache(owner, cache)
        st.session_state["_token_count_cache"] = cache
    return cache


def _cache_put(cache: OrderedDict, key: str, value: int) -> None:
    """Insert only while the conversation is live, preserving the LRU bound."""
    from contextlib import nullcontext

    owner = getattr(cache, "owner", None)
    with owner._lock if owner else nullcontext():
        if owner and owner.released:
            return
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > TOKEN_CACHE_MAX_ENTRIES:
            evict_count = max(1, TOKEN_CACHE_MAX_ENTRIES // 4)
            for _ in range(evict_count):
                cache.popitem(last=False)


def count_text_tokens(text: str) -> int:
    """
    Best-effort token count for text.

    Use the documented conservative UTF-8-byte estimator.
    Full request admission is handled separately by budget_request.

    UX rule: this function must not show user-facing warnings.
    """
    if not text:
        return 0

    cache = _get_token_cache()

    key = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    # Disconnect cleanup can run concurrently with token lookup.
    with cache.owner._lock:
        if key in cache:
            cache.move_to_end(key)
            return cache[key]

    # Verified against Ollama 0.32.15 routes: /api/tokenize is not public.
    # No document content is sent to metadata/tokenization probes.
    st.session_state["tokenizer_available"] = False
    n = _heuristic_token_estimate(text)
    _cache_put(cache, key, n)
    return n
