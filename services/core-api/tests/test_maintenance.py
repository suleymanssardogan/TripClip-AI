from unittest import mock
import threading
import pytest
from app.tasks.maintenance import healthy, run_periodic, settings


def test_transient_failure_retries_and_writes_heartbeat(tmp_path):
    stop = mock.Mock()
    stop.is_set.return_value = False
    stop.wait.side_effect = [False, True]
    callback = mock.Mock(side_effect=[RuntimeError("offline"), None])
    run_periodic("dispatch", callback, 5, stop, tmp_path)
    assert callback.call_count == 2
    assert float((tmp_path / "dispatch").read_text()) > 0
    assert stop.wait.call_args_list == [mock.call(5), mock.call(5)]


def test_health_requires_each_loop_to_be_recent(tmp_path):
    intervals = {"dispatch": 5, "retention": 900}
    assert not healthy(intervals, tmp_path, now=1000)
    (tmp_path / "dispatch").write_text("999")
    (tmp_path / "retention").write_text("100")
    assert healthy(intervals, tmp_path, now=1000)
    (tmp_path / "dispatch").write_text("900")
    assert not healthy(intervals, tmp_path, now=1000)
    (tmp_path / "dispatch").write_text("not-a-timestamp")
    assert not healthy(intervals, tmp_path, now=1000)


def test_slow_retention_does_not_block_dispatch(tmp_path):
    stop = threading.Event(); release = threading.Event(); dispatched = threading.Event()
    retention_started = threading.Event()
    def retention():
        retention_started.set(); release.wait(2)
    retention_thread = threading.Thread(target=run_periodic, args=("retention", retention, 900, stop, tmp_path))
    dispatch_thread = threading.Thread(target=run_periodic, args=("dispatch", dispatched.set, 5, stop, tmp_path))
    try:
        retention_thread.start(); assert retention_started.wait(1)
        dispatch_thread.start(); assert dispatched.wait(1)
    finally:
        stop.set(); release.set()
        retention_thread.join(2); dispatch_thread.join(2)
    assert not retention_thread.is_alive() and not dispatch_thread.is_alive()


def test_stopped_scheduler_does_not_run_callback(tmp_path):
    stop = threading.Event(); stop.set()
    callback = mock.Mock()
    run_periodic("dispatch", callback, 5, stop, tmp_path)
    callback.assert_not_called()


@pytest.mark.parametrize("name,value", [("MAINTENANCE_DISPATCH_INTERVAL", "0"),
                                        ("MAINTENANCE_DISPATCH_INTERVAL", "nan"),
                                        ("MAINTENANCE_RETENTION_INTERVAL", "29")])
def test_invalid_intervals_are_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        settings()
