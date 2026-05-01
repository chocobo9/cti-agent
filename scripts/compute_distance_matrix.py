"""Compute the full pairwise distance matrix from enrichment JSONs.

Usage:
    cd /mnt/d/proj/agent/cti-agent
    source agent-venv/bin/activate
    python -m scripts.compute_distance_matrix
    python -m scripts.compute_distance_matrix --min-features 2 --profile-name coverage_weighted
    python -m scripts.compute_distance_matrix --nan-fill 0.9 --output-dir data/clustering/my_run
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from pathlib import Path

import numpy as np

from cti_agent.clustering.composite import WeightConfig
from cti_agent.clustering.matrix import (
    DistanceMatrixResult,
    build_distance_matrix,
    load_enrichments,
    save_distance_matrix,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute pairwise distance matrix")
    parser.add_argument("--enrichment-dir", type=Path, default=Path("data/enrichment"))
    parser.add_argument("--profile-path", type=Path, default=Path("config/clustering_profiles/coverage_weighted.yaml"))
    parser.add_argument("--profile-name", type=str, default="coverage_weighted")
    parser.add_argument("--output-dir", type=Path, default=Path("data/clustering/distance_matrix"))
    parser.add_argument("--nan-fill", type=float, default=1.0)
    parser.add_argument("--min-features", type=int, default=2)
    parser.add_argument("--dataset", type=Path, default=None,
                        help="JSONL dataset file — only include domains listed here")
    args = parser.parse_args()

    config = WeightConfig.from_yaml(args.profile_path, args.profile_name)
    logger.info("Profile: %s (alpha=%.2f, min_shared=%d)", args.profile_name, config.alpha, config.min_shared_features)

    domain_whitelist = None
    if args.dataset:
        dataset_domains = set()
        for line in args.dataset.read_text(encoding="utf-8").strip().split("\n"):
            dataset_domains.add(json.loads(line)["domain"])
        domain_whitelist = dataset_domains
        logger.info("Dataset filter: %d domains from %s", len(domain_whitelist), args.dataset)

    enrichments, filtered = load_enrichments(args.enrichment_dir, min_features=args.min_features, domain_whitelist=domain_whitelist)
    if not enrichments:
        logger.error("No enrichments loaded")
        return 1

    result = build_distance_matrix(enrichments, config, nan_fill=args.nan_fill)
    result = DistanceMatrixResult(
        matrix=result.matrix,
        domain_labels=result.domain_labels,
        nan_count=result.nan_count,
        total_pairs=result.total_pairs,
        nan_fill_value=result.nan_fill_value,
        filtered_domains=filtered,
        computation_seconds=result.computation_seconds,
    )

    save_distance_matrix(result, args.output_dir, config=config)

    valid = result.matrix[np.triu_indices_from(result.matrix, k=1)]
    vals = valid.tolist()

    logger.info("")
    logger.info("=== Distance Matrix Summary ===")
    logger.info("Domains:          %d (filtered out: %d)", len(result.domain_labels), len(filtered))
    logger.info("Total pairs:      %d", result.total_pairs)
    logger.info("NaN filled:       %d (%.1f%%)", result.nan_count,
                result.nan_count / result.total_pairs * 100 if result.total_pairs > 0 else 0)
    logger.info("Duration:         %.1fs", result.computation_seconds)
    logger.info("")
    logger.info("--- Distribution ---")
    logger.info("Mean:   %.4f", statistics.mean(vals))
    logger.info("Median: %.4f", statistics.median(vals))
    logger.info("StdDev: %.4f", statistics.stdev(vals))
    logger.info("Min:    %.4f", min(vals))
    logger.info("Max:    %.4f", max(vals))
    sorted_vals = sorted(vals)
    p = len(sorted_vals)
    logger.info("P5:     %.4f", sorted_vals[int(p * 0.05)])
    logger.info("P25:    %.4f", sorted_vals[int(p * 0.25)])
    logger.info("P75:    %.4f", sorted_vals[int(p * 0.75)])
    logger.info("P95:    %.4f", sorted_vals[int(p * 0.95)])
    logger.info("")
    logger.info("Output: %s", args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
