"""Display untrusted chat without automatically loading message-supplied media.

No URL allowlist, CSS hiding, DOM cleanup, or model cooperation is involved.
These helpers change rendering only, never retained/model/export content.
"""
import base64
import binascii
from html import escape

from ephemeral.config import MAX_IMAGE_OUTPUT_BYTES


def render_chat_text(text, ui):
    """Use literal text for anything that could contain a Markdown image.

    CommonMark inline/reference images start with literal ![. A deliberately
    conservative check also catches escaped/code examples and incomplete streams.
    Rendering the original text avoids a second Markdown parser, regex URL
    rewriting, or corrupting code examples. Entity/escaped delimiters cannot
    create new Markdown syntax after parsing. Raw HTML is always disabled.
    """
    # Streamlit's help directive can pass decoded text to a second Markdown
    # renderer in a tooltip. Keep it literal too, including entity-encoded images.
    if '![' in text or ':help[' in text:
        ui.text(text)
    else:
        ui.markdown(text, unsafe_allow_html=False)


def label_html(text):
    """Escape both HTML and Markdown image openers in attachment-label HTML.

    A filename containing blank lines can end a Markdown HTML block. HTML
    escaping alone does not neutralize a subsequent Markdown image opener.
    """
    return escape(text).replace('!', '&#33;').replace(':', '&#58;')


def image_preview_bytes(part):
    """Allow bounded in-memory uploads, never URL or filesystem image sources."""
    value = part.get('data') if part.get('type') == 'image' else part.get('image_url', {}).get('url')
    if isinstance(value, (bytes, bytearray)):
        if len(value) <= MAX_IMAGE_OUTPUT_BYTES:
            return bytes(value)
    elif isinstance(value, str):
        for prefix in ('data:image/jpeg;base64,', 'data:image/png;base64,'):
            if value.startswith(prefix):
                if len(value) - len(prefix) > 4 * ((MAX_IMAGE_OUTPUT_BYTES + 2) // 3):
                    break
                encoded = value[len(prefix):]
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error):
                    break
                if len(raw) <= MAX_IMAGE_OUTPUT_BYTES:
                    return raw
                break
    raise ValueError('Unsupported image preview source')
