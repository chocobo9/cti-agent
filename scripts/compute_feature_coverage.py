"""Compute feature coverage rates from enrichment JSONs.

Scans data/enrichment/*.json and checks each of the 7 clustering features
for valid data. Outputs coverage statistics to a YAML file and optionally
generates a coverage_weighted profile.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.compute_feature_coverage
    python -m scripts.compute_feature_coverage --generate-profile
    python -m scripts.compute_feature_coverage --enrichment-dir data/enrichment --output config/clustering_profiles/coverage_stats.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cti_agent.clustering.composite import _has_data_for_feature
from cti_agent.clustering.distance import FEATURE_NAMES
from cti_agent.enrichment.models import DomainEnrichment

logging.basicConfig(
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute feature coverage from enrichment JSONs")
    parser.add_argument("--enrichment-dir", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--output", type=Path, default=Path("config/clustering_profiles/coverage_stats.yaml"))
    parser.add_argument("--generate-profile", action="store_true", help="Also generate coverage_weighted.yaml profile")
    args = parser.parse_args()

    files = sorted(args.enrichment_dir.glob("*.json"))
    if not files:
        logger.error("No JSON files found in %s", args.enrichment_dir)
        return 1

    total = len(files)
    counts: dict[str, int] = {name: 0 for name in FEATURE_NAMES}
    skipped = 0

    for i, path in enumerate(files, 1):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            enrichment = DomainEnrichment.model_validate(data)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path.name, exc)
            skipped += 1
            continue

        for feature in FEATURE_NAMES:
            if _has_data_for_feature(enrichment, feature):
                counts[feature] += 1

        if i % 100 == 0 or i == total:
            logger.info("[%d/%d] scanned", i, total)

    valid = total - skipped
    rates = {name: round(counts[name] / valid, 4) if valid > 0 else 0.0 for name in FEATURE_NAMES}

    logger.info("")
    logger.info("=== Feature Coverage (%d domains, %d skipped) ===", valid, skipped)
    for name in FEATURE_NAMES:
        logger.info("  %-20s %4d / %d  (%5.1f%%)", name, counts[name], valid, rates[name] * 100)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    stats = {
        "coverage_stats": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_dir": str(args.enrichment_dir),
            "total_domains": valid,
            "skipped_files": skipped,
            "features": {
                name: {"count": counts[name], "rate": rates[name]}
                for name in FEATURE_NAMES
            },
        }
    }
    args.output.write_text(yaml.dump(stats, default_flow_style=False, sort_keys=False), encoding="utf-8")
    logger.info("Coverage stats written to %s", args.output)

    if args.generate_profile:
        profile_path = args.output.parent / "coverage_weighted.yaml"
        features_cfg: dict[str, dict] = {}
        for name in FEATURE_NAMES:
            enabled = rates[name] > 0.0
            features_cfg[name] = {
                "weight": 1.0,
                "coverage_rate": rates[name],
                "enabled": enabled,
            }
            if not enabled:
                logger.warning("Feature %s has 0%% coverage — disabled in profile", name)

        profile = {
            "profiles": {
                "coverage_weighted": {
                    "alpha": 0.5,
                    "min_shared_features": 2,
                    "features": features_cfg,
                }
            }
        }
        profile_path.write_text(yaml.dump(profile, default_flow_style=False, sort_keys=False), encoding="utf-8")
        logger.info("Coverage-weighted profile written to %s", profile_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
