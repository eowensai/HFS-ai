from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_requirements_pin_streamlit_163():
    requirements_text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "streamlit==1.63.0" in requirements_text


def test_theme_css_keeps_root_and_chat_role_selectors():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8")
    assert ":root {" in css
    assert '[class*="st-key-user-"]' in css
    assert '[class*="st-key-user_"]' in css
    assert '[class*="st-key-assistant-"]' in css
    assert '[class*="st-key-assistant_"]' in css


def test_assistant_markdown_heading_scale_is_scoped_and_normalized():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8")
    assistant_markdown = (
        '[class*="st-key-assistant-"] [data-testid="stChatMessageContent"] '
        '[data-testid="stMarkdownContainer"]'
    )
    assistant_content = (
        '[class*="st-key-assistant-"] [data-testid="stChatMessageContent"]'
    )

    assert f"{assistant_markdown}," in css
    markdown_rule_body = css.split(f"{assistant_markdown},", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    assert "font-size: 1rem;" in markdown_rule_body
    for heading, size in (("h1", "1.75rem"), ("h2", "1.5rem"), ("h3", "1.25rem")):
        rule_start = f"{assistant_content} {heading},"
        assert rule_start in css
        rule_body = css.split(rule_start, maxsplit=1)[1].split("}", maxsplit=1)[0]
        assert f"font-size: {size};" in rule_body
        assert "margin: 1.25rem 0 0.5rem;" in rule_body
        assert "padding: 0;" in rule_body

    for heading, size in (("h4", "1.125rem"), ("h5", "1rem"), ("h6", "0.875rem")):
        rule_start = f"{assistant_content} {heading},"
        assert rule_start in css
        rule_body = css.split(rule_start, maxsplit=1)[1].split("}", maxsplit=1)[0]
        assert f"font-size: {size};" in rule_body
        assert "margin: 1rem 0 0.4rem;" in rule_body
        assert "padding: 0;" in rule_body

    assert '[class*="st-key-user-"] [data-testid="stMarkdownContainer"]' not in css


def test_assistant_markdown_cool_palette_is_exact_and_scoped():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8")
    assistant_markdown = (
        '[class*="st-key-assistant-"] [data-testid="stChatMessageContent"] '
        '[data-testid="stMarkdownContainer"]'
    )
    palette = {
        "#273C86",
        "#1F2A44",
        "#2F3A4D",
        "#2563B8",
        "#6573E8",
        "#8B86F8",
        "#F7F7FE",
        "#5C657A",
        "#0F766E",
        "#ECF8F6",
        "#F0F2FF",
        "#D9DEEA",
    }

    for color in palette:
        assert color in css
    for selector in (
        ":is(h1, h2)",
        ":is(h3, h4, h5, h6)",
        "a",
        "li::marker",
        "blockquote",
        "blockquote > p:first-child:not(:has(> strong:first-child))",
        ":is(p, li, td, th) > code",
        "th",
        "hr",
    ):
        assert f"{assistant_markdown} {selector}," in css

    assert "text-decoration: underline;" in css
    assert "font-style: italic;" in css
    assert "opacity: 1;" in css
    assert '[class*="st-key-user-"] [data-testid="stMarkdownContainer"]' not in css


def test_theme_css_has_streamlit_156_chat_input_contract_selectors():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8")
    assert '[data-testid="stChatInput"]' in css
    assert '[data-testid="stChatInputTextArea"]' in css
    assert '[data-testid="stChatInputSubmitButton"]' in css


def test_theme_css_supports_sidebar_new_key_variants():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8")
    assert '[class*="st-key-sidebar_new"] .stButton > button' in css
    assert '[class*="st-key-sidebar-new"] .stButton > button' in css


def test_theme_css_keeps_compact_right_aligned_user_message_contract():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8")
    assert '[class*="st-key-user-"] [data-testid="stChatMessage"]' in css
    assert "margin-left: auto;" in css
    assert "width: fit-content;" in css


def test_theme_css_targets_chat_message_container_for_avatar_ordering():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8")
    assert '[class*="st-key-user-"] [data-testid="stChatMessage"],' in css
    assert '[class*="st-key-user-"] [data-testid="stChatMessage"] > div' not in css
    assert 'flex-direction: row-reverse;' in css


def test_theme_css_has_no_external_font_or_cdn_imports():
    css = (REPO_ROOT / "theme.css").read_text(encoding="utf-8").lower()
    forbidden_patterns = [
        "@import url(",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "cdnjs.cloudflare.com",
        "cdn.jsdelivr.net",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in css


def test_streamlit_156_api_cleanup_contracts():
    app_text = (REPO_ROOT / "ephemeral_app.py").read_text(encoding="utf-8")
    assert "streamlit.components.v1" not in app_text
    assert "use_container_width=" not in app_text


def test_welcome_state_copy_contracts():
    app_text = (REPO_ROOT / "ephemeral_app.py").read_text(encoding="utf-8")
    assert "Attach files, not just prompts" in app_text
    assert "Local and session-only" in app_text
    assert "Verify important answers" in app_text
    assert "Images, PDFs, Office files, spreadsheets, text, and more." in app_text
    assert "No account or saved chat history in this app. New Chat clears messages and uploads." in app_text
    assert (
        "This local model has no live web access and may be wrong, especially on current facts." in app_text
    )


def test_new_chat_labels_and_placeholder_contracts():
    app_text = (REPO_ROOT / "ephemeral_app.py").read_text(encoding="utf-8")
    assert "Ask a question or attach files..." in app_text
    assert "New Chat" in app_text
    assert 'key="sidebar_new"' in app_text


def test_docker_service_name_defaults_are_preserved():
    config_text = (REPO_ROOT / "ephemeral/config.py").read_text(encoding="utf-8")
    assert 'LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://ollama:11434/v1")' in config_text
    assert 'TIKA_URL = os.getenv("TIKA_URL", "http://tika-server:9998")' in config_text


def test_thinking_mode_is_one_shot_and_request_uses_captured_value():
    app_text = (REPO_ROOT / "ephemeral_app.py").read_text(encoding="utf-8")
    assert "on_submit=_capture_turn_options" in app_text
    assert "consume_submitted_thinking_mode(st.session_state)" in app_text
    assert "request_builder=build_chat_completion_request" in app_text
    assert "start_work(user_text, files, turn_thinking_mode)" in app_text
    assert 'key=THINKING_MODE_KEY' in app_text
    assert "Ordinary requests use medium reasoning." in app_text
    assert '"reasoning on this submitted turn; it may be much slower. "' in app_text


def test_system_prompt_has_no_reasoning_directives():
    prompt_text = (REPO_ROOT / "system_prompt_template.md").read_text(encoding="utf-8").lower()
    for forbidden in ("/think", "/nothink", "<think>", "reasoning_effort"):
        assert forbidden not in prompt_text


def test_compose_pins_shared_qwen38_profile():
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    required_lines = [
        "image: ollama/ollama:0.32.15",
        "LLM_MODEL_NAME=hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072",
        "LLM_CONTEXT_TOKENS=131072",
        "LLM_OUTPUT_RESERVE_TOKENS=32768",
        "LLM_REQUEST_TIMEOUT_S=1800",
        "LLM_MAX_RETRIES=0",
        "LLM_REASONING_EFFORT=medium",
        "LLM_THINKING_EFFORT=xhigh",
        "LLM_SHOW_REASONING=false",
        "LLM_TEMPERATURE=1.0",
        "LLM_TOP_P=0.95",
        "LLM_PRESENCE_PENALTY=0.0",
        "LLM_MAX_TOKENS=32768",
        "OLLAMA_MAX_LOADED_MODELS=1",
        "OLLAMA_NUM_PARALLEL=1",
        "OLLAMA_KEEP_ALIVE=-1",
        "OLLAMA_FLASH_ATTENTION=1",
        "OLLAMA_KV_CACHE_TYPE=q8_0",
    ]
    for line in required_lines:
        assert line in compose_text


def test_modelfile_pins_shared_unsloth_qwen38_q6_profile():
    modelfile_text = (
        REPO_ROOT / "Modelfile.hfs-ephemeral-shared-qwen3.8-27b-ud-q6km-131072"
    ).read_text(
        encoding="utf-8"
    )
    required_lines = [
        "FROM hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_M",
        "REQUIRES 0.32.15",
        "RENDERER qwen3.8",
        "PARSER qwen3.5",
        "PARAMETER draft_num_predict 2",
        "PARAMETER num_ctx 131072",
        "PARAMETER num_predict 32768",
        "PARAMETER num_batch 128",
        "PARAMETER num_gpu 66",
        "PARAMETER temperature 1.0",
        "PARAMETER top_p 0.95",
        "PARAMETER top_k 20",
        "PARAMETER min_p 0.0",
        "PARAMETER presence_penalty 0.0",
        "PARAMETER repeat_penalty 1.0",
    ]
    for line in required_lines:
        assert line in modelfile_text


def test_no_legacy_model_references_remain_in_text_files():
    # Split the literals so this regression test does not flag its own source.
    forbidden = (
        "qwen3." + "6",
        "qwen" + "36",
        "35b" + "-a3b",
        "ephemeral" + "-default",
    )
    text_suffixes = {".css", ".html", ".md", ".py", ".toml", ".txt", ".yml", ".yaml"}
    text_files = [
        path
        for path in REPO_ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and (path.suffix.lower() in text_suffixes or path.name.startswith(".env"))
    ]
    for path in text_files:
        content = path.read_text(encoding="utf-8").lower()
        for legacy_reference in forbidden:
            assert legacy_reference not in content, f"{legacy_reference!r} remains in {path}"


def test_excluded_same_name_attachments_retain_separate_status_receipts():
    from ephemeral.attachments import exclude_content, status_part
    parts = [status_part({'id': identity, 'name': 'same.txt', 'kind': 'document',
                         'status': 'available'}) for identity in ('first', 'second')]
    excluded = exclude_content(parts, 'Request too large')
    assert [p['_attachment']['id'] for p in excluded] == ['first', 'second']
    assert all(p['_attachment']['status'] == 'unavailable' for p in excluded)


def test_sidebar_logo_encoding_is_cached():
    app_text = (REPO_ROOT / "ephemeral_app.py").read_text(encoding="utf-8")
    assert "@st.cache_data(show_spinner=False)" in app_text
    assert "def _load_logo_b64(" in app_text
    assert "logo_b64 = _load_logo_b64()" in app_text


def test_clipboard_module_is_used():
    app_text = (REPO_ROOT / "ephemeral_app.py").read_text(encoding="utf-8")
    assert "from ephemeral.clipboard import render_copy_button, render_turn_copy_button" in app_text
    assert "def render_copy_button(" not in app_text
    assert "def render_turn_copy_button(" not in app_text


def test_sidebar_state_uses_streamlit_156_pixel_width_contract():
    app_text = (REPO_ROOT / "ephemeral_app.py").read_text(encoding="utf-8")
    assert "initial_sidebar_state=304" in app_text
    assert "HTTP status code" not in app_text
    assert 'initial_sidebar_state="auto"' not in app_text
    assert "initial_sidebar_state='auto'" not in app_text


def test_vision_rechecked_for_history_and_omissions_are_explicit():
    from ephemeral.attachments import api_messages, status_part
    receipt = status_part({'id': 'first', 'name': 'same.png', 'kind': 'image',
                           'status': 'available', 'reason': 'Image available'})
    messages = [{'role': 'user', 'content': [receipt,
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA=='}}]}]
    assert 'data:image/png' in str(api_messages(messages, True))
    hidden = str(api_messages(messages, False))
    assert 'data:image/png' not in hidden
    assert 'unavailable' in hidden and 'vision unavailable' in hidden
