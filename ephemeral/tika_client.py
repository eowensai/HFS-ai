"""Bounded Tika extraction with explicit parser/write-limit status metadata."""
import json
import time
from dataclasses import dataclass

import requests
import streamlit as st
from urllib3.exceptions import ReadTimeoutError

from ephemeral.config import MAX_EXTRACTED_BYTES, TIKA_TIMEOUT_S, TIKA_URL


@dataclass(frozen=True)
class ParsedText:
    text: str
    partial: bool = False


@st.cache_data(ttl=5, show_spinner=False)
def tika_alive() -> bool:
    try:
        with requests.get(f'{TIKA_URL.rstrip("/")}/version', timeout=2) as response:
            return response.ok
    except requests.RequestException:
        return False


def parse_with_tika(data: bytes, filename: str, *, max_bytes=MAX_EXTRACTED_BYTES) -> ParsedText:
    """Use verified Tika 3.3.2 /tika/text JSON metadata and its writeLimit header.

    Limit the handler before extraction and bound JSON before decoding it. JSON
    permits observing parser errors/limits that a plain text stream cannot report.
    Filename is never used as an HTTP header. No parsed metadata is retained.
    """
    deadline = time.monotonic() + TIKA_TIMEOUT_S
    # Worst-case escaped Unicode plus bounded non-content metadata.
    response_limit = max_bytes * 6 + 64 * 1024
    try:
        with requests.put(f'{TIKA_URL.rstrip("/")}/tika/text', data=data,
                          headers={'Accept': 'application/json', 'Accept-Encoding': 'identity',
                                   'writeLimit': str(max_bytes), 'throwOnWriteLimitReached': 'false'},
                          timeout=(5, TIKA_TIMEOUT_S), stream=True) as response:
            response.raise_for_status()
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Unexpected encoded parser response')
            body = bytearray()
            while True:
                # read1 yields available bytes rather than waiting to fill 4096 bytes.
                chunk = response.raw.read1(4096, decode_content=False)
                if not chunk:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Parser deadline exceeded')
                if len(body) + len(chunk) > response_limit:
                    raise ValueError('Parser metadata/response exceeds buffer limit')
                body.extend(chunk)
            metadata = json.loads(body)
            body.clear()
            if not isinstance(metadata, dict):
                raise TypeError('Unexpected parser metadata')
            text = metadata.get('X-TIKA:content', '')
            if isinstance(text, list) and all(isinstance(t, str) for t in text):
                text = '\n'.join(text)
            if not isinstance(text, str):
                raise TypeError('Unexpected parser text')
            partial = any(('exception' in key.lower() or 'warn' in key.lower()) and
                          value not in (None, False, '', 'false', ['false'])
                          for key, value in metadata.items())
            encoded = text.encode('utf-8')
            if len(encoded) > max_bytes:
                partial = True
                text = encoded[:max_bytes].decode('utf-8', errors='ignore')
            return ParsedText(text.strip(), partial)
    except (requests.Timeout, ReadTimeoutError) as exc:
        raise TimeoutError('Document reading timed out') from exc
