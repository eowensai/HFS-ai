import logging
import time
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from ephemeral.export import build_conversation_html, build_conversation_markdown
from ephemeral.turn_options import THINKING_MODE_KEY


REPO_ROOT = Path(__file__).resolve().parents[1]
REASONING_SENTINEL = "HIDDEN_REASONING_SENTINEL"
INLINE_THINK_SENTINEL = "INLINE_THINK_SENTINEL"


class _FakeCompletions:
    def __init__(self, calls):
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        answer = f"Visible synthetic answer {len(self.calls)}."
        return iter(
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                reasoning=REASONING_SENTINEL,
                            )
                        )
                    ],
                    usage=None,
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="stop",
                            delta=SimpleNamespace(
                                content=(
                                    f"<think>{INLINE_THINK_SENTINEL}</think>{answer}"
                                ),
                                reasoning=None,
                            )
                        )
                    ],
                    usage=None,
                ),
            ]
        )


def _install_synthetic_backend(monkeypatch, calls):
    from ephemeral import clipboard, llm_client, tika_client

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=_FakeCompletions(calls))
    )
    monkeypatch.setattr(llm_client, "llm_alive", lambda: True)
    monkeypatch.setattr(llm_client, "get_llm_client", lambda: fake_client)
    monkeypatch.setattr(llm_client, "get_model_ctx", lambda: 131072)
    monkeypatch.setattr(llm_client, "get_image_token_cost", lambda: 2048)
    monkeypatch.setattr(llm_client, "model_supports_images", lambda: False)
    monkeypatch.setattr(llm_client, "count_text_tokens", lambda text: max(1, len(text) // 4))
    # UI tests own all backend calls, including the tokenizer added to admission.
    # Actual BPE and renderer behavior is covered by test_model_tokenizer.py.
    monkeypatch.setattr(llm_client, "get_model_tokenizer", lambda: SimpleNamespace(
        count=lambda text: max(1, len(text.encode('utf-8')))))
    monkeypatch.setattr(tika_client, "tika_alive", lambda: True)
    monkeypatch.setattr(clipboard, "render_copy_button", lambda *args, **kwargs: None)
    monkeypatch.setattr(clipboard, "render_turn_copy_button", lambda *args, **kwargs: None)


def _submit(at, text):
    at.chat_input[0].set_value(text).run()
    settle(at)
    assert not at.exception


def settle(at):
    """AppTest has no browser timer; drive the same fragment completion reruns."""
    for _ in range(100):
        if not at.session_state["_work_gate"].running:
            return at.run()
        time.sleep(0.02)
        at.run()
    raise AssertionError("Synthetic operation did not finish")


def test_browserless_submissions_use_medium_then_one_shot_xhigh_then_medium(
    monkeypatch, caplog
):
    calls = []
    _install_synthetic_backend(monkeypatch, calls)
    caplog.set_level(logging.DEBUG)

    at = AppTest.from_file(
        str(REPO_ROOT / "ephemeral_app.py"),
        default_timeout=10,
    ).run()
    assert not at.exception
    assert at.toggle(key=THINKING_MODE_KEY).value is False

    _submit(at, "Synthetic ordinary request")
    assert calls[-1]["extra_body"] == {"reasoning_effort": "medium"}

    at.toggle(key=THINKING_MODE_KEY).set_value(True).run()
    assert at.toggle(key=THINKING_MODE_KEY).value is True
    _submit(at, "Synthetic one-turn maximum request")
    assert calls[-1]["extra_body"] == {"reasoning_effort": "xhigh"}
    assert at.toggle(key=THINKING_MODE_KEY).value is False

    _submit(at, "Synthetic request after the one-turn maximum")
    assert calls[-1]["extra_body"] == {"reasoning_effort": "medium"}
    assert at.toggle(key=THINKING_MODE_KEY).value is False
    assert [call["extra_body"]["reasoning_effort"] for call in calls] == [
        "medium",
        "xhigh",
        "medium",
    ]

    messages = list(at.session_state["messages"])
    rendered_markdown = "\n".join(str(element.value) for element in at.markdown)
    exported = build_conversation_markdown(messages) + build_conversation_html(messages)
    observable_content = rendered_markdown + repr(messages) + exported + caplog.text

    assert REASONING_SENTINEL not in observable_content
    assert INLINE_THINK_SENTINEL not in observable_content
    assert "Visible synthetic answer 3." in observable_content
