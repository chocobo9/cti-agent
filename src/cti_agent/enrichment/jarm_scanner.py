from __future__ import annotations

import asyncio
import logging
import socket

logger = logging.getLogger(__name__)
JARM_TIMEOUT = 10.0


async def scan_jarm(domain: str, port: int = 443) -> str | None:
    try:
        from jarm.scanner.scanner import Scanner

        def _scan() -> str | None:
            try:
                result = Scanner.scan(domain, port)
                raw = result[0] if isinstance(result, (list, tuple)) else result
                hash_val = str(raw).strip()
                if not hash_val or hash_val == ("0" * 62):
                    return None
                return hash_val
            except (socket.timeout, socket.error, OSError):
                return None

        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _scan),
            timeout=JARM_TIMEOUT,
        )
    except (asyncio.TimeoutError, ImportError, Exception):
        return None
