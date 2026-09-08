from ephemeral.config import reasoning_effort_for_turn
from ephemeral.turn_options import (
    SUBMITTED_THINKING_MODE_KEY,
    THINKING_MODE_KEY,
    capture_thinking_mode_for_submission,
    consume_submitted_thinking_mode,
    reset_thinking_mode,
)


def test_selected_thinking_mode_is_xhigh_once_then_next_submission_returns_to_medium():
    state = {THINKING_MODE_KEY: True}

    capture_thinking_mode_for_submission(state)

    assert state[THINKING_MODE_KEY] is False
    selected_turn = consume_submitted_thinking_mode(state)
    assert selected_turn is True
    assert reasoning_effort_for_turn(selected_turn) == "xhigh"
    assert consume_submitted_thinking_mode(state) is False

    capture_thinking_mode_for_submission(state)
    next_turn = consume_submitted_thinking_mode(state)
    assert next_turn is False
    assert reasoning_effort_for_turn(next_turn) == "medium"
    assert state[THINKING_MODE_KEY] is False


def test_default_submission_keeps_switch_off_and_uses_medium_reasoning():
    state = {THINKING_MODE_KEY: False}

    capture_thinking_mode_for_submission(state)

    submitted_turn = consume_submitted_thinking_mode(state)
    assert submitted_turn is False
    assert reasoning_effort_for_turn(submitted_turn) == "medium"
    assert state[THINKING_MODE_KEY] is False


def test_reset_discards_pending_thinking_turn():
    state = {
        THINKING_MODE_KEY: True,
        SUBMITTED_THINKING_MODE_KEY: True,
    }

    reset_thinking_mode(state)

    assert state == {THINKING_MODE_KEY: False}
