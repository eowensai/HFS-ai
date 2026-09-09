"""Conservative admission of the complete, already serialized model request.

The pinned Ollama public API has no tokenizer endpoint. UTF-8 bytes upper-bound
ordinary byte-BPE text tokens conservatively; this is an estimate, not an exact
count. Fixed template/role allowances and a bounded-image allowance cover the
pinned renderer. No previous-turn usage is used for admission.
"""
from dataclasses import dataclass


class BudgetError(ValueError):
    pass


class ContextError(BudgetError):
    """Context/identity could not be verified; a bounded turn may be retried."""


def _heuristic_token_estimate(text: str) -> int:
    return len(text.encode('utf-8')) if text else 0


@dataclass(frozen=True)
class RequestBudget:
    input_tokens: int
    reserve_tokens: int
    capacity: int

    @property
    def fits(self):
        return self.input_tokens + self.reserve_tokens <= self.capacity


def budget_request(request, capacity, reserve, *, image_tokens=8192):
    if not isinstance(capacity, int) or capacity <= 0:
        raise BudgetError('The running model context could not be verified. Request not sent; retry shortly.')
    # Covers renderer scaffolding, start/end tokens, role labels and reasoning prefix.
    count = 512
    for message in request['messages']:
        count += 64 + _heuristic_token_estimate(message['role'])
        content = message['content']
        if isinstance(content, str):
            count += _heuristic_token_estimate(content)
        else:
            for part in content:
                count += 32
                if part['type'] == 'text':
                    count += _heuristic_token_estimate(part['text'])
                elif part['type'] == 'image_url':
                    count += image_tokens
                else:
                    raise BudgetError('Unsupported request content. Request not sent.')
    # Never reduce the actual output allowance/reserve to force admission.
    return RequestBudget(count, max(reserve, request['max_tokens']), capacity)
