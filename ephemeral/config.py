import os
from typing import Optional

APP_VERSION = "1.9.0"

# Prefix used for synthetic context blocks injected into user messages.
# We use a flag (_synthetic) to identify these, not string matching.
CONTEXT_PREFIX = "Context:\n"

# TTL for session-scoped Tika parse cache (seconds)

# Token estimation behavior
TOKEN_HEURISTIC_CHARS_PER_TOKEN = 3.5
TOKEN_CACHE_MAX_ENTRIES = 256
TOKENIZE_TIMEOUT_S = 2.0  # keep UI snappy; budgeting degrades silently if tokenize is slow/unavailable

# Debug mode (shows technical status in sidebar, and error detail expanders)
DEBUG_MODE = os.getenv("EPHEMERAL_DEBUG", "0").strip().lower() in {"1", "true", "yes", "y", "on"}

# Feature toggle (operator-only)
ENABLE_TOKEN_BUDGETING = os.getenv("ENABLE_TOKEN_BUDGETING", "1").strip().lower() not in {"0", "false", "no"}

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://ollama:11434/v1")
TIKA_URL = os.getenv("TIKA_URL", "http://tika-server:9998")
LLM_SUPPORTS_VISION = os.getenv("LLM_SUPPORTS_VISION")

# HFS Knowledge and EphemerAI deliberately share one immutable resident alias.
# This Q6 alias forces all 66 GPU-offloadable layers because Ollama 0.32.15's
# automatic placement conservatively selected only 58/66 layers.
PINNED_LLM_MODEL_NAME = "hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072"
PINNED_LLM_MODEL_SOURCE = "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_M"
PINNED_LLM_MODEL_DIGEST = (
    "44d415f1e36e9aea1cca2baaaa79da8cef57f255c8dd91f1e9ef0abfc8a6c33d"
)
PINNED_LLM_MODEL_FAMILY = "qwen35"
PINNED_LLM_MODEL_PARAMETER_SIZE = "27.3B"
PINNED_LLM_MODEL_QUANTIZATION = "Q6_K"
PINNED_LLM_REQUIRED_CAPABILITIES = frozenset({"completion", "thinking", "vision"})


def _float_env(name: str, default: float) -> float:
    """Parse a float env var with safe fallback on missing/blank/invalid values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip()
    if not raw:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _int_env_optional(name: str) -> Optional[int]:
    """Parse an optional int env var; return None for missing/blank/invalid/non-positive values."""
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
        return value if value > 0 else None
    except Exception:
        return None


def _int_env(name: str, default: int) -> int:
    """Parse an int env var with safe fallback on missing/blank/invalid values."""
    value = _int_env_optional(name)
    return value if value is not None else default


def _bool_env(name: str, default: bool = False) -> bool:
    """Parse a bool env var with safe fallback on missing/blank/invalid values."""
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _pinned_text_env(name: str, expected: str) -> str:
    """Return a fixed setting and fail fast when an environment value tries to retarget it."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return expected
    configured = raw.strip()
    if configured != expected:
        raise RuntimeError(f"{name} is pinned to {expected!r}; received {configured!r}")
    return expected


TIKA_TIMEOUT_S = _int_env("TIKA_TIMEOUT_S", 15)
LLM_MODEL_NAME = _pinned_text_env("LLM_MODEL_NAME", PINNED_LLM_MODEL_NAME)
LLM_CONTEXT_TOKENS = _int_env("LLM_CONTEXT_TOKENS", 131072)
LLM_OUTPUT_RESERVE_TOKENS = _int_env("LLM_OUTPUT_RESERVE_TOKENS", 32768)
LLM_REQUEST_TIMEOUT_S = _float_env("LLM_REQUEST_TIMEOUT_S", 1800.0)
LLM_MAX_RETRIES = _int_env("LLM_MAX_RETRIES", 0)
LLM_TEMPERATURE = _float_env("LLM_TEMPERATURE", 1.0)
LLM_TOP_P = _float_env("LLM_TOP_P", 0.95)
LLM_PRESENCE_PENALTY = _float_env("LLM_PRESENCE_PENALTY", 0.0)
LLM_REASONING_EFFORT = _pinned_text_env("LLM_REASONING_EFFORT", "medium")
# Ollama's OpenAI-compatible endpoint uses ``reasoning_effort``.  For Qwen3.8,
# its highest supported OpenAI-compatible value is ``xhigh``; native Ollama
# callers use ``think: \"max\"`` instead.  Keep this distinction explicit so the
# UI does not rely on the generic OpenAI ``max`` spelling for this Qwen template.
LLM_THINKING_EFFORT = _pinned_text_env("LLM_THINKING_EFFORT", "xhigh")
LLM_SHOW_REASONING = _bool_env("LLM_SHOW_REASONING", False)
LLM_MAX_TOKENS = _int_env("LLM_MAX_TOKENS", 32768)
IMG_TOKEN_COST_DEFAULT = _int_env("IMG_TOKEN_COST_DEFAULT", 2048)


def _ollama_base_url() -> str:
    """
    Convert an OpenAI-style base URL like http://host:11434/v1 into the native Ollama base http://host:11434.
    If /v1 isn't present, returns the URL without trailing slash.
    """
    return LLM_BASE_URL.rstrip("/").split("/v1")[0]


def reasoning_effort_for_turn(thinking_mode_enabled: bool) -> str:
    """
    Return reasoning effort for the current turn.

    Thinking Mode is a one-turn UI option: default turns use explicit ``medium``
    reasoning and selected turns use the pinned ``xhigh`` effort.
    """
    return LLM_THINKING_EFFORT if thinking_mode_enabled else LLM_REASONING_EFFORT


def max_tokens_for_turn(thinking_mode_enabled: bool) -> int:
    """
    Return max_tokens to send for the current turn.

    Both modes use the HFS Knowledge output ceiling. ``thinking_mode_enabled`` is
    accepted alongside ``reasoning_effort_for_turn`` to keep request construction
    explicit at the call site.
    """
    _ = thinking_mode_enabled
    return LLM_MAX_TOKENS
