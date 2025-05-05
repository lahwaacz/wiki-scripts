import ssl
from typing import Any

import httpx
import truststore

from ws import __url__, __version__

__all__ = ["DEFAULT_USER_AGENT", "HTTPXClient", "HTTPXAsyncClient"]

DEFAULT_USER_AGENT = f"wiki-scripts/{__version__} ({__url__})"


def _get_limits(
    *,
    max_connections: int,
    keepalive_expiry: int,
) -> httpx.Limits:
    return httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=None,  # always allow keep-alive
        keepalive_expiry=keepalive_expiry,
    )


def _get_headers(
    headers: dict[str, str] | None = None,
) -> dict[str, str]:
    if headers is None:
        headers = {}

    # set default user agent for wiki-scripts
    headers.setdefault("User-Agent", DEFAULT_USER_AGENT)

    return headers


def _get_ssl_context() -> ssl.SSLContext:
    # create an SSL context to disallow TLS1.0 and TLS1.1, allow only TLS1.2
    # (and newer if supported by the used openssl version)
    if truststore is not None:
        # use the system certificate store if available via truststore
        ssl_context: ssl.SSLContext = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    else:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    return ssl_context


def HTTPXClient(
    *,
    headers: dict[str, str] | None = None,
    timeout: int | httpx.Timeout = 60,
    retries: int = 3,
    max_connections: int = 100,
    keepalive_expiry: int = 60,
    transport: httpx.BaseTransport | None = None,
    **kwargs: Any,
) -> httpx.Client:
    """Creates an :py:class:`httpx.Client` instance with some wiki-scripts default parameters."""

    if isinstance(timeout, int):
        # disable timeout for waiting for a connection from the pool
        timeout = httpx.Timeout(timeout, pool=None)

    if transport is None:
        transport = httpx.HTTPTransport(retries=retries)

    return httpx.Client(
        transport=transport,
        verify=_get_ssl_context(),
        headers=_get_headers(headers),
        timeout=timeout,
        limits=_get_limits(
            max_connections=max_connections,
            keepalive_expiry=keepalive_expiry,
        ),
        **kwargs,
    )


def HTTPXAsyncClient(
    *,
    headers: dict[str, str] | None = None,
    timeout: int | httpx.Timeout = 60,
    retries: int = 3,
    max_connections: int = 100,
    keepalive_expiry: int = 60,
    transport: httpx.AsyncBaseTransport | None = None,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Creates an :py:class:`httpx.AsyncClient` instance with some wiki-scripts default parameters."""

    if isinstance(timeout, int):
        # disable timeout for waiting for a connection from the pool
        timeout = httpx.Timeout(timeout, pool=None)

    if transport is None:
        transport = httpx.AsyncHTTPTransport(retries=retries)

    return httpx.AsyncClient(
        transport=transport,
        verify=_get_ssl_context(),
        headers=_get_headers(headers),
        timeout=timeout,
        limits=_get_limits(
            max_connections=max_connections,
            keepalive_expiry=keepalive_expiry,
        ),
        **kwargs,
    )
