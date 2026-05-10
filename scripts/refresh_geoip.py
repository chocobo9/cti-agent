"""Temp script — re-run GeoIP lookups on existing enrichment JSONs.

Reads each data/enrichment/{domain}.json, extracts valid IPs from
passive_dns + current_ips, looks them up against the local MaxMind DB,
and overwrites the geoip field in-place.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.refresh_geoip
    python -m scripts.refresh_geoip --enrichment-dir data/enrichment --dry-run
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import sys
from pathlib import Path

from cti_agent.enrichment.geoip import lookup_geoip_batch

logging.basicConfig(
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _is_valid_ip(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not addr.is_unspecified


def _extract_ips(data: dict) -> list[str]:
    seen: set[str] = set()
    ips: list[str] = []
    for record in data.get("passive_dns", []):
        ip = record.get("ip", "")
        if ip not in seen and _is_valid_ip(ip):
            seen.add(ip)
            ips.append(ip)
    for ip in data.get("current_ips", []):
        if ip not in seen and _is_valid_ip(ip):
            seen.add(ip)
            ips.append(ip)
    return ips


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh GeoIP data in enrichment JSONs")
    parser.add_argument("--enrichment-dir", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    files = sorted(args.enrichment_dir.glob("*.json"))
    if not files:
        logger.error("No JSON files found in %s", args.enrichment_dir)
        return 1

    logger.info("Processing %d enrichment files from %s", len(files), args.enrichment_dir)

    updated = 0
    skipped = 0
    had_asn_before = 0
    has_asn_after = 0

    for i, path in enumerate(files, 1):
        data = json.loads(path.read_text(encoding="utf-8"))

        old_geoip = data.get("geoip", [])
        old_has_asn = any(g.get("asn_number") is not None for g in old_geoip)
        if old_has_asn:
            had_asn_before += 1

        ips = _extract_ips(data)
        if not ips:
            skipped += 1
            continue

        new_geoip_objs = lookup_geoip_batch(ips)
        new_geoip = [
            {
                "ip": g.ip,
                "asn_number": g.asn_number,
                "asn_name": g.asn_name,
                "country": g.country,
                "city": g.city,
            }
            for g in new_geoip_objs
        ]

        new_has_asn = any(g["asn_number"] is not None for g in new_geoip)
        if new_has_asn:
            has_asn_after += 1

        data["geoip"] = new_geoip
        errors = data.get("errors", {})
        errors.pop("geoip", None)
        data["errors"] = errors

        if not args.dry_run:
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

        updated += 1
        if i % 100 == 0 or i == len(files):
            logger.info("[%d/%d] processed — %d updated, %d skipped (no IPs)", i, len(files), updated, skipped)

    logger.info("")
    logger.info("=== GeoIP Refresh Complete ===")
    logger.info("Total files:       %d", len(files))
    logger.info("Updated:           %d", updated)
    logger.info("Skipped (no IPs):  %d", skipped)
    logger.info("Had ASN before:    %d", had_asn_before)
    logger.info("Has ASN after:     %d", has_asn_after)
    if args.dry_run:
        logger.info("(DRY RUN — no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
