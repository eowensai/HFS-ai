"""Safe, synthetic uploads exercise the app and Streamlit's real Pillow decoder."""

import io
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest
from test_ephemeral_app import _install_synthetic_backend, settle

REPO_ROOT = Path(__file__).resolve().parents[1]


def synthetic_image(format_name):
    """Small ordinary images only; no malicious dimensions or exploit payloads."""
    width, height = 300, 48  # Wider than the preview, so rendering must decode/resize.
    if format_name == "PSD":
        header = b"8BPS" + struct.pack(">H6sHIIHH", 1, b"\0" * 6, 3, height, width, 8, 3)
        sections = struct.pack(">IIIH", 0, 0, 0, 0)  # Empty sections, raw planar pixels.
        return header + sections + b"".join(
            bytes([channel]) * width * height for channel in (30, 120, 200)
        )
    output = io.BytesIO()
    Image.new("RGB", (width, height), (30, 120, 200)).save(output, format=format_name)
    return output.getvalue()


@pytest.mark.parametrize(
    ("format_name", "filename", "mime"),
    [
        ("PNG", "fictional.png", "image/png"),
        ("JPEG", "fictional.jpg", "image/jpeg"),
        ("GIF", "fictional.gif", "image/gif"),
        ("WEBP", "fictional.webp", "image/webp"),
        ("PSD", "fictional.psd", "image/vnd.adobe.photoshop"),
        ("PSD", "fictional-renamed.jpg", "image/jpeg"),
    ],
)
def test_uploaded_image_reaches_real_decoder(monkeypatch, format_name, filename, mime):
    import streamlit as st

    calls = []
    _install_synthetic_backend(monkeypatch, calls)
    from ephemeral import llm_client
    monkeypatch.setattr(llm_client, "model_supports_images", lambda: True)
    payload = synthetic_image(format_name)
    upload = io.BytesIO(payload)
    upload.name, upload.type, upload.size = filename, mime, len(payload)
    pending = [SimpleNamespace(text="Fictional image rendering check.", files=[upload])]
    monkeypatch.setattr(st, "chat_input", lambda *args, **kwargs: pending.pop() if pending else None)

    opened_formats = []
    original_open = Image.open

    def track_decoder(*args, **kwargs):
        result = original_open(*args, **kwargs)
        opened_formats.append(result.format)
        return result

    monkeypatch.setattr(Image, "open", track_decoder)
    at = AppTest.from_file(str(REPO_ROOT / "ephemeral_app.py"), default_timeout=10).run()
    settle(at)
    assert not at.exception
    assert not at.error
    assert calls  # Submission completed using the synthetic backend.
    assert format_name in opened_formats
    assert at.get("image")
    messages = list(at.session_state["messages"])
    assert any(
        part.get("image_url", {}).get("url", "").startswith("data:image/jpeg;base64,")
        for message in messages if isinstance(message.get("content"), list)
        for part in message["content"] if part.get("type") == "image_url"
    )
    assert upload.closed  # Original bytes are no longer retained after normalization.
    at.run()  # Stored chat history must render through the same path.
    assert not at.exception
    assert not at.error
    assert at.get("image")


def test_invalid_image_reports_error_without_crashing(monkeypatch):
    import streamlit as st

    calls = []
    _install_synthetic_backend(monkeypatch, calls)
    upload = io.BytesIO(b"Fictional non-image content; not an exploit fixture.")
    upload.name, upload.type, upload.size = "invalid.png", "image/png", len(upload.getvalue())
    pending = [SimpleNamespace(text="Fictional invalid image check.", files=[upload])]
    monkeypatch.setattr(st, "chat_input", lambda *args, **kwargs: pending.pop() if pending else None)
    at = AppTest.from_file(str(REPO_ROOT / "ephemeral_app.py"), default_timeout=10).run()
    assert not at.exception
    settle(at)
    assert "unavailable" in str(at.session_state["messages"])
    assert upload.closed
