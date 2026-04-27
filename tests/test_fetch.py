"""Tests for jazz_calendar.fetch — HTTP fetch contract."""

from __future__ import annotations

import socket
import urllib.error
from email.message import Message
from unittest.mock import MagicMock, patch

import pytest

from jazz_calendar.fetch import FetchError, fetch_feed

EXPECTED_USER_AGENT = (
    "jazz-calendar-finland/1.0 "
    "(+https://github.com/akaihola/jazz-calendar-finland)"
)


def test_fetch_feed_returns_bytes_on_2xx() -> None:
    """A 2xx response yields the response body bytes."""
    mock_response = MagicMock()
    mock_response.read.return_value = b"BEGIN:VCALENDAR..."
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = fetch_feed("https://example/")

    assert result == b"BEGIN:VCALENDAR..."


def test_fetch_feed_raises_on_non_2xx() -> None:
    """Non-2xx HTTP responses raise FetchError mentioning URL and status."""
    url = "https://example/"
    err = urllib.error.HTTPError(url, 500, "Server Error", Message(), None)

    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(FetchError) as exc_info:
            fetch_feed(url)

    msg = str(exc_info.value)
    assert url in msg
    assert "500" in msg


def test_fetch_feed_raises_on_timeout() -> None:
    """A socket timeout from urlopen surfaces as FetchError."""
    with patch("urllib.request.urlopen", side_effect=socket.timeout()):
        with pytest.raises(FetchError):
            fetch_feed("https://example/")


def test_fetch_feed_sends_user_agent() -> None:
    """The Request passed to urlopen carries the project User-Agent header."""
    mock_response = MagicMock()
    mock_response.read.return_value = b""
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        fetch_feed("https://example/")

    assert mock_urlopen.call_args is not None
    req = mock_urlopen.call_args.args[0]
    # urllib lowercases header keys via get_header / header_items
    assert req.get_header("User-agent") == EXPECTED_USER_AGENT
