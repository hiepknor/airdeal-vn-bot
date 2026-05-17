from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    def __init__(
        self,
        max_requests_per_minute: int,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_requests_per_minute <= 0:
            raise ValueError("max_requests_per_minute must be positive")
        self.capacity = float(max_requests_per_minute)
        self.refill_per_second = self.capacity / 60.0
        self.clock = clock
        self._buckets: dict[int, _Bucket] = {}

    def allow(self, telegram_id: int) -> bool:
        now = self.clock()
        bucket = self._buckets.get(telegram_id)
        if bucket is None:
            self._buckets[telegram_id] = _Bucket(tokens=self.capacity - 1.0, updated_at=now)
            return True

        elapsed = max(0.0, now - bucket.updated_at)
        bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_per_second)
        bucket.updated_at = now
        if bucket.tokens < 1.0:
            return False
        bucket.tokens -= 1.0
        return True
