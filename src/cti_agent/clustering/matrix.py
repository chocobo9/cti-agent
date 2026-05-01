"""Pairwise distance matrix computation for domain clustering.

Loads enrichment JSONs, computes NxN composite distance matrix using
PDS+FWPD, and persists the result for DBSCAN consumption.

Output format (three files in one directory):
  distance_matrix.npy   — NxN numpy float64 array
  domain_labels.json    — ordered list of domain names (index = row/col)
  matrix_metadata.json  — profile config, NaN stats, filtered domains, timing
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from cti_agent.clustering.composite import (
    WeightConfig,
    _has_data_for_feature,
    composite_distance,
)
from cti_agent.clustering.distance import FEATURE_NAMES
from cti_agent.enrichment.models import DomainEnrichment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DistanceMatrixResult:
    matrix: np.ndarray
    domain_labels: list[str]
    nan_count: int
    total_pairs: int
    nan_fill_value: float
    filtered_domains: list[str]
    computation_seconds: float


def load_enrichments(
    enrichment_dir: Path,
    min_features: int = 2,
    domain_whitelist: set[str] | None = None,
) -> tuple[list[DomainEnrichment], list[str]]:
    """Load enrichment JSONs, optionally filtering sparse domains.

    When *domain_whitelist* is provided, only domains in the set are loaded.
    Returns (included_enrichments, filtered_domain_names), both sorted
    alphabetically by domain.
    """
    files = sorted(enrichment_dir.glob("*.json"))
    if not files:
        return [], []

    enrichments: list[DomainEnrichment] = []
    filtered: list[str] = []
    skipped_parse = 0

    for i, path in enumerate(files, 1):
        if domain_whitelist is not None and path.stem not in domain_whitelist:
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            e = DomainEnrichment.model_validate(data)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path.name, exc)
            skipped_parse += 1
            continue

        if min_features > 0:
            feat_count = sum(1 for f in FEATURE_NAMES if _has_data_for_feature(e, f))
            if feat_count < min_features:
                filtered.append(e.domain)
                continue

        enrichments.append(e)

        if i % 100 == 0:
            logger.info("[%d/%d] loaded", i, len(files))

    enrichments.sort(key=lambda e: e.domain)
    filtered.sort()

    logger.info(
        "Loaded %d enrichments, filtered %d (< %d features), %d parse errors",
        len(enrichments), len(filtered), min_features, skipped_parse,
    )
    return enrichments, filtered


def build_distance_matrix(
    enrichments: list[DomainEnrichment],
    config: WeightConfig,
    nan_fill: float = 1.0,
) -> DistanceMatrixResult:
    """Compute the full NxN pairwise distance matrix."""
    n = len(enrichments)
    total_pairs = n * (n - 1) // 2
    matrix = np.zeros((n, n), dtype=np.float64)
    nan_count = 0

    start = time.perf_counter()

    for i in range(n):
        for j in range(i + 1, n):
            d = composite_distance(enrichments[i], enrichments[j], config=config)
            if math.isnan(d):
                nan_count += 1
                d = nan_fill
            matrix[i, j] = d
            matrix[j, i] = d

        if (i + 1) % 100 == 0 or i + 1 == n:
            elapsed = time.perf_counter() - start
            logger.info("[%d/%d] rows computed (%.1fs)", i + 1, n, elapsed)

    elapsed = time.perf_counter() - start

    return DistanceMatrixResult(
        matrix=matrix,
        domain_labels=[e.domain for e in enrichments],
        nan_count=nan_count,
        total_pairs=total_pairs,
        nan_fill_value=nan_fill,
        filtered_domains=[],
        computation_seconds=round(elapsed, 2),
    )


def save_distance_matrix(
    result: DistanceMatrixResult,
    output_dir: Path,
    config: WeightConfig | None = None,
) -> None:
    """Persist matrix, labels, and metadata to *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)

    np.save(output_dir / "distance_matrix.npy", result.matrix)

    (output_dir / "domain_labels.json").write_text(
        json.dumps(result.domain_labels, indent=2), encoding="utf-8",
    )

    metadata: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain_count": len(result.domain_labels),
        "total_pairs": result.total_pairs,
        "nan_count": result.nan_count,
        "nan_percentage": round(result.nan_count / result.total_pairs * 100, 2) if result.total_pairs > 0 else 0.0,
        "nan_fill_value": result.nan_fill_value,
        "filtered_domains": result.filtered_domains,
        "filtered_count": len(result.filtered_domains),
        "computation_seconds": result.computation_seconds,
    }
    if config is not None:
        metadata["weight_config"] = config.model_dump(mode="json")

    (output_dir / "matrix_metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8",
    )
    logger.info("Saved to %s (matrix + labels + metadata)", output_dir)


def load_distance_matrix(output_dir: Path) -> DistanceMatrixResult:
    """Load a previously saved distance matrix result."""
    matrix_path = output_dir / "distance_matrix.npy"
    labels_path = output_dir / "domain_labels.json"
    meta_path = output_dir / "matrix_metadata.json"

    for p in (matrix_path, labels_path, meta_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    matrix = np.load(matrix_path)
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if matrix.shape[0] != len(labels):
        raise ValueError(
            f"Shape mismatch: matrix {matrix.shape[0]}x{matrix.shape[1]} vs {len(labels)} labels"
        )

    return DistanceMatrixResult(
        matrix=matrix,
        domain_labels=labels,
        nan_count=meta.get("nan_count", 0),
        total_pairs=meta.get("total_pairs", 0),
        nan_fill_value=meta.get("nan_fill_value", 1.0),
        filtered_domains=meta.get("filtered_domains", []),
        computation_seconds=meta.get("computation_seconds", 0.0),
    )
