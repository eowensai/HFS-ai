"""One bounded in-memory operation per session; workers never access session_state."""
import threading
import time
import uuid
from dataclasses import dataclass

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
from ephemeral.token_budget import (
    BudgetError,
    BudgetSnapshot,
    ContextError,
    budget_request,
)

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


@dataclass(frozen=True)
class WorkSnapshot:
    stage: str
    elapsed: int
    partial: str
    error: str
    notice: str
    done: bool
    messages: tuple
    pending: dict | None
    waiting_for_display: bool
    retryable: bool
    expired: bool
    budget: BudgetSnapshot | None
    revision: int


class TurnWork:
    def __init__(self, owner, messages, text, files, thinking, system, default_prompt):
        # One lock order for publication, rendering and owner release. Never hold
        # it over parser/model I/O. Shared ownership makes a snapshot consistent.
        self.lock = owner._lock
        self.owner, self.messages = owner, messages
        self.id = uuid.uuid4().hex
        self.text, self.files = text, files
        self.thinking, self.system, self.default_prompt = thinking, system, default_prompt
        self.stage = 'Preparing the submission…'
        self.partial = ''
        self.error = ''
        self.notice = ''
        self.done = False
        self.cancelled = threading.Event()
        self._model_guard = None
        self.user_message = None
        self.retryable = False
        self.require_display_ack = False
        self.waiting_for_display = False
        self.displayed = threading.Event()
        self.started = time.monotonic()
        self.stage_started = self.started
        self.request_budget = None
        self.deadline = self.started + cfg.UPLOAD_PROCESS_TIMEOUT_S
        owner.own(self)

    def clear(self):
        self.cancelled.set()
        self.displayed.set()
        if self._model_guard is not None:
            self._model_guard.abort()
        with self.lock:
            for upload in self.files:
                upload.close()
            self.files.clear()
            self.partial = self.text = self.system = self.error = self.notice = ''
            self.user_message = None
            self.stage = ''
            self.stage_started = None
            self.request_budget = None
            self.waiting_for_display = self.retryable = False

    def stopped(self):
        return self.cancelled.is_set() or self.owner.released or time.monotonic() >= self.deadline

    def progress(self, value):
        with self.lock:
            if not self.done and not self.stopped() and value != self.stage:
                self.stage = value
                self.stage_started = time.monotonic()

    def reasoning_event(self, present):
        """Accept only presence; never accept/store dedicated reasoning text."""
        if present is True:
            with self.lock:
                if self.stage != 'Writing…':
                    self.progress('Thinking…')

    def check_running(self):
        if self.stopped():
            raise TimeoutError('Request no longer active')

    def finish(self):
        with self.lock:
            for upload in self.files:
                upload.close()
            self.files.clear()
            self.done = True
            self.stage = ''
            self.stage_started = None
            self.request_budget = None
            self.waiting_for_display = False

    def snapshot(self):
        with self.lock:
            pending = self.user_message or (
                {'id': self.id, 'role': 'user', 'content': self.text} if self.text else None)
            return WorkSnapshot(
                self.stage, max(0, int(time.monotonic() - self.stage_started))
                if self.stage_started is not None else 0,
                self.partial, self.error, self.notice, self.done,
                tuple(self.messages), pending, self.waiting_for_display, self.retryable,
                self.stopped() and not self.owner.released and not self.cancelled.is_set(),
                self.owner.budget_snapshot if self.done else self.request_budget,
                self.messages.revision,
            )

    def acknowledge_display(self):
        with self.lock:
            if self.waiting_for_display and not self.stopped() and not self.done:
                self.displayed.set()

    def append(self, message):
        with self.owner._lock:
            if not self.stopped():
                self.messages.append(message)
                return True
        return False


def conversation_room(messages, pending_bytes=0, *, pending_messages=2):
    return (len(messages) + pending_messages <= cfg.MAX_CONVERSATION_MESSAGES and
            retained_bytes(messages) + pending_bytes + cfg.MAX_RESPONSE_BYTES <= cfg.MAX_CONVERSATION_BYTES)


def run_turn(work, *, parse, model_ready, vision_ready, context, request_builder, client,
             measure=budget_request):
    """Small injectable boundaries support failure tests without changing shared services."""
    stream = None
    sdk_client = None
    model_guard = None
    capacity = None
    context_checked = False
    measurement_started = measurement_ready = False
    receipts = [status_part(attachment_record(f)) for f in work.files[:cfg.MAX_UPLOAD_COUNT]]
    if len(work.files) > cfg.MAX_UPLOAD_COUNT:
        receipts = [status_part({'id': work.id, 'name': 'Upload batch', 'size': 0,
                                 'kind': 'document', 'status': 'unavailable',
                                 'reason': 'Upload count exceeded; no files read.'})]
    try:
        with work.lock:
            work.check_running()
            is_retry = work.user_message is not None and any(m is work.user_message for m in work.messages)
            slots = 1 if is_retry else 2
            if not conversation_room(work.messages, len(work.text.encode('utf-8')), pending_messages=slots):
                raise BudgetError('Conversation storage limit reached. Existing conversation is intact; start New Chat to continue.')
            if len(work.text.encode('utf-8')) > cfg.MAX_PROMPT_BYTES:
                raise BudgetError('Message exceeds the text limit. Shorten it and submit again; existing conversation is intact.')
        vision = vision_ready()
        if work.user_message is None:
            parts = prepare_attachments(work.files, parse, vision, work.progress, work.stopped)
            has_content = available_count(parts)
            with work.lock:
                # Release may occur during parsing. Publish only to a live owner.
                work.check_running()
                text = work.text or (work.default_prompt if has_content else '')
                if text:
                    parts.append({'type': 'text', 'text': text})
                user = {'id': work.id, 'role': 'user', 'content': parts or text}
                if not conversation_room(work.messages, retained_bytes(user)):
                    # Keep receipts in the existing rejection path, not contents.
                    work.user_message = user
                    raise BudgetError('Conversation storage limit reached. New content was excluded; existing conversation is intact.')
                work.user_message = user
                if not work.text and not has_content:
                    work.append(user)
                    work.append({'id': uuid.uuid4().hex, 'role': 'assistant',
                                 'content': 'No attachment content was available, so no analysis request was sent. '
                                            'Upload a readable file or type a question.'})
                    work.user_message = None
                    return
        work.progress('Checking the complete request…')
        with work.lock:
            work.check_running()
            user = work.user_message
            is_stored = any(m is user for m in work.messages)
            pending = [] if is_stored else [user]
            if not conversation_room(work.messages, 0 if is_stored else retained_bytes(user),
                                     pending_messages=1 if is_stored else 2):
                raise BudgetError('Conversation storage limit reached. New content was excluded; existing conversation is intact.')
            payload = [{'role': 'system', 'content': work.system}, *api_messages([*work.messages, *pending], vision)]
            request = request_builder(payload, work.thinking)
        context_checked = True
        capacity = context()
        measurement_started = True
        budget = measure(request, capacity, cfg.LLM_OUTPUT_RESERVE_TOKENS)
        measurement_ready = True
        with work.lock:
            work.check_running()
            work.request_budget = BudgetSnapshot(work.owner.id, work.messages.revision, budget)
            if not budget.fits:
                raise BudgetError(f'Request needs an estimated {budget.input_tokens:,} input tokens plus '
                                  f'{budget.reserve_tokens:,} reserved output tokens; verified capacity is {budget.capacity:,}. '
                                  'No answer was generated. Shorten the request or start New Chat.')
            work.notice = (f'Complete request: conservative estimate {budget.input_tokens:,} input tokens + '
                           f'{budget.reserve_tokens:,} output reserve / {budget.capacity:,} context.')
            if not is_stored:
                work.append(user)
            work.request_budget = BudgetSnapshot(work.owner.id, work.messages.revision, budget)
            work.retryable = True
        if not model_ready():
            raise ConnectionError('Required model unavailable')
        with work.lock:
            work.check_running()
            if work.require_display_ack:
                work.waiting_for_display = True
        if work.require_display_ack:
            while not work.displayed.wait(0.1):
                work.check_running()
        with work.lock:
            work.check_running()
            work.waiting_for_display = False
            work.deadline = time.monotonic() + cfg.LLM_REQUEST_TIMEOUT_S
            work.progress('Waiting for the AI…')
        sdk_client = client()
        model_guard = getattr(sdk_client, '_ephemerai_abort_guard', None)
        if model_guard is not None:
            with work.lock:
                work._model_guard = model_guard
                model_guard.arm(work.deadline)
                if work.stopped():
                    model_guard.abort()
                work.check_running()
        stream = sdk_client.chat.completions.create(**request)
        filter_ = ThinkStreamFilter()
        complete = False
        for chunk in stream:
            work.check_running()
            if not getattr(chunk, 'choices', None):
                continue
            choice = chunk.choices[0]
            delta_obj = getattr(choice, 'delta', None)
            # Verified Ollama 0.32.15 dedicated field. Only a boolean crosses into
            # feedback state; never retain, display or log its text.
            work.reasoning_event(isinstance(getattr(delta_obj, 'reasoning', None), str)
                                 and bool(delta_obj.reasoning.strip()))
            delta = getattr(delta_obj, 'content', None)
            if delta:
                visible = filter_.process_chunk(delta)
                with work.lock:
                    work.check_running()
                    if len(work.partial.encode('utf-8')) + len(visible.encode('utf-8')) > cfg.MAX_RESPONSE_BYTES:
                        raise ValueError('Response buffer limit reached')
                    work.partial += visible
                    if visible.strip():
                        work.progress('Writing…')
            reason = getattr(choice, 'finish_reason', None)
            if reason:
                complete = reason == 'stop'
                if not complete:
                    raise ValueError('Response ended before completion')
        if not complete or work.stopped() or filter_.in_think_block:
            raise ValueError('Response interrupted before completion')
        tail = filter_.finalize()
        with work.lock:
            work.check_running()
            if len(work.partial.encode('utf-8')) + len(tail.encode('utf-8')) > cfg.MAX_RESPONSE_BYTES:
                raise ValueError('Response buffer limit reached')
            answer = strip_think_blocks(work.partial + tail)
            if not answer.strip():
                raise ValueError('No visible answer received')
            work.append({'id': uuid.uuid4().hex, 'role': 'assistant', 'content': answer})
            work.partial = ''
            work.user_message = None
            work.retryable = False
    except ContextError as exc:
        with work.lock:
            if not work.owner.released and not work.cancelled.is_set():
                work.error = str(exc)
                user = work.user_message
                if (user and not any(m is user for m in work.messages)
                        and conversation_room(work.messages, retained_bytes(user))):
                    work.append(user)
                work.retryable = user is not None and any(m is user for m in work.messages)
                if not work.retryable:
                    work.user_message = None
    except BudgetError as exc:
        with work.lock:
            if not work.owner.released and not work.cancelled.is_set():
                work.error = str(exc)
                work.retryable = False
                user = work.user_message
                if user and not any(m is user for m in work.messages):
                    receipts = exclude_content(user['content'] if isinstance(user['content'], list) else [],
                                               'Excluded: request or conversation limit; content was not sent.')
                    stub = {'id': work.id, 'role': 'user', 'content': receipts}
                    if receipts and conversation_room(work.messages, retained_bytes(stub)):
                        work.append(stub)
                work.user_message = None
    except Exception as exc:  # noqa: BLE001 - sanitize all backend errors at the UI boundary
        with work.lock:
            if not work.owner.released and not work.cancelled.is_set():
                if (isinstance(exc, TimeoutError) or 'timeout' in type(exc).__name__.lower()
                        or (model_guard is not None and model_guard.expired)):
                    work.error = 'Work timed out. Any partial reply is incomplete and is excluded from model history.'
                else:
                    work.error = ('The model request failed or the response ended before completion. '
                                  'Any partial reply is incomplete and is excluded from model history.')
                # Exceptions can contain content: never display/log their strings.
    finally:
        if model_guard is not None:
            model_guard.finish()
        if stream is not None and hasattr(stream, 'close'):
            try:
                stream.close()
            except Exception:  # noqa: BLE001 - cleanup must preserve the original status
                with work.lock:
                    work.retryable = False
        if sdk_client is not None and hasattr(sdk_client, 'close'):
            try:
                sdk_client.close()
            except Exception:  # noqa: BLE001 - never expose transport exception content
                pass
        with work.lock:
            work._model_guard = None
            if (work.error and receipts and not work.owner.released and not work.cancelled.is_set()
                    and not any(m.get('id') == work.id for m in work.messages)):
                stub = {'id': work.id, 'role': 'user', 'content': exclude_content(receipts,
                        'Unavailable: the request failed validation or reading; content was not sent.')}
                if conversation_room(work.messages, retained_bytes(stub)):
                    work.messages.append(stub)
            live = not work.stopped()
        # No polling/probe for the caption: once at this content transition, using
        # this request's verified capacity. Failed verification stays unavailable.
        if live and not context_checked:
            try:
                capacity = context()
            except Exception:  # noqa: BLE001 - optional measurement cannot mask the request outcome
                capacity = None
        retained = None
        with work.lock:
            if not work.stopped():
                work.owner.budget_snapshot = None
                if capacity is not None and (not measurement_started or measurement_ready):
                    try:
                        retained = request_builder([{'role': 'system', 'content': work.system},
                                                    *api_messages(work.messages)], False)
                        revision = work.messages.revision
                    except Exception:  # noqa: BLE001 - optional feedback must not mask an outcome or block cleanup
                        retained = None
        # Counting can initialize public model metadata. Never hold the owner
        # lock over that work, or retry a failed admission count for feedback.
        measured = None
        if retained is not None:
            try:
                measured = measure(retained, capacity, cfg.LLM_OUTPUT_RESERVE_TOKENS)
            except Exception:  # noqa: BLE001 - optional feedback cannot mask the request outcome
                measured = None
        with work.lock:
            if (measured is not None and not work.owner.released and not work.cancelled.is_set()
                    and work.messages.revision == revision):
                work.owner.budget_snapshot = BudgetSnapshot(work.owner.id, revision, measured)
            work.text = ''
            work.system = ''
            work.stage = ''
            work.stage_started = None
            work.request_budget = None
            work.waiting_for_display = False
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
