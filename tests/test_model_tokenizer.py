"""Pure regressions plus the real production admission wiring; all data synthetic."""
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from ephemeral import llm_client, model_tokenizer
from ephemeral.model_tokenizer import ModelTokenizer, pieces, rendered_text
from ephemeral.token_budget import ContextError, budget_request


@pytest.fixture
def tokenizer(monkeypatch):
    # A small byte-complete BPE vocabulary with known merges, not a fake counter.
    decoder = model_tokenizer._byte_decoder()
    tokens = list(decoder) + ['ab', 'abc', '<|im_start|>', '<|im_end|>']
    data = {'tokenizer.ggml.tokens': tokens, 'tokenizer.ggml.token_type': [1] * 258 + [3, 3],
            'tokenizer.ggml.merges': ['a b', 'ab c']}
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True,
                                            separators=(',', ':')).encode()).hexdigest()
    monkeypatch.setattr(model_tokenizer, 'TOKENIZER_SHA256', fingerprint)
    return ModelTokenizer(data)


@pytest.mark.parametrize('text,expected', [
    ('hello world', ['hello', ' world']),
    ("we'RE fine", ['we', "'RE", ' fine']),
    ('12345', list('12345')),
    ('e\u0301lan', ['e\u0301lan']),
    ('a  b', ['a', ' ', ' b']),
    ('a\r\n  b', ['a', '\r\n', ' ', ' b']),
    ('hello!\n\nnext', ['hello', '!\n\n', 'next']),
    ('\t\n\t\r  ', ['\t\n\t\r', '  ']),
    ('\u0301', ['\u0301']),
    ('\x1cfoo', ['\x1cfoo']),
])
def test_qwen35_presplit(text, expected):
    assert list(pieces(text)) == expected


@pytest.mark.parametrize('text,count', [('abc', 1), ('abcabc', 2), ('abx', 2), ('axbc', 4),
                                       ('<|im_start|>abc<|im_end|>', 3), ('', 0)])
def test_real_bpe_merges_and_specials(tokenizer, text, count):
    assert tokenizer.count(text) == count


def test_tokenizer_rejects_unverified_metadata():
    with pytest.raises(ValueError, match='does not match'):
        ModelTokenizer({'tokenizer.ggml.tokens': []})


def test_exceptional_work_is_bounded(tokenizer):
    assert tokenizer.count('x' * 5000) == 5000
    assert tokenizer.count('\u0378') == len('\u0378'.encode())


def test_concurrent_counting_keeps_only_public_vocabulary(tokenizer):
    before = dict(vars(tokenizer))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(tokenizer.count, ['abc' * 100] * 20))
    assert results == [100] * 20
    assert vars(tokenizer) == before


def request(content='abc', thinking=False):
    return llm_client.build_chat_completion_request(
        [{'role': 'system', 'content': 'Test.'}, {'role': 'user', 'content': content}], thinking)


def test_renderer_wraps_history_and_one_turn_reasoning():
    req = request()
    req['messages'].insert(1, {'role': 'assistant', 'content': ' Previous. '})
    rendered = rendered_text(req)
    assert '<|im_start|>assistant\n<think>\n\n</think>\n\nPrevious.<|im_end|>\n' in rendered
    assert rendered.endswith('<|im_start|>assistant\n<think>\n')
    assert model_tokenizer._XHIGH not in rendered
    assert model_tokenizer._XHIGH in rendered_text(request(thinking=True))
    assert model_tokenizer._XHIGH not in rendered_text(request())


@pytest.mark.parametrize('mutation', [
    lambda r: r.update(tools=[{}]),
    lambda r: r['messages'].append({'role': 'developer', 'content': 'unsupported'}),
    lambda r: r['messages'][1].update(reasoning='must not be counted or retained'),
    lambda r: r['extra_body'].update(reasoning_effort='unexpected'),
])
def test_unknown_rendering_cannot_silently_undercount(mutation):
    req = request()
    mutation(req)
    with pytest.raises(ValueError):
        rendered_text(req)


def test_canonical_admission_counts_rendered_request_and_preserves_output(tokenizer):
    req = request('abc ' * 1000)
    count = tokenizer.count(rendered_text(req))
    budget = budget_request(req, count + 32768, 1, tokenizer=tokenizer)
    assert budget.input_tokens == count
    assert budget.reserve_tokens == 32768 and budget.fits
    assert not budget_request(req, count + 32767, 1, tokenizer=tokenizer).fits
    assert budget_request(req, count + 32769, 1, tokenizer=tokenizer).fits
    assert budget_request(req, count + 40000, 40000, tokenizer=tokenizer).fits


def test_image_allowance_preserved_without_counting_base64(tokenizer):
    req = request()
    req['messages'][1]['content'] = [{'type': 'text', 'text': 'abc'},
                                    {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,synthetic'}}]
    budget = budget_request(req, 131072, 32768, tokenizer=tokenizer)
    assert 8192 < budget.input_tokens < 9192
    req['messages'][1]['content'][1]['image_url']['url'] += 'x' * 10000
    assert budget_request(req, 131072, 32768, tokenizer=tokenizer) == budget


def test_production_measurement_never_falls_back_on_failure(monkeypatch):
    def unavailable():
        raise ContextError('unavailable')
    monkeypatch.setattr(llm_client, 'get_model_tokenizer', unavailable)
    with pytest.raises(ContextError):
        llm_client.measure_model_request(request(), 131072, 32768)


def test_production_measurement_uses_verified_tokenizer(monkeypatch, tokenizer):
    monkeypatch.setattr(llm_client, 'get_model_tokenizer', lambda: tokenizer)
    req = request('abc ' * 1000)
    measured = llm_client.measure_model_request(req, 131072, 32768)
    assert measured.input_tokens == tokenizer.count(rendered_text(req))
    assert measured.input_tokens < budget_request(req, 131072, 32768).input_tokens


def test_loading_metadata_is_bounded_and_retries(monkeypatch):
    monkeypatch.setattr(llm_client, '_model_tokenizer', None)
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
        def raise_for_status(self):
            pass
        def iter_content(self, _):
            yield b'x' * (32 * 1024 * 1024)
            yield b'x'
    response = Response()
    response.json = lambda: {'version': '0.32.15'}
    monkeypatch.setattr(llm_client.requests, 'get', lambda *a, **k: response)
    monkeypatch.setattr(llm_client.requests, 'post', lambda *a, **k: response)
    with pytest.raises(ContextError):
        llm_client.get_model_tokenizer()
    assert response.closed and llm_client._model_tokenizer is None


def test_unknown_backend_renderer_does_not_guess(monkeypatch):
    monkeypatch.setattr(llm_client, '_model_tokenizer', None)
    class Version:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def json(self):
            return {'version': 'unknown'}
    monkeypatch.setattr(llm_client.requests, 'get', lambda *a, **k: Version())
    monkeypatch.setattr(llm_client.requests, 'post', lambda *a, **k: pytest.fail('Should stop at version mismatch'))
    with pytest.raises(ContextError):
        llm_client.get_model_tokenizer()


def test_worker_uses_same_measurement_for_admission_and_retention(monkeypatch, tokenizer):
    from test_reliability_boundaries import chunk, work

    from ephemeral.request_lifecycle import run_turn
    seen = []
    def measure(req, capacity, reserve):
        seen.append(req)
        return budget_request(req, capacity, reserve, tokenizer=tokenizer)
    w = work('abc')
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: iter([chunk('abc'), chunk('', 'stop')]))))
    run_turn(w, parse=None, model_ready=lambda: True, vision_ready=lambda: True,
             context=lambda: 131072, request_builder=llm_client.build_chat_completion_request,
             client=lambda: client, measure=measure)
    assert not w.error and len(seen) == 2
    assert seen[0]['messages'][-1]['role'] == 'user'
    assert seen[1]['messages'][-1]['role'] == 'assistant'
    assert w.owner.budget_snapshot.budget.input_tokens == tokenizer.count(rendered_text(seen[1]))


def test_app_supplies_production_measurement():
    import ast
    from pathlib import Path
    tree = ast.parse(Path('ephemeral_app.py').read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'run_turn']
    assert calls and all(any(k.arg == 'measure' and isinstance(k.value, ast.Name)
                            and k.value.id == 'measure_model_request' for k in c.keywords) for c in calls)


def test_admission_count_failure_does_not_retry_for_feedback():
    from test_reliability_boundaries import work

    from ephemeral.request_lifecycle import run_turn
    attempts = []
    def fail_count(*args):
        attempts.append(True)
        raise ContextError('Counting unavailable. Request not sent.')
    w = work('abc')
    run_turn(w, parse=None, model_ready=lambda: True, vision_ready=lambda: True,
             context=lambda: 131072, request_builder=llm_client.build_chat_completion_request,
             client=lambda: pytest.fail('Must not dispatch'), measure=fail_count)
    assert len(attempts) == 1
    assert w.retryable and w.owner.budget_snapshot is None


@pytest.mark.parametrize('change', ['none', 'release', 'revision'])
def test_retained_measurement_does_not_lock_or_publish_stale_results(tokenizer, change):
    from test_reliability_boundaries import chunk, work

    from ephemeral.request_lifecycle import run_turn
    w = work('abc')
    attempts, lock_available = [], []
    def measure(req, capacity, reserve):
        attempts.append(True)
        if len(attempts) == 2:
            def concurrent_action():
                acquired = w.lock.acquire(timeout=0.5)
                lock_available.append(acquired)
                if acquired:
                    try:
                        if change == 'release':
                            w.owner.release()
                        elif change == 'revision':
                            w.messages.append({'role': 'user', 'content': 'concurrent receipt'})
                    finally:
                        w.lock.release()
            thread = threading.Thread(target=concurrent_action)
            thread.start()
            thread.join(2)
        return budget_request(req, capacity, reserve, tokenizer=tokenizer)
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: iter([chunk('abc'), chunk('', 'stop')]))))
    run_turn(w, parse=None, model_ready=lambda: True, vision_ready=lambda: True,
             context=lambda: 131072, request_builder=llm_client.build_chat_completion_request,
             client=lambda: client, measure=measure)
    assert lock_available == [True]
    assert (w.owner.budget_snapshot is not None) == (change == 'none')
