"""One bounded in-memory operation per session; workers never access session_state."""
import threading
import time
import uuid

from ephemeral import config as cfg
from ephemeral.attachments import (
    api_messages,
    attachment_record,
    available_count,
    exclude_content,
    prepare_attachments,
    retained_bytes,
    status_part,
)
from ephemeral.stream_filter import ThinkStreamFilter, strip_think_blocks
from ephemeral.token_budget import BudgetError, ContextError, budget_request

_ACTIVE = threading.BoundedSemaphore(cfg.MAX_ACTIVE_REQUESTS)


class WorkGate:
    def __init__(self):
        self.lock = threading.RLock()
        self.active = None
        self.running = False

    def start(self, work, target):
        with self.lock:
            if self.running or not _ACTIVE.acquire(blocking=False):
                return False
            self.active, self.running = work, True

        def run():
            try:
                target(work)
            finally:
                work.finish()
                with self.lock:
                    self.running = False
                _ACTIVE.release()
        threading.Thread(target=run, daemon=True, name='ephemerai-request').start()
        return True


class TurnWork:
    def __init__(self, owner, messages, text, files, thinking, system, default_prompt):
        self.lock = threading.RLock()
        self.owner, self.messages = owner, messages
        self.id = uuid.uuid4().hex
        self.text, self.files = text, files
        self.thinking, self.system, self.default_prompt = thinking, system, default_prompt
        self.stage = 'Reading attachments…' if files else 'Checking request…'
        self.partial = ''
        self.error = ''
        self.notice = ''
        self.done = False
        self.cancelled = threading.Event()
        self.user_message = None
        self.retryable = False
        self.require_display_ack = False
        self.waiting_for_display = False
        self.displayed = threading.Event()
        self.started = time.monotonic()
        self.deadline = self.started + cfg.UPLOAD_PROCESS_TIMEOUT_S
        owner.own(self)

    def clear(self):
        self.cancelled.set()
        self.displayed.set()
        with self.lock:
            for upload in self.files:
                upload.close()
            self.files.clear()
            self.partial = self.text = self.system = self.error = self.notice = ''
            self.user_message = None

    def stopped(self):
        return self.cancelled.is_set() or self.owner.released or time.monotonic() >= self.deadline

    def progress(self, value):
        with self.lock:
            if not self.stopped():
                self.stage = value

    def finish(self):
        with self.lock:
            for upload in self.files:
                upload.close()
            self.files.clear()
            self.done = True

    def snapshot(self):
        with self.lock:
            return self.stage, self.partial, self.error, self.notice, self.done

    def append(self, message):
        with self.owner._lock:
            if not self.stopped():
                self.messages.append(message)
                return True
        return False


def conversation_room(messages, pending_bytes=0):
    return (len(messages) + 2 <= cfg.MAX_CONVERSATION_MESSAGES and
            retained_bytes(messages) + pending_bytes + cfg.MAX_RESPONSE_BYTES <= cfg.MAX_CONVERSATION_BYTES)


def run_turn(work, *, parse, model_ready, vision_ready, context, request_builder, client):
    """Small injectable boundaries support failure tests without changing shared services."""
    stream = None
    receipts = [status_part(attachment_record(f)) for f in work.files[:cfg.MAX_UPLOAD_COUNT]]
    if len(work.files) > cfg.MAX_UPLOAD_COUNT:
        receipts = [status_part({'id': work.id, 'name': 'Upload batch', 'size': 0,
                                 'kind': 'document', 'status': 'unavailable',
                                 'reason': 'Upload count exceeded; no files read.'})]
    try:
        if not conversation_room(work.messages, len(work.text.encode('utf-8'))):
            raise BudgetError('Conversation storage limit reached. Existing conversation is intact; start New Chat to continue.')
        if len(work.text.encode('utf-8')) > cfg.MAX_PROMPT_BYTES:
            raise BudgetError('Message exceeds the text limit. Shorten it and submit again; existing conversation is intact.')
        vision = vision_ready()
        if work.user_message is None:
            parts = prepare_attachments(work.files, parse, vision, work.progress, work.stopped)
            if work.stopped():
                raise TimeoutError('Reading deadline exceeded')
            has_content = available_count(parts)
            text = work.text or (work.default_prompt if has_content else '')
            if text:
                parts.append({'type': 'text', 'text': text})
            work.user_message = {'id': work.id, 'role': 'user', 'content': parts or text}
            # No content reached the model: never create an automatic analysis request.
            if not work.text and not has_content:
                work.append(work.user_message)
                work.append({'id': uuid.uuid4().hex, 'role': 'assistant',
                             'content': 'No attachment content was available, so no analysis request was sent. '
                                        'Upload a readable file or type a question.'})
                work.user_message = None
                return
        user = work.user_message
        is_stored = any(m is user for m in work.messages)
        pending = [] if is_stored else [user]
        if not conversation_room(work.messages, 0 if is_stored else retained_bytes(user)):
            raise BudgetError('Conversation storage limit reached. New content was excluded; existing conversation is intact.')
        payload = [{'role': 'system', 'content': work.system}, *api_messages([*work.messages, *pending], vision)]
        request = request_builder(payload, work.thinking)
        budget = budget_request(request, context(), cfg.LLM_OUTPUT_RESERVE_TOKENS)
        if not budget.fits:
            raise BudgetError(f'Request needs an estimated {budget.input_tokens:,} input tokens plus '
                              f'{budget.reserve_tokens:,} reserved output tokens; verified capacity is {budget.capacity:,}. '
                              'No answer was generated. Shorten the request or start New Chat.')
        work.notice = (f'Complete request: conservative estimate {budget.input_tokens:,} input tokens + '
                       f'{budget.reserve_tokens:,} output reserve / {budget.capacity:,} context.')
        if not is_stored:
            work.append(user)
        # Retain the bounded user turn for a manual retry; never append it twice.
        work.retryable = True
        if not model_ready():
            raise ConnectionError('Required model unavailable')
        if work.stopped():
            return
        if work.require_display_ack:
            work.waiting_for_display = True
            while not work.displayed.wait(0.1):
                if work.stopped():
                    return
        if work.stopped():
            return
        work.deadline = time.monotonic() + cfg.LLM_REQUEST_TIMEOUT_S
        work.progress('Waiting for model response…')
        stream = client().chat.completions.create(**request)
        filter_ = ThinkStreamFilter()
        complete = False
        for chunk in stream:
            if work.stopped():
                raise TimeoutError('Model response deadline exceeded')
            if not getattr(chunk, 'choices', None):
                continue
            choice = chunk.choices[0]
            delta = getattr(getattr(choice, 'delta', None), 'content', None)
            # Hidden reasoning is never read into application state or UI output.
            if delta:
                visible = filter_.process_chunk(delta)
                with work.lock:
                    if work.stopped():
                        break
                    if len(work.partial.encode('utf-8')) + len(visible.encode('utf-8')) > cfg.MAX_RESPONSE_BYTES:
                        raise ValueError('Response buffer limit reached')
                    work.partial += visible
                    work.stage = 'Receiving response…'
            reason = getattr(choice, 'finish_reason', None)
            if reason:
                complete = reason == 'stop'
                if not complete:
                    raise ValueError('Response ended before completion')
        if not complete or work.stopped() or filter_.in_think_block:
            raise ValueError('Response interrupted before completion')
        tail = filter_.finalize()
        if len(work.partial.encode('utf-8')) + len(tail.encode('utf-8')) > cfg.MAX_RESPONSE_BYTES:
            raise ValueError('Response buffer limit reached')
        answer = strip_think_blocks(work.partial + tail)
        if not answer.strip():
            raise ValueError('No visible answer received')
        work.append({'id': uuid.uuid4().hex, 'role': 'assistant', 'content': answer})
        work.partial = ''
        work.user_message = None
        work.retryable = False
        work.stage = 'Complete'
    except ContextError as exc:
        work.error = str(exc)
        user = work.user_message
        if (user and not any(m is user for m in work.messages)
                and conversation_room(work.messages, retained_bytes(user))):
            work.append(user)
        work.retryable = user is not None and any(m is user for m in work.messages)
        if not work.retryable:
            work.user_message = None
    except BudgetError as exc:
        work.error = str(exc)
        work.retryable = False
        user = work.user_message
        if user and not any(m is user for m in work.messages):
            # Record excluded attachment status, not the rejected text or contents.
            receipts = exclude_content(user['content'] if isinstance(user['content'], list) else [],
                                       'Excluded: request or conversation limit; content was not sent.')
            stub = {'id': work.id, 'role': 'user', 'content': receipts}
            if receipts and conversation_room(work.messages, retained_bytes(stub)):
                work.append(stub)
        work.user_message = None
    except Exception as exc:  # noqa: BLE001 - sanitize all backend errors at the UI boundary
        if isinstance(exc, (TimeoutError,)) or 'timeout' in type(exc).__name__.lower():
            work.error = 'Work timed out. Any partial reply is incomplete and is excluded from model history.'
        else:
            work.error = ('The model request failed or the response ended before completion. '
                          'Any partial reply is incomplete and is excluded from model history.')
        # Exceptions may contain prompts, document text or server bodies; never display/log them.
    finally:
        if (work.error and receipts and not work.owner.released and not work.cancelled.is_set()
                and not any(m.get('id') == work.id for m in work.messages)):
            stub = {'id': work.id, 'role': 'user', 'content': exclude_content(receipts,
                    'Unavailable: the request failed validation or reading; content was not sent.')}
            if conversation_room(work.messages, retained_bytes(stub)):
                work.messages.append(stub)
        if stream is not None and hasattr(stream, 'close'):
            try:
                stream.close()
            except Exception:  # noqa: BLE001 - cleanup must preserve the original status
                work.retryable = False
        work.text = ''
        work.system = ''
        for upload in work.files:
            upload.close()
        work.files.clear()


def record_rejected_uploads(messages, files, reason):
    """A rejected submission still leaves bounded, truthful attachment receipts."""
    receipts = [status_part(attachment_record(f)) for f in files[:cfg.MAX_UPLOAD_COUNT]]
    if len(files) > cfg.MAX_UPLOAD_COUNT:
        receipts = [status_part({'id': uuid.uuid4().hex, 'name': 'Upload batch', 'size': 0,
                                 'kind': 'document', 'status': 'unavailable', 'reason': reason})]
    if not receipts:
        return
    stub = {'id': uuid.uuid4().hex, 'role': 'user', 'content': exclude_content(receipts, reason)}
    with messages.owner._lock:
        if conversation_room(messages, retained_bytes(stub)):
            messages.append(stub)
