import pytest

from app.bot.middleware.rate_limit import TokenBucketRateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_token_bucket_allows_configured_burst_then_blocks():
    clock = Clock()
    limiter = TokenBucketRateLimiter(max_requests_per_minute=3, clock=clock)

    assert limiter.allow(123) is True
    assert limiter.allow(123) is True
    assert limiter.allow(123) is True
    assert limiter.allow(123) is False


def test_token_bucket_refills_over_time_per_user():
    clock = Clock()
    limiter = TokenBucketRateLimiter(max_requests_per_minute=2, clock=clock)

    assert limiter.allow(123) is True
    assert limiter.allow(123) is True
    assert limiter.allow(123) is False
    assert limiter.allow(456) is True

    clock.advance(30)

    assert limiter.allow(123) is True
    assert limiter.allow(123) is False


def test_token_bucket_rejects_invalid_limit():
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(max_requests_per_minute=0)
