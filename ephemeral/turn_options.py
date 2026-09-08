from collections.abc import MutableMapping
from typing import Any

THINKING_MODE_KEY = "thinking_mode_enabled"
SUBMITTED_THINKING_MODE_KEY = "_submitted_thinking_mode"


def capture_thinking_mode_for_submission(state: MutableMapping[str, Any]) -> None:
    """Snapshot the composer toggle for one request and immediately reset the UI switch."""
    state[SUBMITTED_THINKING_MODE_KEY] = bool(state.get(THINKING_MODE_KEY, False))
    state[THINKING_MODE_KEY] = False


def consume_submitted_thinking_mode(state: MutableMapping[str, Any]) -> bool:
    """Return and remove the one-shot Thinking Mode value captured at submission."""
    return bool(state.pop(SUBMITTED_THINKING_MODE_KEY, False))


def reset_thinking_mode(state: MutableMapping[str, Any]) -> None:
    """Restore the ordinary medium-reasoning state and discard any pending snapshot."""
    state[THINKING_MODE_KEY] = False
    state.pop(SUBMITTED_THINKING_MODE_KEY, None)
