"""Regression paths use synthetic data and reduced limits, never shared failures."""
import gzip
import logging
from itertools import product
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import APIConnectionError, OpenAI
from openai._streaming import SSEDecoder
from test_reliability_boundaries import ByteStream, chunk, execute, upload, work

from ephemeral import config as cfg
from ephemeral import request_lifecycle as lifecycle
from ephemeral.attachments import api_messages
from ephemeral.bounded_transport import BoundedStream, BoundedTransport
from ephemeral.export import build_conversation_html, build_conversation_markdown
from ephemeral.llm_client import build_chat_completion_request
from ephemeral.tika_client import ParsedText
from ephemeral.token_budget import (
    BudgetSnapshot,
    RequestBudget,
    budget_caption,
    budget_percent,
    budget_request,
)


def test_retry_uses_only_the_remaining_assistant_slot(monkeypatch):
    monkeypatch.setattr(cfg, 'MAX_CONVERSATION_MESSAGES', 4)
    first = work()
    first.messages.append({'role': 'user', 'content': 'Earlier question'})
    first.messages.append({'role': 'assistant', 'content': 'Earlier answer'})
    execute(first, [chunk('Interrupted synthetic answer')])
    assert first.error and first.retryable and len(first.messages) == 3
    second = work('', owner=first.owner, messages=first.messages)
    second.user_message = first.user_message
    assert len(execute(second)) == 1
    assert len(second.messages) == 4 and not second.error


def test_pre_dispatch_deadline_reports_failure_and_allows_retry():
    w = work()
    def ready():
        w.deadline = 0
        return True
    lifecycle.run_turn(w, parse=None, model_ready=ready, vision_ready=lambda: True,
                       context=lambda: 131072, request_builder=build_chat_completion_request,
                       client=lambda: pytest.fail('Expired request dispatched'))
    w.finish()
    assert 'timed out' in w.error and w.retryable
    assert len(w.messages) == 1
    assert w.snapshot().stage == '' and w.request_budget is None


def test_release_between_parsing_and_publication_does_not_revive_payload(monkeypatch):
    w = work(files=[upload()])
    original = lifecycle.available_count
    def release(parts):
        w.owner.release()
        return original(parts)
    monkeypatch.setattr(lifecycle, 'available_count', release)
    assert not execute(w)
    w.progress('Late stage')
    w.reasoning_event(True)
    w.finish()
    assert w.user_message is None and not w.messages
    assert not w.partial and not w.stage and not w.error and not w.text
    assert w.request_budget is None and w.owner.budget_snapshot is None
    assert w.snapshot().pending is None


@pytest.mark.parametrize('newline', [b'\n', b'\r\n', b'\r'])
def test_unknown_sse_fields_do_not_reset_sdk_event_bound(monkeypatch, newline):
    monkeypatch.setattr(cfg, 'MAX_STREAM_EVENT_BYTES', 100)
    fields = [b'data: {"a":"' + b'a' * 60 + b'",', b'x',
              b'data: "b":"' + b'b' * 60 + b'"}', b'', b'']
    raw = ByteStream([newline.join(fields)])
    with pytest.raises(ValueError, match='event|frame'):
        list(SSEDecoder().iter_bytes(BoundedStream(raw, lifecycle.time.monotonic())))


@pytest.mark.parametrize('newline', [b'\n', b'\r\n', b'\r'])
def test_real_sse_separators_reset_bound_across_chunks(monkeypatch, newline):
    monkeypatch.setattr(cfg, 'MAX_STREAM_EVENT_BYTES', 30)
    data = (b'data: {"ok":true}' + newline + newline) * 3
    raw = ByteStream([bytes([b]) for b in data])
    events = list(SSEDecoder().iter_bytes(BoundedStream(raw, lifecycle.time.monotonic())))
    assert len(events) == 3 and all(event.json() == {'ok': True} for event in events)


def test_mixed_sse_newlines_cannot_accumulate_an_oversized_sdk_frame(monkeypatch):
    monkeypatch.setattr(cfg, 'MAX_STREAM_EVENT_BYTES', 100)
    raw = ByteStream([b'data: {"ok":true}\n\r'] * 10)
    with pytest.raises(ValueError, match='frame'):
        list(SSEDecoder()._iter_chunks(BoundedStream(raw, lifecycle.time.monotonic())))


@pytest.mark.parametrize('separator', [bytes(chars) for size in range(1, 5)
                                     for chars in product((10, 13), repeat=size)])
@pytest.mark.parametrize('partition', ['whole', 'record', 'byte'])
def test_frame_bound_matches_installed_sdk_line_and_chunk_boundaries(monkeypatch, separator, partition):
    monkeypatch.setattr(cfg, 'MAX_STREAM_EVENT_BYTES', 100)
    record = b'data: {"ok":true}' + separator
    data = record * 20
    chunks = ([data] if partition == 'whole' else [record] * 20 if partition == 'record'
              else [bytes([b]) for b in data])
    # The installed SDK is the oracle, including CRCRLF and split CRLF cases.
    largest = max(map(len, SSEDecoder()._iter_chunks(iter(chunks))))
    bounded = BoundedStream(ByteStream(chunks), lifecycle.time.monotonic())
    if largest > 100:
        with pytest.raises(ValueError, match='frame|event'):
            list(bounded)
    else:
        assert list(bounded) == chunks


@pytest.mark.parametrize('partition', ['whole', 'byte'])
def test_surplus_newline_does_not_inherit_previous_frame_suffix(monkeypatch, partition):
    monkeypatch.setattr(cfg, 'MAX_STREAM_EVENT_BYTES', 100)
    for length in (98, 99, 100, 101):
        data = b'data: a\n\n\n' + b'x' * length
        chunks = [data] if partition == 'whole' else [bytes([b]) for b in data]
        largest = max(map(len, SSEDecoder()._iter_chunks(iter(chunks))))
        bounded = BoundedStream(ByteStream(chunks), lifecycle.time.monotonic())
        if largest > 100:
            with pytest.raises(ValueError, match='frame'):
                list(bounded)
        else:
            assert list(bounded) == chunks


def test_sdk_rejects_compressed_response_before_decompression(monkeypatch):
    raw = ByteStream([gzip.compress(b'data: ' + b'x' * 2000)])
    observed = []
    def respond(self, request):
        observed.append(request.headers['Accept-Encoding'])
        return httpx.Response(200, headers={'Content-Encoding': 'gzip'}, stream=raw)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', respond)
    with (OpenAI(api_key='synthetic', max_retries=0,
                 http_client=httpx.Client(transport=BoundedTransport())) as client,
          pytest.raises(APIConnectionError, match='Connection error')):
        client.chat.completions.create(model=cfg.LLM_MODEL_NAME, messages=[], stream=True)
    assert observed == ['identity'] and raw.closed


def test_stage_clock_changes_only_on_real_stage_transition(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(lifecycle.time, 'monotonic', lambda: now[0])
    w = work()
    assert w.snapshot().stage == 'Preparing the submission…'
    now[0] = 12.9
    assert w.snapshot().elapsed == 2
    w.progress('Reading file 1 of 2…')
    now[0] = 16.0
    w.progress('Reading file 1 of 2…')
    assert w.snapshot().elapsed == 3
    w.progress('Reading file 2 of 2…')
    assert w.snapshot().elapsed == 0
    now[0] = 18
    w.progress('Waiting for the AI…')
    w.reasoning_event(False)
    now[0] = 20
    assert w.snapshot().stage == 'Waiting for the AI…' and w.snapshot().elapsed == 2
    w.reasoning_event(True)
    now[0] = 24
    w.reasoning_event(True)
    assert w.snapshot().elapsed == 4
    w.progress('Writing…')
    w.reasoning_event(True)
    assert w.stage == 'Writing…'
    w.finish()
    w.progress('Late event')
    assert not w.stage and w.stage_started is None


def test_dedicated_reasoning_presence_only_and_filtered_writing(caplog):
    caplog.set_level(logging.DEBUG)
    w = work()
    w.thinking = True
    observed = []
    sentinel = 'PRIVATE_DEDICATED_SENTINEL'
    inline = 'PRIVATE_INLINE_SENTINEL'
    def stream():
        observed.append(w.snapshot())
        yield chunk('   ')
        observed.append(w.snapshot())
        yield NS(choices=[NS(delta=NS(reasoning='', content=None), finish_reason=None)])
        observed.append(w.snapshot())
        yield NS(choices=[NS(delta=NS(reasoning=sentinel, content=None), finish_reason=None)])
        observed.append(w.snapshot())
        yield chunk(f'<think>{inline}</think>')
        observed.append(w.snapshot())
        yield chunk('A visible synthetic answer long enough to pass the filter. ')
        observed.append(w.snapshot())
        yield NS(choices=[NS(delta=NS(reasoning=sentinel, content=None), finish_reason='stop')])
    execute(w, stream())
    assert [s.stage for s in observed[:3]] == ['Waiting for the AI…'] * 3
    assert [s.stage for s in observed[3:5]] == ['Thinking…'] * 2
    assert observed[-1].stage == 'Writing…' and observed[-1].partial.strip()
    assert all(not s.error for s in observed)
    w.finish()
    exposed = (repr(observed) + repr(vars(w)) + repr(w.messages) + caplog.text
               + build_conversation_markdown(w.messages) + build_conversation_html(w.messages))
    assert sentinel not in exposed and inline not in exposed
    assert not w.snapshot().stage and w.snapshot().budget == w.owner.budget_snapshot


@pytest.mark.parametrize(('tokens', 'expected'), [
    (799, '~79% used'), (800, '~80% used · Getting full'),
    (949, '~94% used · Getting full'), (950, '~95% used · Almost full'),
    (1000, '~100% used · Almost full'), (1001, '~100% used · Over limit'),
])
def test_budget_display_thresholds_and_exact_boundary(tokens, expected):
    measurement = BudgetSnapshot('owner', 3, RequestBudget(tokens, 300, 1300))
    assert budget_caption(measurement, 'owner', 3) == 'Conversation budget: ' + expected
    assert budget_caption(measurement, 'owner', 3, submitted=True) == 'This request’s budget: ' + expected
    assert measurement.budget.fits is (tokens <= 1000)


@pytest.mark.parametrize('measurement', [None,
    BudgetSnapshot('owner', 3, None),
    BudgetSnapshot('other', 3, RequestBudget(0, 300, 1300)),
    BudgetSnapshot('owner', 2, RequestBudget(0, 300, 1300)),
    BudgetSnapshot('owner', 3, RequestBudget(0, 1300, 1300)),
    BudgetSnapshot('owner', 3, RequestBudget(-1, 300, 1300)),
    BudgetSnapshot('owner', 3, RequestBudget(True, 300, 1300)),
])
def test_unknown_stale_and_invalid_measurements_are_unavailable(measurement):
    assert budget_caption(measurement, 'owner', 3) == 'Conversation budget unavailable'
    assert budget_percent(measurement, 'owner', 3) is None


def test_request_and_retained_snapshots_match_canonical_admission_through_retry():
    w = work(files=[upload()])
    observed = []
    def stream():
        observed.append(w.snapshot())
        yield chunk('Interrupted synthetic response long enough to render')
    calls = execute(w, stream())
    expected = budget_request(calls[0], 131072, cfg.LLM_OUTPUT_RESERVE_TOKENS)
    assert observed[0].budget.budget == expected
    assert observed[0].budget.revision == w.messages.revision
    assert w.owner.budget_snapshot.budget == expected  # Only the user was retained.
    assert 'Interrupted' not in build_conversation_markdown(w.messages)
    retry = work('', owner=w.owner, messages=w.messages)
    retry.user_message = w.user_message
    execute(retry)
    retained = build_chat_completion_request([{'role': 'system', 'content': 'system policy'},
                                              *api_messages(w.messages)], False)
    assert w.owner.budget_snapshot.budget == budget_request(retained, 131072, cfg.LLM_OUTPUT_RESERVE_TOKENS)
    assert w.owner.budget_snapshot.revision == w.messages.revision == 2
    w.messages.append({'role': 'user', 'content': 'Changed content'})
    assert w.owner.budget_snapshot is None
    w.owner.release()
    assert w.owner.budget_snapshot is None and not w.messages


def test_rejection_recomputes_retained_budget_without_rejected_text():
    w = work()
    execute(w)
    prior = w.owner.budget_snapshot
    rejected = work('x' * (cfg.MAX_PROMPT_BYTES + 1), owner=w.owner, messages=w.messages)
    assert not execute(rejected)
    assert rejected.error and rejected.owner.budget_snapshot == prior


def test_missing_context_does_not_restore_previous_safe_measurement():
    from ephemeral.token_budget import ContextError
    w = work()
    execute(w)
    failed = work(owner=w.owner, messages=w.messages)
    def unavailable():
        raise ContextError('Context unavailable')
    lifecycle.run_turn(failed, parse=lambda *a, **k: ParsedText(''), model_ready=lambda: True,
                       vision_ready=lambda: True, context=unavailable,
                       request_builder=build_chat_completion_request, client=None)
    assert failed.owner.budget_snapshot is None and failed.retryable


def test_all_failed_upload_still_measures_retained_receipts_and_notice():
    w = work('', files=[upload()])
    probes = []
    def context():
        probes.append(True)
        return 131072
    lifecycle.run_turn(w, parse=lambda *a, **k: ParsedText(''), model_ready=lambda: True,
                       vision_ready=lambda: True, context=context,
                       request_builder=build_chat_completion_request,
                       client=lambda: pytest.fail('All-failed upload dispatched'))
    retained = build_chat_completion_request([{'role': 'system', 'content': 'system policy'},
                                              *api_messages(w.messages)], False)
    assert len(probes) == 1 and len(w.messages) == 2
    assert w.owner.budget_snapshot.budget == budget_request(retained, 131072, cfg.LLM_OUTPUT_RESERVE_TOKENS)


def test_invalid_capacity_feedback_does_not_break_error_cleanup():
    w = work()
    lifecycle.run_turn(w, parse=None, model_ready=lambda: True, vision_ready=lambda: True,
                       context=lambda: 0, request_builder=build_chat_completion_request, client=None)
    assert w.error and not w.system and not w.files
    assert w.owner.budget_snapshot is None


@pytest.mark.parametrize('tokens', [800, 950, 1000, 1001])
def test_cached_budget_thresholds_render_without_extra_probes(monkeypatch, tokens):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest
    from test_ephemeral_app import _install_synthetic_backend, _submit

    from ephemeral import llm_client
    calls = []
    _install_synthetic_backend(monkeypatch, calls)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'ephemeral_app.py')).run()
    assert not any('Conversation budget' in c.value for c in app.caption)
    _submit(app, 'Synthetic retained conversation')
    messages = app.session_state['messages']
    owner = messages.owner
    owner.budget_snapshot = BudgetSnapshot(owner.id, messages.revision, RequestBudget(tokens, 300, 1300))
    monkeypatch.setattr(llm_client, 'get_model_ctx', lambda: pytest.fail('Caption probed backend'))
    app.run()
    expected = budget_caption(owner.budget_snapshot, owner.id, messages.revision)
    assert expected in [c.value for c in app.caption]
    owner.budget_snapshot = BudgetSnapshot(owner.id, messages.revision - 1, RequestBudget(0, 300, 1300))
    app.run()
    assert 'Conversation budget unavailable' in [c.value for c in app.caption]
    app.button(key='sidebar_new').click().run()
    assert not any('Conversation budget' in c.value for c in app.caption)
    assert owner.budget_snapshot is None


def test_busy_rejection_keeps_failed_turn_available_for_explicit_retry(monkeypatch):
    import threading
    from pathlib import Path

    from streamlit.testing.v1 import AppTest
    from test_ephemeral_app import _install_synthetic_backend, _submit, settle

    from ephemeral import llm_client
    calls = []
    _install_synthetic_backend(monkeypatch, calls)
    successful_client = llm_client.get_llm_client
    monkeypatch.setattr(lifecycle, '_ACTIVE', threading.BoundedSemaphore(1))
    monkeypatch.setattr(llm_client, 'get_llm_client', lambda: NS(chat=NS(completions=NS(
        create=lambda **kwargs: iter([chunk('Synthetic unfinished answer')])))))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'ephemeral_app.py')).run()
    _submit(app, 'Synthetic retained request')
    old = app.session_state['_work_gate'].active
    assert old.retryable and app.button(key='retry_response')
    assert lifecycle._ACTIVE.acquire(blocking=False)
    try:
        app.button(key='retry_response').click().run()
        assert not app.exception and app.button(key='retry_response')
        assert app.session_state['_work_gate'].active is old and old.retryable
        assert len(app.session_state['messages']) == 1
    finally:
        lifecycle._ACTIVE.release()
    monkeypatch.setattr(llm_client, 'get_llm_client', successful_client)
    app.run()
    app.button(key='retry_response').click().run()
    settle(app)
    assert not app.exception and len(calls) == 1
    assert [m['role'] for m in app.session_state['messages']] == ['user', 'assistant']
