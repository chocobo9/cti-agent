"""Parameter grid search for campaign discovery (θ_min × γ)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import adjusted_rand_score, silhouette_score

from cti_agent.campaign.leiden import run_leiden_stable
from cti_agent.campaign.similarity import (
    IncidentRecord,
    build_similarity_graph,
    jaccard_similarity,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GridSearchResult:
    theta_min: float
    gamma: float
    n_communities: int
    modularity: float
    silhouette: float | None
    ari: float | None
    n_edges: int
    n_vertices: int
    membership: list[int]
    community_sizes: list[int]


@dataclass(frozen=True)
class GridSearchConfig:
    theta_min_values: list[float]
    gamma_values: list[float]
    n_runs_per_config: int = 10
    time_window_days: int = 90
    no_time_filter: bool = False


def _compute_silhouette(
    eligible: list[IncidentRecord],
    membership: list[int],
) -> float | None:
    n = len(eligible)
    if n < 2 or len(set(membership)) < 2:
        return None

    dist_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = 1.0 - jaccard_similarity(eligible[i].cluster_tag_set, eligible[j].cluster_tag_set)
            dist_matrix[i, j] = d
            dist_matrix[j, i] = d

    try:
        return float(silhouette_score(dist_matrix, membership, metric="precomputed"))
    except Exception:
        return None


def _compute_ari(
    membership: list[int],
    eligible: list[IncidentRecord],
    ground_truth: dict[str, str],
) -> float | None:
    true_labels = [ground_truth.get(inc.incident_id) for inc in eligible]
    if any(l is None for l in true_labels):
        valid = [(m, t) for m, t in zip(membership, true_labels) if t is not None]
        if len(valid) < 2:
            return None
        pred, true = zip(*valid)
        return float(adjusted_rand_score(list(true), list(pred)))

    return float(adjusted_rand_score(true_labels, membership))


def run_grid_search(
    incidents: list[IncidentRecord],
    config: GridSearchConfig,
    ground_truth: dict[str, str] | None = None,
) -> list[GridSearchResult]:
    results: list[GridSearchResult] = []
    total = len(config.theta_min_values) * len(config.gamma_values)
    count = 0

    for theta_min in config.theta_min_values:
        graph, eligible = build_similarity_graph(
            incidents,
            theta_min=theta_min,
            time_window_days=config.time_window_days,
            no_time_filter=config.no_time_filter,
        )

        for gamma in config.gamma_values:
            count += 1
            leiden_result = run_leiden_stable(graph, resolution=gamma, n_runs=config.n_runs_per_config)

            sil = _compute_silhouette(eligible, leiden_result.membership)
            ari = _compute_ari(leiden_result.membership, eligible, ground_truth) if ground_truth else None

            results.append(GridSearchResult(
                theta_min=theta_min,
                gamma=gamma,
                n_communities=leiden_result.n_communities,
                modularity=round(leiden_result.modularity, 4),
                silhouette=round(sil, 4) if sil is not None else None,
                ari=round(ari, 4) if ari is not None else None,
                n_edges=graph.ecount(),
                n_vertices=graph.vcount(),
                membership=leiden_result.membership,
                community_sizes=leiden_result.community_sizes,
            ))

            if count % 20 == 0 or count == total:
                logger.info("[Grid %d/%d] θ=%.2f γ=%.1f → %d communities, %d edges",
                            count, total, theta_min, gamma, leiden_result.n_communities, graph.ecount())

    return results


def find_best_config(
    results: list[GridSearchResult],
    metric: str = "ari",
) -> GridSearchResult | None:
    valid = [r for r in results if getattr(r, metric) is not None]
    if not valid:
        fallback = "silhouette" if metric == "ari" else "ari"
        valid = [r for r in results if getattr(r, fallback) is not None]
        if not valid:
            return results[0] if results else None
    return max(valid, key=lambda r: getattr(r, metric))
