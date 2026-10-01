from unittest import mock
import pytest
from app.ml.request_budget import request_budget, remaining_timeout, retry_wait


def test_budget_shrinks_across_calls_and_resets_after_exit():
    with mock.patch("app.ml.request_budget.time.monotonic", side_effect=[100, 110, 144, 146]):
        with request_budget(45):
            assert remaining_timeout(90) == 35
            assert remaining_timeout(30) == 1
            with pytest.raises(TimeoutError):
                remaining_timeout(90)
    assert remaining_timeout(90) == 90


def test_retry_never_sleeps_past_remaining_budget():
    with mock.patch("app.ml.request_budget.time.monotonic", side_effect=[100, 140]), \
         mock.patch("app.ml.request_budget.time.sleep") as sleep:
        with request_budget(45), pytest.raises(TimeoutError):
            retry_wait(15)
    sleep.assert_not_called()
