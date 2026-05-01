"""Structural quality scoring for domain clusters (Dupont et al., 2021).

For each cluster, computes per-feature average dissimilarity (AD_i) using
the 7 M3.1 distance functions.  A feature is "similar" if AD_i < t_diss.
Quality score = similar_feature_count / 7.

Special cases:
  size=1 → quality=0.0, never filtered
  size=2 → quality=1-pair_distance, never filtered
  size≥3 → filtered if quality < threshold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from cti_agent.clustering.composite import _compute_feature_distance, _has_data_for_feature
from cti_agent.clustering.distance import FEATURE_NAMES
from cti_agent.enrichment.models import DomainEnrichment

logger = logging.getLogger(__name__)

DEFAULT_T_DISS: float = 0.2
DEFAULT_T_GOOD: int = 4


@dataclass(frozen=True)
class FeatureQualityMetrics:
    feature_name: str
    avg_dissimilarity: float
    is_similar: bool
    num_pairs: int


@dataclass(frozen=True)
class ClusterQualityResult:
    cluster_id: int
    quality_score: float
    is_good: bool
    feature_metrics: list[FeatureQualityMetrics]
    similar_count: int
    total_features: int


def compute_feature_dissimilarity(
    enrichments: list[DomainEnrichment],
    feature: str,
) -> tuple[float, int]:
    """Compute average pairwise dissimilarity for one feature within a cluster."""
    n = len(enrichments)
    if n < 2:
        return 0.0, 0

    distances: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            if not _has_data_for_feature(enrichments[i], feature):
                continue
            if not _has_data_for_feature(enrichments[j], feature):
                continue
            d = _compute_feature_distance(enrichments[i], enrichments[j], feature)
            distances.append(d)

    if not distances:
        return 1.0, 0
    return float(np.mean(distances)), len(distances)


def compute_cluster_quality(
    cluster_enrichments: list[DomainEnrichment],
    cluster_id: int = -1,
    t_diss: float = DEFAULT_T_DISS,
    t_good: int = DEFAULT_T_GOOD,
) -> ClusterQualityResult:
    """Compute structural quality score for a single cluster."""
    feature_metrics: list[FeatureQualityMetrics] = []
    similar_count = 0

    for feature in FEATURE_NAMES:
        avg_dissim, num_pairs = compute_feature_dissimilarity(cluster_enrichments, feature)
        is_similar = avg_dissim < t_diss
        if is_similar:
            similar_count += 1
        feature_metrics.append(FeatureQualityMetrics(
            feature_name=feature,
            avg_dissimilarity=round(avg_dissim, 4),
            is_similar=is_similar,
            num_pairs=num_pairs,
        ))

    total = len(FEATURE_NAMES)
    return ClusterQualityResult(
        cluster_id=cluster_id,
        quality_score=round(similar_count / total, 4),
        is_good=similar_count >= t_good,
        feature_metrics=feature_metrics,
        similar_count=similar_count,
        total_features=total,
    )


def filter_clusters_by_structural_quality(
    labels: np.ndarray,
    enrichments: list[DomainEnrichment],
    matrix: np.ndarray,
    threshold: float = 0.40,
    t_diss: float = DEFAULT_T_DISS,
    t_good: int = DEFAULT_T_GOOD,
) -> tuple[np.ndarray, dict[int, ClusterQualityResult]]:
    """Filter low-quality clusters to noise.

    Singletons (size=1) and pairs (size=2) are scored but never filtered.
    Only clusters with size >= 3 and quality_score < threshold are set to -1.

    Returns (filtered_labels, quality_results).
    """
    filtered = labels.copy()
    unique_clusters = set(labels)
    unique_clusters.discard(-1)

    quality_results: dict[int, ClusterQualityResult] = {}
    filtered_count = 0
    singleton_count = 0
    pair_count = 0

    for cid in sorted(unique_clusters):
        indices = [i for i in range(len(labels)) if labels[i] == cid]
        size = len(indices)

        if size == 1:
            singleton_count += 1
            quality_results[cid] = ClusterQualityResult(
                cluster_id=cid, quality_score=0.0, is_good=False,
                feature_metrics=[], similar_count=0, total_features=len(FEATURE_NAMES),
            )
            continue

        if size == 2:
            pair_count += 1
            pair_dist = float(matrix[indices[0], indices[1]])
            pair_quality = max(0.0, min(1.0, 1.0 - pair_dist))
            quality_results[cid] = ClusterQualityResult(
                cluster_id=cid, quality_score=round(pair_quality, 4),
                is_good=pair_quality >= (t_good / len(FEATURE_NAMES)),
                feature_metrics=[], similar_count=0, total_features=len(FEATURE_NAMES),
            )
            continue

        cluster_enrichments = [enrichments[i] for i in indices]
        qr = compute_cluster_quality(cluster_enrichments, cluster_id=cid, t_diss=t_diss, t_good=t_good)
        quality_results[cid] = qr

        if qr.quality_score < threshold:
            filtered[labels == cid] = -1
            filtered_count += 1

    logger.info(
        "Quality filter: %d clusters → %d filtered (threshold=%.2f), %d singletons, %d pairs kept",
        len(unique_clusters), filtered_count, threshold, singleton_count, pair_count,
    )
    return filtered, quality_results
