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
        after_cr = False
        frame = 0
        ending = 0
        for chunk in self.stream:
            if time.monotonic() - self.started >= cfg.LLM_REQUEST_TIMEOUT_S:
                raise TimeoutError('Model response deadline exceeded')
            total += len(chunk)
            if total > cfg.MAX_STREAM_TOTAL_BYTES:
                raise ValueError('Model response exceeds transport limit')
            # A single HTTP read may contain many SSE events. Check before yielding
            # to the SDK, including endless data lines with no event separator.
            for index, byte in enumerate(chunk):
                # OpenAI 1.97.2 buffers raw frames until one of these three
                # endings. Mixed SSE newlines may end a logical event earlier.
                frame += 1
                ending = ((ending << 8) | byte) & 0xFFFFFFFF
                if frame > cfg.MAX_STREAM_EVENT_BYTES:
                    raise ValueError('Model response frame exceeds buffer limit')
                # Match chunk.splitlines(keepends=True) without copying lines:
                # CRLF is atomic within a raw chunk; a chunk's final piece is
                # also checked. A delimiter substring inside CRLF is not enough.
                line_end = (index + 1 == len(chunk) or byte == 10 or
                            (byte == 13 and chunk[index + 1] != 10))
                if line_end and (ending & 0xFFFF in (0x0A0A, 0x0D0D) or ending == 0x0D0A0D0A):
                    frame = 0
                    ending = 0
                event += 1
                if after_cr and byte == 10:
                    after_cr = False
                    continue  # The LF half of a CRLF is not another empty line.
                after_cr = byte == 13
                if byte in (10, 13):
                    if line == 0:
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
        # Bounds apply before HTTPX decoding. Do not allow compressed expansion.
        request.headers['Accept-Encoding'] = 'identity'
        started = time.monotonic()
        response = super().handle_request(request)
        if response.headers.get('Content-Encoding', 'identity').strip().lower() != 'identity':
            response.close()
            raise ValueError('Unexpected encoded model response')
        response.stream = BoundedStream(response.stream, started)
        return response
