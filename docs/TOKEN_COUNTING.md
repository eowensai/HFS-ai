# Model-matched local admission counting

The byte-per-token admission rule rejected useful text context too early. A
synthetic two-turn conversation counted as 8,319 input tokens under that rule but
as 1,500 by the installed model. A larger synthetic conversation counted as
103,398 versus 19,499: the former rejected it despite ample verified capacity.

The local candidate supplies `budget_request` with a tokenizer constructed from
the installed model's public GGUF vocabulary, token types, and ranked merge rules.
It matches the `qwen35` Unicode pre-split and byte-pair encoding. Text-only requests
include the pinned Ollama Qwen3.8 renderer's role delimiters, whitespace handling,
empty assistant thought blocks, generation prefix, and the additional instruction
used for the one-turn xhigh mode. This is static renderer scaffolding, not saved
model reasoning. The serializer used for actual dispatch is unchanged.

There is no character/token ratio and no learned multiplier from previous replies.
Admission remains `input_tokens + max(configured_reserve, max_tokens) <= capacity`.
Both the 131,072 context and 32,768 output allowance/reserve remain unchanged. No
history truncation, summarization, context enlargement, or bypass was added.

## Validation and failure behavior

The tokenizer metadata fingerprint is pinned to the supported installed model:
`1c86283d5ec7f949be9df2f76c443c32296008c6844b7146b674abe8dc3645e8`.
Initialization verifies Ollama 0.32.15 and downloads public metadata once per app
process from `/api/show` with `verbose: true`. Reading is time/size bounded, and
only the vocabulary/merge tables remain in memory. Existing model identity and
fresh context checks remain in the request path. Unsupported metadata/version or
loading failure prevents dispatch with a retryable error; it does not silently
substitute the old byte rule. Cached numeric snapshots use the same measurement
function as admission. No backend counting request runs per turn or per refresh.

The counting correction changed no production dependency, framework, model,
backend service, network setting, or UI layout. A subsequent presentation-only
change removed the percentage caption, Budget help, and near-limit copy reminder.
Canonical counting, snapshots, admission checks, and rejection errors remain intact.

## Deliberately conservative cases

- Image requests retain the reviewed 8,192-token allowance per bounded image and
  template/part overhead. Their text is now tokenized; base64 is not counted as text.
- An uninterrupted pre-tokenization piece exceeding 4,096 bytes keeps a byte
  bound for that piece, avoiding a large adversarial merge heap.
- Text containing codepoints unassigned in Python's Unicode database keeps its
  byte bound rather than guessing a newer backend's character classification.

Those exceptional cases can still overcount. Ordinary supported text uses model
tokenization, including non-English letters, combining marks, emoji, code, numbers,
and punctuation. This is not a claim that all image or arbitrary Unicode inputs
have an exact count, nor does it remove the separate upload/conversation limits.
There are no input/token caches, generated-content logs, or on-disk conversation
artifacts. The public vocabulary is shared read-only; request text remains local
to the counting call.

## Reproducible acceptance

Run repository tests normally. `tests/test_model_tokenizer.py` covers byte-complete
BPE merges, Unicode splitting, special tokens, metadata/version rejection,
concurrent use without input caching, exact/over-limit admission, unchanged output
and image allowances, and production wiring through admission/retention.

`python scripts/verify_token_counting.py --backend` uses only synthetic content and
one output token per generation. It compares local rendering with the backend's
debug renderer in memory, then local counts with actual backend input usage.
Near-limit cases are counted locally and use adjusted capacity boundaries; they
do not dispatch a full-context request. Only numeric results/booleans are printed.

For independent test-only oracles, install `requirements-oracles.txt` in
an isolated test environment. Provide an ignored JSON file containing the public
`tokenizer.ggml.*` metadata to
`python scripts/verify_token_counting.py --oracle-metadata PATH`. The deterministic
corpus has 1,005 cases. These packages are not needed or installed in production.
The controlled browser runner uses that same public metadata file through
`TOKENIZER_TEST_METADATA=PATH`; its inference/parser endpoints remain doubles.
The real browser runner includes a >98-KB document through Tika and the supported
model, checking both end markers and retained-file follow-up.

## Implementation sources

- [Pinned Ollama Qwen3.8 renderer](https://github.com/ollama/ollama/blob/v0.32.15/model/renderers/qwen35.go)
- [Pinned Ollama OpenAI message conversion](https://github.com/ollama/ollama/blob/v0.32.15/openai/openai.go)
- [Qwen35 pre-tokenization expression](https://github.com/ggml-org/llama.cpp/blob/master/src/llama-vocab.cpp)
- [Pinned Ollama byte-pair encoding](https://github.com/ollama/ollama/blob/v0.32.15/tokenizer/bytepairencoding.go)

Actual installed-backend comparisons, rather than a family-name assumption, are
the acceptance evidence for this pinned profile. Any model/tokenizer/renderer
upgrade requires revalidation.

Python 3.14 acceptance also compares Unicode 15/16 assignments (new letters,
combining marks and digits) with the pinned backend. These cases match exactly;
the existing unassigned-codepoint byte bound remains in force.
