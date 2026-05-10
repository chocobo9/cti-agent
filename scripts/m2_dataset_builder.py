"""Steps 2.3-2.7: ThreatFox filtering, cross-source intersection, grouping, and final dataset generation.

Reads ThreatFox CSV and OTX conflict-resolved CSV, filters and samples domains
into three evaluation groups, and produces the final M1-compatible JSONL dataset.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source /mnt/d/proj/agent/agent-venv/bin/activate
    python -m scripts.m2_dataset_builder 
    python -m scripts.m2_dataset_builder --actor-config my.json   # uses custom config

Inputs:
    data/raw/threatfox_full.csv              ThreatFox IOC dump
    data/dataset/otx_conflict_resolved.csv   Conflict-free OTX data from step 2.2

Outputs:
    data/dataset/threatfox_domains.csv           All ThreatFox domain IOCs
    data/dataset/attribution_dataset_v1.jsonl     Final M1-compatible dataset (3 groups)
    data/dataset/dataset_report.md               Statistics for the paper
    data/dataset/dataset_build_log.json          Full audit trail
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DATA_RAW = Path("data/raw")
DATA_DATASET = Path("data/dataset")

THREATFOX_CSV = DATA_RAW / "threatfox_full.csv"
OTX_RESOLVED_CSV = DATA_DATASET / "otx_conflict_resolved.csv"

OUTPUT_TF_DOMAINS = DATA_DATASET / "threatfox_domains.csv"
OUTPUT_DATASET = DATA_DATASET / "attribution_dataset_v1.jsonl"
OUTPUT_REPORT = DATA_DATASET / "dataset_report.md"
OUTPUT_LOG = DATA_DATASET / "dataset_build_log.json"

TF_FIELDNAMES = [
    "first_seen_utc", "ioc_id", "ioc_value", "ioc_type", "threat_type",
    "fk_malware", "malware_alias", "malware_printable", "last_seen_utc",
    "confidence_level", "is_compromised", "reference", "tags", "anonymous", "reporter",
]

FAMILY_GROUP_CONFIG: dict[str, str] = {
    "js.clearfake": "ClearFake",
    "win.asyncrat": "AsyncRAT",
    "win.lumma": "Lumma Stealer",
    "win.formbook": "Formbook",
}
FAMILY_SAMPLE_PER_FAMILY = 60

SHARED_INFRA_CONFIG: dict[str, str] = {
    "win.cobalt_strike": "BEACON",
    "win.phorpiex": "phorphiex",
}
SHARED_INFRA_SAMPLE_PER_FAMILY = 50

DEFAULT_ACTOR_CONFIG = DATA_DATASET / "actor_group_config.json"

RNG_SEED = 42


def load_actor_config(path: Path) -> tuple[list[str], int]:
    """Load actor selection and sample count from a JSON config file."""
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    actors = config["actors"]
    sample_per_actor = config["sample_per_actor"]
    return actors, sample_per_actor


def parse_threatfox_csv(path: Path) -> list[dict[str, str]]:
    """Read ThreatFox CSV, skip comments, strip quotes, filter to domain IOCs."""
    rows: list[dict[str, str]] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        for raw_row in reader:
            if not raw_row or raw_row[0].strip().startswith("#"):
                continue
            fields = [x.strip().strip('"') for x in raw_row]
            if len(fields) < len(TF_FIELDNAMES):
                continue
            if fields[3] != "domain":
                continue
            rows.append({
                "domain": fields[2],
                "fk_malware": fields[5],
                "family": fields[7],
                "first_seen": fields[0][:10],
            })
    return rows


def stratified_time_sample(
    domains: list[dict[str, str]],
    n: int,
    rng: random.Random,
) -> list[dict[str, str]]:
    """Sample n domains stratified across 4 time quartiles of first_seen."""
    if len(domains) <= n:
        return list(domains)

    sorted_domains = sorted(domains, key=lambda d: d.get("first_seen", ""))
    total = len(sorted_domains)
    quartile_size = total // 4
    quartiles = [
        sorted_domains[:quartile_size],
        sorted_domains[quartile_size:2 * quartile_size],
        sorted_domains[2 * quartile_size:3 * quartile_size],
        sorted_domains[3 * quartile_size:],
    ]

    per_q = math.ceil(n / 4)
    sampled: list[dict[str, str]] = []
    deficit = 0
    for q in quartiles:
        target = per_q + deficit
        if len(q) <= target:
            sampled.extend(q)
            deficit = target - len(q)
        else:
            sampled.extend(rng.sample(q, target))
            deficit = 0

    if len(sampled) > n:
        sampled = sampled[:n]

    return sampled


def build_family_attribution_group(
    tf_domains: list[dict[str, str]],
    rng: random.Random,
) -> list[dict[str, str]]:
    """Select and sample domains for the Family Attribution Group."""
    by_family: dict[str, list[dict[str, str]]] = {}
    for row in tf_domains:
        fk = row["fk_malware"]
        if fk in FAMILY_GROUP_CONFIG:
            by_family.setdefault(fk, []).append(row)

    result: list[dict[str, str]] = []
    for fk, expected_family in FAMILY_GROUP_CONFIG.items():
        pool = by_family.get(fk, [])
        sampled = stratified_time_sample(pool, FAMILY_SAMPLE_PER_FAMILY, rng)
        for d in sampled:
            result.append({
                "domain": d["domain"],
                "source": "threatfox",
                "actor": None,
                "family": d["family"],
                "shared_infrastructure": False,
                "group": "family_attribution",
                "first_seen": d["first_seen"],
            })
    return result


def build_shared_infra_group(
    tf_domains: list[dict[str, str]],
    rng: random.Random,
) -> list[dict[str, str]]:
    """Select and sample domains for the Shared Infrastructure Group."""
    by_family: dict[str, list[dict[str, str]]] = {}
    for row in tf_domains:
        fk = row["fk_malware"]
        if fk in SHARED_INFRA_CONFIG:
            by_family.setdefault(fk, []).append(row)

    result: list[dict[str, str]] = []
    for fk, expected_family in SHARED_INFRA_CONFIG.items():
        pool = by_family.get(fk, [])
        sampled = stratified_time_sample(pool, SHARED_INFRA_SAMPLE_PER_FAMILY, rng)
        for d in sampled:
            result.append({
                "domain": d["domain"],
                "source": "threatfox",
                "actor": None,
                "family": d["family"],
                "shared_infrastructure": True,
                "group": "shared_infra",
                "first_seen": d["first_seen"],
            })
    return result


def find_intersection(
    otx_domains: set[str],
    tf_domains: set[str],
) -> set[str]:
    """Find domains present in both OTX and ThreatFox."""
    return otx_domains & tf_domains


def load_otx_resolved(path: Path) -> list[dict[str, str]]:
    """Load the conflict-resolved OTX CSV."""
    rows: list[dict[str, str]] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def build_actor_attribution_group(
    otx_rows: list[dict[str, str]],
    actor_selection: list[str],
    sample_per_actor: int,
    rng: random.Random,
) -> list[dict[str, str]]:
    """Select configured actors and sample N domains each."""
    by_actor: dict[str, list[dict[str, str]]] = {}
    for row in otx_rows:
        by_actor.setdefault(row["actor"], []).append(row)

    result: list[dict[str, str]] = []
    missing_actors: list[str] = []

    for actor in actor_selection:
        rows = by_actor.get(actor, [])
        seen: set[str] = set()
        unique_rows: list[dict[str, str]] = []
        for r in rows:
            if r["domain"] not in seen:
                seen.add(r["domain"])
                unique_rows.append(r)

        if len(unique_rows) < sample_per_actor:
            missing_actors.append(f"{actor} ({len(unique_rows)} domains)")
            if not unique_rows:
                continue

        pool_with_dates = []
        for r in unique_rows:
            pool_with_dates.append({
                "domain": r["domain"],
                "first_seen": r.get("created", "")[:10],
                "actor": actor,
            })
        sampled = stratified_time_sample(pool_with_dates, sample_per_actor, rng)
        for d in sampled:
            result.append({
                "domain": d["domain"],
                "source": "otx",
                "actor": d["actor"],
                "family": None,
                "shared_infrastructure": False,
                "group": "actor_attribution",
                "first_seen": d["first_seen"],
            })

    if missing_actors:
        print(f"  Warning: actors with fewer than {sample_per_actor} domains: {missing_actors}")

    return result


def merge_to_jsonl(
    actor_group: list[dict],
    family_group: list[dict],
    shared_group: list[dict],
) -> list[dict]:
    """Merge three groups, deduplicate by domain within each group."""
    all_entries: list[dict] = []
    seen_per_group: dict[str, set[str]] = {
        "actor_attribution": set(),
        "family_attribution": set(),
        "shared_infra": set(),
    }

    for entry in actor_group + family_group + shared_group:
        group = entry["group"]
        domain = entry["domain"]
        if domain not in seen_per_group[group]:
            seen_per_group[group].add(domain)
            all_entries.append(entry)

    return all_entries


def generate_stats_report(
    entries: list[dict],
    intersection_count: int,
    otx_total_domains: int,
    tf_total_domains: int,
    viable_actor_count: int,
) -> str:
    """Generate a Markdown statistics report for the paper."""
    by_group: dict[str, list[dict]] = {}
    for e in entries:
        by_group.setdefault(e["group"], []).append(e)

    actor_group = by_group.get("actor_attribution", [])
    family_group = by_group.get("family_attribution", [])
    shared_group = by_group.get("shared_infra", [])

    actor_dist = Counter(e["actor"] for e in actor_group if e.get("actor"))
    family_dist = Counter(e["family"] for e in family_group if e.get("family"))
    shared_dist = Counter(e["family"] for e in shared_group if e.get("family"))

    def time_stats(group: list[dict]) -> tuple[str, str, int]:
        dates = sorted(e["first_seen"] for e in group if e.get("first_seen"))
        if not dates:
            return ("N/A", "N/A", 0)
        return (dates[0], dates[-1], len(dates))

    lines = [
        "# Dataset Statistics Report",
        "",
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total domains | {len(entries)} |",
        f"| Actor Attribution Group | {len(actor_group)} |",
        f"| Family Attribution Group | {len(family_group)} |",
        f"| Shared Infrastructure Group | {len(shared_group)} |",
        f"| OTX source domains (post-cleaning) | {otx_total_domains} |",
        f"| ThreatFox domain IOCs | {tf_total_domains} |",
        f"| Cross-source intersection | {intersection_count} |",
        f"| Selected actors | {viable_actor_count} |",
        "",
        "## Actor Attribution Group",
        "",
        "| Actor | Domains |",
        "|-------|---------|",
    ]
    for actor, count in actor_dist.most_common():
        lines.append(f"| {actor} | {count} |")

    earliest, latest, n = time_stats(actor_group)
    lines += [
        "",
        f"Time range: {earliest} to {latest} ({n} domains with dates)",
        "",
        "## Family Attribution Group",
        "",
        "| Family | Domains |",
        "|--------|---------|",
    ]
    for family, count in family_dist.most_common():
        lines.append(f"| {family} | {count} |")

    earliest, latest, n = time_stats(family_group)
    lines += [
        "",
        f"Time range: {earliest} to {latest} ({n} domains with dates)",
        "",
        "## Shared Infrastructure Group",
        "",
        "| Family | Domains |",
        "|--------|---------|",
    ]
    for family, count in shared_dist.most_common():
        lines.append(f"| {family} | {count} |")

    earliest, latest, n = time_stats(shared_group)
    lines += [
        "",
        f"Time range: {earliest} to {latest} ({n} domains with dates)",
        "",
    ]

    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build M2 attribution dataset")
    parser.add_argument(
        "--actor-config", type=Path, default=DEFAULT_ACTOR_CONFIG,
        help="JSON config with actor selection and sample_per_actor (default: %(default)s)",
    )
    return parser.parse_args()


def run_dataset_builder(actor_config_path: Path = DEFAULT_ACTOR_CONFIG) -> None:
    DATA_DATASET.mkdir(parents=True, exist_ok=True)
    rng = random.Random(RNG_SEED)

    # --- Load actor config ---
    print(f"Loading actor config from {actor_config_path}...")
    actor_selection, sample_per_actor = load_actor_config(actor_config_path)
    print(f"  {len(actor_selection)} actors, {sample_per_actor} domains each")

    # --- Phase 1: ThreatFox filtering (2.3) ---
    print(f"Loading ThreatFox CSV from {THREATFOX_CSV}...")
    tf_domains = parse_threatfox_csv(THREATFOX_CSV)
    print(f"  ThreatFox domain IOCs: {len(tf_domains)}")

    tf_out_fields = ["domain", "family", "fk_malware", "first_seen"]
    with open(OUTPUT_TF_DOMAINS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=tf_out_fields)
        writer.writeheader()
        for row in tf_domains:
            writer.writerow(row)
    print(f"  Wrote {OUTPUT_TF_DOMAINS} ({len(tf_domains)} rows)")

    family_group = build_family_attribution_group(tf_domains, rng)
    family_dist = Counter(e["family"] for e in family_group)
    print(f"\n  Family Attribution Group: {len(family_group)} domains")
    for fam, count in family_dist.most_common():
        print(f"    {fam}: {count}")

    shared_group = build_shared_infra_group(tf_domains, rng)
    shared_dist = Counter(e["family"] for e in shared_group)
    print(f"\n  Shared Infrastructure Group: {len(shared_group)} domains")
    for fam, count in shared_dist.most_common():
        print(f"    {fam}: {count}")

    # --- Phase 2: Cross-source intersection (2.4) ---
    print(f"\nLoading OTX conflict-resolved CSV from {OTX_RESOLVED_CSV}...")
    otx_rows = load_otx_resolved(OTX_RESOLVED_CSV)
    otx_unique_domains = set(r["domain"] for r in otx_rows)
    tf_unique_domains = set(r["domain"] for r in tf_domains)
    intersection = find_intersection(otx_unique_domains, tf_unique_domains)
    print(f"  OTX unique domains: {len(otx_unique_domains)}")
    print(f"  ThreatFox unique domains: {len(tf_unique_domains)}")
    print(f"  Intersection: {len(intersection)} domains in both sources")

    # --- Phase 3: Actor group sampling (2.5) ---
    actor_group = build_actor_attribution_group(otx_rows, actor_selection, sample_per_actor, rng)
    actor_dist = Counter(e["actor"] for e in actor_group)
    print(f"\n  Actor Attribution Group: {len(actor_group)} domains, {len(actor_dist)} actors")

    # --- Phase 4: Merge and output (2.6 + 2.7) ---
    all_entries = merge_to_jsonl(actor_group, family_group, shared_group)
    print(f"\n  Total dataset: {len(all_entries)} domains")

    with open(OUTPUT_DATASET, "w", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  Wrote {OUTPUT_DATASET}")

    by_actor: dict[str, set[str]] = {}
    for row in otx_rows:
        by_actor.setdefault(row["actor"], set()).add(row["domain"])
    viable_actor_count = len(actor_selection)

    build_log = {
        "generated_at": datetime.now(timezone.utc)
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "rng_seed": RNG_SEED,
        "threatfox_total_domain_iocs": len(tf_domains),
        "otx_total_domains": len(otx_unique_domains),
        "cross_source_intersection": len(intersection),
        "intersection_domains_sample": sorted(intersection)[:50],
        "family_group": {
            "total": len(family_group),
            "per_family": dict(family_dist.most_common()),
            "config": {fk: fam for fk, fam in FAMILY_GROUP_CONFIG.items()},
            "sample_per_family": FAMILY_SAMPLE_PER_FAMILY,
        },
        "shared_infra_group": {
            "total": len(shared_group),
            "per_family": dict(shared_dist.most_common()),
            "config": {fk: fam for fk, fam in SHARED_INFRA_CONFIG.items()},
            "sample_per_family": SHARED_INFRA_SAMPLE_PER_FAMILY,
        },
        "actor_group": {
            "total": len(actor_group),
            "num_actors": len(actor_dist),
            "selected_actors": len(actor_selection),
            "sample_per_actor": sample_per_actor,
            "config_file": str(actor_config_path),
            "actor_list": actor_selection,
            "per_actor": dict(actor_dist.most_common()),
        },
        "final_dataset": {
            "total_domains": len(all_entries),
            "by_group": dict(Counter(e["group"] for e in all_entries)),
        },
    }

    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(build_log, f, indent=2)
    print(f"  Wrote {OUTPUT_LOG}")

    report = generate_stats_report(
        all_entries,
        intersection_count=len(intersection),
        otx_total_domains=len(otx_unique_domains),
        tf_total_domains=len(tf_unique_domains),
        viable_actor_count=viable_actor_count,
    )
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Wrote {OUTPUT_REPORT}")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("DATASET BUILD SUMMARY")
    print("=" * 70)
    print(f"Actor Attribution Group:       {len(actor_group)} domains ({len(actor_dist)} actors)")
    print(f"Family Attribution Group:      {len(family_group)} domains ({len(family_dist)} families)")
    print(f"Shared Infrastructure Group:   {len(shared_group)} domains ({len(shared_dist)} families)")
    print(f"Cross-source intersection:     {len(intersection)} domains")
    print(f"Total dataset:                 {len(all_entries)} domains")
    print(f"Output: {OUTPUT_DATASET}")


if __name__ == "__main__":
    args = _parse_args()
    run_dataset_builder(actor_config_path=args.actor_config)
