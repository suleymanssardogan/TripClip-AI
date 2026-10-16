"""Process-local HTTP pool with isolated per-call cookies/headers and no hidden retries."""
import atexit
import os
import threading
import requests

exceptions = requests.exceptions
_adapter = None
_pid = None
_lock = threading.Lock()


def close_pool():
    global _adapter, _pid
    if _adapter is not None:
        _adapter.close()
    _adapter = None
    _pid = None


def _after_fork():
    global _lock
    close_pool()
    _lock = threading.Lock()


atexit.register(close_pool)
if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork)


class _BorrowedAdapter(requests.adapters.BaseAdapter):
    def __init__(self, adapter):
        self.adapter = adapter

    def send(self, request, **kwargs):
        return self.adapter.send(request, **kwargs)

    def close(self):
        pass


def request(method, url, **kwargs):
    global _adapter, _pid
    if kwargs.get("stream"):
        raise ValueError("Pooled provider requests must consume their response")
    if kwargs.get("timeout") is None:
        raise ValueError("Provider requests require an explicit timeout")
    with _lock:
        if _adapter is None or _pid != os.getpid():
            close_pool()
            _adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
            _pid = os.getpid()
        adapter = _adapter
    with requests.Session() as session:
        session.mount("https://", _BorrowedAdapter(adapter))
        session.mount("http://", _BorrowedAdapter(adapter))
        return session.request(method, url, **kwargs)


def get(url, **kwargs):
    return request("GET", url, **kwargs)


def post(url, **kwargs):
    return request("POST", url, **kwargs)
