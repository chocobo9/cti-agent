"""Backfill RDAP data using Whoxy WHOIS History API.

For domains in v2 dataset that lack RDAP data (creation_date/registrar),
queries Whoxy history API and picks the WHOIS record closest to the
domain's first_seen date. Writes results into existing enrichment JSONs.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    export WHOXY_API_KEY=your_key_here
    python -m scripts.whoxy_rdap_backfill
    python -m scripts.whoxy_rdap_backfill --dry-run --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

import httpx

logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

WHOXY_API_URL = "https://api.whoxy.com/"
ENRICHMENT_DIR = Path("data/enrichment")
DATASET_PATH = Path("data/dataset/attribution_dataset_v2.jsonl")


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def _find_closest_record(records: list[dict], target_date: date | None) -> dict | None:
    if not records:
        return None
    if target_date is None:
        return records[-1]

    best = None
    best_diff = float("inf")
    for rec in records:
        rec_date = _parse_date(rec.get("create_date") or rec.get("update_date"))
        if rec_date is None:
            continue
        diff = abs((rec_date - target_date).days)
        if diff < best_diff:
            best_diff = diff
            best = rec
    return best or records[-1]


async def query_whoxy_history(
    domain: str,
    api_key: str,
    timeout: float = 15.0,
) -> dict:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        resp = await client.get(WHOXY_API_URL, params={"key": api_key, "history": domain})
        resp.raise_for_status()
        data = resp.json()
    if data.get("status") != 1:
        raise ValueError(f"Whoxy error: {data.get('status_reason', 'unknown')}")
    return data


def extract_rdap_fields(record: dict) -> dict:
    registrar_info = record.get("domain_registrar", {})
    registrant = record.get("registrant_contact", {})

    registrar_name = registrar_info.get("registrar_name")
    iana_id = registrar_info.get("iana_id")
    if registrar_name and iana_id:
        registrar = f"{registrar_name} (IANA #{iana_id})"
    else:
        registrar = registrar_name

    return {
        "creation_date": record.get("create_date"),
        "expiration_date": record.get("expiry_date"),
        "registrar": registrar,
        "registrant_org": registrant.get("company_name"),
    }


def find_domains_needing_rdap(dataset_path: Path, enrichment_dir: Path) -> list[tuple[str, str | None]]:
    need: list[tuple[str, str | None]] = []
    for line in dataset_path.read_text(encoding="utf-8").strip().split("\n"):
        entry = json.loads(line)
        domain = entry["domain"]
        first_seen = entry.get("first_seen")

        enrichment_path = enrichment_dir / f"{domain}.json"
        if not enrichment_path.exists():
            need.append((domain, first_seen))
            continue

        data = json.loads(enrichment_path.read_text(encoding="utf-8"))
        if data.get("creation_date") or data.get("registrar"):
            continue
        need.append((domain, first_seen))

    return need


async def run_backfill(
    api_key: str,
    delay: float = 0.5,
    max_retries: int = 3,
    dry_run: bool = False,
    limit: int | None = None,
) -> None:
    domains_needing = find_domains_needing_rdap(DATASET_PATH, ENRICHMENT_DIR)
    if limit:
        domains_needing = domains_needing[:limit]

    total = len(domains_needing)
    logger.info("Domains needing RDAP: %d (limit=%s)", total, limit or "none")

    if not domains_needing:
        logger.info("Nothing to do.")
        return

    succeeded = 0
    failed = 0
    skipped = 0
    start = time.monotonic()

    for i, (domain, first_seen) in enumerate(domains_needing, 1):
        target_date = _parse_date(first_seen)

        for attempt in range(max_retries):
            try:
                data = await query_whoxy_history(domain, api_key)
                records = data.get("whois_records", [])

                if not records:
                    logger.info("[%d/%d] %s: no WHOIS history records", i, total, domain)
                    skipped += 1
                    break

                best = _find_closest_record(records, target_date)
                fields = extract_rdap_fields(best)

                if dry_run:
                    logger.info("[%d/%d] %s: DRY RUN — creation=%s registrar=%s",
                                i, total, domain, fields["creation_date"], fields["registrar"])
                    succeeded += 1
                    break

                enrichment_path = ENRICHMENT_DIR / f"{domain}.json"
                if enrichment_path.exists():
                    enrichment = json.loads(enrichment_path.read_text(encoding="utf-8"))
                else:
                    enrichment = {"domain": domain, "errors": {}}

                enrichment["creation_date"] = fields["creation_date"]
                enrichment["expiration_date"] = fields["expiration_date"]
                enrichment["registrar"] = fields["registrar"]
                enrichment.get("errors", {}).pop("rdap", None)

                enrichment_path.write_text(
                    json.dumps(enrichment, indent=2, default=str), encoding="utf-8")

                logger.info("[%d/%d] %s: creation=%s registrar=%s",
                            i, total, domain, fields["creation_date"], fields["registrar"])
                succeeded += 1
                break

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    backoff = delay * (2 ** attempt)
                    logger.warning("[%d/%d] %s: 429 rate limited, waiting %.0fs",
                                   i, total, domain, backoff)
                    await asyncio.sleep(backoff)
                else:
                    logger.warning("[%d/%d] %s: HTTP %d", i, total, domain, exc.response.status_code)
                    failed += 1
                    break
            except (httpx.TimeoutException, httpx.ConnectError, ValueError) as exc:
                logger.warning("[%d/%d] %s: %s (attempt %d/%d)",
                               i, total, domain, exc, attempt + 1, max_retries)
                if attempt == max_retries - 1:
                    failed += 1
                await asyncio.sleep(delay)

        if i < total:
            await asyncio.sleep(delay)

    duration = time.monotonic() - start

    before_count = 0
    after_count = 0
    total_v2 = 0
    for line in DATASET_PATH.read_text(encoding="utf-8").strip().split("\n"):
        entry = json.loads(line)
        total_v2 += 1
        path = ENRICHMENT_DIR / f"{entry['domain']}.json"
        if path.exists():
            d = json.loads(path.read_text(encoding="utf-8"))
            if d.get("creation_date") or d.get("registrar"):
                after_count += 1

    before_count = after_count - succeeded

    logger.info("")
    logger.info("=" * 50)
    logger.info("WHOXY BACKFILL SUMMARY")
    logger.info("=" * 50)
    logger.info("Total queried:   %d", total)
    logger.info("Succeeded:       %d", succeeded)
    logger.info("Failed:          %d", failed)
    logger.info("No records:      %d", skipped)
    logger.info("Duration:        %.1fs", duration)
    logger.info("")
    logger.info("RDAP Coverage (v2 dataset, %d domains):", total_v2)
    logger.info("  Before: %d (%.1f%%)", before_count, before_count / total_v2 * 100 if total_v2 else 0)
    logger.info("  After:  %d (%.1f%%)", after_count, after_count / total_v2 * 100 if total_v2 else 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill RDAP data via Whoxy WHOIS History API")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between requests (default: 0.5 = 2 req/s)")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Max domains to query (for testing)")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("WHOXY_API_KEY", "")
    if not api_key:
        logger.error("WHOXY_API_KEY not set. Add to .env or export WHOXY_API_KEY=...")
        return 1

    asyncio.run(run_backfill(
        api_key=api_key,
        delay=args.delay,
        max_retries=args.max_retries,
        dry_run=args.dry_run,
        limit=args.limit,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
