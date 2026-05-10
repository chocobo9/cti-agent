"""Basic statistics for OTX domain↔actor export CSV.

Input columns: domain,actor,pulse_id,pulse_name,created

Usage:
    python -m scripts.otx_domain_pulse_iocs_stats
    python -m scripts.otx_domain_pulse_iocs_stats --csv data/raw/otx_domain_pulse_iocs.csv
    python -m scripts.otx_domain_pulse_iocs_stats --top-actors 20 --show-conflict-samples 15
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def norm_domain(s: str) -> str:
    return s.strip().lower()


def norm_actor(s: str) -> str:
    return s.strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--csv",
        type=Path,
        default=Path("data/raw/otx_domain_pulse_iocs.csv"),
        help="Path to domain,actor,pulse_id,pulse_name,created CSV.",
    )
    p.add_argument("--top-actors", type=int, default=30, help="Print this many actors by unique domain count.")
    p.add_argument(
        "--show-conflict-samples",
        type=int,
        default=20,
        help="Print up to N example domains that map to multiple actors (0 to disable).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    path = args.csv
    if not path.exists():
        print(f"File not found: {path}", flush=True)
        return 2

    rows_read = 0
    skipped = 0
    domain_to_actors: dict[str, set[str]] = defaultdict(set)
    actor_to_domains: dict[str, set[str]] = defaultdict(set)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        expected = {"domain", "actor", "pulse_id", "pulse_name", "created"}
        if reader.fieldnames is None:
            print("CSV has no header row.", flush=True)
            return 2
        cols = {c.strip() for c in reader.fieldnames}
        if not expected.issubset(cols):
            print(f"Unexpected columns. Need {sorted(expected)}, got {sorted(cols)}", flush=True)
            return 2

        for row in reader:
            rows_read += 1
            raw_dom = row.get("domain") or ""
            raw_act = row.get("actor") or ""
            d = norm_domain(raw_dom)
            a = norm_actor(raw_act)
            if not d or not a:
                skipped += 1
                continue
            domain_to_actors[d].add(a)
            actor_to_domains[a].add(d)

    unique_domains = len(domain_to_actors)
    unique_actors = len(actor_to_domains)
    conflict_domains = [d for d, actors in domain_to_actors.items() if len(actors) > 1]
    conflict_count = len(conflict_domains)

    print("=== OTX domain pulse IOCs — basic stats ===")
    print(f"CSV path:           {path.resolve()}")
    print(f"Rows read:          {rows_read}")
    print(f"Rows skipped:       {skipped} (missing domain or actor)")
    print(f"Unique domains:     {unique_domains}")
    print(f"Unique actors:      {unique_actors}")
    print(f"Multi-actor domains:{conflict_count}  (same domain string, >1 distinct actor label)")

    actor_unique_counts = [(a, len(ds)) for a, ds in actor_to_domains.items()]
    actor_unique_counts.sort(key=lambda x: (-x[1], x[0].lower()))

    print()
    print(f"--- Top {args.top_actors} actors by unique domain count ---")
    for actor, n in actor_unique_counts[: args.top_actors]:
        print(f"  {n:6d}  {actor}")

    if args.show_conflict_samples > 0 and conflict_domains:
        conflict_domains.sort(key=lambda d: (-len(domain_to_actors[d]), d))
        print()
        print(f"--- Sample multi-actor domains (up to {args.show_conflict_samples}) ---")
        for d in conflict_domains[: args.show_conflict_samples]:
            actors = sorted(domain_to_actors[d])
            print(f"  {d}")
            print(f"    actors ({len(actors)}): {', '.join(actors)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
