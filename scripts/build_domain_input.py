"""Convert OTX and ThreatFox CSV files into the JSONL format used by run_batch.py.

This script reads the raw CSV data files already on disk and produces a single
JSONL file that the M1 batch pipeline (scripts/run_batch.py) can consume.

Input sources (in data/raw/):
    otx_domain_pulse_iocs.csv   — 71K rows, columns: domain,actor,pulse_id,pulse_name,created
    threatfox_full.csv          — 167K rows, columns: date,id,ioc,ioc_type,...,malware,...,family,...

Output format (JSONL):
    {"domain": "evil.com", "source": "otx", "actor": "Comment Crew", "family": null, "shared_infrastructure": false}
    {"domain": "malware.net", "source": "threatfox", "actor": null, "family": "ClearFake", "shared_infrastructure": false}

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source /mnt/d/proj/agent/agent-venv/bin/activate

    # Build from OTX only (all unique domains with actor labels):
    python -m scripts.build_domain_input --otx data/raw/otx_domain_pulse_iocs.csv -o data/raw/domains.jsonl

    # Build from ThreatFox only (domain IOCs with family labels):
    python -m scripts.build_domain_input --threatfox data/raw/threatfox_full.csv -o data/raw/domains.jsonl

    # Build from both sources combined:
    python -m scripts.build_domain_input \
        --otx data/raw/otx_domain_pulse_iocs.csv \
        --threatfox data/raw/threatfox_full.csv \
        -o data/raw/domains.jsonl

    # Limit output size (e.g. first 200 domains for a test run):
    python -m scripts.build_domain_input --otx data/raw/otx_domain_pulse_iocs.csv --max 200 -o data/raw/domains_200.jsonl

    # Then feed into the batch pipeline:
    python -m scripts.run_batch data/raw/domains.jsonl --init-schema

Shared infrastructure detection:
    Domains from ThreatFox with family "Cobalt Strike" or "Phorpiex" are
    automatically marked shared_infrastructure=true.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SHARED_INFRA_FAMILIES = {"Cobalt Strike", "Phorpiex", "cobaltstrike"}


def _parse_otx(path: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get("domain", "").strip()
            if not domain or domain in seen:
                continue
            seen.add(domain)
            actor = row.get("actor", "").strip() or None
            entries.append({
                "domain": domain,
                "source": "otx",
                "actor": actor,
                "family": None,
                "shared_infrastructure": False,
            })
    return entries


def _parse_threatfox(path: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = next(csv.reader([line]))
            except csv.Error:
                continue
            if len(parts) < 8:
                continue
            ioc = parts[2].strip().strip('"')
            ioc_type = parts[3].strip().strip('"')
            if ioc_type != "domain":
                continue
            if ioc in seen:
                continue
            seen.add(ioc)
            family = parts[7].strip().strip('"') or None
            shared = family in SHARED_INFRA_FAMILIES if family else False
            entries.append({
                "domain": ioc,
                "source": "threatfox",
                "actor": None,
                "family": family,
                "shared_infrastructure": shared,
            })
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert OTX / ThreatFox CSVs to JSONL for run_batch.py",
    )
    parser.add_argument("--otx", type=Path, help="Path to otx_domain_pulse_iocs.csv")
    parser.add_argument("--threatfox", type=Path, help="Path to threatfox_full.csv")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output JSONL file path")
    parser.add_argument("--max", type=int, default=0, help="Max domains to output (0 = unlimited)")
    args = parser.parse_args()

    if not args.otx and not args.threatfox:
        parser.error("At least one of --otx or --threatfox is required")

    all_entries: list[dict[str, object]] = []
    seen_domains: set[str] = set()

    if args.otx:
        otx_entries = _parse_otx(args.otx)
        for e in otx_entries:
            if e["domain"] not in seen_domains:
                seen_domains.add(e["domain"])  # type: ignore[arg-type]
                all_entries.append(e)
        print(f"OTX:       {len(otx_entries)} unique domains from {args.otx}")

    if args.threatfox:
        tf_entries = _parse_threatfox(args.threatfox)
        for e in tf_entries:
            if e["domain"] not in seen_domains:
                seen_domains.add(e["domain"])  # type: ignore[arg-type]
                all_entries.append(e)
        print(f"ThreatFox: {len(tf_entries)} unique domains from {args.threatfox}")

    if args.max > 0:
        all_entries = all_entries[: args.max]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, default=str) + "\n")

    print(f"Wrote {len(all_entries)} domains to {args.output}")


if __name__ == "__main__":
    main()
