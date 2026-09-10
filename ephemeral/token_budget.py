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


@dataclass(frozen=True)
class BudgetSnapshot:
    conversation_id: str
    revision: int
    budget: RequestBudget


BUDGET_HELP = (
    "This is the app’s conservative estimate, with room reserved for an answer—"
    "not measured computer memory or exact model usage. New text and files are "
    "checked when you send them. A new chat does not carry over this conversation or its files."
)


def budget_percent(snapshot, conversation_id, revision):
    """Return a floored estimate or None for missing, stale or invalid data."""
    if (not isinstance(snapshot, BudgetSnapshot) or snapshot.conversation_id != conversation_id
            or snapshot.revision != revision):
        return None
    budget = snapshot.budget
    if (not isinstance(budget, RequestBudget) or any(type(n) is not int for n in
            (budget.input_tokens, budget.reserve_tokens, budget.capacity))
            or budget.input_tokens < 0 or budget.reserve_tokens < 0
            or budget.capacity <= budget.reserve_tokens):
        return None
    # Reserve once. Integer arithmetic floors, including at/above the valid boundary.
    return budget.input_tokens * 100 // (budget.capacity - budget.reserve_tokens)


def budget_caption(snapshot, conversation_id, revision, *, submitted=False):
    """Format cached numbers only; no new counting or backend probes in rendering."""
    label = 'This request’s budget' if submitted else 'Conversation budget'
    percent = budget_percent(snapshot, conversation_id, revision)
    if percent is None:
        return f'{label} unavailable'
    warning = ('Over limit' if not snapshot.budget.fits else
               'Almost full' if percent >= 95 else 'Getting full' if percent >= 80 else '')
    return f'{label}: ~{percent}% used' + (f' · {warning}' if warning else '')


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
