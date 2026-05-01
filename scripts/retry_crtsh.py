"""Retry crt.sh queries for domains that failed during the batch pipeline.

Reads enrichment JSONs from data/enrichment/, finds domains with ct_logs
errors, and retries them sequentially with a configurable delay to avoid
rate limiting.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source /mnt/d/proj/agent/agent-venv/bin/activate
    python -m scripts.retry_crtsh
    python -m scripts.retry_crtsh --delay 5 --max-retries 2

Inputs:
    data/enrichment/*.json    Per-domain enrichment JSONs from run_batch

Outputs:
    Updates enrichment JSONs in place (adds certificates, removes ct_logs error)
    Log file: data/logs/retry_crtsh_YYYYMMDD_HHMMSS.log
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from cti_agent.enrichment.ct_logs import CRT_SH_URL, _dedup_key, _entry_to_cert

ENRICHMENT_DIR = Path("data/enrichment")
LOG_DIR = Path("data/logs")


def _setup_logging() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"retry_crtsh_{timestamp}.log"

    fmt = "%(asctime)s %(levelname)-7s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(console)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(file_handler)

    return log_file


def find_domains_needing_crtsh(enrichment_dir: Path) -> list[Path]:
    """Find enrichment JSONs that need crt.sh data: either has a ct_logs error or has no certificates at all."""
    need_query: list[Path] = []
    for json_path in sorted(enrichment_dir.glob("*.json")):
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        if "ct_logs" in data.get("errors", {}):
            need_query.append(json_path)
        elif not data.get("certificates"):
            need_query.append(json_path)
    return need_query


async def query_crtsh_single(domain: str, timeout: float = 30.0) -> list[dict]:
    """Query crt.sh for a single domain, return raw certificate list."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": "CTI-Agent-Enrichment/0.1"},
        follow_redirects=True,
    ) as client:
        resp = await client.get(CRT_SH_URL, params={"q": domain, "output": "json"})
        resp.raise_for_status()
        return resp.json()


async def retry_domain(
    json_path: Path,
    delay: float,
    max_retries: int,
) -> bool:
    """Retry crt.sh for one domain. Returns True on success."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    domain = data["domain"]

    for attempt in range(max_retries):
        try:
            raw_certs = await query_crtsh_single(domain)
            certs = []
            seen_keys: set[str] = set()
            for entry in raw_certs:
                cert = _entry_to_cert(entry)
                key = _dedup_key(cert)
                if key not in seen_keys:
                    seen_keys.add(key)
                    certs.append(cert.model_dump(mode="json"))

            data["certificates"] = certs
            data["errors"].pop("ct_logs", None)

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            return True

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                data["certificates"] = []
                data["errors"].pop("ct_logs", None)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str)
                logging.info("  %s: 404 — no certificates in CT logs (expected)", domain)
                return True
            if exc.response.status_code == 429:
                backoff = delay * (2 ** attempt)
                logging.warning(
                    "  %s: 429 rate limited, waiting %.0fs (attempt %d/%d)",
                    domain, backoff, attempt + 1, max_retries,
                )
                await asyncio.sleep(backoff)
            else:
                logging.warning("  %s: HTTP %d (attempt %d/%d)", domain, exc.response.status_code, attempt + 1, max_retries)
                await asyncio.sleep(delay)

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logging.warning("  %s: %s (attempt %d/%d)", domain, type(exc).__name__, attempt + 1, max_retries)
            await asyncio.sleep(delay)

    return False


async def run_retry(delay: float = 3.0, max_retries: int = 5) -> None:
    log_file = _setup_logging()
    logging.info("Log file: %s", log_file)
    logging.info("Settings: delay=%.1fs, max_retries=%d", delay, max_retries)

    failed_paths = find_domains_needing_crtsh(ENRICHMENT_DIR)
    logging.info("Found %d domains needing crt.sh query", len(failed_paths))

    if not failed_paths:
        logging.info("Nothing to retry.")
        return

    succeeded = 0
    still_failed = 0
    start = time.monotonic()

    for i, json_path in enumerate(failed_paths, 1):
        domain = json_path.stem
        logging.info("[%d/%d] Retrying %s...", i, len(failed_paths), domain)

        ok = await retry_domain(json_path, delay, max_retries)
        if ok:
            succeeded += 1
            logging.info("  %s: OK", domain)
        else:
            still_failed += 1
            logging.warning("  %s: FAILED after %d attempts", domain, max_retries)

        if i < len(failed_paths):
            await asyncio.sleep(delay)

    duration = time.monotonic() - start
    logging.info("")
    logging.info("=" * 50)
    logging.info("RETRY SUMMARY")
    logging.info("=" * 50)
    logging.info("Total retried:   %d", len(failed_paths))
    logging.info("Succeeded:       %d", succeeded)
    logging.info("Still failed:    %d", still_failed)
    logging.info("Duration:        %.1fs", duration)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retry failed crt.sh queries sequentially")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between requests (default: 3.0)")
    parser.add_argument("--max-retries", type=int, default=5, help="Max retry attempts per domain (default: 5)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run_retry(delay=args.delay, max_retries=args.max_retries))
