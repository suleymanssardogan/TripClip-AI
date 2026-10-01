"""A shared deadline for all provider calls and retries in one conversation."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_deadline = ContextVar("ai_request_deadline", default=None)


@contextmanager
def request_budget(seconds):
    token = _deadline.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def remaining_timeout(default):
    deadline = _deadline.get()
    if deadline is None:
        return default
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("AI request budget exhausted")
    return min(default, remaining)


def retry_wait(seconds):
    if remaining_timeout(seconds + 0.1) <= seconds:
        raise TimeoutError("Insufficient AI budget for another retry")
    time.sleep(seconds)
