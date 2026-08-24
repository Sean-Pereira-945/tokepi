"""Tests for the sliding-window rate limiter middleware."""
import time

from driftguard.middleware import _SlidingWindowCounter


def test_allows_requests_within_limit():
    limiter = _SlidingWindowCounter(limit=5, window_seconds=60)
    for _ in range(5):
        assert limiter.is_allowed("127.0.0.1") is True


def test_blocks_when_limit_exceeded():
    limiter = _SlidingWindowCounter(limit=3, window_seconds=60)
    for _ in range(3):
        limiter.is_allowed("10.0.0.1")
    assert limiter.is_allowed("10.0.0.1") is False


def test_isolates_different_clients():
    limiter = _SlidingWindowCounter(limit=2, window_seconds=60)
    limiter.is_allowed("client-a")
    limiter.is_allowed("client-a")
    # client-a is now at limit, client-b should still pass
    assert limiter.is_allowed("client-a") is False
    assert limiter.is_allowed("client-b") is True


def test_remaining_decrements_correctly():
    limiter = _SlidingWindowCounter(limit=10, window_seconds=60)
    assert limiter.remaining("192.168.1.1") == 10
    limiter.is_allowed("192.168.1.1")
    limiter.is_allowed("192.168.1.1")
    assert limiter.remaining("192.168.1.1") == 8


def test_window_expiry_allows_new_requests():
    """Using a very short window to verify hits expire."""
    limiter = _SlidingWindowCounter(limit=2, window_seconds=1)
    limiter.is_allowed("expire-test")
    limiter.is_allowed("expire-test")
    assert limiter.is_allowed("expire-test") is False

    # Wait for the window to expire
    time.sleep(1.05)
    assert limiter.is_allowed("expire-test") is True
