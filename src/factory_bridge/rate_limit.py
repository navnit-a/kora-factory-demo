WINDOW_S = 3600
LIMIT = 5


def allowed(history: tuple[float, ...], now: float) -> bool:
    return len(_recent(history, now)) < LIMIT


def record(history: tuple[float, ...], now: float) -> tuple[float, ...]:
    return (*_recent(history, now), now)


def retry_at(history: tuple[float, ...], now: float) -> float:
    recent = sorted(_recent(history, now))
    if len(recent) < LIMIT:
        return now
    return recent[-LIMIT] + WINDOW_S


def _recent(history: tuple[float, ...], now: float) -> tuple[float, ...]:
    return tuple(stamp for stamp in history if now - stamp < WINDOW_S)
