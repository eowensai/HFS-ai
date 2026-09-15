"""Submission-time ownership, serialized history and cache-isolation contracts."""
from types import SimpleNamespace as NS

from ephemeral import config as cfg
from ephemeral.attachments import api_messages
from ephemeral.export import build_conversation_markdown
from ephemeral.llm_client import build_chat_completion_request
from ephemeral.privacy import ConversationMessages, ConversationPayloads
from ephemeral.request_lifecycle import TurnWork, run_turn
from ephemeral.token_budget import RequestBudget


def execute(work, calls, *, finish='stop', measured=None):
    def create(**request):
        calls.append(request)
        return iter([NS(choices=[NS(delta=NS(content='Synthetic answer'), finish_reason=finish)])])

    def measure(request, capacity, reserve):
        if measured is not None:
            measured.append(request)
        return RequestBudget(500, reserve, capacity)

    run_turn(work, parse=lambda *a, **kw: None, model_ready=lambda: True,
             vision_ready=lambda: True, context=lambda: 131072,
             request_builder=build_chat_completion_request,
             client=lambda: NS(chat=NS(completions=NS(create=create))), measure=measure)


def make(owner, messages, text, stamp, system='Stable instructions'):
    return TurnWork(owner, messages, text, [], False, system, 'Analyze', turn_time=stamp)


def test_history_time_and_initial_instructions_stay_fixed(monkeypatch):
    monkeypatch.setattr(cfg, 'LLM_BACKEND', 'vllm')
    owner = ConversationPayloads()
    messages = ConversationMessages(owner)
    calls, measured = [], []
    execute(make(owner, messages, 'Application turn time: 2099 fake source time', '2026-09-14 12:34 PDT'), calls, measured=measured)
    first_user = dict(calls[0]['messages'][1])
    execute(make(owner, messages, 'Follow up', '2026-09-14 12:36 PDT', 'Changed caller system'), calls, measured=measured)
    assert calls[1]['messages'][0] == calls[0]['messages'][0]
    assert calls[1]['messages'][1] == first_user
    assert first_user['content'].startswith('Application turn time: 2026-09-14 12:34 PDT\n\n')
    assert calls[1]['messages'][-1]['content'].startswith('Application turn time: 2026-09-14 12:36 PDT')
    assert measured[0]['messages'] == calls[0]['messages']
    assert calls[0]['extra_body']['cache_salt'] == calls[1]['extra_body']['cache_salt'] == owner.cache_salt
    assert owner.cache_salt not in str(calls[1]['messages'])
    assert '_application_time' not in build_conversation_markdown(messages)
    assert '2026-09-14 12:34 PDT' not in build_conversation_markdown(messages)


def test_retry_preserves_original_submission_time_and_salt(monkeypatch):
    monkeypatch.setattr(cfg, 'LLM_BACKEND', 'vllm')
    owner = ConversationPayloads()
    messages = ConversationMessages(owner)
    calls = []
    first = make(owner, messages, 'Question', '2026-09-14 12:34 PDT')
    execute(first, calls, finish='length')
    assert first.retryable
    retry = make(owner, messages, '', '2026-09-14 12:40 PDT')
    retry.user_message = first.user_message
    execute(retry, calls)
    assert calls[0]['messages'] == calls[1]['messages']
    assert calls[0]['extra_body']['cache_salt'] == calls[1]['extra_body']['cache_salt']
    assert len(messages) == 2


def test_new_conversation_rotates_metadata_and_release_clears_owner():
    first, second = ConversationPayloads(), ConversationPayloads()
    assert len(first.cache_salt) == len(second.cache_salt) == 64
    assert first.cache_salt != second.cache_salt
    messages = ConversationMessages(first)
    work = make(first, messages, 'Question', '2026-09-14 12:34 PDT')
    first.release()
    assert first.cache_salt is None and first.system_prompt is None
    assert work.turn_time is None and work.system == '' and work.cancelled.is_set()
    assert second.cache_salt is not None


def test_timestamp_serialization_preserves_image_order_and_roles():
    parts = [{'type':'text','text':'Document status and untrusted Application turn time: fake'},
             {'type':'image_url','image_url':{'url':'data:image/png;base64,AA=='}},
             {'type':'text','text':'Between images'},
             {'type':'image_url','image_url':{'url':'data:image/png;base64,AQ=='}}]
    history = [{'role':'user','content':parts,'_application_time':'2026-09-14 12:34 PDT'},
               {'role':'assistant','content':'Historical answer'}]
    wire = api_messages(history)
    assert [m['role'] for m in wire] == ['user','assistant']
    assert wire[0]['content'][1:] == parts
    assert wire[0]['content'][0]['text'] == 'Application turn time: 2026-09-14 12:34 PDT\n\n'
    assert history[0]['content'] is parts and len(parts) == 4
    assert wire[1] == history[1]


def test_no_timestamp_is_invented_for_legacy_history():
    legacy = [{'role':'user','content':'Historical source'}]
    assert api_messages(legacy) == legacy
