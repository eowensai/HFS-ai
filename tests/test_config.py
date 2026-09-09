import pytest

from ephemeral import config


def test_float_env_valid_invalid_blank_missing(monkeypatch):
    monkeypatch.setenv("X_FLOAT", " 1.25 ")
    assert config._float_env("X_FLOAT", 9.0) == 1.25

    monkeypatch.setenv("X_FLOAT", "")
    assert config._float_env("X_FLOAT", 9.0) == 9.0

    monkeypatch.setenv("X_FLOAT", "abc")
    assert config._float_env("X_FLOAT", 9.0) == 9.0

    monkeypatch.delenv("X_FLOAT", raising=False)
    assert config._float_env("X_FLOAT", 9.0) == 9.0


def test_int_env_optional_cases(monkeypatch):
    monkeypatch.setenv("X_INT_OPT", " 42 ")
    assert config._int_env_optional("X_INT_OPT") == 42

    monkeypatch.setenv("X_INT_OPT", "0")
    assert config._int_env_optional("X_INT_OPT") is None

    monkeypatch.setenv("X_INT_OPT", "-5")
    assert config._int_env_optional("X_INT_OPT") is None

    monkeypatch.setenv("X_INT_OPT", "")
    assert config._int_env_optional("X_INT_OPT") is None

    monkeypatch.setenv("X_INT_OPT", "oops")
    assert config._int_env_optional("X_INT_OPT") is None

    monkeypatch.delenv("X_INT_OPT", raising=False)
    assert config._int_env_optional("X_INT_OPT") is None


def test_int_env_with_default(monkeypatch):
    monkeypatch.setenv("X_INT", "10")
    assert config._int_env("X_INT", 7) == 10

    monkeypatch.setenv("X_INT", "")
    assert config._int_env("X_INT", 7) == 7

    monkeypatch.setenv("X_INT", "bad")
    assert config._int_env("X_INT", 7) == 7


def test_bool_env_variants(monkeypatch):
    for raw in ["1", "true", "yes", "y", "on", "  YES  "]:
        monkeypatch.setenv("X_BOOL", raw)
        assert config._bool_env("X_BOOL", False) is True

    for raw in ["0", "false", "no", "n", "off", " Off "]:
        monkeypatch.setenv("X_BOOL", raw)
        assert config._bool_env("X_BOOL", True) is False

    monkeypatch.setenv("X_BOOL", "maybe")
    assert config._bool_env("X_BOOL", True) is True
    assert config._bool_env("X_BOOL", False) is False

    monkeypatch.delenv("X_BOOL", raising=False)
    assert config._bool_env("X_BOOL", True) is True


def test_pinned_text_env_rejects_retargeting(monkeypatch):
    monkeypatch.setenv("X_PINNED", "wrong-model")
    with pytest.raises(RuntimeError, match="is pinned"):
        config._pinned_text_env("X_PINNED", "required-model")

    monkeypatch.setenv("X_PINNED", " required-model ")
    assert config._pinned_text_env("X_PINNED", "required-model") == "required-model"


def test_qwen38_profile_defaults_are_pinned():
    assert config.LLM_MODEL_NAME == "hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072"
    assert config.PINNED_LLM_MODEL_SOURCE == "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_M"
    assert config.PINNED_LLM_MODEL_DIGEST == (
        "44d415f1e36e9aea1cca2baaaa79da8cef57f255c8dd91f1e9ef0abfc8a6c33d"
    )
    assert config.PINNED_LLM_MODEL_FAMILY == "qwen35"
    assert config.PINNED_LLM_MODEL_PARAMETER_SIZE == "27.3B"
    assert config.PINNED_LLM_MODEL_QUANTIZATION == "Q6_K"
    assert config.PINNED_LLM_REQUIRED_CAPABILITIES == {
        "completion",
        "thinking",
        "vision",
    }
    assert config.LLM_CONTEXT_TOKENS == 131072
    assert config.LLM_OUTPUT_RESERVE_TOKENS == 32768
    assert config.LLM_REQUEST_TIMEOUT_S == 1800.0
    assert config.LLM_MAX_RETRIES == 0
    assert config.LLM_TEMPERATURE == 1.0
    assert config.LLM_TOP_P == 0.95
    assert config.LLM_PRESENCE_PENALTY == 0.0
    assert config.LLM_MAX_TOKENS == 32768
    assert config.LLM_REASONING_EFFORT == "medium"
    assert config.LLM_THINKING_EFFORT == "xhigh"


def test_ollama_base_url_variants(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://ollama:11434/v1")
    assert config._ollama_base_url() == "http://ollama:11434"

    monkeypatch.setattr(config, "LLM_BASE_URL", "http://ollama:11434/v1/")
    assert config._ollama_base_url() == "http://ollama:11434"

    monkeypatch.setattr(config, "LLM_BASE_URL", "http://ollama:11434")
    assert config._ollama_base_url() == "http://ollama:11434"

    monkeypatch.setattr(config, "LLM_BASE_URL", "http://ollama:11434/")
    assert config._ollama_base_url() == "http://ollama:11434"


@pytest.mark.parametrize(
    ("thinking_mode_enabled", "expected_effort"),
    [
        (False, "medium"),
        (True, "xhigh"),
    ],
)
def test_reasoning_effort_for_turn(monkeypatch, thinking_mode_enabled, expected_effort):
    monkeypatch.setattr(config, "LLM_REASONING_EFFORT", "medium")
    monkeypatch.setattr(config, "LLM_THINKING_EFFORT", "xhigh")
    assert config.reasoning_effort_for_turn(thinking_mode_enabled) == expected_effort


@pytest.mark.parametrize(
    ("thinking_mode_enabled", "configured_max_tokens", "expected_max_tokens"),
    [
        (False, 2048, 2048),
        (True, 2048, 2048),
    ],
)
def test_max_tokens_for_turn(monkeypatch, thinking_mode_enabled, configured_max_tokens, expected_max_tokens):
    monkeypatch.setattr(config, "LLM_MAX_TOKENS", configured_max_tokens)
    assert config.max_tokens_for_turn(thinking_mode_enabled) == expected_max_tokens
