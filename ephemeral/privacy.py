"""Conversation ownership, independent of Streamlit callback thread context."""
from collections import OrderedDict
from secrets import token_hex
from threading import RLock
from uuid import uuid4


class ConversationPayloads:
    """Release owned mutable payloads without looking up another thread's session."""

    def __init__(self):
        self._lock = RLock()
        self._owned = []
        self.released = False
        self.id = uuid4().hex
        self.budget_snapshot = None
        self.cache_salt = token_hex(32)
        self.system_prompt = None

    def own(self, payload):
        with self._lock:
            if self.released:
                self._clear(payload)
            elif not any(item is payload for item in self._owned):
                self._owned.append(payload)
        return payload

    def disown(self, payload):
        """Release completed work without retaining superseded results until New Chat."""
        with self._lock:
            self._owned[:] = [item for item in self._owned if item is not payload]

    @staticmethod
    def _clear(payload):
        if hasattr(payload, "close"):
            payload.close()
        else:
            payload.clear()

    def release(self):
        with self._lock:
            self.released = True
            self.budget_snapshot = None
            self.cache_salt = None
            self.system_prompt = None
            owned, self._owned = self._owned, []
            for payload in owned:
                try:
                    self._clear(payload)
                except Exception:
                    # One failing close must not retain every other payload or
                    # prevent late-result rejection. Never log exception content.
                    continue


class ConversationMessages(list):
    """Prevent an in-flight response from repopulating a released conversation."""

    def __init__(self, owner, values=()):
        super().__init__(values)
        self.owner = owner
        self.revision = 0
        owner.budget_snapshot = None
        owner.own(self)

    def append(self, value):
        with self.owner._lock:
            if not self.owner.released:
                super().append(value)
                self.revision += 1
                self.owner.budget_snapshot = None

    def clear(self):
        with self.owner._lock:
            super().clear()
            self.revision += 1
            self.owner.budget_snapshot = None


class ConversationTokenCache(OrderedDict):
    """Hash/count metadata cannot be repopulated after session release."""

    def __init__(self, owner, values=()):
        self.owner = owner
        super().__init__(values)
        owner.own(self)
