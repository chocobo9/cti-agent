"""Step 2.2: Multi-Actor Conflict Resolution.

Reads the normalized OTX CSV from step 2.1, excludes confirmed noise actors
(Hacking Team, Group5), detects domains labeled with multiple distinct actors,
and resolves or drops conflicts to produce a conflict-free dataset.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source /mnt/d/proj/agent/agent-venv/bin/activate
    python -m scripts.m2_conflict_resolution

Inputs:
    data/dataset/otx_normalized.csv       Normalized OTX CSV from step 2.1

Outputs:
    data/dataset/otx_conflict_resolved.csv  Conflict-free CSV (one actor per domain)
    data/dataset/conflict_report.json       Detailed conflict analysis and audit trail
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DATA_DATASET = Path("data/dataset")

INPUT_CSV = DATA_DATASET / "otx_normalized.csv"
OUTPUT_CSV = DATA_DATASET / "otx_conflict_resolved.csv"
OUTPUT_REPORT = DATA_DATASET / "conflict_report.json"

FIELDNAMES = ["domain", "actor", "actor_original", "pulse_id", "pulse_name", "created"]

NOISE_ACTORS_EXTENDED = frozenset({"Hacking Team", "Group5"})

MAJORITY_VOTE_RATIO = 2.0


@dataclass(frozen=True)
class ConflictRecord:
    domain: str
    actors: list[str]
    pulse_counts: dict[str, int]
    action: str  # "resolve_majority" | "resolve_recency" | "drop_tie" | "drop_multi"
    resolved_actor: str | None
    reason: str


def load_and_exclude_noise(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Filter out rows belonging to noise actors.

    Returns the filtered rows and a dict of {actor: removed_count}.
    """
    noise_stats: Counter[str] = Counter()
    clean: list[dict[str, str]] = []
    for row in rows:
        actor = row["actor"]
        if actor in NOISE_ACTORS_EXTENDED:
            noise_stats[actor] += 1
        else:
            clean.append(row)
    return clean, dict(noise_stats)


def detect_conflicts(
    rows: list[dict[str, str]],
) -> tuple[
    dict[str, list[dict[str, str]]],
    dict[str, list[dict[str, str]]],
    dict[str, list[dict[str, str]]],
]:
    """Group rows by domain and categorize by conflict type.

    Returns (clean_domains, two_actor_conflicts, multi_actor_conflicts),
    each mapping domain -> list of rows.
    """
    by_domain: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_domain.setdefault(row["domain"], []).append(row)

    clean: dict[str, list[dict[str, str]]] = {}
    two_actor: dict[str, list[dict[str, str]]] = {}
    multi_actor: dict[str, list[dict[str, str]]] = {}

    for domain, domain_rows in by_domain.items():
        actors = {r["actor"] for r in domain_rows}
        if len(actors) == 1:
            clean[domain] = domain_rows
        elif len(actors) == 2:
            two_actor[domain] = domain_rows
        else:
            multi_actor[domain] = domain_rows

    return clean, two_actor, multi_actor


def resolve_two_actor_conflict(
    domain: str,
    domain_rows: list[dict[str, str]],
) -> ConflictRecord:
    """Resolve a domain with exactly 2 actors using majority vote or recency."""
    pulse_counts: Counter[str] = Counter()
    latest_pulse: dict[str, str] = {}

    for row in domain_rows:
        actor = row["actor"]
        pulse_counts[actor] += 1
        created = row.get("created", "")
        if created > latest_pulse.get(actor, ""):
            latest_pulse[actor] = created

    actors = list(pulse_counts.keys())
    a, b = actors[0], actors[1]
    count_a, count_b = pulse_counts[a], pulse_counts[b]

    sorted_actors = sorted(actors)
    sorted_counts = {ac: pulse_counts[ac] for ac in sorted_actors}

    if count_a >= MAJORITY_VOTE_RATIO * count_b:
        return ConflictRecord(
            domain=domain,
            actors=sorted_actors,
            pulse_counts=sorted_counts,
            action="resolve_majority",
            resolved_actor=a,
            reason=f"{a} has {count_a} pulses vs {b} has {count_b} (>={MAJORITY_VOTE_RATIO}x)",
        )
    if count_b >= MAJORITY_VOTE_RATIO * count_a:
        return ConflictRecord(
            domain=domain,
            actors=sorted_actors,
            pulse_counts=sorted_counts,
            action="resolve_majority",
            resolved_actor=b,
            reason=f"{b} has {count_b} pulses vs {a} has {count_a} (>={MAJORITY_VOTE_RATIO}x)",
        )

    latest_a = latest_pulse.get(a, "")
    latest_b = latest_pulse.get(b, "")

    if latest_a > latest_b:
        return ConflictRecord(
            domain=domain,
            actors=sorted_actors,
            pulse_counts=sorted_counts,
            action="resolve_recency",
            resolved_actor=a,
            reason=f"{a} has more recent pulse ({latest_a}) vs {b} ({latest_b})",
        )
    if latest_b > latest_a:
        return ConflictRecord(
            domain=domain,
            actors=sorted_actors,
            pulse_counts=sorted_counts,
            action="resolve_recency",
            resolved_actor=b,
            reason=f"{b} has more recent pulse ({latest_b}) vs {a} ({latest_a})",
        )

    return ConflictRecord(
        domain=domain,
        actors=sorted_actors,
        pulse_counts=sorted_counts,
        action="drop_tie",
        resolved_actor=None,
        reason=f"Tie: both actors have {count_a} pulses and same latest date ({latest_a})",
    )


def build_conflict_free_dataset(
    clean_domains: dict[str, list[dict[str, str]]],
    two_actor_conflicts: dict[str, list[dict[str, str]]],
    resolutions: list[ConflictRecord],
) -> list[dict[str, str]]:
    """Assemble the final conflict-free row list."""
    resolution_map = {r.domain: r for r in resolutions}

    result: list[dict[str, str]] = []

    for domain_rows in clean_domains.values():
        result.extend(domain_rows)

    for domain, domain_rows in two_actor_conflicts.items():
        record = resolution_map.get(domain)
        if record is None or record.resolved_actor is None:
            continue
        result.extend(r for r in domain_rows if r["actor"] == record.resolved_actor)

    return result


def build_conflict_report(
    *,
    input_path: str,
    noise_stats: dict[str, int],
    rows_after_noise: int,
    total_unique_domains: int,
    clean_count: int,
    two_actor_count: int,
    multi_actor_count: int,
    resolutions: list[ConflictRecord],
    multi_actor_domains: dict[str, list[dict[str, str]]],
    final_rows: list[dict[str, str]],
) -> dict:
    """Build the full conflict analysis report."""
    resolved = [r for r in resolutions if r.resolved_actor is not None]
    dropped_two = [r for r in resolutions if r.resolved_actor is None]

    dropped_multi = []
    for domain, domain_rows in multi_actor_domains.items():
        actors = sorted({r["actor"] for r in domain_rows})
        pulse_counts = dict(Counter(r["actor"] for r in domain_rows))
        dropped_multi.append(
            ConflictRecord(
                domain=domain,
                actors=actors,
                pulse_counts=pulse_counts,
                action="drop_multi",
                resolved_actor=None,
                reason=f"Domain has {len(actors)} actors — too ambiguous",
            )
        )

    final_domains = {r["domain"] for r in final_rows}
    final_actors = {r["actor"] for r in final_rows}

    return {
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "input_file": input_path,
        "noise_excluded": noise_stats,
        "noise_rows_removed_total": sum(noise_stats.values()),
        "rows_after_noise_exclusion": rows_after_noise,
        "total_unique_domains": total_unique_domains,
        "clean_domains_count": clean_count,
        "two_actor_conflict_count": two_actor_count,
        "multi_actor_conflict_count": multi_actor_count,
        "two_actor_resolved_count": len(resolved),
        "two_actor_dropped_count": len(dropped_two),
        "multi_actor_dropped_count": len(dropped_multi),
        "total_domains_dropped": len(dropped_two) + len(dropped_multi),
        "two_actor_resolutions": [asdict(r) for r in resolutions],
        "multi_actor_dropped": [asdict(r) for r in dropped_multi],
        "final_unique_domains": len(final_domains),
        "final_unique_actors": len(final_actors),
        "final_row_count": len(final_rows),
    }


def run_conflict_resolution() -> None:
    DATA_DATASET.mkdir(parents=True, exist_ok=True)

    print(f"Loading normalized CSV from {INPUT_CSV}...")
    with open(INPUT_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
    print(f"  Loaded {len(all_rows)} rows")

    # --- Noise exclusion ---
    rows, noise_stats = load_and_exclude_noise(all_rows)
    print(f"\n  Noise exclusion:")
    for actor, count in sorted(noise_stats.items()):
        print(f"    {actor}: {count} rows removed")
    print(f"  Rows after noise exclusion: {len(rows)}")

    # --- Conflict detection ---
    clean, two_actor, multi_actor = detect_conflicts(rows)
    total_domains = len(clean) + len(two_actor) + len(multi_actor)
    print(f"\n  Conflict detection ({total_domains} unique domains):")
    print(f"    Clean (1 actor):    {len(clean)}")
    print(f"    2-actor conflicts:  {len(two_actor)}")
    print(f"    3+ actor conflicts: {len(multi_actor)}")

    # --- Resolve 2-actor conflicts ---
    resolutions: list[ConflictRecord] = []
    for domain, domain_rows in sorted(two_actor.items()):
        record = resolve_two_actor_conflict(domain, domain_rows)
        resolutions.append(record)

    resolved = [r for r in resolutions if r.resolved_actor is not None]
    dropped = [r for r in resolutions if r.resolved_actor is None]
    print(f"\n  2-actor resolution:")
    print(f"    Resolved (majority vote): {sum(1 for r in resolved if r.action == 'resolve_majority')}")
    print(f"    Resolved (recency):       {sum(1 for r in resolved if r.action == 'resolve_recency')}")
    print(f"    Dropped (tie):            {len(dropped)}")

    if multi_actor:
        print(f"\n  3+ actor domains dropped:")
        for domain in sorted(multi_actor):
            actors = sorted({r["actor"] for r in multi_actor[domain]})
            print(f"    {domain}: {actors}")

    # --- Build conflict-free dataset ---
    final_rows = build_conflict_free_dataset(clean, two_actor, resolutions)
    final_domains = {r["domain"] for r in final_rows}
    final_actors = {r["actor"] for r in final_rows}

    # --- Write output CSV ---
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in final_rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    print(f"\n  Wrote conflict-free CSV: {OUTPUT_CSV} ({len(final_rows)} rows)")

    # --- Write conflict report ---
    report = build_conflict_report(
        input_path=str(INPUT_CSV),
        noise_stats=noise_stats,
        rows_after_noise=len(rows),
        total_unique_domains=total_domains,
        clean_count=len(clean),
        two_actor_count=len(two_actor),
        multi_actor_count=len(multi_actor),
        resolutions=resolutions,
        multi_actor_domains=multi_actor,
        final_rows=final_rows,
    )
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"  Wrote conflict report: {OUTPUT_REPORT}")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("CONFLICT RESOLUTION SUMMARY")
    print("=" * 70)
    print(f"Input rows:              {len(all_rows)}")
    print(f"Noise rows removed:      {sum(noise_stats.values())}")
    print(f"Rows after noise:        {len(rows)}")
    print(f"Unique domains (input):  {total_domains}")
    print(f"  Clean (1 actor):       {len(clean)}")
    print(f"  2-actor conflicts:     {len(two_actor)}")
    print(f"    Resolved:            {len(resolved)}")
    print(f"    Dropped (tie):       {len(dropped)}")
    print(f"  3+ actor conflicts:    {len(multi_actor)} (all dropped)")
    print(f"Unique domains (output): {len(final_domains)}")
    print(f"Unique actors (output):  {len(final_actors)}")
    print(f"Output rows:             {len(final_rows)}")


if __name__ == "__main__":
    run_conflict_resolution()
