from __future__ import annotations

from limits import parse

from aerisun.core.db import get_session_factory
from aerisun.core.rate_limit import (
    RATE_COMMENT_IMAGE_UPLOAD,
    RATE_WRITE_ENGAGEMENT,
    RATE_WRITE_REACTION,
    comment_image_upload_rate_limit,
    limiter,
)
from aerisun.domain.site_config.models import CommunityConfig


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


def test_comment_image_upload_rate_limit_uses_community_config(client) -> None:
    assert parse(RATE_COMMENT_IMAGE_UPLOAD).amount == 18
    assert comment_image_upload_rate_limit() == "18/30 minute"

    with get_session_factory()() as session:
        config = session.query(CommunityConfig).one()
        config.comment_image_rate_limit_count = 4
        config.comment_image_rate_limit_window_minutes = 9
        session.commit()

    assert comment_image_upload_rate_limit() == "4/9 minute"
    assert str(parse(comment_image_upload_rate_limit())) == "4 per 9 minute"
