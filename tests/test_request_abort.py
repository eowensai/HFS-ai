"""Real loopback sockets: a blocked peer must observe cancellation, not just a flag."""

import socket
import threading
import time

import httpx
import pytest

from ephemeral.bounded_transport import BoundedTransport
from ephemeral.request_abort import RequestAbort


@pytest.mark.parametrize("headers", [False, True])
def test_cancel_interrupts_headers_or_body_and_peer_sees_eof(headers):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    received = threading.Event()
    eof = threading.Event()

    def peer():
        with server.accept()[0] as conn:
            conn.settimeout(2)
            conn.recv(65536)
            if headers:
                conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            received.set()
            eof.set() if conn.recv(1) == b"" else None

    thread = threading.Thread(target=peer)
    thread.start()
    guard = RequestAbort()
    guard.arm(time.monotonic() + 5)
    finished = threading.Event()
    errors = []

    def worker():
        try:
            with httpx.Client(
                transport=BoundedTransport(abort_guard=guard), timeout=5
            ) as client:
                with client.stream(
                    "GET", f"http://127.0.0.1:{server.getsockname()[1]}"
                ) as response:
                    list(response.iter_bytes())
        except (httpx.TransportError, TimeoutError) as exc:
            errors.append(type(exc).__name__)
        finally:
            guard.finish()
            finished.set()

    worker_thread = threading.Thread(target=worker)
    worker_thread.start()
    try:
        assert received.wait(2)
        guard.abort()
        guard.abort()
        assert finished.wait(2)
        assert eof.wait(2)
        assert errors
    finally:
        guard.abort()
        server.close()
        thread.join(2)
        worker_thread.join(2)


def test_absolute_deadline_interrupts_trickling_response():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()

    def peer():
        with server.accept()[0] as conn:
            conn.recv(65536)
            conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            try:
                for _ in range(100):
                    conn.sendall(b"1\r\nx\r\n")
                    time.sleep(0.03)
            except OSError:
                pass

    thread = threading.Thread(target=peer)
    thread.start()
    guard = RequestAbort()
    start = time.monotonic()
    guard.arm(start + 0.2)
    try:
        with pytest.raises((httpx.TransportError, TimeoutError)):
            with httpx.Client(
                transport=BoundedTransport(abort_guard=guard), timeout=5
            ) as client:
                with client.stream(
                    "GET", f"http://127.0.0.1:{server.getsockname()[1]}"
                ) as response:
                    list(response.iter_bytes())
        assert guard.expired
        assert time.monotonic() - start < 2
    finally:
        guard.finish()
        server.close()
        thread.join(2)


def test_late_registration_is_shutdown_before_use():
    a, b = socket.socketpair()

    class Stream:
        def get_extra_info(self, name):
            return a

    guard = RequestAbort()
    guard.abort()
    try:
        with pytest.raises(TimeoutError):
            guard.trace("connection.connect_tcp.complete", {"return_value": Stream()})
        assert b.recv(1) == b""
    finally:
        a.close()
        b.close()


def test_finished_guard_cannot_shutdown_a_connection():
    a, b = socket.socketpair()

    class Stream:
        def get_extra_info(self, name):
            return a

    guard = RequestAbort()
    try:
        guard.trace("connection.connect_tcp.complete", {"return_value": Stream()})
        guard.finish()
        guard.abort()
        a.sendall(b"ok")
        assert b.recv(2) == b"ok"
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("expire", [False, True])
def test_blocked_sdk_releases_global_slot_and_skips_final_recount(monkeypatch, expire):
    from openai import OpenAI
    from test_reliability_boundaries import execute, work

    from ephemeral import config as cfg
    from ephemeral import request_lifecycle
    from ephemeral.llm_client import build_chat_completion_request
    from ephemeral.request_lifecycle import WorkGate, run_turn
    from ephemeral.token_budget import RequestBudget

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    received, eof = threading.Event(), threading.Event()

    def peer():
        with server.accept()[0] as conn:
            conn.settimeout(3)
            data = b""
            while b"\r\n\r\n" not in data:
                data += conn.recv(65536)
            header, body = data.split(b"\r\n\r\n", 1)
            size = int(
                next(
                    line.split(b":", 1)[1]
                    for line in header.splitlines()
                    if line.lower().startswith(b"content-length:")
                )
            )
            while len(body) < size:
                body += conn.recv(size - len(body))
            received.set()
            if conn.recv(1) == b"":
                eof.set()

    peer_thread = threading.Thread(target=peer)
    peer_thread.start()
    guard = RequestAbort()
    sdk = OpenAI(
        base_url=f"http://127.0.0.1:{server.getsockname()[1]}/v1",
        api_key="synthetic",
        max_retries=0,
        timeout=3,
        http_client=httpx.Client(transport=BoundedTransport(abort_guard=guard)),
    )
    sdk._ephemerai_abort_guard = guard
    monkeypatch.setattr(cfg, "LLM_REQUEST_TIMEOUT_S", 0.5 if expire else 5)
    # The normal app permits several bounded workers waiting for the serial
    # backend. Use one worker slot here to prove release/reacquisition exactly.
    monkeypatch.setattr(request_lifecycle, "_ACTIVE", threading.BoundedSemaphore(1))
    first, second = work(), work("Other session")
    counts = []

    def measure(*args):
        counts.append(1)
        return RequestBudget(100, 32768, 131072)

    gate = WorkGate()

    def target(w):
        run_turn(
            w,
            parse=None,
            model_ready=lambda: True,
            vision_ready=lambda: True,
            context=lambda: 131072,
            request_builder=build_chat_completion_request,
            client=lambda: sdk,
            measure=measure,
        )

    try:
        assert gate.start(first, target)
        assert received.wait(2)
        assert not WorkGate().start(second, execute)
        if not expire:
            first.owner.release()
        limit = time.monotonic() + 3
        while gate.running and time.monotonic() < limit:
            time.sleep(0.01)
        assert not gate.running and eof.wait(1)
        assert counts == [1], (
            "cancelled/expired work must not begin a final token count"
        )
        assert sdk.is_closed()
        if expire:
            assert "timed out" in first.error and first.retryable
            assert all(m["role"] == "user" for m in first.messages)
        else:
            assert not first.messages and not first.partial and not first.error
        other_gate = WorkGate()
        assert other_gate.start(second, execute)
        while other_gate.running and time.monotonic() < limit:
            time.sleep(0.01)
        assert not other_gate.running and second.messages[-1]["content"] == "answer"
    finally:
        guard.abort()
        sdk.close()
        server.close()
        peer_thread.join(3)
