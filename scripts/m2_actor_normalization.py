"""Step 2.1: Actor Name Normalization using MITRE ATT&CK STIX data.

Reads the raw OTX CSV and normalizes actor names to MITRE preferred names
using the alias mappings from enterprise-attack.json, with manual overrides
for known MITRE duplicates and OTX-specific issues.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source /mnt/d/proj/agent/agent-venv/bin/activate
    python -m scripts.m2_actor_normalization

Inputs:
    data/raw/enterprise-attack.json      MITRE ATT&CK STIX bundle
    data/raw/otx_domain_pulse_iocs.csv   Raw OTX domain IOCs

Outputs:
    data/dataset/otx_normalized.csv      OTX CSV with normalized actor names
    data/dataset/normalization_log.json   Mapping of original -> normalized names
    data/dataset/actor_distribution.csv   Per-actor domain counts (sorted desc)
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timezone
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

NOISE_ACTORS = frozenset({"[Unnamed group]", "Unnamed Actor", "Hacking Team", "Group5"})

# MITRE has duplicate entries that cause mapping conflicts. These overrides
# ensure consolidation to the preferred group ID:
#   G0058 "Charming Kitten" (standalone) should merge into G0059 "Magic Hound"
#   "Sandworm" (bare name) should map to G0034 "Sandworm Team"
#   "Turla Group" should map to G0010 "Turla"
MANUAL_OVERRIDES: dict[str, str] = {
    "charming kitten": "Magic Hound",
    "sandworm": "Sandworm Team",
    "turla group": "Turla",
}

ANOMALY_ACTORS = ["Hacking Team", "Group5"]
ANOMALY_SAMPLE_SIZE = 10


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

    alias_to_primary.update(MANUAL_OVERRIDES)
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
    print(f"  Manual overrides applied: {list(MANUAL_OVERRIDES.values())}")

    print(f"\nLoading OTX CSV from {OTX_CSV_PATH}...")
    rows: list[dict[str, str]] = []
    with open(OTX_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"  Loaded {len(rows)} rows")

    # --- Noise exclusion ---
    noise_count = sum(1 for r in rows if r["actor"].strip() in NOISE_ACTORS)
    rows = [r for r in rows if r["actor"].strip() not in NOISE_ACTORS]
    print(f"  Excluded {noise_count} rows from noise actors: {sorted(NOISE_ACTORS)}")
    print(f"  Remaining: {len(rows)} rows")

    # --- Normalization ---
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

    # --- Write normalized CSV ---
    fieldnames = ["domain", "actor", "actor_original", "pulse_id", "pulse_name", "created"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in normalized_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"\nWrote normalized CSV: {OUTPUT_CSV} ({len(normalized_rows)} rows)")

    # --- Write normalization log ---
    log = {
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "total_original_actors": len(original_actors),
        "total_normalized_actors": len(normalized_actors),
        "actors_consolidated": len(original_actors) - len(normalized_actors),
        "noise_excluded": sorted(NOISE_ACTORS),
        "noise_rows_removed": noise_count,
        "manual_overrides": MANUAL_OVERRIDES,
        "mitre_mapped_count": len(mapped_names),
        "unmapped_count": len(unmapped_names),
        "mapped": dict(sorted(mapped_names.items())),
        "unmapped": sorted(unmapped_names),
    }
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    print(f"Wrote normalization log: {OUTPUT_LOG}")

    # --- Write actor distribution ---
    with open(OUTPUT_DIST, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["actor", "domain_count", "viable_ge20"])
        for actor, count in actor_counter.most_common():
            writer.writerow([actor, count, count >= 20])
    print(f"Wrote actor distribution: {OUTPUT_DIST}")

    # --- Print summary ---
    print("\n" + "=" * 70)
    print("ACTOR NORMALIZATION SUMMARY (v2 — with overrides + noise removal)")
    print("=" * 70)
    print(f"Original rows loaded:      {len(rows) + noise_count}")
    print(f"Noise rows removed:        {noise_count}")
    print(f"Rows after cleaning:       {len(normalized_rows)}")
    print(f"Original unique actors:    {len(original_actors)}")
    print(f"Normalized unique actors:  {len(normalized_actors)}")
    print(f"Actors consolidated:       {len(original_actors) - len(normalized_actors)}")
    print(f"  - MITRE-mapped merges:   {len(mapped_names)}")
    print(f"  - Unmapped (kept as-is): {len(unmapped_names)}")

    viable = [(a, c) for a, c in actor_counter.most_common() if c >= 20]
    print(f"\nViable actors (>=20 domains): {len(viable)}")
    print(f"{'Actor':<30s} {'Domains':>8s}  {'Viable':>6s}")
    print("-" * 48)
    for actor, count in viable:
        print(f"{actor:<30s} {count:>8d}  {'Yes':>6s}")

    total_viable_domains = sum(c for _, c in viable)
    print(f"\nTotal domains in viable actors: {total_viable_domains}")

    print("\n--- Mapped actor name changes ---")
    for original, normalized in sorted(mapped_names.items()):
        count = actor_counter.get(normalized, 0)
        print(f"  {original:<30s} -> {normalized:<30s} ({count} domains)")

    # --- Anomaly sampling ---
    print("\n" + "=" * 70)
    print("ANOMALOUS ACTOR SAMPLE REPORT (for manual investigation)")
    print("=" * 70)
    rng = random.Random(42)
    for anomaly_actor in ANOMALY_ACTORS:
        anomaly_rows = [r for r in normalized_rows if r["actor"] == anomaly_actor]
        sample = rng.sample(anomaly_rows, min(ANOMALY_SAMPLE_SIZE, len(anomaly_rows)))
        print(f"\n{anomaly_actor} ({len(anomaly_rows)} domains) — {ANOMALY_SAMPLE_SIZE} random samples:")
        for r in sample:
            pulse = r.get("pulse_name", "")[:80]
            print(f"  {r['domain']:<40s} | {pulse}")


if __name__ == "__main__":
    run_normalization()
