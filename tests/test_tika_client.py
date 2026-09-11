"""Tika 4 wire contract, bounded buffers, and honest partial results."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from ephemeral import tika_client as client


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.status_code = status
        self.headers = headers or {}
        self.raw = SimpleNamespace(read1=self.read)
        self.reads = 0
        self.closed = False

    def read(self, amount, **kwargs):
        self.reads += 1
        chunk, self.body = self.body[:amount], self.body[amount:]
        return chunk

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'Parser HTTP {self.status_code}', response=self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


def install(monkeypatch, payload, **kwargs):
    response = Response(payload, **kwargs)
    calls = []
    def put(url, **options):
        calls.append((url, options))
        return response
    monkeypatch.setattr(client.requests, 'put', put)
    return response, calls


def test_markdown_wire_contract_and_no_filename_or_removed_headers(monkeypatch):
    markdown = '# Ownership\n\n| System | Owner |\n| --- | --- |\n| Beacon | Mira |'
    response, calls = install(monkeypatch, {'tk:content': markdown})
    assert client.parse_with_tika(b'fictional', 'PRIVATE-NAME\r\nX: injected') == client.ParsedText(markdown)
    assert calls[0][0].endswith('/tika/json/markdown')
    assert calls[0][1]['headers'] == {'Accept': 'application/json', 'Accept-Encoding': 'identity'}
    assert 'PRIVATE-NAME' not in str(calls)
    assert response.closed


@pytest.mark.parametrize('metadata', [
    {'tk:exception:write-limit-reached': 'true'},
    {'tk:exception:container-exception': ['synthetic problem']},
    {'tk:exception:embedded-exception': ['synthetic problem']},
    {'tk:task-deadline-reached': True},
    {'tk:embedded-resource-limit-reached': True},
    {'tk:embedded-depth-limit-reached': True},
    {'tk:pipes-result': 'PARTIAL_TIMEOUT'},
    {'tk:pipes-result': ['PARSE_SUCCESS_WITH_EXCEPTION']},
    {'tk:warning': 'synthetic warning'},
])
def test_retains_usable_text_and_marks_partial(monkeypatch, metadata):
    install(monkeypatch, {'tk:content': 'Usable fictional evidence', **metadata})
    assert client.parse_with_tika(b'x', 'x.txt') == client.ParsedText('Usable fictional evidence', True)


@pytest.mark.parametrize('value', [False, None, '', 'false', ['false'], []])
def test_false_exception_flags_do_not_mark_partial(monkeypatch, value):
    install(monkeypatch, {'tk:content': 'Evidence', 'tk:exception:write-limit-reached': value,
                          'tk:pipes-result': 'PARSE_SUCCESS'})
    assert not client.parse_with_tika(b'x', 'x.txt').partial


def test_multibyte_cap_does_not_cut_utf8_or_shrink_wire_budget(monkeypatch):
    install(monkeypatch, {'tk:content': '你好🌊' * 10000})
    result = client.parse_with_tika(b'x', 'x.txt', max_bytes=7)
    assert result == client.ParsedText('你好', True)
    assert len(result.text.encode()) == 6


def test_content_arrays_and_empty_results(monkeypatch):
    install(monkeypatch, {'tk:content': ['Root', 'Embedded']})
    assert client.parse_with_tika(b'x', 'x.txt').text == 'Root\nEmbedded'
    install(monkeypatch, {})
    assert client.parse_with_tika(b'x', 'x.txt') == client.ParsedText('')


@pytest.mark.parametrize('payload', [[], {'tk:content': 4}, {'tk:content': ['ok', 4]},
                                     {'X-TIKA:content': 'old server'}, b'not JSON'])
def test_incompatible_or_malformed_output_is_rejected(monkeypatch, payload):
    response, _ = install(monkeypatch, payload)
    with pytest.raises((ValueError, TypeError)):
        client.parse_with_tika(b'x', 'x.txt')
    assert response.closed


@pytest.mark.parametrize('status', [400, 413, 422, 429, 500, 503])
def test_http_failures_are_not_retried_or_read_as_document_text(monkeypatch, status):
    response, calls = install(monkeypatch, {'status': 'synthetic'}, status=status)
    with pytest.raises(requests.HTTPError):
        client.parse_with_tika(b'x', 'x.txt')
    assert len(calls) == 1 and response.closed and response.reads == 0


def test_compressed_response_is_rejected_before_reading(monkeypatch):
    response, _ = install(monkeypatch, b'compressed', headers={'Content-Encoding': 'gzip'})
    with pytest.raises(ValueError, match='encoded'):
        client.parse_with_tika(b'x', 'x.txt')
    assert response.closed and response.reads == 0


def test_deadline_includes_final_read(monkeypatch):
    response, _ = install(monkeypatch, {'tk:content': 'Evidence'})
    ticks = iter([0, 1, client.TIKA_TIMEOUT_S + 1])
    monkeypatch.setattr(client.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError, match='deadline'):
        client.parse_with_tika(b'x', 'x.txt')
    assert response.closed


def test_no_capacity_rejects_before_network(monkeypatch):
    _, calls = install(monkeypatch, {})
    with pytest.raises(ValueError, match='capacity'):
        client.parse_with_tika(b'x', 'x.txt', max_bytes=0)
    assert not calls


def test_server_profile_agrees_with_client_contract():
    path = Path(__file__).resolve().parents[1] / 'deployment/tika/tika-config.json'
    config = json.loads(path.read_text())
    assert config['parse-context']['output-limits']['writeLimit'] == client.TIKA_WRITE_LIMIT_CHARS
    assert config['parse-context']['output-limits']['throwOnWriteLimit'] is True
    assert config['parse-context']['timeout-limits']['totalTaskTimeoutMillis'] < client.TIKA_TIMEOUT_S * 1000
    assert config['server']['allowPerRequestConfig'] is False
    assert config['server']['allowPipes'] is False
    assert config['pipes']['tempDirectory'] == '/tmp'


def test_markdown_escaped_whitespace_is_an_empty_result(monkeypatch):
    install(monkeypatch, {'tk:content': '&#32;\n&#9;\n'})
    assert client.parse_with_tika(b' \n\t', 'empty.txt').text == ''


def test_comment_appendix_shares_the_application_byte_limit(monkeypatch):
    install(monkeypatch, {'tk:content': 'Body', 'Content-Type':
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})
    monkeypatch.setattr(client, 'word_comment_attribution', lambda data: ('\nComment by Mira: '+ '界'*20, False))
    result = client.parse_with_tika(b'fictional', 'comments.docx', max_bytes=32)
    assert result.partial and len(result.text.encode()) <= 32 and '\ufffd' not in result.text
