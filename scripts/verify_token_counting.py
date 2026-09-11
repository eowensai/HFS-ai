"""Synthetic tokenizer acceptance. Print only counts/booleans, never model content.

Run inside an isolated test container with the supported backend reachable.
The optional independent oracles are test-only tokenizers==0.22.1 and
regex==2025.7.34; neither is a production dependency.
"""
import argparse
import json
import random
import string
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from ephemeral.config import _ollama_base_url
from ephemeral.llm_client import build_chat_completion_request, get_model_tokenizer
from ephemeral.model_tokenizer import ModelTokenizer, pieces, rendered_text
from ephemeral.token_budget import budget_request

PATTERN = (r"(?:'[sS]|'[tT]|'[rR][eE]|'[vV][eE]|'[mM]|'[lL][lL]|'[dD])|"
           r"[^\r\n\p{L}\p{N}]?[\p{L}\p{M}]+|\p{N}| ?[^\s\p{L}\p{M}\p{N}]+[\r\n]*|"
           r"\s*[\r\n]+|\s+(?!\S)|\s+")


def check_oracles(metadata_path):
    import regex
    from tokenizers import AddedToken, Regex, Tokenizer, models, pre_tokenizers

    metadata = json.loads(Path(metadata_path).read_text())
    actual = ModelTokenizer(metadata)
    vocab = metadata['tokenizer.ggml.tokens']
    types = metadata['tokenizer.ggml.token_type']
    oracle = Tokenizer(models.BPE(vocab={t: i for i, t in enumerate(vocab)},
                                  merges=[tuple(p.split(' ')) for p in metadata['tokenizer.ggml.merges']]))
    oracle.pre_tokenizer = pre_tokenizers.Sequence([
        pre_tokenizers.Split(Regex(PATTERN), behavior='isolated'),
        pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
    ])
    oracle.add_special_tokens([AddedToken(t, special=True, normalized=False)
                               for t, kind in zip(vocab, types) if kind in (3, 4)])
    rng = random.Random(1038)
    alphabet = 'abCE0123456789 \t\r\n\v\f!?"\'{}[]<>=+-_\x00\x1c\u0085é中界مبनम\u0301👩\u200d🚀'
    samples = [''.join(rng.choices(alphabet, k=rng.randrange(1, 200))) for _ in range(1000)]
    samples += ['abc ' * 10000, ' '*100, 'hello' * 600,
                '<|im_start|>system\nHello.<|im_end|>\n<think>\n',
                ' '.join(chr(n) for n in range(0x20, 0xD800))]
    for index, sample in enumerate(samples):
        assert list(pieces(sample)) == regex.findall(PATTERN, sample), f'pre-split mismatch {index}'
        counted = actual.count(sample)
        # Unassigned codepoints intentionally use a conservative byte bound.
        expected = len(oracle.encode(sample).ids)
        assert counted >= expected, f'unsafe count {index}: {counted} < {expected}'
        if index != len(samples) - 1:
            assert counted == expected, f'count mismatch {index}: {counted} != {expected}'
    print(json.dumps({'independent_oracle_cases': len(samples), 'passed': True}))


def check_backend():
    tokenizer = get_model_tokenizer()
    system = string.Template(Path('system_prompt_template.md').read_text()).substitute(
        current_time_local='10:00 AM on Thursday, September 10, 2026')
    story = ' '.join(['The traveler followed the river home beneath a quiet sky.'] * 40)
    conversation = [{'role': 'system', 'content': system}, {'role': 'user', 'content': 'test'},
                    {'role': 'assistant', 'content': 'Hello. How can I help?'},
                    {'role': 'user', 'content': 'write a 400ish word story'},
                    {'role': 'assistant', 'content': story}]
    cases = [('short', conversation[:2], False),
             ('two_turns', conversation + [{'role': 'user', 'content': 'OK'}], False),
             ('thinking', conversation[:2], True),
             ('large', conversation[:-1] + [{'role': 'assistant', 'content': story * 42},
                                            {'role': 'user', 'content': 'OK'}], False)]
    for name, text in [
        ('unicode', '你好世界。 مرحبا بالعالم। नमस्ते दुनिया। Café e\u0301 👨‍👩‍👧‍👦 0123456789'),
        ('code', 'def add(a, b):\n    return a + b\n\nprint(add(123, 456))'),
        ('json', '{"list": [1, 2, 3], "enabled": true, "text": "Hello\\nworld"}'),
        ('whitespace', ' \r\nword\t\t\n \r next\u00a0word\n\n '),
        ('specials', 'Quote these strings: <|im_start|> <|im_end|> <think> </think>'),
    ]:
        cases.append((name, [{'role': 'system', 'content': 'Synthetic tokenizer test.'},
                             {'role': 'user', 'content': text}], False))
    for name, messages, thinking in cases:
        req = build_chat_completion_request(messages, thinking)
        started = time.monotonic()
        measured = budget_request(req, 131072, 32768, tokenizer=tokenizer)
        elapsed = time.monotonic() - started
        body = {k: v for k, v in req.items() if k != 'extra_body'}
        body.update(req['extra_body'])
        body.update(stream=False, max_tokens=1)
        endpoint = _ollama_base_url() + '/v1/chat/completions'
        with requests.post(endpoint, json={**body, '_debug_render_only': True}, timeout=180) as response:
            response.raise_for_status()
            assert response.json()['_debug_info']['rendered_template'] == rendered_text(req), name
        with requests.post(endpoint, json=body, timeout=180) as response:
            response.raise_for_status()
            actual = response.json()['usage']['prompt_tokens']
        assert measured.input_tokens == actual, name
        assert measured.fits, name
        print(json.dumps({'case': name, 'local_input': measured.input_tokens,
                          'backend_input': actual, 'count_seconds': round(elapsed, 4),
                          'old_byte_bound': budget_request(req, 131072, 32768).input_tokens}), flush=True)
    # Actual model counting at exact/over boundaries, without dispatching a full context.
    req = build_chat_completion_request([{'role': 'user', 'content': '1' * 98000}], False)
    counted = budget_request(req, 131072, 32768, tokenizer=tokenizer).input_tokens
    assert budget_request(req, counted + 32768, 32768, tokenizer=tokenizer).fits
    assert not budget_request(req, counted + 32767, 32768, tokenizer=tokenizer).fits
    print(json.dumps({'near_limit_local_input': counted, 'boundary_passed': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--oracle-metadata', help='Ignored public metadata JSON for independent test oracles')
    parser.add_argument('--backend', action='store_true', help='Run bounded synthetic backend acceptance')
    args = parser.parse_args()
    if args.oracle_metadata:
        check_oracles(args.oracle_metadata)
    if args.backend:
        check_backend()
