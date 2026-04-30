"""Step 2.1: Actor Name Normalization using MITRE ATT&CK STIX data.

Reads the raw OTX CSV and normalizes actor names to MITRE preferred names
using the alias mappings from enterprise-attack.json.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source /mnt/d/proj/agent/agent-venv/bin/activate
    python -m scripts.m2_actor_normalization

Inputs:
    data/raw/enterprise-attack.json      MITRE ATT&CK STIX bundle
    data/raw/otx_domain_pulse_iocs.csv   Raw OTX domain IOCs

Outputs:
    data/dataset/otx_normalized.csv      OTX CSV with normalized actor names
    data/dataset/normalization_log.json   Mapping of original → normalized names
    data/dataset/actor_distribution.csv   Per-actor domain counts (sorted desc)
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

DATA_RAW = Path("data/raw")
DATA_DATASET = Path("data/dataset")

MITRE_STIX_PATH = DATA_RAW / "enterprise-attack.json"
OTX_CSV_PATH = DATA_RAW / "otx_domain_pulse_iocs.csv"

OUTPUT_CSV = DATA_DATASET / "otx_normalized.csv"
OUTPUT_LOG = DATA_DATASET / "normalization_log.json"
OUTPUT_DIST = DATA_DATASET / "actor_distribution.csv"

APT_SPACE_RE = re.compile(r"^(APT)\s+(\d+)$", re.IGNORECASE)


def build_mitre_alias_map(stix_path: Path) -> dict[str, str]:
    """Parse MITRE STIX JSON and build lowercase-alias to primary-name map."""
    with open(stix_path, encoding="utf-8") as f:
        bundle = json.load(f)

    alias_to_primary: dict[str, str] = {}
    for obj in bundle["objects"]:
        if obj.get("type") != "intrusion-set":
            continue
        primary = obj["name"]
        for alias in obj.get("aliases", []):
            key = alias.strip().lower()
            alias_to_primary[key] = primary

    return alias_to_primary


def clean_actor_format(name: str) -> str:
    """Normalize formatting: strip whitespace, collapse 'APT 29' to 'APT29'."""
    name = name.strip()
    m = APT_SPACE_RE.match(name)
    if m:
        name = f"APT{m.group(2)}"
    return name


def normalize_actor(
    raw_name: str,
    alias_map: dict[str, str],
) -> tuple[str, bool]:
    """Normalize an actor name. Returns (normalized_name, was_mapped)."""
    cleaned = clean_actor_format(raw_name)
    key = cleaned.lower()
    if key in alias_map:
        return alias_map[key], True
    return cleaned, False


def run_normalization() -> None:
    DATA_DATASET.mkdir(parents=True, exist_ok=True)

    print("Loading MITRE ATT&CK STIX data...")
    alias_map = build_mitre_alias_map(MITRE_STIX_PATH)
    print(f"  Built alias map: {len(alias_map)} aliases -> intrusion-sets")

    print(f"Loading OTX CSV from {OTX_CSV_PATH}...")
    rows: list[dict[str, str]] = []
    with open(OTX_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"  Loaded {len(rows)} rows")

    original_actors: set[str] = set()
    mapped_names: dict[str, str] = {}
    unmapped_names: set[str] = set()
    normalized_rows: list[dict[str, str]] = []

    for row in rows:
        raw_actor = row["actor"]
        original_actors.add(raw_actor)
        normalized, was_mapped = normalize_actor(raw_actor, alias_map)

        if was_mapped:
            cleaned = clean_actor_format(raw_actor)
            if cleaned != normalized:
                mapped_names[cleaned] = normalized
            elif raw_actor != normalized:
                mapped_names[raw_actor] = normalized
        else:
            unmapped_names.add(normalized)

        new_row = dict(row)
        new_row["actor_original"] = raw_actor
        new_row["actor"] = normalized
        normalized_rows.append(new_row)

    normalized_actors = set()
    actor_counter: Counter[str] = Counter()
    for row in normalized_rows:
        normalized_actors.add(row["actor"])
        actor_counter[row["actor"]] += 1

    fieldnames = ["domain", "actor", "actor_original", "pulse_id", "pulse_name", "created"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in normalized_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"\nWrote normalized CSV: {OUTPUT_CSV} ({len(normalized_rows)} rows)")

    log = {
        "total_original_actors": len(original_actors),
        "total_normalized_actors": len(normalized_actors),
        "actors_consolidated": len(original_actors) - len(normalized_actors),
        "mitre_mapped_count": len(mapped_names),
        "unmapped_count": len(unmapped_names),
        "mapped": dict(sorted(mapped_names.items())),
        "unmapped": sorted(unmapped_names),
    }
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    print(f"Wrote normalization log: {OUTPUT_LOG}")

    with open(OUTPUT_DIST, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["actor", "domain_count", "viable_ge20"])
        for actor, count in actor_counter.most_common():
            writer.writerow([actor, count, count >= 20])
    print(f"Wrote actor distribution: {OUTPUT_DIST}")

    print("\n" + "=" * 70)
    print("ACTOR NORMALIZATION SUMMARY")
    print("=" * 70)
    print(f"Original unique actors:    {len(original_actors)}")
    print(f"Normalized unique actors:  {len(normalized_actors)}")
    print(f"Actors consolidated:       {len(original_actors) - len(normalized_actors)}")
    print(f"  - MITRE-mapped merges:   {len(mapped_names)}")
    print(f"  - Unmapped (kept as-is): {len(unmapped_names)}")

    viable = [(a, c) for a, c in actor_counter.most_common() if c >= 20]
    print(f"\nViable actors (>=20 domains): {len(viable)}")
    print(f"{'Actor':<30s} {'Domains':>8s}")
    print("-" * 40)
    for actor, count in viable:
        print(f"{actor:<30s} {count:>8d}")

    total_viable_domains = sum(c for _, c in viable)
    print(f"\nTotal domains in viable actors: {total_viable_domains}")

    print("\n--- Mapped actor name changes ---")
    for original, normalized in sorted(mapped_names.items()):
        count = actor_counter.get(normalized, 0)
        print(f"  {original:<30s} -> {normalized:<30s} ({count} domains)")


if __name__ == "__main__":
    run_normalization()
