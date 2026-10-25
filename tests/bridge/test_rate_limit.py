from factory_bridge.rate_limit import LIMIT, WINDOW_S, allowed, record, retry_at

NOW = 1_800_000_000.0


def _history(count: int, start: float = NOW - 600) -> tuple[float, ...]:
    return tuple(start + minute * 60 for minute in range(count))


def test_first_five_ideas_are_allowed():
    assert allowed((), NOW)
    assert allowed(_history(LIMIT - 1), NOW)


def test_sixth_idea_in_an_hour_is_refused():
    assert not allowed(_history(LIMIT), NOW)


def test_old_entries_fall_out_of_the_window():
    stale = (NOW - WINDOW_S - 1, NOW - WINDOW_S)
    assert record((*stale, NOW - 10), NOW) == (NOW - 10, NOW)
    assert allowed((*stale, *_history(LIMIT - 1)), NOW)


def test_record_leaves_the_history_it_was_given():
    history = (NOW - 10,)
    record(history, NOW)
    assert history == (NOW - 10,)


def test_retry_at_is_when_the_oldest_recent_entry_leaves():
    history = _history(LIMIT)
    assert retry_at(history, NOW) == history[0] + WINDOW_S
    assert allowed(history, retry_at(history, NOW))


def test_retry_at_is_now_while_allowed():
    assert retry_at(_history(2), NOW) == NOW
