"""Bound the SDK's SSE/error buffering before its decoder allocates an event."""
import time

import httpx

from ephemeral import config as cfg


class BoundedStream(httpx.SyncByteStream):
    def __init__(self, stream, started):
        self.stream = stream
        self.started = started

    def __iter__(self):
        total = 0
        line = 0
        event = 0
        for chunk in self.stream:
            if time.monotonic() - self.started >= cfg.LLM_REQUEST_TIMEOUT_S:
                raise TimeoutError('Model response deadline exceeded')
            total += len(chunk)
            if total > cfg.MAX_STREAM_TOTAL_BYTES:
                raise ValueError('Model response exceeds transport limit')
            # A single HTTP read may contain many SSE events. Check before yielding
            # to the SDK, including endless data lines with no event separator.
            for byte in chunk:
                event += 1
                if byte == 10:
                    if line <= 1:  # LF or CRLF blank line
                        event = 0
                    line = 0
                else:
                    line += 1
                if event > cfg.MAX_STREAM_EVENT_BYTES:
                    raise ValueError('Model response event exceeds buffer limit')
            yield chunk

    def close(self):
        self.stream.close()


class BoundedTransport(httpx.HTTPTransport):
    def handle_request(self, request):
        started = time.monotonic()
        response = super().handle_request(request)
        response.stream = BoundedStream(response.stream, started)
        return response
