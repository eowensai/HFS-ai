"""Local text counting for the pinned GGUF qwen35 byte-pair tokenizer.

Only public vocabulary metadata is retained. No input/token cache, logging,
network I/O, or Streamlit dependency. See docs/TOKEN_COUNTING.md for provenance.
"""
import hashlib
import heapq
import json
import re
import unicodedata

TOKENIZER_SHA256 = '1c86283d5ec7f949be9df2f76c443c32296008c6844b7146b674abe8dc3645e8'
MAX_PIECE_BYTES = 4096
_SPACE = frozenset('\t\n\v\f\r \x85\xa0\u1680\u2000\u2001\u2002\u2003'
                   '\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000')
_CONTRACTION = re.compile("'(?:[sStTmMdD]|[rR][eE]|[vV][eE]|[lL][lL])")


def pieces(text):
    """Equivalent qwen35 pre-split, using Unicode categories instead of a dependency.

    Ordered alternatives match the upstream expression, including combining
    marks, single digits, punctuation/newlines, and whitespace backtracking.
    """
    i, size = 0, len(text)
    while i < size:
        start = i
        contraction = _CONTRACTION.match(text, i)
        if contraction:
            i = contraction.end()
        else:
            category = unicodedata.category(text[i])[0]
            j = i
            if text[j] not in '\r\n' and category not in 'LN':
                j += 1
            if j < size and unicodedata.category(text[j])[0] in 'LM':
                i = j + 1
                while i < size and unicodedata.category(text[i])[0] in 'LM':
                    i += 1
            elif category in 'LM':
                i += 1
                while i < size and unicodedata.category(text[i])[0] in 'LM':
                    i += 1
            elif category == 'N':
                i += 1
            else:
                j = i + (text[i] == ' ')
                if j < size and text[j] not in _SPACE and unicodedata.category(text[j])[0] not in 'LMN':
                    i = j + 1
                    while i < size and text[i] not in _SPACE and unicodedata.category(text[i])[0] not in 'LMN':
                        i += 1
                    while i < size and text[i] in '\r\n':
                        i += 1
                elif text[i] in _SPACE:
                    j, last_newline = i, None
                    while j < size and text[j] in _SPACE:
                        if text[j] in '\r\n':
                            last_newline = j
                        j += 1
                    i = (last_newline + 1 if last_newline is not None else
                         j - 1 if j < size and j - start > 1 else j)
                else:
                    i += 1
        yield text[start:i]


def _byte_decoder():
    visible = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256))
    result = {chr(b): b for b in visible}
    for i, b in enumerate(b for b in range(256) if b not in visible):
        result[chr(256 + i)] = b
    return result


class ModelTokenizer:
    def __init__(self, metadata):
        metadata = {k: v for k, v in metadata.items() if k.startswith('tokenizer.ggml.')}
        digest = hashlib.sha256(json.dumps(metadata, sort_keys=True, ensure_ascii=True,
                                           separators=(',', ':')).encode()).hexdigest()
        if digest != TOKENIZER_SHA256:
            raise ValueError('Tokenizer metadata does not match the supported model')
        decoder = _byte_decoder()

        def decode(value):
            return bytes(decoder[c] for c in value)

        tokens, types = metadata['tokenizer.ggml.tokens'], metadata['tokenizer.ggml.token_type']
        self._vocab = frozenset(decode(t) for t, kind in zip(tokens, types) if kind == 1)
        self._merges = {tuple(decode(t) for t in pair.split(' ')): rank
                        for rank, pair in enumerate(metadata['tokenizer.ggml.merges'])}
        special = sorted((t for t, kind in zip(tokens, types) if kind in (3, 4)), key=len, reverse=True)
        self._special = re.compile('(' + '|'.join(re.escape(t) for t in special) + ')')

    def count(self, text):
        # Python's Unicode table may predate a newly assigned character. Do not
        # guess how a newer backend groups it: retain the safe byte bound there.
        if any(unicodedata.category(c) == 'Cn' for c in text):
            return len(text.encode('utf-8'))
        count = 0
        for i, fragment in enumerate(self._special.split(text)):
            if i % 2:
                count += 1
            else:
                count += sum(self._count_piece(piece.encode('utf-8')) for piece in pieces(fragment))
        return count

    def _count_piece(self, raw):
        if raw in self._vocab:
            return 1
        # Adversarial uninterrupted strings must not cause unbounded heap work.
        # Bound only this exceptional piece; normal words still use exact BPE.
        if len(raw) > MAX_PIECE_BYTES:
            return len(raw)
        values = [bytes([b]) for b in raw]
        previous = list(range(-1, len(raw) - 1))
        following = list(range(1, len(raw) + 1))
        heap = []

        def enqueue(left):
            if left < 0:
                return
            right = following[left]
            if right < len(raw):
                pair = (values[left], values[right])
                rank = self._merges.get(pair)
                if rank is not None:
                    heapq.heappush(heap, (rank, left, right, pair))

        for left in range(len(raw) - 1):
            enqueue(left)
        remaining = len(raw)
        while heap:
            _, left, right, pair = heapq.heappop(heap)
            if following[left] != right or (values[left], values[right]) != pair:
                continue
            merged = pair[0] + pair[1]
            if merged not in self._vocab:
                continue
            values[left], values[right] = merged, b''
            following[left] = following[right]
            if following[right] < len(raw):
                previous[following[right]] = left
            remaining -= 1
            enqueue(previous[left])
            enqueue(left)
        return remaining


# Pinned Ollama 0.32.15 Qwen3.8 renderer instruction, not generated reasoning.
_XHIGH = ('Reasoning effort is set to xhigh. Please think carefully through the task, '
          'validate key assumptions, consider plausible alternatives, and prioritize '
          'correctness, consistency, and clarity in the final answer.')


def rendered_text(request):
    """Render the app's supported text-only request exactly like pinned Ollama.

    Reject new roles/tools/parts instead of silently undercounting. Multimodal
    requests retain separate bounded-image accounting in the canonical budget.
    """
    if request.get('tools') or request.get('tool_choice'):
        raise ValueError('Unsupported request tools')
    effort = request.get('extra_body', {}).get('reasoning_effort', 'medium')
    if effort not in ('medium', 'xhigh'):
        raise ValueError('Unsupported request reasoning profile')
    messages = request['messages']
    output = []
    for i, message in enumerate(messages):
        role, content = message['role'], message['content']
        if role not in ('system', 'user', 'assistant') or not isinstance(content, str):
            raise ValueError('Unsupported request message')
        if any(k not in ('role', 'content') for k in message) or (role == 'system' and i != 0):
            raise ValueError('Unsupported request message fields')
        content = content.strip(''.join(_SPACE))
        if i == 0:
            system = content if role == 'system' else ''
            if effort == 'xhigh':
                system = _XHIGH + ('\n\n' + system if system else '')
            if system:
                output.append('<|im_start|>system\n' + system + '<|im_end|>\n')
        if role == 'system':
            continue
        output.append('<|im_start|>' + role + '\n')
        if role == 'assistant':
            output.append('<think>\n\n</think>\n\n')
        output.append(content)
        if not (i == len(messages) - 1 and role == 'assistant'):
            output.append('<|im_end|>\n')
    if messages and messages[-1]['role'] != 'assistant':
        output.append('<|im_start|>assistant\n<think>\n')
    return ''.join(output)
