"""Bounded Tika 4 Markdown extraction; metadata never leaves this helper."""
import html
import json
import time
from dataclasses import dataclass

import requests
import streamlit as st
from urllib3.exceptions import ReadTimeoutError

from ephemeral.config import MAX_EXTRACTED_BYTES, TIKA_TIMEOUT_S, TIKA_URL
from ephemeral.office_comments import word_comment_attribution

# The server limit counts characters; the application limit counts UTF-8 bytes.
# A smaller remaining conversation allowance must not shrink the JSON envelope.
TIKA_WRITE_LIMIT_CHARS = 262144
TIKA_RESPONSE_LIMIT_BYTES = TIKA_WRITE_LIMIT_CHARS * 6 + 64 * 1024


def _has_value(value) -> bool:
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    return value not in (None, False, '', 'false', 'False')


def _partial_metadata(metadata: dict) -> bool:
    for key, value in metadata.items():
        name = key.lower()
        if (('exception' in name or 'warn' in name or 'limit-reached' in name or 'deadline-reached' in name)
                and _has_value(value)):
            return True
        if name == 'tk:pipes-result':
            values = value if isinstance(value, list) else [value]
            if any(item not in ('PARSE_SUCCESS', 'EMIT_SUCCESS', None, '') for item in values):
                return True
    return False


@dataclass(frozen=True)
class ParsedText:
    text: str
    partial: bool = False


@st.cache_data(ttl=5, show_spinner=False)
def tika_alive() -> bool:
    try:
        with requests.get(f'{TIKA_URL.rstrip("/")}/version', timeout=2) as response:
            return response.ok and response.text.strip().startswith('Apache Tika 4.')
    except requests.RequestException:
        return False


def parse_with_tika(data: bytes, filename: str, *, max_bytes=MAX_EXTRACTED_BYTES) -> ParsedText:
    """Read Tika 4 JSON/Markdown with server character and local byte limits.

    Server config enforces the handler limit and parsing deadline. Tika 4 ignores
    the former writeLimit headers. Bound JSON before decoding and preserve partial
    results. Filename is never sent to Tika; no parsed metadata is retained.
    """
    if max_bytes <= 0:
        raise ValueError('No document text capacity remains')
    deadline = time.monotonic() + TIKA_TIMEOUT_S
    try:
        with requests.put(f'{TIKA_URL.rstrip("/")}/tika/json/markdown', data=data,
                          headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'},
                          timeout=(5, TIKA_TIMEOUT_S), stream=True) as response:
            response.raise_for_status()
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Unexpected encoded parser response')
            body = bytearray()
            while True:
                # read1 yields available bytes rather than waiting to fill 4096 bytes.
                chunk = response.raw.read1(4096, decode_content=False)
                if time.monotonic() >= deadline:
                    raise TimeoutError('Parser deadline exceeded')
                if not chunk:
                    break
                if len(body) + len(chunk) > TIKA_RESPONSE_LIMIT_BYTES:
                    raise ValueError('Parser metadata/response exceeds buffer limit')
                body.extend(chunk)
            metadata = json.loads(body)
            body.clear()
            if not isinstance(metadata, dict):
                raise TypeError('Unexpected parser metadata')
            if 'X-TIKA:content' in metadata and 'tk:content' not in metadata:
                raise ValueError('Unsupported parser version')
            text = metadata.get('tk:content', '')
            if isinstance(text, list) and all(isinstance(t, str) for t in text):
                text = '\n'.join(text)
            if not isinstance(text, str):
                raise TypeError('Unexpected parser text')
            if not html.unescape(text).strip():
                text = ''
            partial = _partial_metadata(metadata)
            if (metadata.get('Content-Type') ==
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'):
                appendix, comments_partial = word_comment_attribution(data)
                text += appendix
                partial = partial or comments_partial
            if time.monotonic() >= deadline:
                raise TimeoutError('Parser deadline exceeded')
            encoded = text.encode('utf-8')
            if len(encoded) > max_bytes:
                partial = True
                text = encoded[:max_bytes].decode('utf-8', errors='ignore')
            return ParsedText(text.strip(), partial)
    except (requests.Timeout, ReadTimeoutError) as exc:
        raise TimeoutError('Document reading timed out') from exc
