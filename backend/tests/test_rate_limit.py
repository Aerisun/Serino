from __future__ import annotations

from limits import parse

from aerisun.core.rate_limit import RATE_WRITE_ENGAGEMENT, RATE_WRITE_REACTION, limiter


def test_guestbook_rate_limited() -> None:
    limiter.enabled = True
    limiter.reset()
    item = parse(RATE_WRITE_ENGAGEMENT)
    bucket = "test:guestbook:127.0.0.1"

    try:
        for index in range(5):
            assert limiter._limiter.hit(item, bucket), f"Request {index + 1} should not be rate limited"
        assert limiter._limiter.test(item, bucket) is False
    finally:
        limiter.reset()
        limiter.enabled = False


def test_reactions_rate_limited() -> None:
    limiter.enabled = True
    limiter.reset()
    item = parse(RATE_WRITE_REACTION)
    bucket = "test:reactions:127.0.0.1"

    try:
        for index in range(10):
            assert limiter._limiter.hit(item, bucket), f"Request {index + 1} should not be rate limited"
        assert limiter._limiter.test(item, bucket) is False
    finally:
        limiter.reset()
        limiter.enabled = False
