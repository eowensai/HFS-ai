import base64
from html.parser import HTMLParser
from types import SimpleNamespace

import pytest

from ephemeral import chat_display
from ephemeral.chat_display import image_preview_bytes, label_html, render_chat_text
from ephemeral.export import build_message_html, build_message_markdown


@pytest.mark.parametrize('text', [
    '![alt](https://example.invalid/image)',
    '![alt][ref]\n\n[ref]: //example.invalid/image',
    '![ref][]\n\n[ref]: /local-path',
    '![ref]\n\n[ref]: https://example.invalid/image',
    '[![nested](https://example.invalid/image)](https://example.invalid/link)',
    '\\![escaped](https://example.invalid/image)',
    '``![code](https://example.invalid/image)``',
    '```md\n![code](https://example.invalid/image)\n```',
    '![incomplete',
    ':help[&#33;&#91;image&#93;&#40;https://example.invalid/image&#41;]',
    '```mermaid\ngraph LR\nA-->B\n```',
    '> ~~~mermaid\ngraph LR\nA-->B',
    '```&#109;ermaid\ngraph LR\nA-->B\n```',
    '```MERMAID\nnot yet a complete diagram',
])
def test_possible_images_render_exact_literal_text(text):
    calls = []
    ui = SimpleNamespace(text=lambda s: calls.append(s),
                         markdown=lambda *a, **k: pytest.fail('Image-bearing text reached Markdown'))
    render_chat_text(text, ui)
    assert calls == [text]


@pytest.mark.parametrize('text', [
    '**Bold** and *italic*. [A link](https://example.invalid/manual)',
    '| Table | Value |\n| --- | --- |\n| One | Two |',
    '```python\nprint("hello!")\n```',
    '<img src="https://example.invalid/image">',
    '&#33;[entity](https://example.invalid/image)',
])
def test_other_markdown_keeps_formatting_with_html_disabled(text):
    calls = []
    ui = SimpleNamespace(text=lambda *a: pytest.fail('Unexpected plain text'),
                         markdown=lambda s, **k: calls.append((s, k)))
    render_chat_text(text, ui)
    assert calls == [(text, {'unsafe_allow_html': False})]


def test_every_stream_prefix_uses_guard_without_state():
    answer = 'Before ![tracking](https://example.invalid/image) after.'
    for end in range(len(answer) + 1):
        calls = []
        ui = SimpleNamespace(text=lambda s, target=calls: target.append(('text', s)),
                             markdown=lambda s, target=calls, **k: target.append(('markdown', s)))
        prefix = answer[:end]
        render_chat_text(prefix, ui)
        assert calls == [('text' if '![' in prefix else 'markdown', prefix)]


def test_diagram_stream_stays_literal_and_copy_preserves_fences():
    answer = 'Introduction\n```mermaid\ngraph LR\nA-->B\n```\nAfterword'
    for end in range(len(answer) + 1):
        prefix = answer[:end]
        calls = []
        ui = SimpleNamespace(text=lambda s: calls.append(('text', s)),
                             markdown=lambda s, **k: calls.append(('markdown', s)))
        render_chat_text(prefix, ui)
        assert calls == [('text' if 'mermaid' in prefix else 'markdown', prefix)]
    assert answer in build_message_markdown({'role': 'assistant', 'content': answer})


def test_html_labels_neutralize_markdown_and_html_without_losing_name():
    name = '\n\n![filename](https://example.invalid/image)\n\n<img src="bad">'
    safe = label_html(name)
    assert '![' not in safe and '<img' not in safe
    from html import unescape
    assert unescape(safe) == name


@pytest.mark.parametrize('source', ['https://example.invalid/image', '//example.invalid/image',
                                    '/etc/passwd', 'file:///tmp/image', 'data:image/svg+xml,<svg/>',
                                    'data:image/jpeg;base64,%%%', 'blob:synthetic'])
def test_previews_never_resolve_urls_or_paths(source):
    for part in ({'type': 'image', 'data': source}, {'type': 'image_url', 'image_url': {'url': source}}):
        with pytest.raises(ValueError):
            image_preview_bytes(part)


def test_preview_decodes_owned_data_url_and_bounds_allocations(monkeypatch):
    monkeypatch.setattr(chat_display, 'MAX_IMAGE_OUTPUT_BYTES', 3)
    raw = b'abc'
    assert image_preview_bytes({'type': 'image', 'data': raw}) == raw
    value = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()
    assert image_preview_bytes({'type': 'image_url', 'image_url': {'url': value}}) == raw
    with pytest.raises(ValueError):
        image_preview_bytes({'type': 'image', 'data': b'abcd'})
    with pytest.raises(ValueError):
        image_preview_bytes({'type': 'image_url', 'image_url': {'url': value + 'AAAA'}})


def test_copy_export_preserves_source_without_active_html_media():
    text = '![image](https://example.invalid/image)\n<img src="https://example.invalid/raw">'
    message = {'role': 'assistant', 'content': text}
    calls = []
    render_chat_text(text, SimpleNamespace(text=calls.append))
    assert message['content'] == text and text in build_message_markdown(message)
    tags = []
    class Tags(HTMLParser):
        def handle_starttag(self, tag, attrs):
            tags.append(tag)
    Tags().feed(build_message_html(message))
    assert not {'img', 'video', 'audio', 'iframe', 'source', 'script'} & set(tags)


def test_application_chat_sinks_use_guard():
    import ast
    from pathlib import Path
    tree = ast.parse(Path('ephemeral_app.py').read_text())
    guarded = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Name) and n.func.id == 'render_chat_text']
    assert len(guarded) == 3  # Multipart, ordinary/pending, and streaming text.
    images = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and isinstance(n.func.value, ast.Name) and n.func.value.id == 'st' and n.func.attr == 'image']
    assert images and all(isinstance(n.args[0], ast.Call) and n.args[0].func.id == 'image_preview_bytes'
                          for n in images)
