from __future__ import annotations

import base64

import httpx
import mmh3

from cti_agent.enrichment.utils import create_http_client, retry_async


@retry_async(retryable_exceptions=(httpx.TimeoutException, httpx.ConnectError))
async def _fetch_favicon(url: str) -> bytes | None:
    async with create_http_client() as client:
        resp = await client.get(url)
        if resp.status_code != 200 or not resp.content:
            return None
        return resp.content


def _compute_favicon_hash(body: bytes) -> int:
    encoded = base64.encodebytes(body)
    return mmh3.hash(encoded)


async def get_favicon_hash(domain: str) -> int | None:
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/favicon.ico"
        try:
            body = await _fetch_favicon(url)
            if body:
                return _compute_favicon_hash(body)
        except (httpx.TimeoutException, httpx.ConnectError, Exception):
            continue
    return None
