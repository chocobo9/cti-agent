"""M2.5-revised — Pulse-Based Actor Group Resampling

Replaces the actor group's cross-quartile random sampling with pulse-aggregated
sampling: domains from the same OTX pulse (attack report) stay together,
preserving infrastructure-sharing signals.

Family and Shared Infra groups are copied from v1 unchanged.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.m2_pulse_resampling
    python -m scripts.m2_pulse_resampling --target-per-actor 24 --max-pulses 6
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

CONFLICT_RESOLVED_CSV = Path("data/dataset/otx_conflict_resolved.csv")
ACTOR_CONFIG_PATH = Path("data/dataset/actor_group_config.json")
V1_DATASET = Path("data/dataset/attribution_dataset_v1.jsonl")
OUTPUT_DATASET = Path("data/dataset/attribution_dataset_v2.jsonl")
OUTPUT_REPORT = Path("data/dataset/dataset_report_v2.md")
OUTPUT_LOG = Path("data/dataset/pulse_sampling_log.json")


def load_actor_list(config_path: Path) -> list[str]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return config["actors"]


def load_otx_data(csv_path: Path, actors: list[str]) -> dict[str, list[dict]]:
    actor_set = set(actors)
    by_actor: dict[str, list[dict]] = defaultdict(list)
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["actor"] in actor_set:
                by_actor[row["actor"]].append(row)
    return dict(by_actor)


def sample_actor_pulses(
    actor: str,
    rows: list[dict],
    target_per_actor: int,
    max_pulses: int,
    max_domains_per_pulse: int,
    min_pulse_size: int,
    min_actor_domains: int,
) -> tuple[list[dict], dict]:
    by_pulse: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_pulse[r["pulse_id"]].append(r)

    pulse_stats = [
        {"pulse_id": pid, "pulse_name": doms[0].get("pulse_name", ""), "domain_count": len(doms), "created": doms[0].get("created", "")}
        for pid, doms in by_pulse.items()
    ]
    pulse_stats.sort(key=lambda x: -x["domain_count"])

    eligible = [p for p in pulse_stats if p["domain_count"] >= min_pulse_size]

    selected_domains: list[dict] = []
    selected_pulses: list[dict] = []
    seen_domains: set[str] = set()

    for pulse in eligible[:max_pulses]:
        if len(selected_domains) >= target_per_actor:
            break
        pid = pulse["pulse_id"]
        pulse_doms = by_pulse[pid]
        pulse_doms.sort(key=lambda r: r.get("created", ""))

        taken = []
        for r in pulse_doms:
            if r["domain"] not in seen_domains and len(taken) < max_domains_per_pulse:
                taken.append(r)
                seen_domains.add(r["domain"])
        selected_domains.extend(taken)
        selected_pulses.append({
            "pulse_id": pid,
            "pulse_name": pulse["pulse_name"],
            "total_domains_in_pulse": pulse["domain_count"],
            "domains_taken": len(taken),
            "created": pulse["created"],
        })

    warnings = []
    if len(selected_domains) < min_actor_domains:
        warnings.append(f"Low domain count: {len(selected_domains)} < {min_actor_domains}")
    if len(selected_pulses) < 2:
        warnings.append(f"Single pulse actor: only {len(selected_pulses)} pulse(s) available")

    log_entry = {
        "actor": actor,
        "total_available_domains": len(set(r["domain"] for r in rows)),
        "total_pulses": len(by_pulse),
        "eligible_pulses": len(eligible),
        "selected_pulses": len(selected_pulses),
        "selected_domains": len(selected_domains),
        "pulse_details": selected_pulses,
        "warnings": warnings,
    }
    return selected_domains, log_entry


def load_v1_non_actor_entries(v1_path: Path) -> list[dict]:
    entries = []
    for line in v1_path.read_text(encoding="utf-8").strip().split("\n"):
        entry = json.loads(line)
        if entry.get("group") != "actor_attribution":
            entries.append(entry)
    return entries


def write_report(
    v2_actor_entries: list[dict],
    v1_actor_entries: list[dict],
    non_actor_entries: list[dict],
    sampling_log: list[dict],
    output_path: Path,
) -> None:
    lines = ["# Dataset v2 Report — Pulse-Based Actor Resampling", ""]

    v1_actors = defaultdict(set)
    for e in v1_actor_entries:
        if e.get("actor"):
            v1_actors[e["actor"]].add(e["domain"])

    v2_actors = defaultdict(set)
    for e in v2_actor_entries:
        if e.get("actor"):
            v2_actors[e["actor"]].add(e["domain"])

    lines.append("## Per-Actor Comparison (v1 → v2)")
    lines.append("")
    lines.append("| Actor | v1 | v2 | Pulses | New | Removed |")
    lines.append("|-------|----|----|--------|-----|---------|")
    for log in sampling_log:
        actor = log["actor"]
        v1_set = v1_actors.get(actor, set())
        v2_set = v2_actors.get(actor, set())
        new = len(v2_set - v1_set)
        removed = len(v1_set - v2_set)
        lines.append(f"| {actor} | {len(v1_set)} | {len(v2_set)} | {log['selected_pulses']} | {new} | {removed} |")

    family_count = sum(1 for e in non_actor_entries if e.get("group") == "family_attribution")
    shared_count = sum(1 for e in non_actor_entries if e.get("group") == "shared_infra")
    total_v1_actor = sum(len(s) for s in v1_actors.values())

    lines.extend([
        "",
        "## Summary",
        "",
        f"- Actor group: v1={total_v1_actor} → v2={len(v2_actor_entries)} domains",
        f"- Family group: {family_count} (unchanged from v1)",
        f"- Shared infra group: {shared_count} (unchanged from v1)",
        f"- **Total v2: {len(v2_actor_entries) + len(non_actor_entries)} domains**",
        "",
    ])

    warned = [log for log in sampling_log if log["warnings"]]
    if warned:
        lines.append("## Warnings")
        lines.append("")
        for log in warned:
            lines.append(f"- **{log['actor']}**: {'; '.join(log['warnings'])}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pulse-based actor group resampling")
    parser.add_argument("--target-per-actor", type=int, default=24)
    parser.add_argument("--max-pulses", type=int, default=6)
    parser.add_argument("--max-domains-per-pulse", type=int, default=8)
    parser.add_argument("--min-pulse-size", type=int, default=3)
    parser.add_argument("--min-actor-domains", type=int, default=15)
    args = parser.parse_args()

    actors = load_actor_list(ACTOR_CONFIG_PATH)
    logger.info("Actors: %d from config", len(actors))

    otx_data = load_otx_data(CONFLICT_RESOLVED_CSV, actors)
    logger.info("OTX data loaded for %d actors", len(otx_data))

    v2_actor_entries: list[dict] = []
    sampling_log: list[dict] = []

    for actor in actors:
        rows = otx_data.get(actor, [])
        if not rows:
            logger.warning("No OTX data for %s — skipping", actor)
            sampling_log.append({"actor": actor, "total_available_domains": 0, "selected_domains": 0, "selected_pulses": 0, "warnings": ["No data"]})
            continue

        selected, log_entry = sample_actor_pulses(
            actor, rows,
            target_per_actor=args.target_per_actor,
            max_pulses=args.max_pulses,
            max_domains_per_pulse=args.max_domains_per_pulse,
            min_pulse_size=args.min_pulse_size,
            min_actor_domains=args.min_actor_domains,
        )
        sampling_log.append(log_entry)

        for r in selected:
            v2_actor_entries.append({
                "domain": r["domain"],
                "source": "otx",
                "actor": actor,
                "family": None,
                "shared_infrastructure": False,
                "group": "actor_attribution",
                "first_seen": r.get("created", "")[:10],
                "pulse_id": r["pulse_id"],
            })

        logger.info("  %s: %d domains from %d pulses%s",
                     actor, log_entry["selected_domains"], log_entry["selected_pulses"],
                     f" ⚠ {'; '.join(log_entry['warnings'])}" if log_entry["warnings"] else "")

    non_actor = load_v1_non_actor_entries(V1_DATASET)
    logger.info("Non-actor entries from v1: %d (family=%d, shared=%d)",
                len(non_actor),
                sum(1 for e in non_actor if e.get("group") == "family_attribution"),
                sum(1 for e in non_actor if e.get("group") == "shared_infra"))

    all_entries = v2_actor_entries + non_actor
    OUTPUT_DATASET.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in all_entries) + "\n",
        encoding="utf-8",
    )
    logger.info("v2 dataset: %d entries → %s", len(all_entries), OUTPUT_DATASET)

    OUTPUT_LOG.write_text(json.dumps(sampling_log, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Sampling log → %s", OUTPUT_LOG)

    v1_actor_entries = [
        json.loads(line)
        for line in V1_DATASET.read_text(encoding="utf-8").strip().split("\n")
        if json.loads(line).get("group") == "actor_attribution"
    ]
    write_report(v2_actor_entries, v1_actor_entries, non_actor, sampling_log, OUTPUT_REPORT)
    logger.info("Report → %s", OUTPUT_REPORT)

    return 0


if __name__ == "__main__":
    sys.exit(main())
