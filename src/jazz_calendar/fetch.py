"""HTTP fetch for upstream ICS feeds.

Stdlib-only. Wraps :mod:`urllib.request` with a project User-Agent and
normalizes transport errors into a single :class:`FetchError`.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

USER_AGENT = (
    "jazz-calendar-helsinki-unified/1.0 "
    "(+https://github.com/akaihola/jazz-calendar-helsinki-unified)"
)


class FetchError(Exception):
    """Raised when an upstream feed cannot be retrieved."""


def fetch_feed(url: str, *, timeout: float = 30.0) -> bytes:
    """Fetch ``url`` and return the response body as bytes.

    Raises :class:`FetchError` on HTTP errors, network errors, or timeout.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"URL error fetching {url}: {exc.reason}") from exc
    except (socket.timeout, TimeoutError) as exc:
        raise FetchError(f"Timeout fetching {url}: {exc}") from exc
