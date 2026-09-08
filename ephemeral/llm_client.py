import hashlib
import logging
import re
from collections import OrderedDict
from typing import Any, Dict, Optional

import requests
import streamlit as st
from openai import OpenAI

from ephemeral.config import (
    ENABLE_TOKEN_BUDGETING,
    IMG_TOKEN_COST_DEFAULT,
    LLM_BASE_URL,
    LLM_CONTEXT_TOKENS,
    LLM_MAX_RETRIES,
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
    TOKENIZE_TIMEOUT_S,
    _ollama_base_url,
    reasoning_effort_for_turn,
)
from ephemeral.token_budget import _heuristic_token_estimate


@st.cache_data(ttl=5, show_spinner=False)
def llm_alive() -> bool:
    """
    Return True only when the required immutable alias and profile are present.

    A generic Ollama health response is insufficient: EphemerAI must fail closed
    instead of silently sending a turn to a missing or retargeted model alias.
    """
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


# ── Cached OpenAI client ──────────────────────────────────────────
@st.cache_resource
def get_llm_client() -> OpenAI:
    """Return a cached OpenAI client instance configured for the backend."""
    return OpenAI(
        base_url=LLM_BASE_URL,
        api_key="not-needed",
        timeout=LLM_REQUEST_TIMEOUT_S,
        max_retries=LLM_MAX_RETRIES,
    )


def build_chat_completion_request(
    messages: list[dict], thinking_mode_enabled: bool
) -> dict[str, Any]:
    """Build the exact shared-profile request for one EphemerAI turn."""
    return {
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


@st.cache_data(ttl=60, show_spinner=False)
def get_model_ctx() -> Optional[int]:
    """
    Return model context tokens for app-side budgeting.

    If LLM_CONTEXT_TOKENS is set to a positive integer, that value is used first
    as an application budgeting override (it does not change Ollama runtime model settings).
    Otherwise, context is discovered from Ollama /api/show metadata.
    """
    if LLM_CONTEXT_TOKENS:
        return LLM_CONTEXT_TOKENS

    payload = _ollama_show()
    if not payload:
        return None

    parameters = payload.get("parameters")
    if isinstance(parameters, str):
        match = re.search(r"\bnum_ctx\s+(\d+)", parameters)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass

    model_info = payload.get("model_info") or {}

    for key in ("num_ctx", "context_length"):
        value = model_info.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    for key, value in model_info.items():
        if isinstance(key, str) and key.endswith(".context_length"):
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)

    return None


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

    If ENABLE_TOKEN_BUDGETING is on, we try Ollama /api/tokenize.
    If unavailable or slow, we silently fall back to a heuristic.

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

    if not ENABLE_TOKEN_BUDGETING:
        n = _heuristic_token_estimate(text)
        _cache_put(cache, key, n)
        return n

    if st.session_state.get("tokenizer_available") is False:
        n = _heuristic_token_estimate(text)
        _cache_put(cache, key, n)
        return n

    tokenize_url = f"{_ollama_base_url()}/api/tokenize"
    try:
        resp = requests.post(
            tokenize_url,
            json={"model": LLM_MODEL_NAME, "content": text},
            timeout=TOKENIZE_TIMEOUT_S,
        )

        if resp.status_code == 404:
            st.session_state["tokenizer_available"] = False
            n = _heuristic_token_estimate(text)
            _cache_put(cache, key, n)
            return n

        resp.raise_for_status()
        payload = resp.json()

        tokens = payload.get("tokens")
        tokenizer_ok = True
        if isinstance(tokens, list):
            n = len(tokens)
        elif isinstance(tokens, int):
            n = tokens
        elif isinstance(tokens, str) and tokens.isdigit():
            n = int(tokens)
        else:
            tokenizer_ok = False
            n = _heuristic_token_estimate(text)

        st.session_state["tokenizer_available"] = tokenizer_ok
        _cache_put(cache, key, n)
        return n
    except Exception:
        st.session_state["tokenizer_available"] = False
        n = _heuristic_token_estimate(text)
        _cache_put(cache, key, n)
        return n
