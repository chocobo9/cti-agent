"""Per-source rate limiting for enrichment API calls.

Prevents 429 errors during bulk enrichment by throttling requests to each
external source independently. Rate limits are configurable via environment
variables (see enrichment/config.py):

    CRTSH_RATE_LIMIT=5.0       # crt.sh: max requests/second
    OTX_RATE_LIMIT=10.0        # OTX pDNS: max requests/second
    RDAP_RATE_LIMIT=5.0        # RDAP: max requests/second
    JARM_CONCURRENCY_LIMIT=5   # JARM: max concurrent active scans
    FAVICON_CONCURRENCY_LIMIT=10  # Favicon: max concurrent HTTP fetches
"""

from __future__ import annotations

import asyncio
import logging
import random

from aiolimiter import AsyncLimiter

logger = logging.getLogger(__name__)


class RateLimitedSession:
    """Per-source rate limiters shared across all concurrent domain enrichments.

    AsyncLimiter (crt.sh, OTX, RDAP) enforces requests-per-second.
    Semaphore (JARM, favicon) limits concurrent active connections.
    """

    def __init__(
        self,
        *,
        crtsh_rate: float = 5.0,
        otx_rate: float = 10.0,
        rdap_rate: float = 5.0,
        jarm_concurrency: int = 5,
        favicon_concurrency: int = 10,
    ) -> None:
        self.crtsh = AsyncLimiter(crtsh_rate, 1.0)
        self.otx = AsyncLimiter(otx_rate, 1.0)
        self.rdap = AsyncLimiter(rdap_rate, 1.0)
        self.jarm = asyncio.Semaphore(jarm_concurrency)
        self.favicon = asyncio.Semaphore(favicon_concurrency)


async def retry_with_backoff_429(
    response_status: int,
    retry_after: str | None,
    attempt: int,
    source_name: str,
) -> None:
    """Sleep with exponential backoff + jitter when a 429 is received."""
    if retry_after and retry_after.isdigit():
        delay = int(retry_after)
    else:
        delay = min(2 ** (attempt + 1), 60)
    jitter = random.uniform(0, delay * 0.25)
    total = delay + jitter
    logger.warning(
        "%s: 429 rate limited, backing off %.1fs (attempt %d)",
        source_name,
        total,
        attempt + 1,
    )
    await asyncio.sleep(total)
