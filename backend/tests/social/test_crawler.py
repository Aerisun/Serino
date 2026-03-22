"""Tests for the RSS feed crawler module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import respx

from aerisun.domain.social.crawler import (
    _check_feed,
    _parse_published_time,
    _replace_non_domain,
    crawl_all_feeds,
    crawl_single_source,
)

# ---------------------------------------------------------------------------
# _parse_published_time — pure function tests
# ---------------------------------------------------------------------------


def test_parse_published_time_rfc2822():
    result = _parse_published_time("Mon, 01 Jan 2024 12:00:00 +0000")
    assert result is not None
    assert result.year == 2024 and result.month == 1 and result.day == 1


def test_parse_published_time_iso8601():
    result = _parse_published_time("2024-06-15T08:30:00Z")
    assert result is not None
    assert result.year == 2024 and result.month == 6


def test_parse_published_time_date_only():
    result = _parse_published_time("2024-03-20")
    assert result is not None
    assert result.year == 2024


def test_parse_published_time_with_timezone():
    result = _parse_published_time("2024-01-01T20:00:00+08:00")
    assert result is not None
    # Should be converted to UTC: 12:00
    assert result.hour == 12


def test_parse_published_time_empty():
    assert _parse_published_time("") is None


def test_parse_published_time_unparseable():
    assert _parse_published_time("not a date at all xyz") is None


# ---------------------------------------------------------------------------
# _replace_non_domain — pure function tests
# ---------------------------------------------------------------------------


def test_replace_non_domain_localhost():
    result = _replace_non_domain("http://localhost:4000/posts/hello", "https://blog.example.com")
    assert result == "https://blog.example.com/posts/hello"


def test_replace_non_domain_ip():
    result = _replace_non_domain("http://192.168.1.1/article/1", "https://blog.example.com")
    assert result == "https://blog.example.com/article/1"


def test_replace_non_domain_normal():
    result = _replace_non_domain("https://other.com/post/1", "https://blog.example.com")
    assert result == "https://other.com/post/1"


# ---------------------------------------------------------------------------
# _check_feed — requires httpx mock
# ---------------------------------------------------------------------------


@respx.mock
def test_check_feed_found_atom():
    base = "https://blog.example.com"
    respx.get(f"{base}/atom.xml").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/atom+xml"},
            text="<feed></feed>",
        )
    )
    with httpx.Client() as client:
        feed_type, feed_url = _check_feed(base, client)
    assert feed_type == "atom"
    assert feed_url == f"{base}/atom.xml"


@respx.mock
def test_check_feed_found_by_content():
    base = "https://blog.example.com"
    # First path returns 404
    respx.get(f"{base}/atom.xml").mock(return_value=httpx.Response(404))
    # Second path returns 200 with text/html content-type but body contains <rss
    respx.get(f"{base}/rss.xml").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<?xml version='1.0'?><rss version='2.0'><channel></channel></rss>",
        )
    )
    with httpx.Client() as client:
        feed_type, _feed_url = _check_feed(base, client)
    assert feed_type == "rss"


@respx.mock
def test_check_feed_not_found():
    base = "https://blog.example.com"
    # All paths return 404
    respx.route().mock(return_value=httpx.Response(404))
    with httpx.Client() as client:
        feed_type, feed_url = _check_feed(base, client)
    assert feed_type == "none"
    assert feed_url == base


# ---------------------------------------------------------------------------
# Sample RSS feed used by integration tests
# ---------------------------------------------------------------------------

SAMPLE_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <item>
      <title>Hello World</title>
      <link>https://blog.example.com/hello</link>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <description>A test post</description>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://blog.example.com/second</link>
      <pubDate>Tue, 02 Jan 2024 12:00:00 +0000</pubDate>
      <description>Another post</description>
    </item>
  </channel>
</rss>"""


def _setup_friend_and_source(session):
    """Helper to create a Friend and FriendFeedSource in the database."""
    from aerisun.domain.social.models import Friend, FriendFeedSource

    friend = Friend(
        name="Test Blog",
        url="https://blog.example.com",
        avatar_url="",
        status="active",
    )
    session.add(friend)
    session.flush()
    source = FriendFeedSource(
        friend_id=friend.id,
        feed_url="https://blog.example.com/rss.xml",
        is_enabled=True,
    )
    session.add(source)
    session.flush()
    return friend, source


# ---------------------------------------------------------------------------
# crawl_single_source — DB + httpx mock integration tests
# ---------------------------------------------------------------------------


@respx.mock
def test_crawl_single_source_success(client):
    from aerisun.core.db import get_session_factory
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.models import FriendFeedItem

    factory = get_session_factory()
    settings = get_settings()
    with factory() as session:
        friend, source = _setup_friend_and_source(session)

        respx.get("https://blog.example.com/rss.xml").mock(return_value=httpx.Response(200, text=SAMPLE_RSS))

        result = crawl_single_source(session, source, friend, settings)
        session.commit()

        assert result["status"] == "ok"
        assert result["inserted"] == 2

        items = session.query(FriendFeedItem).filter(FriendFeedItem.source_id == source.id).all()
        assert len(items) == 2


@respx.mock
def test_crawl_single_source_304(client):
    from aerisun.core.db import get_session_factory
    from aerisun.core.settings import get_settings

    factory = get_session_factory()
    settings = get_settings()
    with factory() as session:
        friend, source = _setup_friend_and_source(session)
        source.etag = '"abc123"'
        session.flush()

        respx.get("https://blog.example.com/rss.xml").mock(return_value=httpx.Response(304))

        result = crawl_single_source(session, source, friend, settings)
        assert result["status"] == "not_modified"


@respx.mock
def test_crawl_single_source_auto_discovery(client):
    from aerisun.core.db import get_session_factory
    from aerisun.core.settings import get_settings

    factory = get_session_factory()
    settings = get_settings()
    with factory() as session:
        friend, source = _setup_friend_and_source(session)

        # Original feed URL fails
        respx.get("https://blog.example.com/rss.xml").mock(return_value=httpx.Response(500))
        # Auto-discovery succeeds on atom.xml
        respx.get("https://blog.example.com/atom.xml").mock(
            return_value=httpx.Response(
                200,
                headers={"content-type": "application/atom+xml"},
                text=SAMPLE_RSS,
            )
        )
        # Other discovery paths return 404
        respx.route().mock(return_value=httpx.Response(404))

        result = crawl_single_source(session, source, friend, settings)
        session.commit()

        assert result["feed_url_updated"] is True
        assert result["inserted"] >= 1


@respx.mock
def test_crawl_single_source_filters_future_articles(client):
    """Articles with dates far in the future (>2 days) should be filtered out."""
    from aerisun.core.db import get_session_factory
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.models import FriendFeedItem

    future_date = datetime.now(UTC) + timedelta(days=10)
    future_str = future_date.strftime("%a, %d %b %Y %H:%M:%S +0000")

    rss_with_future = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <item>
      <title>Future Post</title>
      <link>https://blog.example.com/future</link>
      <pubDate>{future_str}</pubDate>
      <description>A post from the future</description>
    </item>
    <item>
      <title>Past Post</title>
      <link>https://blog.example.com/past</link>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <description>A post from the past</description>
    </item>
  </channel>
</rss>"""

    factory = get_session_factory()
    settings = get_settings()
    with factory() as session:
        friend, source = _setup_friend_and_source(session)

        respx.get("https://blog.example.com/rss.xml").mock(return_value=httpx.Response(200, text=rss_with_future))

        result = crawl_single_source(session, source, friend, settings)
        session.commit()

        # Only the past post should be inserted; future post filtered
        assert result["inserted"] == 1

        items = session.query(FriendFeedItem).filter(FriendFeedItem.source_id == source.id).all()
        assert len(items) == 1
        assert items[0].title == "Past Post"


@respx.mock
def test_crawl_single_source_deduplication(client):
    """Running crawl twice on the same feed should not duplicate items."""
    from aerisun.core.db import get_session_factory
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.models import FriendFeedItem

    factory = get_session_factory()
    settings = get_settings()
    with factory() as session:
        friend, source = _setup_friend_and_source(session)

        respx.get("https://blog.example.com/rss.xml").mock(return_value=httpx.Response(200, text=SAMPLE_RSS))

        # First crawl
        result1 = crawl_single_source(session, source, friend, settings)
        session.commit()
        assert result1["inserted"] == 2

        # Second crawl of the same feed
        result2 = crawl_single_source(session, source, friend, settings)
        session.commit()
        assert result2["inserted"] == 0

        items = session.query(FriendFeedItem).filter(FriendFeedItem.source_id == source.id).all()
        assert len(items) == 2


# ---------------------------------------------------------------------------
# crawl_all_feeds — full integration test
# ---------------------------------------------------------------------------


@respx.mock
def test_crawl_all_feeds(client):
    """End-to-end test: set up DB data, mock HTTP, call crawl_all_feeds."""
    from aerisun.core.db import get_session_factory
    from aerisun.core.settings import get_settings
    from aerisun.domain.social.models import Friend, FriendFeedSource

    factory = get_session_factory()
    settings = get_settings()

    with factory() as session:
        friend = Friend(
            name="All-Feeds Blog",
            url="https://all.example.com",
            avatar_url="",
            status="active",
        )
        session.add(friend)
        session.flush()
        source = FriendFeedSource(
            friend_id=friend.id,
            feed_url="https://all.example.com/rss.xml",
            is_enabled=True,
        )
        session.add(source)
        session.commit()

    # Our specific feed returns valid RSS (register BEFORE the catch-all)
    respx.get("https://all.example.com/rss.xml").mock(return_value=httpx.Response(200, text=SAMPLE_RSS))
    # Catch-all: return 404 for any seeded feeds we don't care about
    respx.route().mock(return_value=httpx.Response(404))

    summary = crawl_all_feeds(settings)

    assert summary["status"] == "completed"
    assert summary["sources_crawled"] >= 1
    assert summary["items_inserted"] >= 2
    # Find our specific source in the details
    our_detail = [d for d in summary["details"] if d["friend_name"] == "All-Feeds Blog"]
    assert len(our_detail) == 1
    assert our_detail[0]["status"] == "ok"
    assert our_detail[0]["inserted"] == 2
